#!/usr/bin/env python3
"""
Complete LuatVietnam.vn Crawler - Crawl ALL Traffic Law Documents
================================================================
This script will systematically crawl ALL pages to collect all 16,463 documents.
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import logging
from datetime import datetime
import os
import re
from collections import deque
import hashlib

class CompleteLuatVietnamCrawler:
    def __init__(self):
        """Initialize the complete crawler"""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Setup logging
        self.setup_logging()
        
        # Data storage
        self.all_documents = []
        self.processed_urls = set()
        self.failed_urls = []
        
        # Configuration
        self.base_url = "https://luatvietnam.vn"
        self.traffic_base = f"{self.base_url}/giao-thong-28"
        self.delay = 2  # seconds between requests
        self.save_interval = 250  # save every N documents
        
        # Load existing data
        self.load_existing_data()
        
        self.logger.info(f"🚀 Complete Crawler initialized")
        self.logger.info(f"📊 Current collection: {len(self.processed_urls):,} documents")
        self.logger.info(f"🎯 Target: 16,463 documents")
        self.logger.info(f"📈 Remaining: {16463 - len(self.processed_urls):,} documents")

    def setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('complete_crawler.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def load_existing_data(self):
        """Load existing crawled documents to avoid duplicates"""
        # Try to load the most recent backup file - prioritize complete backups
        backup_files = [f for f in os.listdir('.') if f.startswith('luatvietnam_complete_backup_')]
        if not backup_files:
            backup_files = [f for f in os.listdir('.') if f.startswith('luatvietnam_quality_backup_')]
        
        if backup_files:
            # Find the backup with the highest document count (best progress)
            best_file = None
            max_docs = 0
            
            for backup_file in backup_files:
                try:
                    df = pd.read_excel(backup_file)
                    doc_count = len(df)
                    if doc_count > max_docs:
                        max_docs = doc_count
                        best_file = backup_file
                except:
                    continue
            
            if best_file:
                try:
                    df = pd.read_excel(best_file)
                    for _, row in df.iterrows():
                        url = row['url']
                        self.processed_urls.add(url)
                        # Store the document data too
                        doc = {
                            'title': row['title'],
                            'url': url,
                            'publication_date': row.get('publication_date', ''),
                            'document_type': row.get('document_type', ''),
                            'source_page': row.get('source_page', ''),
                            'crawled_date': row.get('crawled_date', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                        }
                        self.all_documents.append(doc)
                    
                    progress = (len(self.all_documents) / 16463) * 100
                    self.logger.info(f"📂 Loaded {len(self.all_documents):,} existing documents from {best_file}")
                    self.logger.info(f"📈 Resuming from {progress:.1f}% progress")
                    return
                except Exception as e:
                    self.logger.error(f"❌ Error loading {best_file}: {e}")
        
        # Also try other files
        for filename in ['luatvietnam_complete_collection.xlsx', 'luatvietnam_traffic_laws.xlsx']:
            if os.path.exists(filename) and len(self.processed_urls) == 0:
                try:
                    df = pd.read_excel(filename)
                    for _, row in df.iterrows():
                        url = row['url']
                        self.processed_urls.add(url)
                    self.logger.info(f"📂 Loaded {len(self.processed_urls):,} URLs from {filename}")
                    break
                except Exception as e:
                    self.logger.error(f"❌ Error loading {filename}: {e}")

    def is_quality_document(self, title):
        """Filter out auxiliary content and keep only real legal documents"""
        if not title or len(title.strip()) < 10:
            return False
        
        # Skip auxiliary content
        skip_patterns = [
            'VB liên quan', 'Thuộc tính', 'Tải về', 'Tóm tắt', 'Hiệu lực',
            'Văn bản gốc', 'Tình trạng', 'Loại văn bản', 'Cơ quan ban hành',
            'Người ký', 'Ngày ban hành', 'Ngày hiệu lực', 'Ngày hết hiệu lực',
            'Tình trạng hiệu lực', 'Lĩnh vực', 'Tệp đính kèm', 'Link tải',
            'Chi tiết', 'Xem thêm', 'Đọc thêm', 'Liên kết', 'Kết nối'
        ]
        
        for pattern in skip_patterns:
            if pattern.lower() in title.lower():
                return False
        
        # Must contain legal document indicators
        legal_patterns = [
            'luật', 'nghị định', 'thông tư', 'quyết định', 'công văn',
            'chỉ thị', 'nghị quyết', 'thông báo', 'kế hoạch', 'chương trình',
            'văn bản', 'pháp lệnh', 'sắc lệnh', 'hiến pháp'
        ]
        
        title_lower = title.lower()
        return any(pattern in title_lower for pattern in legal_patterns)

    def extract_document_info(self, title, url, source_page):
        """Extract document information from title and URL"""
        # Extract document type
        document_type = "Unknown"
        type_patterns = {
            'Luật': r'luật\s+',
            'Nghị định': r'nghị định\s+',
            'Thông tư': r'thông tư\s+',
            'Quyết định': r'quyết định\s+',
            'Công văn': r'công văn\s+',
            'Chỉ thị': r'chỉ thị\s+',
            'Nghị quyết': r'nghị quyết\s+',
            'Thông báo': r'thông báo\s+',
            'Kế hoạch': r'kế hoạch\s+',
            'Chương trình': r'chương trình\s+'
        }
        
        title_lower = title.lower()
        for doc_type, pattern in type_patterns.items():
            if re.search(pattern, title_lower):
                document_type = doc_type
                break
        
        # Extract publication date (if available in title)
        publication_date = ""
        date_patterns = [
            r'(\d{1,2}/\d{1,2}/\d{4})',
            r'(\d{4})',
            r'năm\s+(\d{4})'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, title)
            if match:
                publication_date = match.group(1)
                break
        
        return {
            'title': title.strip(),
            'url': url,
            'publication_date': publication_date,
            'document_type': document_type,
            'source_page': source_page,
            'crawled_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    def fetch_page(self, url, max_retries=3):
        """Fetch a page with retries"""
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                return response
            except Exception as e:
                self.logger.warning(f"⚠️ Attempt {attempt + 1} failed for {url}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(self.delay * (attempt + 1))
                else:
                    self.failed_urls.append(url)
                    self.logger.error(f"❌ Failed to fetch {url} after {max_retries} attempts")
                    return None

    def extract_documents_from_page(self, page_url):
        """Extract all documents from a single page"""
        response = self.fetch_page(page_url)
        if not response:
            return []
        
        soup = BeautifulSoup(response.content, 'html.parser')
        documents = []
        
        # Find all document links
        # Look for various link patterns used on the site
        link_selectors = [
            'a[href*="/giao-thong/"]',
            '.search-result-item a',
            '.document-title a',
            '.result-item a',
            'h3 a',
            '.title a'
        ]
        
        found_links = set()
        for selector in link_selectors:
            for link in soup.select(selector):
                href = link.get('href', '')
                title = link.get_text(strip=True)
                
                if href and title:
                    # Convert relative URLs to absolute
                    if href.startswith('/'):
                        full_url = self.base_url + href
                    elif href.startswith('http'):
                        full_url = href
                    else:
                        continue
                    
                    # Skip if already processed or not a quality document
                    if full_url in self.processed_urls or not self.is_quality_document(title):
                        continue
                    
                    found_links.add((title, full_url))
        
        # Convert to document objects
        for title, url in found_links:
            doc = self.extract_document_info(title, url, page_url)
            documents.append(doc)
            self.processed_urls.add(url)
        
        self.logger.info(f"📄 Found {len(documents)} new documents on {page_url}")
        return documents

    def generate_all_page_urls(self):
        """Generate all possible page URLs to crawl"""
        page_urls = []
        
        # Main traffic law category pages with different formats
        base_patterns = [
            f"{self.traffic_base}-f6.html",  # Main format
            f"{self.traffic_base}-f1.html",  # Alternative format
            f"{self.traffic_base}-f2.html",  # Another format
            f"{self.traffic_base}.html",     # Simple format
        ]
        
        # Generate page URLs for each format
        for base_pattern in base_patterns:
            # Add base URL without page parameter
            page_urls.append(base_pattern)
            
            # Add paginated URLs
            for page_num in range(1, 825):  # Up to page 824
                # Various pagination formats
                pagination_formats = [
                    f"{base_pattern}?page={page_num}",
                    f"{base_pattern}?ShowSapo=0&page={page_num}",
                    f"{base_pattern}?ShowSapo=1&page={page_num}",
                    f"{base_pattern}?page={page_num}&ShowSapo=0",
                    f"{base_pattern}?page={page_num}&ShowSapo=1",
                ]
                
                page_urls.extend(pagination_formats)
        
        # Add search-based URLs
        for page_num in range(1, 825):
            search_urls = [
                f"{self.base_url}/tim-kiem.html?q=giao+thong&page={page_num}",
                f"{self.base_url}/search?category=28&page={page_num}",
            ]
            page_urls.extend(search_urls)
        
        # Remove duplicates and return
        unique_urls = list(set(page_urls))
        self.logger.info(f"🔗 Generated {len(unique_urls):,} page URLs to crawl")
        return unique_urls

    def save_progress(self):
        """Save current progress to Excel file"""
        if not self.all_documents:
            return
        
        # Create DataFrame
        df = pd.DataFrame(self.all_documents)
        
        # Remove duplicates by URL
        df = df.drop_duplicates(subset=['url'], keep='first')
        
        # Save with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"luatvietnam_complete_backup_{timestamp}.xlsx"
        
        try:
            df.to_excel(filename, index=False)
            self.logger.info(f"💾 Saved {len(df):,} documents to {filename}")
            
            # Progress calculation
            total_target = 16463
            progress_pct = (len(df) / total_target) * 100
            remaining = total_target - len(df)
            
            print(f"\n📊 PROGRESS UPDATE:")
            print(f"   ✅ Total documents: {len(df):,}")
            print(f"   📈 Progress: {progress_pct:.1f}%")
            print(f"   📋 Remaining: {remaining:,}")
            print(f"   💾 Saved to: {filename}")
            
        except Exception as e:
            self.logger.error(f"❌ Error saving progress: {e}")

    def crawl_all_documents(self):
        """Main method to crawl all documents"""
        self.logger.info("🚀 Starting complete crawl of all traffic law documents...")
        
        # Generate all page URLs
        page_urls = self.generate_all_page_urls()
        
        total_pages = len(page_urls)
        processed_pages = 0
        documents_found = len(self.all_documents)
        
        self.logger.info(f"📋 Will crawl {total_pages:,} pages")
        
        # Crawl each page
        for i, page_url in enumerate(page_urls):
            try:
                # Extract documents from this page
                new_docs = self.extract_documents_from_page(page_url)
                self.all_documents.extend(new_docs)
                documents_found += len(new_docs)
                processed_pages += 1
                
                # Progress update
                if processed_pages % 50 == 0:
                    progress_pct = (processed_pages / total_pages) * 100
                    print(f"📊 Progress: {processed_pages:,}/{total_pages:,} pages ({progress_pct:.1f}%) - {documents_found:,} documents found")
                
                # Save progress periodically
                if len(new_docs) > 0 and documents_found % self.save_interval == 0:
                    self.save_progress()
                
                # Delay between requests
                time.sleep(self.delay)
                
            except KeyboardInterrupt:
                self.logger.info("⚠️ Crawling interrupted by user")
                break
            except Exception as e:
                self.logger.error(f"❌ Error processing {page_url}: {e}")
                continue
        
        # Final save
        self.save_progress()
        
        # Summary
        total_docs = len(self.all_documents)
        unique_docs = len(set(doc['url'] for doc in self.all_documents))
        
        print(f"\n" + "="*60)
        print(f"🎉 COMPLETE CRAWL FINISHED!")
        print(f"="*60)
        print(f"📄 Total documents collected: {total_docs:,}")
        print(f"🔗 Unique documents: {unique_docs:,}")
        print(f"📋 Pages processed: {processed_pages:,}/{total_pages:,}")
        print(f"❌ Failed URLs: {len(self.failed_urls)}")
        print(f"🎯 Target completion: {(unique_docs/16463)*100:.1f}%")
        print(f"="*60)
        
        if self.failed_urls:
            print(f"\n❌ Failed URLs:")
            for url in self.failed_urls[:10]:  # Show first 10
                print(f"   - {url}")
            if len(self.failed_urls) > 10:
                print(f"   ... and {len(self.failed_urls)-10} more")

def main():
    """Main execution function"""
    crawler = CompleteLuatVietnamCrawler()
    crawler.crawl_all_documents()

if __name__ == "__main__":
    main()
