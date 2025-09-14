#!/usr/bin/env python3
"""
LuatVietnam.vn Traffic Law Crawler
=================================

A focused crawler to extract traffic law documents from luatvietnam.vn/giao-thong-28-f1.html

Features:
- Clean extraction of document titles, URLs, publication dates
- Pagination handling 
- Export to Excel format
- Anti-detection measures
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
import logging
from urllib.parse import urljoin, urlparse
import re
from datetime import datetime
import os
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('luatvietnam_crawler.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

class LuatVietnamCrawler:
    def __init__(self):
        self.base_url = "https://luatvietnam.vn"
        self.start_url = "https://luatvietnam.vn/giao-thong-28-f1.html"
        self.session = requests.Session()
        
        # Set up session headers to mimic a real browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'vi-VN,vi;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
        self.documents = []
        
        # Error logging for crawler
        self.crawler_error_log = "crawler_failed_urls.json"
        self.failed_urls = self.load_failed_urls()
        
    def load_failed_urls(self):
        """Load previously failed URLs for tracking"""
        if os.path.exists(self.crawler_error_log):
            try:
                with open(self.crawler_error_log, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def log_failed_url(self, url, error_message, error_type="crawling"):
        """Log failed URL with detailed information"""
        failed_entry = {
            "timestamp": datetime.now().isoformat(),
            "url": url,
            "error": error_message,
            "error_type": error_type,  # "crawling", "parsing", "pagination"
            "retry_count": 0
        }
        
        # Check if this URL already failed before
        existing_entry = None
        for entry in self.failed_urls:
            if entry.get('url') == url:
                existing_entry = entry
                break
        
        if existing_entry:
            existing_entry['retry_count'] += 1
            existing_entry['timestamp'] = datetime.now().isoformat()
            existing_entry['error'] = error_message
        else:
            self.failed_urls.append(failed_entry)
        
        # Save to file
        with open(self.crawler_error_log, 'w', encoding='utf-8') as f:
            json.dump(self.failed_urls, f, ensure_ascii=False, indent=2)
        
        logging.error(f"Failed URL logged: {url} - {error_message}")
        
    def get_page(self, url):
        """Get page content with error handling and rate limiting"""
        try:
            # Random delay to avoid being blocked
            time.sleep(random.uniform(1, 3))
            
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            logging.info(f"Successfully fetched: {url}")
            return response.text
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Error fetching {url}: {e}"
            logging.error(error_msg)
            self.log_failed_url(url, str(e), "crawling")
            return None
    
    def extract_documents_from_page(self, html_content, page_url):
        """Extract document information from a single page"""
        soup = BeautifulSoup(html_content, 'html.parser')
        documents = []
        
        # Find all document entries - they appear to be in specific patterns
        # Looking for links that match the document pattern
        doc_links = soup.find_all('a', href=re.compile(r'/giao-thong/.*\.html'))
        
        for link in doc_links:
            try:
                # Extract document title
                title = link.get_text(strip=True)
                if not title or len(title) < 10:  # Skip short/empty titles
                    continue
                
                # Extract URL
                doc_url = urljoin(self.base_url, link.get('href'))
                
                # Try to find publication date in nearby text
                pub_date = None
                parent = link.parent
                if parent:
                    # Look for date pattern in parent element
                    date_text = parent.get_text()
                    date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', date_text)
                    if date_match:
                        pub_date = date_match.group(1)
                    else:
                        # Look for "Ban hành:" pattern
                        ban_hanh_match = re.search(r'Ban hành:\s*(\d{1,2}/\d{1,2}/\d{4})', date_text)
                        if ban_hanh_match:
                            pub_date = ban_hanh_match.group(1)
                
                # Extract document type/category from URL
                doc_type = "Giao thông"
                if '/nghi-dinh' in doc_url:
                    doc_type = "Nghị định"
                elif '/thong-tu' in doc_url:
                    doc_type = "Thông tư"
                elif '/quyet-dinh' in doc_url:
                    doc_type = "Quyết định"
                elif '/cong-van' in doc_url:
                    doc_type = "Công văn"
                elif '/luat' in doc_url:
                    doc_type = "Luật"
                elif '/chi-thi' in doc_url:
                    doc_type = "Chỉ thị"
                
                doc_info = {
                    'title': title,
                    'url': doc_url,
                    'publication_date': pub_date,
                    'document_type': doc_type,
                    'source_page': page_url,
                    'crawled_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                documents.append(doc_info)
                logging.info(f"Extracted: {title[:50]}...")
                
            except Exception as e:
                error_msg = f"Error extracting document info from {page_url}: {e}"
                logging.error(error_msg)
                # Log the parsing error with the page URL
                self.log_failed_url(page_url, f"Document parsing failed: {e}", "parsing")
                continue
        
        return documents
    
    def find_pagination_links(self, html_content):
        """Find pagination links to crawl additional pages"""
        soup = BeautifulSoup(html_content, 'html.parser')
        pagination_links = []
        
        # Pattern 1: Direct page number links (f1.html, f2.html, etc.)
        page_links = soup.find_all('a', href=re.compile(r'giao-thong-28-f\d+\.html'))
        for link in page_links:
            href = link.get('href')
            if href:
                full_url = urljoin(self.base_url, href)
                pagination_links.append(full_url)
        
        # Pattern 2: Look for pagination container
        pagination_containers = soup.find_all(['div', 'ul', 'nav'], class_=re.compile(r'pag|page', re.I))
        for container in pagination_containers:
            links = container.find_all('a', href=True)
            for link in links:
                href = link.get('href')
                if href and 'giao-thong' in href and 'f' in href:
                    full_url = urljoin(self.base_url, href)
                    pagination_links.append(full_url)
        
        # Pattern 3: "Next" or navigation links
        next_patterns = ['Next', 'Tiếp', 'Tiếp theo', '»', '>', 'Trang sau']
        for pattern in next_patterns:
            next_links = soup.find_all('a', string=re.compile(pattern, re.I))
            for link in next_links:
                href = link.get('href')
                if href and 'giao-thong' in href:
                    full_url = urljoin(self.base_url, href)
                    pagination_links.append(full_url)
        
        # Pattern 4: Look for numbered links (1, 2, 3, etc.)
        number_links = soup.find_all('a', string=re.compile(r'^\d+$'))
        for link in number_links:
            href = link.get('href')
            if href and 'giao-thong' in href:
                full_url = urljoin(self.base_url, href)
                pagination_links.append(full_url)
        
        # Remove duplicates and current page
        unique_links = []
        for link in pagination_links:
            if link not in unique_links:
                unique_links.append(link)
        
        return unique_links
    
    def crawl_all_pages(self):
        """Crawl all pages starting from the main traffic law page"""
        logging.info("Starting LuatVietnam.vn Traffic Law Crawler")
        logging.info(f"Starting URL: {self.start_url}")
        
        visited_urls = set()
        urls_to_visit = [self.start_url]
        
        while urls_to_visit:
            current_url = urls_to_visit.pop(0)
            
            if current_url in visited_urls:
                continue
                
            logging.info(f"Crawling page: {current_url}")
            visited_urls.add(current_url)
            
            # Get page content
            html_content = self.get_page(current_url)
            if not html_content:
                continue
            
            # Extract documents from current page
            page_documents = self.extract_documents_from_page(html_content, current_url)
            self.documents.extend(page_documents)
            
            logging.info(f"Found {len(page_documents)} documents on this page")
            logging.info(f"Total documents so far: {len(self.documents)}")
            
            # Progress report every 10 pages
            if len(visited_urls) % 10 == 0:
                print(f"📊 Progress: Crawled {len(visited_urls)} pages, found {len(self.documents)} documents")
            
            # Save progress periodically
            if len(self.documents) % 500 == 0 and len(self.documents) > 0:
                self.save_to_excel(f"luatvietnam_progress_{len(self.documents)}.xlsx")
                print(f"💾 Progress saved: {len(self.documents)} documents")
            
            # Find pagination links for more pages
            # Remove artificial limit to get all documents
            try:
                pagination_links = self.find_pagination_links(html_content)
                for link in pagination_links:
                    if link not in visited_urls and link not in urls_to_visit:
                        urls_to_visit.append(link)
                        logging.info(f"Added to queue: {link}")
            except Exception as e:
                error_msg = f"Failed to find pagination links on {current_url}: {e}"
                logging.error(error_msg)
                self.log_failed_url(current_url, error_msg, "pagination")
            
            # Safety check to prevent infinite loops
            if len(visited_urls) > 850:  # Allow for all 824 pages plus some margin
                logging.warning("Reached safety limit of 850 pages")
                break
        
        logging.info(f"Crawling completed! Total documents found: {len(self.documents)}")
        
        # Show failed URLs summary
        if self.failed_urls:
            logging.warning(f"Encountered {len(self.failed_urls)} failed URLs during crawling")
            print(f"⚠️ {len(self.failed_urls)} URLs failed during crawling - check {self.crawler_error_log}")
        else:
            print("✅ No URLs failed during crawling!")
            
        return self.documents
    
    def save_to_excel(self, filename="luatvietnam_traffic_laws.xlsx"):
        """Save extracted documents to Excel file"""
        if not self.documents:
            logging.warning("No documents to save!")
            return
        
        df = pd.DataFrame(self.documents)
        
        # Remove duplicates based on URL
        initial_count = len(df)
        df = df.drop_duplicates(subset=['url'], keep='first')
        final_count = len(df)
        
        if initial_count != final_count:
            logging.info(f"Removed {initial_count - final_count} duplicate documents")
        
        # Sort by publication date (newest first)
        df['pub_date_parsed'] = pd.to_datetime(df['publication_date'], format='%d/%m/%Y', errors='coerce')
        df = df.sort_values('pub_date_parsed', ascending=False, na_position='last')
        df = df.drop('pub_date_parsed', axis=1)
        
        # Save to Excel
        df.to_excel(filename, index=False, sheet_name='Traffic Laws')
        
        logging.info(f"Saved {len(df)} documents to {filename}")
        
        # Print summary statistics
        self.print_summary(df)
        
        return filename
    
    def print_summary(self, df):
        """Print summary statistics"""
        print("\n" + "="*60)
        print("📊 LUATVIETNAM.VN CRAWLER SUMMARY")
        print("="*60)
        print(f"📄 Total Documents: {len(df)}")
        
        # Handle date range safely
        valid_dates = df['publication_date'].dropna()
        if len(valid_dates) > 0:
            print(f"📅 Date Range: {valid_dates.min()} to {valid_dates.max()}")
        else:
            print("📅 Date Range: No valid dates found")
        
        print("\n📋 Document Types:")
        type_counts = df['document_type'].value_counts()
        for doc_type, count in type_counts.items():
            print(f"  {doc_type}: {count}")
        
        print("\n🔗 Sample Documents:")
        for i, row in df.head(5).iterrows():
            print(f"  • {row['title'][:80]}...")
            print(f"    📅 {row['publication_date']} | 🔗 {row['url']}")
        
        print("="*60)

    def show_failed_urls(self):
        """Display all failed URLs for review"""
        if not self.failed_urls:
            print("✅ No failed URLs found during crawling!")
            return
        
        print(f"\n📋 FAILED URLS DURING CRAWLING ({len(self.failed_urls)} items):")
        print("="*80)
        
        # Group by error type
        error_types = {}
        for entry in self.failed_urls:
            error_type = entry.get('error_type', 'unknown')
            if error_type not in error_types:
                error_types[error_type] = []
            error_types[error_type].append(entry)
        
        # Show summary by error type
        print("\n📊 FAILURE BREAKDOWN:")
        for error_type, entries in error_types.items():
            print(f"• {error_type}: {len(entries)} URLs")
        
        print(f"\n📝 DETAILED FAILED URLS:")
        print("-" * 80)
        
        for i, entry in enumerate(self.failed_urls, 1):
            print(f"{i:3d}. {entry.get('url', 'Unknown')}")
            print(f"     Error Type: {entry.get('error_type', 'unknown')}")
            print(f"     Error: {entry.get('error', 'Unknown')}")
            print(f"     Retry Count: {entry.get('retry_count', 0)}")
            print(f"     Last Attempt: {entry.get('timestamp', 'Unknown')}")
            print()
    
    def retry_failed_urls(self):
        """Retry crawling all previously failed URLs"""
        if not self.failed_urls:
            print("✅ No failed URLs to retry!")
            return
        
        print(f"🔄 RETRYING {len(self.failed_urls)} FAILED URLS")
        print("="*80)
        
        # Extract URLs to retry
        retry_urls = [entry['url'] for entry in self.failed_urls]
        
        # Clear previous failures to start fresh
        self.failed_urls = []
        
        # Retry each URL
        visited_urls = set()
        for url in retry_urls:
            if url in visited_urls:
                continue
                
            print(f"🔄 Retrying: {url}")
            visited_urls.add(url)
            
            # Get page content
            html_content = self.get_page(url)
            if not html_content:
                continue
            
            # Extract documents from current page
            page_documents = self.extract_documents_from_page(html_content, url)
            self.documents.extend(page_documents)
            
            print(f"  ✅ Found {len(page_documents)} documents")

def main():
    """Main function to run the crawler"""
    import sys
    
    crawler = LuatVietnamCrawler()
    
    # Check command line arguments
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "show-failed":
            crawler.show_failed_urls()
            return
        elif command == "retry-failed":
            crawler.retry_failed_urls()
            if crawler.documents:
                filename = crawler.save_to_excel("luatvietnam_retry_results.xlsx")
                print(f"✅ Retry completed! Results saved to: {filename}")
            return
        else:
            print("❌ Unknown command. Use 'show-failed' or 'retry-failed'")
            print("Usage:")
            print("  python luatvietnam_crawler.py              - Normal crawling")
            print("  python luatvietnam_crawler.py show-failed  - Show failed URLs")
            print("  python luatvietnam_crawler.py retry-failed - Retry failed URLs")
            return
    
    try:
        # Normal crawling
        documents = crawler.crawl_all_pages()
        
        if documents:
            # Save to Excel
            filename = crawler.save_to_excel()
            print(f"\n✅ Crawling completed successfully!")
            print(f"📁 Results saved to: {filename}")
        else:
            print("❌ No documents found!")
            
    except KeyboardInterrupt:
        print("\n⚠️ Crawling interrupted by user")
        if crawler.documents:
            filename = crawler.save_to_excel("luatvietnam_partial_results.xlsx")
            print(f"💾 Partial results saved to: {filename}")
    except Exception as e:
        logging.error(f"❌ Crawler error: {e}")
        print(f"❌ Crawler error: {e}")
        if crawler.documents:
            filename = crawler.save_to_excel("luatvietnam_partial_results.xlsx")
            print(f"💾 Partial results saved to: {filename}")
        print(f"❌ Error occurred: {e}")

if __name__ == "__main__":
    main()
