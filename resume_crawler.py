#!/usr/bin/env python3
"""
Resume LuatVietnam.vn Traffic Law Crawler
========================================

A smart crawler that resumes from where it left off, avoiding duplicate work.

Features:
- Loads existing documents from Excel file
- Identifies which pages have already been crawled
- Resumes crawling from unprocessed pages
- Prevents duplicate document collection
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
import logging
from urllib.parse import urljoin, urlparse, parse_qs
import re
from datetime import datetime
import os
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('resume_crawler.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

class ResumeCrawler:
    def __init__(self, existing_excel_file="luatvietnam_complete_collection.xlsx"):
        self.base_url = "https://luatvietnam.vn"
        self.existing_file = existing_excel_file
        self.session = requests.Session()
        
        # Set up session headers
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'vi-VN,vi;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
        # Load existing documents and find processed pages
        self.existing_documents = self.load_existing_documents()
        self.processed_pages = self.find_processed_pages()
        self.new_documents = []
        
        print(f"📊 RESUME CRAWLER INITIALIZATION:")
        print(f"   - Existing documents: {len(self.existing_documents):,}")
        print(f"   - Processed pages: {len(self.processed_pages):,}")
        print(f"   - Ready to resume crawling...")
    
    def load_existing_documents(self):
        """Load existing documents from Excel file"""
        if not os.path.exists(self.existing_file):
            print(f"⚠️ No existing file found: {self.existing_file}")
            return pd.DataFrame()
        
        try:
            df = pd.read_excel(self.existing_file)
            print(f"✅ Loaded {len(df):,} existing documents from {self.existing_file}")
            return df
        except Exception as e:
            print(f"❌ Error loading existing file: {e}")
            return pd.DataFrame()
    
    def find_processed_pages(self):
        """Analyze source_page column to find which pages have been processed"""
        if self.existing_documents.empty:
            return set()
        
        processed_pages = set()
        
        # Extract page information from source_page column
        for _, row in self.existing_documents.iterrows():
            source_page = row.get('source_page', '')
            if pd.notna(source_page):
                # Try to extract page number from source_page
                # Examples: "https://luatvietnam.vn/giao-thong-28-f1.html?page=1"
                try:
                    if 'page=' in source_page:
                        page_num = source_page.split('page=')[1].split('&')[0]
                        processed_pages.add(int(page_num))
                    elif source_page.endswith('f1.html'):
                        processed_pages.add(1)  # Main page
                except:
                    continue
        
        print(f"📋 Found processed pages: {min(processed_pages) if processed_pages else 'None'} to {max(processed_pages) if processed_pages else 'None'}")
        return processed_pages
    
    def generate_unprocessed_urls(self):
        """Generate URLs for pages that haven't been processed yet"""
        base_urls = [
            "https://luatvietnam.vn/giao-thong-28-f1.html",
            "https://luatvietnam.vn/giao-thong-28-f2.html",
            "https://luatvietnam.vn/giao-thong-28-f6.html"
        ]
        
        unprocessed_urls = []
        
        # Find the range of pages to process
        # If we have processed pages, start from the highest + 1
        # Otherwise start from page 1
        if self.processed_pages:
            start_page = max(self.processed_pages) + 1
            print(f"🎯 Resuming from page {start_page} (highest processed: {max(self.processed_pages)})")
        else:
            start_page = 1
            print(f"🎯 Starting fresh from page 1")
        
        # Generate URLs for pages 1 to 850 (covers all 824 known pages)
        for page_num in range(start_page, 851):
            if page_num in self.processed_pages:
                continue  # Skip already processed pages
            
            for base_url in base_urls:
                # Add different page variations
                variations = [
                    f"{base_url}?page={page_num}",
                    f"{base_url}?page={page_num}&ShowSapo=0",
                    f"{base_url}?page={page_num}&ShowSapo=1",
                    f"{base_url}?ShowSapo=0&page={page_num}",
                    f"{base_url}?ShowSapo=1&page={page_num}"
                ]
                
                for url in variations:
                    unprocessed_urls.append(url)
        
        print(f"📋 Generated {len(unprocessed_urls):,} unprocessed URLs to crawl")
        return unprocessed_urls
    
    def get_page(self, url, max_retries=3):
        """Fetch page content with retry logic"""
        for attempt in range(max_retries):
            try:
                # Random delay between requests
                time.sleep(random.uniform(1, 3))
                
                response = self.session.get(url, timeout=15)
                
                if response.status_code == 200:
                    return response.text
                else:
                    logging.warning(f"HTTP {response.status_code} for {url}")
                    
            except Exception as e:
                logging.error(f"Attempt {attempt + 1} failed for {url}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(random.uniform(2, 5))
        
        return None
    
    def extract_documents_from_page(self, html_content, source_url):
        """Extract document information from a single page"""
        soup = BeautifulSoup(html_content, 'html.parser')
        documents = []
        
        # Find all article links - look for various patterns
        selectors = [
            'h2.title-luat a',
            'h3.title-luat a', 
            '.title-luat a',
            '.item-search h2 a',
            '.item-search h3 a',
            'h2 a[href*="/giao-thong/"]',
            'h3 a[href*="/giao-thong/"]',
            'a[href*="/giao-thong/"]'
        ]
        
        found_links = set()
        
        for selector in selectors:
            links = soup.select(selector)
            for link in links:
                href = link.get('href')
                if href and '/giao-thong/' in href:
                    full_url = urljoin(self.base_url, href)
                    found_links.add(full_url)
        
        # Extract document info for each unique link
        for link_url in found_links:
            try:
                # Extract title
                link_element = soup.find('a', href=lambda x: x and link_url.endswith(x) if x else False)
                if not link_element:
                    continue
                
                title = link_element.get_text(strip=True)
                if not title or title in ['Thuộc tính', 'VB liên quan', 'VB được hợp nhất']:
                    continue
                
                # Try to extract publication date from various sources
                pub_date = self.extract_publication_date(link_element, soup)
                
                # Determine document type from title
                doc_type = self.determine_document_type(title)
                
                documents.append({
                    'title': title,
                    'url': link_url,
                    'publication_date': pub_date,
                    'document_type': doc_type,
                    'source_page': source_url,
                    'crawled_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                
                logging.info(f"Extracted: {title[:50]}...")
                
            except Exception as e:
                logging.error(f"Error extracting document: {e}")
                continue
        
        return documents
    
    def extract_publication_date(self, link_element, soup):
        """Extract publication date from various page elements"""
        # Try multiple strategies to find publication date
        
        # Look for date near the link
        parent = link_element.parent
        if parent:
            date_text = parent.get_text()
            date_match = re.search(r'(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4})', date_text)
            if date_match:
                return date_match.group(1)
        
        # Look for common date patterns in the page
        date_patterns = [
            r'(\d{1,2}\/\d{1,2}\/\d{4})',
            r'(\d{1,2}\-\d{1,2}\-\d{4})',
            r'(\d{4}\/\d{1,2}\/\d{1,2})',
            r'(\d{4}\-\d{1,2}\-\d{1,2})'
        ]
        
        page_text = soup.get_text()
        for pattern in date_patterns:
            matches = re.findall(pattern, page_text)
            if matches:
                return matches[0]
        
        return datetime.now().strftime('%d/%m/%Y')
    
    def determine_document_type(self, title):
        """Determine document type from title"""
        title_lower = title.lower()
        
        if any(word in title_lower for word in ['luật', 'law']):
            return 'Luật'
        elif any(word in title_lower for word in ['nghị định', 'nđ-cp']):
            return 'Nghị định'
        elif any(word in title_lower for word in ['thông tư', 'tt-']):
            return 'Thông tư'
        elif any(word in title_lower for word in ['quyết định', 'qđ-']):
            return 'Quyết định'
        elif any(word in title_lower for word in ['công văn']):
            return 'Công văn'
        elif any(word in title_lower for word in ['chỉ thị']):
            return 'Chỉ thị'
        elif any(word in title_lower for word in ['thông báo']):
            return 'Thông báo'
        elif any(word in title_lower for word in ['kế hoạch']):
            return 'Kế hoạch'
        else:
            return 'Khác'
    
    def crawl_unprocessed_pages(self, max_pages=200):
        """Crawl only unprocessed pages"""
        logging.info("Starting resume crawling of unprocessed pages")
        
        unprocessed_urls = self.generate_unprocessed_urls()
        
        if not unprocessed_urls:
            print("✅ All pages have been processed!")
            return []
        
        # Limit the number of pages to process in this session
        urls_to_process = unprocessed_urls[:max_pages * 5]  # 5 variations per page
        
        print(f"🎯 Processing {len(urls_to_process):,} URLs (estimated {len(urls_to_process)//5} pages)")
        
        processed_count = 0
        
        for i, url in enumerate(urls_to_process):
            logging.info(f"Crawling: {url}")
            
            # Get page content
            html_content = self.get_page(url)
            if not html_content:
                continue
            
            # Extract documents from page
            page_documents = self.extract_documents_from_page(html_content, url)
            self.new_documents.extend(page_documents)
            
            processed_count += 1
            
            logging.info(f"Found {len(page_documents)} documents on this page")
            logging.info(f"Total new documents so far: {len(self.new_documents)}")
            
            # Progress report every 10 pages
            if processed_count % 10 == 0:
                print(f"📊 Progress: Processed {processed_count} URLs, found {len(self.new_documents)} new documents")
            
            # Save progress every 100 new documents
            if len(self.new_documents) % 100 == 0 and len(self.new_documents) > 0:
                self.save_progress()
        
        logging.info(f"Resume crawling completed! Found {len(self.new_documents)} new documents")
        return self.new_documents
    
    def save_progress(self):
        """Save current progress by merging with existing documents"""
        if not self.new_documents:
            return
        
        # Create DataFrame from new documents
        new_df = pd.DataFrame(self.new_documents)
        
        # Combine with existing documents
        if not self.existing_documents.empty:
            combined_df = pd.concat([self.existing_documents, new_df], ignore_index=True)
        else:
            combined_df = new_df
        
        # Remove duplicates
        combined_df = combined_df.drop_duplicates(subset=['url'], keep='first')
        
        # Save to file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f"luatvietnam_complete_collection_backup_{timestamp}.xlsx"
        
        # Backup existing file
        if os.path.exists(self.existing_file):
            os.rename(self.existing_file, backup_file)
            print(f"💾 Backup created: {backup_file}")
        
        # Save combined data
        combined_df.to_excel(self.existing_file, index=False)
        file_size = os.path.getsize(self.existing_file) / 1024 / 1024
        
        print(f"✅ Progress saved: {len(combined_df):,} total documents ({file_size:.1f} MB)")
        
        # Update completion status
        target_docs = 16463
        completion_pct = (len(combined_df) / target_docs) * 100
        print(f"📈 Completion: {completion_pct:.1f}% ({len(combined_df):,}/{target_docs:,})")

def main():
    """Main function to run the resume crawler"""
    try:
        crawler = ResumeCrawler()
        
        # Check if we need to continue crawling
        target_docs = 16463
        current_docs = len(crawler.existing_documents)
        
        if current_docs >= target_docs * 0.95:  # 95% completion threshold
            print(f"🎉 Collection is {(current_docs/target_docs)*100:.1f}% complete!")
            print(f"📊 Current: {current_docs:,} / Target: {target_docs:,}")
            print("✅ Ready for bulk downloading!")
            return
        
        print(f"🎯 RESUME CRAWLING TARGET:")
        print(f"   - Current: {current_docs:,} documents")
        print(f"   - Target: {target_docs:,} documents")
        print(f"   - Remaining: {target_docs - current_docs:,} documents")
        print(f"   - Completion: {(current_docs/target_docs)*100:.1f}%")
        print()
        
        # Start resume crawling
        new_documents = crawler.crawl_unprocessed_pages(max_pages=100)
        
        if new_documents:
            crawler.save_progress()
            print(f"\n✅ Resume crawling completed!")
            print(f"📊 Found {len(new_documents):,} new documents")
        else:
            print("⚠️ No new documents found")
            
    except KeyboardInterrupt:
        print("\n⚠️ Crawling interrupted by user")
        if hasattr(crawler, 'new_documents') and crawler.new_documents:
            crawler.save_progress()
            print(f"💾 Progress saved: {len(crawler.new_documents):,} new documents")
    except Exception as e:
        logging.error(f"❌ Resume crawler error: {e}")
        print(f"❌ Error: {e}")
        if hasattr(crawler, 'new_documents') and crawler.new_documents:
            crawler.save_progress()
            print(f"💾 Progress saved despite error")

if __name__ == "__main__":
    main()
