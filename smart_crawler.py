#!/usr/bin/env python3
"""
Smart Vietnamese Traffic Law Crawler
Focuses on finding actual working URLs first, then crawling efficiently
"""

import time
import logging
import pandas as pd
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import hashlib
import os
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('smart_crawler.log'),
        logging.StreamHandler()
    ]
)

class SmartCrawler:
    def __init__(self, max_workers=6):
        self.base_url = "https://luatvietnam.vn"
        self.documents = []
        self.processed_urls = set()
        self.failed_urls = []
        self.working_urls = set()
        self.max_workers = max_workers
        self.lock = threading.Lock()
        
        # Setup session with better headers
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
    def load_existing_data(self):
        """Load existing crawled data from Excel files"""
        excel_files = [f for f in os.listdir('.') if f.startswith('luatvietnam_') and f.endswith('.xlsx')]
        
        if not excel_files:
            logging.info("No existing backup files found. Starting fresh.")
            return
            
        # Sort by creation time and pick the most recent
        excel_files.sort(key=lambda x: os.path.getctime(x), reverse=True)
        latest_file = excel_files[0]
        
        try:
            df = pd.read_excel(latest_file)
            existing_docs = len(df)
            
            logging.info(f"Loading existing data from {latest_file}")
            logging.info(f"Found {existing_docs} existing documents")
            
            # Convert to our format and track processed URLs
            for _, row in df.iterrows():
                doc = {
                    'title': row['title'],
                    'url': row['url'],
                    'summary': row.get('summary', ''),
                    'category': row.get('category', ''),
                    'date': row.get('date', ''),
                    'file_type': row.get('file_type', ''),
                    'file_url': row.get('file_url', ''),
                    'md5_hash': row.get('md5_hash', '')
                }
                self.documents.append(doc)
                self.processed_urls.add(row['url'])
            
            logging.info(f"Loaded {len(self.documents)} documents from backup")
            logging.info(f"Progress: {len(self.documents)/16463*100:.1f}%")
            
        except Exception as e:
            logging.error(f"Error loading existing data: {e}")
    
    def discover_working_urls(self):
        """Discover which base URLs actually work before full crawling"""
        logging.info("Phase 1: Discovering working URLs...")
        
        # Test main base URLs first
        base_patterns = [
            "https://luatvietnam.vn/giao-thong-28.html",
            "https://luatvietnam.vn/giao-thong-28-f1.html", 
            "https://luatvietnam.vn/giao-thong-28-f2.html",
            "https://luatvietnam.vn/giao-thong-28-f6.html",
            "https://luatvietnam.vn/search?category=28",
            "https://luatvietnam.vn/tim-kiem.html?q=giao+thong"
        ]
        
        working_patterns = []
        
        for base in base_patterns:
            try:
                response = self.session.get(base, timeout=10)
                if response.status_code == 200:
                    working_patterns.append(base)
                    logging.info(f"Working base URL: {base}")
                    
                    # Test pagination for this pattern
                    max_page = self.find_max_pages(base)
                    logging.info(f"Max pages for {base}: {max_page}")
                    
            except Exception as e:
                logging.warning(f"Failed to test {base}: {e}")
        
        return working_patterns
    
    def find_max_pages(self, base_url):
        """Find the maximum page number for a given base URL"""
        max_page = 1
        
        # Binary search to find max page efficiently
        left, right = 1, 200
        
        while left <= right:
            mid = (left + right) // 2
            test_url = self.build_page_url(base_url, mid)
            
            try:
                response = self.session.get(test_url, timeout=10)
                if response.status_code == 200 and self.has_content(response.text):
                    max_page = mid
                    left = mid + 1
                else:
                    right = mid - 1
            except:
                right = mid - 1
        
        return max_page
    
    def build_page_url(self, base_url, page_num):
        """Build a page URL with proper parameters"""
        if "search?" in base_url:
            return f"{base_url}&page={page_num}"
        elif "tim-kiem.html?" in base_url:
            return f"{base_url}&page={page_num}"
        else:
            return f"{base_url}?page={page_num}"
    
    def has_content(self, html):
        """Check if the page has actual content (not just empty pagination)"""
        if not html:
            return False
            
        soup = BeautifulSoup(html, 'html.parser')
        
        # Look for document links
        selectors = [
            'a[href*="/van-ban/"]',
            'a[href*="/chi-thi/"]', 
            'a[href*="/thong-tu/"]',
            'a[href*="/nghi-dinh/"]',
            'a[href*="/quyet-dinh/"]',
            '.doc-title a',
            '.document-item a',
            '.search-result a'
        ]
        
        for selector in selectors:
            if soup.select(selector):
                return True
        
        return False
    
    def extract_documents_from_page(self, url):
        """Extract document information from a single page"""
        try:
            response = self.session.get(url, timeout=15)
            if response.status_code != 200:
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            page_docs = []
            
            # Look for document links in various formats
            selectors = [
                'a[href*="/van-ban/"]',
                'a[href*="/chi-thi/"]', 
                'a[href*="/thong-tu/"]',
                'a[href*="/nghi-dinh/"]',
                'a[href*="/quyet-dinh/"]',
                'a[href*="/luat/"]',
                'a[href*="/cong-van/"]',
                'a[href*="/thong-bao/"]',
                '.doc-title a',
                '.document-item a',
                '.search-result a',
                'h3 a',
                'h4 a'
            ]
            
            found_links = set()
            for selector in selectors:
                links = soup.select(selector)
                for link in links:
                    href = link.get('href')
                    if href:
                        full_url = urljoin(self.base_url, href)
                        if self.is_traffic_document(link.get_text(strip=True)):
                            found_links.add((full_url, link.get_text(strip=True)))
            
            # Process each document link
            for doc_url, title in found_links:
                if doc_url in self.processed_urls:
                    continue
                    
                if title and len(title) > 10:  # Filter out very short titles
                    doc_info = {
                        'title': title,
                        'url': doc_url,
                        'summary': '',
                        'category': 'Giao thông',
                        'date': '',
                        'file_type': '',
                        'file_url': '',
                        'md5_hash': self.calculate_md5(doc_url)
                    }
                    page_docs.append(doc_info)
            
            return page_docs
            
        except Exception as e:
            logging.warning(f"Error extracting from {url}: {e}")
            return []
    
    def is_traffic_document(self, title):
        """Check if a document title is related to traffic"""
        if not title:
            return False
        
        title_lower = title.lower()
        
        # Traffic-related keywords
        traffic_keywords = [
            'giao thông', 'giao thong', 'xe cộ', 'ô tô', 'xe máy', 
            'đường bộ', 'duong bo', 'vận tải', 'van tai',
            'lái xe', 'lai xe', 'bằng lái', 'bang lai',
            'vi phạm', 'vi pham', 'phạt nguội', 'phat nguoi',
            'tốc độ', 'toc do', 'an toàn', 'an toan',
            'đường sắt', 'duong sat', 'tàu hỏa', 'tau hoa',
            'hàng không', 'hang khong', 'máy bay', 'may bay',
            'cảng', 'port', 'bến xe', 'ben xe',
            'biển số', 'bien so', 'đăng ký', 'dang ky',
            'kiểm định', 'kiem dinh', 'bảo hiểm', 'bao hiem'
        ]
        
        return any(keyword in title_lower for keyword in traffic_keywords)
    
    def calculate_md5(self, text):
        """Calculate MD5 hash for deduplication"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    def save_progress(self):
        """Save current progress to Excel file"""
        if not self.documents:
            return
            
        df = pd.DataFrame(self.documents)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"luatvietnam_smart_backup_{timestamp}.xlsx"
        
        try:
            df.to_excel(filename, index=False)
            logging.info(f"Saved {len(self.documents)} documents to {filename}")
            return filename
        except Exception as e:
            logging.error(f"Error saving progress: {e}")
            return None
    
    def crawl_urls_parallel(self, urls):
        """Crawl multiple URLs in parallel"""
        new_documents = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all URLs for processing
            future_to_url = {executor.submit(self.extract_documents_from_page, url): url for url in urls}
            
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    page_docs = future.result()
                    if page_docs:
                        with self.lock:
                            for doc in page_docs:
                                if doc['url'] not in self.processed_urls:
                                    new_documents.append(doc)
                                    self.processed_urls.add(doc['url'])
                        
                        logging.info(f"Found {len(page_docs)} new docs on {url}")
                    
                except Exception as e:
                    logging.warning(f"Failed to process {url}: {e}")
                    self.failed_urls.append(url)
        
        return new_documents
    
    def run_smart_crawl(self):
        """Run the smart crawling process"""
        logging.info("Starting Smart Crawler")
        
        # Load existing data
        self.load_existing_data()
        start_count = len(self.documents)
        
        # Phase 1: Discover working URLs
        working_patterns = self.discover_working_urls()
        if not working_patterns:
            logging.error("No working base URLs found!")
            return 0, 0
        
        # Phase 2: Generate focused URL list
        all_urls = []
        for pattern in working_patterns:
            max_pages = self.find_max_pages(pattern)
            for page in range(1, max_pages + 1):
                url = self.build_page_url(pattern, page)
                all_urls.append(url)
                
                # Also try with ShowSapo variations for non-search URLs
                if "search?" not in pattern and "tim-kiem" not in pattern:
                    all_urls.append(f"{pattern}?page={page}&ShowSapo=0")
                    all_urls.append(f"{pattern}?page={page}&ShowSapo=1")
        
        logging.info(f"Generated {len(all_urls)} focused URLs to crawl")
        
        # Phase 3: Parallel crawling
        batch_size = 50
        total_new = 0
        
        for i in range(0, len(all_urls), batch_size):
            batch = all_urls[i:i+batch_size]
            logging.info(f"Processing batch {i//batch_size + 1}/{(len(all_urls) + batch_size - 1)//batch_size}")
            
            new_docs = self.crawl_urls_parallel(batch)
            if new_docs:
                self.documents.extend(new_docs)
                total_new += len(new_docs)
                
                current_total = len(self.documents)
                progress = current_total / 16463 * 100
                logging.info(f"Progress: {current_total} docs ({progress:.1f}%) - {len(new_docs)} new in this batch")
                
                # Save progress every few batches
                if (i // batch_size + 1) % 5 == 0:
                    self.save_progress()
        
        # Final results
        final_count = len(self.documents)
        new_found = final_count - start_count
        
        logging.info("SMART CRAWL COMPLETED!")
        logging.info(f"Total documents: {final_count}")
        logging.info(f"New documents found: {new_found}")
        logging.info(f"Overall progress: {final_count/16463*100:.1f}%")
        logging.info(f"Failed URLs: {len(self.failed_urls)}")
        
        # Save final results
        final_file = self.save_progress()
        if final_file:
            logging.info(f"Final results saved to: {final_file}")
        
        return final_count, new_found

def main():
    """Main execution function"""
    try:
        crawler = SmartCrawler(max_workers=6)
        total_docs, new_docs = crawler.run_smart_crawl()
        
        print(f"\nCRAWLING SUMMARY:")
        print(f"   Total documents: {total_docs}")
        print(f"   New documents: {new_docs}")
        print(f"   Progress: {total_docs/16463*100:.1f}%")
        
    except Exception as e:
        logging.error(f"Critical error: {e}")
        return 1
        
    return 0

if __name__ == "__main__":
    exit(main())
