#!/usr/bin/env python3
"""
Fast Selenium-based Vietnamese Traffic Law Crawler
Enhanced for speed and efficiency using parallel processing
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
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
import queue

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('selenium_crawler.log'),
        logging.StreamHandler()
    ]
)

class FastSeleniumCrawler:
    def __init__(self, max_workers=8, headless=True):
        self.base_url = "https://luatvietnam.vn"
        self.documents = []
        self.processed_urls = set()
        self.failed_urls = []
        self.max_workers = max_workers
        self.headless = headless
        self.lock = threading.Lock()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
        # Chrome options for performance
        self.chrome_options = Options()
        if headless:
            self.chrome_options.add_argument('--headless')
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--disable-dev-shm-usage')
        self.chrome_options.add_argument('--disable-gpu')
        self.chrome_options.add_argument('--disable-extensions')
        self.chrome_options.add_argument('--disable-logging')
        self.chrome_options.add_argument('--disable-web-security')
        self.chrome_options.add_argument('--allow-running-insecure-content')
        self.chrome_options.add_argument('--disable-features=VizDisplayCompositor')
        self.chrome_options.add_argument('--window-size=1920,1080')
        
        # Performance optimizations
        prefs = {
            "profile.default_content_setting_values": {
                "images": 2,  # Block images
                "plugins": 2,  # Block plugins
                "popups": 2,  # Block popups
                "geolocation": 2,  # Block location sharing
                "notifications": 2,  # Block notifications
                "media_stream": 2,  # Block media stream
            }
        }
        self.chrome_options.add_experimental_option("prefs", prefs)
        
    def create_driver(self):
        """Create a new Chrome driver instance"""
        try:
            driver = webdriver.Chrome(options=self.chrome_options)
            driver.set_page_load_timeout(30)
            driver.implicitly_wait(10)
            return driver
        except Exception as e:
            logging.error(f"Failed to create Chrome driver: {e}")
            return None
    
    def load_existing_data(self):
        """Load existing crawled data from Excel files"""
        excel_files = [f for f in os.listdir('.') if f.startswith('luatvietnam_complete_backup_') and f.endswith('.xlsx')]
        
        if not excel_files:
            logging.info("No existing backup files found. Starting fresh.")
            return
            
        # Sort by creation time and pick the most recent
        excel_files.sort(key=lambda x: os.path.getctime(x), reverse=True)
        latest_file = excel_files[0]
        
        try:
            df = pd.read_excel(latest_file)
            existing_docs = len(df)
            
            logging.info(f"📂 Loading existing data from {latest_file}")
            logging.info(f"📄 Found {existing_docs} existing documents")
            
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
            
            logging.info(f"✅ Loaded {len(self.documents)} documents from backup")
            logging.info(f"📊 Progress: {len(self.documents)/16463*100:.1f}%")
            
        except Exception as e:
            logging.error(f"❌ Error loading existing data: {e}")
    
    def generate_all_urls(self):
        """Generate all possible page URLs for comprehensive crawling"""
        urls = []
        
        # Main category pages with different formats and parameters
        base_patterns = [
            "https://luatvietnam.vn/giao-thong-28.html",
            "https://luatvietnam.vn/giao-thong-28-f1.html", 
            "https://luatvietnam.vn/giao-thong-28-f2.html",
            "https://luatvietnam.vn/giao-thong-28-f6.html",
            "https://luatvietnam.vn/search?category=28",
            "https://luatvietnam.vn/tim-kiem.html?q=giao+thong"
        ]
        
        # Generate paginated URLs (much wider range for completeness)
        for base in base_patterns:
            for page in range(1, 1001):  # Test up to 1000 pages
                if "search?" in base:
                    urls.append(f"{base}&page={page}")
                elif "tim-kiem.html?" in base:
                    urls.append(f"{base}&page={page}")
                else:
                    # Multiple parameter combinations
                    urls.extend([
                        f"{base}?page={page}",
                        f"{base}?page={page}&ShowSapo=0",
                        f"{base}?page={page}&ShowSapo=1", 
                        f"{base}?ShowSapo=0&page={page}",
                        f"{base}?ShowSapo=1&page={page}"
                    ])
        
        logging.info(f"🔗 Generated {len(urls)} URLs to crawl")
        return urls
    
    def extract_documents_from_page(self, driver, url):
        """Extract document information from a page using Selenium"""
        try:
            driver.get(url)
            
            # Wait for content to load
            WebDriverWait(driver, 10).wait(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Get page source and parse with BeautifulSoup for easier handling
            soup = BeautifulSoup(driver.page_source, 'html.parser')
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
                        found_links.add(full_url)
            
            # Process each document link
            for doc_url in found_links:
                if doc_url in self.processed_urls:
                    continue
                    
                try:
                    # Extract basic info from the current page
                    link_element = soup.find('a', href=lambda x: x and doc_url.split('/')[-1] in x)
                    if link_element:
                        title = link_element.get_text(strip=True)
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
                            
                except Exception as e:
                    logging.debug(f"Error processing link {doc_url}: {e}")
                    continue
            
            return page_docs
            
        except TimeoutException:
            logging.warning(f"⏰ Timeout loading {url}")
            return []
        except WebDriverException as e:
            logging.warning(f"⚠️ WebDriver error for {url}: {e}")
            return []
        except Exception as e:
            logging.error(f"❌ Unexpected error for {url}: {e}")
            return []
    
    def worker_crawl_pages(self, url_queue, results_queue):
        """Worker function to crawl pages using Selenium"""
        driver = self.create_driver()
        if not driver:
            logging.error("Failed to create driver for worker")
            return
            
        try:
            while True:
                try:
                    url = url_queue.get(timeout=1)
                except queue.Empty:
                    break
                    
                try:
                    page_docs = self.extract_documents_from_page(driver, url)
                    results_queue.put((url, page_docs, None))
                    
                except Exception as e:
                    results_queue.put((url, [], str(e)))
                finally:
                    url_queue.task_done()
                    
        finally:
            driver.quit()
    
    def calculate_md5(self, text):
        """Calculate MD5 hash for deduplication"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    def save_progress(self):
        """Save current progress to Excel file"""
        if not self.documents:
            return
            
        df = pd.DataFrame(self.documents)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"luatvietnam_selenium_backup_{timestamp}.xlsx"
        
        try:
            df.to_excel(filename, index=False)
            logging.info(f"💾 Saved {len(self.documents)} documents to {filename}")
            return filename
        except Exception as e:
            logging.error(f"❌ Error saving progress: {e}")
            return None
    
    def run_fast_crawl(self):
        """Run the fast Selenium-based crawl"""
        logging.info("🚀 Starting Fast Selenium Crawler")
        logging.info(f"⚙️ Configuration: {self.max_workers} workers, headless={self.headless}")
        
        # Load existing data
        self.load_existing_data()
        start_count = len(self.documents)
        
        # Generate URLs to crawl
        all_urls = self.generate_all_urls()
        
        # Filter out already processed URLs  
        remaining_urls = [url for url in all_urls if not any(processed in url for processed in self.processed_urls)]
        logging.info(f"📊 URLs to process: {len(remaining_urls)}")
        
        # Setup queues for parallel processing
        url_queue = queue.Queue()
        results_queue = queue.Queue()
        
        # Add URLs to queue
        for url in remaining_urls:
            url_queue.put(url)
        
        # Start worker threads
        workers = []
        for i in range(self.max_workers):
            worker = threading.Thread(target=self.worker_crawl_pages, args=(url_queue, results_queue))
            worker.daemon = True
            worker.start()
            workers.append(worker)
            
        logging.info(f"👥 Started {len(workers)} worker threads")
        
        # Process results
        processed_count = 0
        new_docs = 0
        
        try:
            while processed_count < len(remaining_urls):
                try:
                    url, page_docs, error = results_queue.get(timeout=60)
                    processed_count += 1
                    
                    if error:
                        self.failed_urls.append(url)
                        logging.warning(f"❌ Failed {url}: {error}")
                    else:
                        # Add new documents
                        for doc in page_docs:
                            if doc['url'] not in self.processed_urls:
                                with self.lock:
                                    self.documents.append(doc)
                                    self.processed_urls.add(doc['url'])
                                    new_docs += 1
                        
                        if page_docs:
                            logging.info(f"📄 Found {len(page_docs)} new docs on {url}")
                    
                    # Progress update every 50 URLs
                    if processed_count % 50 == 0:
                        current_total = len(self.documents)
                        progress = current_total / 16463 * 100
                        logging.info(f"📊 Progress: {processed_count}/{len(remaining_urls)} URLs | {current_total} docs ({progress:.1f}%)")
                        
                        # Save progress periodically
                        if processed_count % 200 == 0:
                            self.save_progress()
                            
                except queue.Empty:
                    logging.warning("⏰ Timeout waiting for results")
                    break
                    
        except KeyboardInterrupt:
            logging.info("⚠️ Crawling interrupted by user")
        
        # Wait for all workers to finish
        for worker in workers:
            worker.join(timeout=30)
        
        # Final results
        final_count = len(self.documents)
        new_found = final_count - start_count
        
        logging.info("🎉 SELENIUM CRAWL COMPLETED!")
        logging.info(f"📄 Total documents: {final_count}")
        logging.info(f"🆕 New documents found: {new_found}")
        logging.info(f"📊 Overall progress: {final_count/16463*100:.1f}%")
        logging.info(f"❌ Failed URLs: {len(self.failed_urls)}")
        
        # Save final results
        final_file = self.save_progress()
        if final_file:
            logging.info(f"💾 Final results saved to: {final_file}")
        
        return final_count, new_found

def main():
    """Main execution function"""
    try:
        # Configure for maximum speed
        crawler = FastSeleniumCrawler(
            max_workers=8,  # Adjust based on your system
            headless=True   # Set to False if you want to see browsers
        )
        
        # Run the crawl
        total_docs, new_docs = crawler.run_fast_crawl()
        
        print(f"\n🎯 CRAWLING SUMMARY:")
        print(f"   📄 Total documents: {total_docs}")
        print(f"   🆕 New documents: {new_docs}")
        print(f"   📊 Progress: {total_docs/16463*100:.1f}%")
        
    except Exception as e:
        logging.error(f"💥 Critical error: {e}")
        return 1
        
    return 0

if __name__ == "__main__":
    exit(main())
