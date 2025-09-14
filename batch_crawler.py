#!/usr/bin/env python3
"""
Batch Crawler - Modified version of bulk_download_all.py with batch support
Features:
- Choose Excel file to crawl from batch_files/
- Input username and password interactively
- Support for batch downloading with progress tracking
"""

import time
import os
import re
import sys
import requests
import pandas as pd
import json
import getpass
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

class LuatVietnamBatchCrawler:
    def __init__(self, username, password, excel_file, download_folder=None):
        self.username = username
        self.password = password
        self.excel_file = excel_file
        
        # Create download folder based on Excel file name if not provided
        if download_folder is None:
            file_base = os.path.splitext(os.path.basename(excel_file))[0]
            self.download_folder = f"downloads_{file_base}"
        else:
            self.download_folder = download_folder
        
        # Ensure download folder exists
        if not os.path.exists(self.download_folder):
            os.makedirs(self.download_folder)
        
        # Track progress with batch-specific names
        file_base = os.path.splitext(os.path.basename(excel_file))[0]
        self.progress_file = f"progress_{file_base}.txt"
        self.downloaded_urls = self.load_progress()
        
        # Error logging with batch-specific names
        self.error_log_file = f"failed_downloads_{file_base}.json"
        self.failed_downloads = self.load_failed_downloads()
        
        # Create fast lookup set for failed URLs (optimization)
        self.failed_urls = {failure['url'] for failure in self.failed_downloads}
        
        # Excel error logging
        self.excel_error_log_file = f"failed_downloads_log_{file_base}.xlsx"
        self.failed_downloads_df = self.load_failed_downloads_excel()
        
        # Initialize browser once for all downloads
        self.driver = None
        self.is_logged_in = False
        
        print(f"📁 Download folder: {self.download_folder}")
        print(f"📊 Excel file: {excel_file}")
        print(f"📊 Previously downloaded: {len(self.downloaded_urls)} documents")
        if self.failed_downloads:
            print(f"⚠️ Previously failed: {len(self.failed_downloads)} documents (will be skipped)")
        print(f"🚀 Skip failed downloads: {len(self.failed_urls)} URLs will be ignored")
        if os.path.exists(self.excel_error_log_file):
            print(f"📋 Excel error log: {self.excel_error_log_file}")
    
    def load_progress(self):
        """Load previously downloaded URLs to resume if interrupted"""
        downloaded_urls = set()
        
        # Load from progress file if it exists
        if os.path.exists(self.progress_file):
            with open(self.progress_file, 'r', encoding='utf-8') as f:
                downloaded_urls.update(line.strip() for line in f)
        
        # If progress file is missing or empty but we have downloaded files,
        # try to rebuild progress from Excel file and existing files
        if len(downloaded_urls) == 0 and os.path.exists(self.download_folder):
            existing_files = os.listdir(self.download_folder)
            if len(existing_files) > 0:
                print(f"🔄 Rebuilding progress from {len(existing_files)} existing files...")
                downloaded_urls = self.rebuild_progress_from_files()
        
        return downloaded_urls
    
    def rebuild_progress_from_files(self):
        """Rebuild progress tracking from existing downloaded files"""
        try:
            # Load Excel file to get URL mappings
            df = pd.read_excel(self.excel_file)
            existing_files = set(os.listdir(self.download_folder))
            downloaded_urls = set()
            
            for _, row in df.iterrows():
                document_title = row['title']
                document_url = row['url']
                
                # Generate the same filename that would be created
                safe_filename = re.sub(r'[^\w\s-]', '', document_title)
                safe_filename = re.sub(r'[-\s]+', '_', safe_filename)
                safe_filename = safe_filename[:90]
                
                import hashlib
                url_hash = hashlib.md5(document_url.encode()).hexdigest()[:8]
                expected_filename = f"{safe_filename}_{url_hash}.pdf"
                
                # If this file exists, add URL to downloaded set
                if expected_filename in existing_files:
                    downloaded_urls.add(document_url)
                    # Save to progress file
                    with open(self.progress_file, 'a', encoding='utf-8') as f:
                        f.write(document_url + '\n')
            
            print(f"✅ Rebuilt progress: {len(downloaded_urls)} URLs from existing files")
            return downloaded_urls
            
        except Exception as e:
            print(f"⚠️ Could not rebuild progress: {e}")
            return set()
    
    def save_progress(self, url):
        """Save downloaded URL to progress file"""
        with open(self.progress_file, 'a', encoding='utf-8') as f:
            f.write(url + '\n')
        self.downloaded_urls.add(url)
    
    def load_failed_downloads(self):
        """Load previously failed downloads for retry tracking"""
        if os.path.exists(self.error_log_file):
            try:
                with open(self.error_log_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def log_failed_download(self, document_info, error_message, additional_info=None):
        """Log failed download with detailed information for later retry"""
        failed_entry = {
            "timestamp": datetime.now().isoformat(),
            "title": document_info.get('title', 'Unknown'),
            "url": document_info.get('url', 'Unknown'),
            "pdf_url": document_info.get('pdf_url', 'Not found'),
            "error": error_message,
            "error_type": self._categorize_error(error_message),
            "retry_count": 0,
            "file_size_attempted": document_info.get('file_size', 0)
        }
        
        # Add any additional debugging information
        if additional_info:
            failed_entry.update(additional_info)
        
        # Check if this URL already failed before
        existing_entry = None
        for entry in self.failed_downloads:
            if entry.get('url') == document_info.get('url'):
                existing_entry = entry
                break
        
        if existing_entry:
            existing_entry['retry_count'] += 1
            existing_entry['timestamp'] = datetime.now().isoformat()
            existing_entry['error'] = error_message
            existing_entry['error_type'] = self._categorize_error(error_message)
            if additional_info:
                existing_entry.update(additional_info)
        else:
            self.failed_downloads.append(failed_entry)
        
        # Save to file
        try:
            with open(self.error_log_file, 'w', encoding='utf-8') as f:
                json.dump(self.failed_downloads, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Could not save error log: {e}")
        
        print(f"📝 Logged failure: {document_info.get('title', 'Unknown')[:50]}...")
        print(f"   Error type: {self._categorize_error(error_message)}")
        
        # Also log to Excel file
        self.log_failed_download_excel(document_info, error_message, additional_info)
    
    def load_failed_downloads_excel(self):
        """Load previously failed downloads from Excel file"""
        if os.path.exists(self.excel_error_log_file):
            try:
                return pd.read_excel(self.excel_error_log_file)
            except Exception as e:
                print(f"⚠️ Could not load Excel error log: {e}")
                return pd.DataFrame()
        return pd.DataFrame()
    
    def log_failed_download_excel(self, document_info, error_message, additional_info=None):
        """Log failed download to Excel file for easy analysis"""
        try:
            # Create new row for failed download
            new_row = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'title': document_info.get('title', 'Unknown'),
                'url': document_info.get('url', 'Unknown'),
                'pdf_url': document_info.get('pdf_url', 'Not found'),
                'error_message': error_message,
                'error_type': self._categorize_error(error_message),
                'file_size_attempted': document_info.get('file_size', 0),
                'filename': document_info.get('filename', 'Unknown'),
                'index': document_info.get('index', 0),
                'batch_file': os.path.basename(self.excel_file)
            }
            
            # Add additional info if provided
            if additional_info:
                for key, value in additional_info.items():
                    if key not in new_row:  # Don't overwrite existing keys
                        new_row[key] = value
            
            # Create new DataFrame with this row
            new_df = pd.DataFrame([new_row])
            
            # If Excel file exists, load and append
            if os.path.exists(self.excel_error_log_file):
                try:
                    existing_df = pd.read_excel(self.excel_error_log_file)
                    updated_df = pd.concat([existing_df, new_df], ignore_index=True)
                except Exception as e:
                    print(f"⚠️ Could not load existing Excel log, creating new: {e}")
                    updated_df = new_df
            else:
                updated_df = new_df
            
            # Save updated DataFrame
            updated_df.to_excel(self.excel_error_log_file, index=False)
            
        except Exception as e:
            print(f"⚠️ Could not save to Excel error log: {e}")
    
    def _categorize_error(self, error_message):
        """Categorize error types for better analysis"""
        error_msg = error_message.lower()
        
        if 'timeout' in error_msg or 'time out' in error_msg:
            return 'TIMEOUT_ERROR'
        elif 'connection' in error_msg or 'network' in error_msg:
            return 'CONNECTION_ERROR'
        elif 'pdf' in error_msg and ('not found' in error_msg or 'no pdf' in error_msg):
            return 'PDF_NOT_FOUND'
        elif 'login' in error_msg or 'authentication' in error_msg:
            return 'LOGIN_ERROR'
        elif 'download' in error_msg and 'failed' in error_msg:
            return 'DOWNLOAD_FAILED'
        elif 'file size' in error_msg or 'size' in error_msg:
            return 'FILE_SIZE_ERROR'
        elif 'element' in error_msg and 'not found' in error_msg:
            return 'ELEMENT_NOT_FOUND'
        elif 'json' in error_msg:
            return 'JSON_PARSE_ERROR'
        elif 'http' in error_msg or 'status' in error_msg:
            return 'HTTP_ERROR'
        else:
            return 'UNKNOWN_ERROR'
    
    def setup_browser(self):
        """Initialize Chrome browser with download settings"""
        if self.driver is not None:
            return True
        
        print("🌐 Initializing Chrome browser...")
        
        try:
            # Chrome options for downloading
            chrome_options = Options()
            
            # Download preferences
            download_prefs = {
                "download.default_directory": os.path.abspath(self.download_folder),
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True,
                "safebrowsing.disable_download_protection": True,
                "plugins.always_open_pdf_externally": True
            }
            
            chrome_options.add_experimental_option("prefs", download_prefs)
            
            # Additional options for stability
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-plugins")
            chrome_options.add_argument("--disable-images")
            # chrome_options.add_argument("--disable-javascript")  # REMOVED: JavaScript needed for login
            
            # Set up the driver
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Set timeouts
            self.driver.implicitly_wait(10)
            self.driver.set_page_load_timeout(30)
            
            print("✅ Browser initialized successfully")
            return True
            
        except Exception as e:
            print(f"❌ Failed to initialize browser: {e}")
            return False
    
    def login_to_luatvietnam(self):
        """Login to luatvietnam.vn"""
        if self.is_logged_in:
            return True
        
        print("🔑 Logging in to luatvietnam.vn...")
        
        try:
            # Navigate to main page first
            self.driver.get("https://luatvietnam.vn/")
            time.sleep(3)
            
            # Try to find and click login link
            login_success = False
            try:
                # Look for login link/button
                login_selectors = [
                    "//a[contains(@href, 'login')]",
                    "//a[contains(text(), 'Đăng nhập')]",
                    "//button[contains(text(), 'Đăng nhập')]",
                    ".login-link",
                    "#login-btn"
                ]
                
                login_element = None
                for selector in login_selectors:
                    try:
                        if selector.startswith('//'):
                            login_element = WebDriverWait(self.driver, 3).until(
                                EC.element_to_be_clickable((By.XPATH, selector))
                            )
                        else:
                            login_element = WebDriverWait(self.driver, 3).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                            )
                        break
                    except:
                        continue
                
                if login_element:
                    print("   🔗 Found login link, clicking...")
                    login_element.click()
                    time.sleep(2)
                
            except Exception as e:
                print(f"   ⚠️ Could not find login link: {e}")
            
            # Now try to fill in login form
            try:
                # Wait for login form to appear
                username_field = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.NAME, "username"))
                )
                password_field = self.driver.find_element(By.NAME, "password")
                
                print("   📝 Filling in credentials...")
                
                # Clear and enter credentials
                username_field.clear()
                username_field.send_keys(self.username)
                
                password_field.clear()
                password_field.send_keys(self.password)
                
                # Find submit button
                submit_selectors = [
                    "//button[contains(text(), 'Đăng nhập')]",
                    "//button[@type='submit']",
                    "//input[@type='submit']",
                    ".btn-login",
                    "#login-submit"
                ]
                
                submit_button = None
                for selector in submit_selectors:
                    try:
                        if selector.startswith('//'):
                            submit_button = self.driver.find_element(By.XPATH, selector)
                        else:
                            submit_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                        break
                    except:
                        continue
                
                if submit_button:
                    print("   🚀 Submitting login form...")
                    submit_button.click()
                    time.sleep(5)
                    
                    # Check for successful login by trying to detect logged-in state
                    success_indicators = [
                        "//a[contains(@href, 'logout')]",
                        "//a[contains(@href, 'profile')]", 
                        "//span[contains(text(), 'Chào')]",
                        ".user-menu",
                        ".logout-link"
                    ]
                    
                    for indicator in success_indicators:
                        try:
                            if indicator.startswith('//'):
                                element = WebDriverWait(self.driver, 5).until(
                                    EC.presence_of_element_located((By.XPATH, indicator))
                                )
                            else:
                                element = WebDriverWait(self.driver, 5).until(
                                    EC.presence_of_element_located((By.CSS_SELECTOR, indicator))
                                )
                            if element:
                                print("✅ Login successful - found user indicator")
                                self.is_logged_in = True
                                login_success = True
                                break
                        except:
                            continue
                    
                    if not login_success:
                        # Check if we're still on login page (login failed)
                        try:
                            still_on_login = self.driver.find_element(By.NAME, "username")
                            if still_on_login:
                                print("❌ Login failed - still on login page")
                                return False
                        except:
                            # No username field found, might have moved away from login page
                            print("⚠️ Login status unclear - proceeding cautiously")
                            self.is_logged_in = True
                            login_success = True
                
                else:
                    print("❌ Could not find submit button")
                    return False
                    
            except Exception as e:
                print(f"❌ Failed to fill login form: {e}")
                return False
                
        except Exception as e:
            print(f"❌ Login process failed: {e}")
            return False
        
        return login_success
    
    def clean_filename(self, filename):
        """Clean filename for safe saving"""
        # Remove invalid characters
        safe_filename = re.sub(r'[^\w\s-]', '', filename)
        # Replace multiple spaces/hyphens with single underscore
        safe_filename = re.sub(r'[-\s]+', '_', safe_filename)
        # Limit length
        safe_filename = safe_filename[:90]
        return safe_filename.strip('_')
        
    def verify_pdf_content(self, filepath, document_title):
        """Verify that the downloaded PDF is actual content, not a login page"""
        try:
            if not os.path.exists(filepath):
                return False, "File does not exist"
            
            file_size = os.path.getsize(filepath)
            
            # Check file size - login pages are typically small
            if file_size < 2048:  # Less than 2KB is suspicious
                return False, f"File too small: {file_size} bytes"
            
            # Try to read first few bytes to check PDF header
            with open(filepath, 'rb') as f:
                header = f.read(10)
                if not header.startswith(b'%PDF'):
                    return False, "Not a valid PDF file"
            
            # Additional check: if file is very small for a legal document
            if file_size < 10240:  # Less than 10KB is unusual for legal documents
                print(f"   ⚠️ Warning: Small file size ({file_size} bytes) for legal document")
            
            return True, f"Valid PDF ({file_size:,} bytes)"
            
        except Exception as e:
            return False, f"Error verifying PDF: {e}"
    
    def extract_document_url_from_source(self, page_source):
        """Extract document URL from page source (similar to bulk_download_all.py)"""
        try:
            # Look for PDF or DOC download links in the HTML
            import re
            
            # Pattern for PDF URLs
            pdf_patterns = [
                r'https://luatvietnam\.vn/uploads/[^"\']*\.pdf',
                r'href="([^"]*\.pdf[^"]*)"',
                r"href='([^']*\.pdf[^']*)'",
                r'src="([^"]*\.pdf[^"]*)"'
            ]
            
            # Pattern for DOC URLs  
            doc_patterns = [
                r'https://luatvietnam\.vn/uploads/[^"\']*\.docx?',
                r'href="([^"]*\.docx?[^"]*)"',
                r"href='([^']*\.docx?[^']*)'",
                r'src="([^"]*\.docx?[^"]*)"'
            ]
            
            # Try PDF first
            for pattern in pdf_patterns:
                matches = re.findall(pattern, page_source, re.IGNORECASE)
                if matches:
                    url = matches[0] if isinstance(matches[0], str) else matches[0][0]
                    if 'luatvietnam.vn' in url and '.pdf' in url.lower():
                        return url, 'PDF'
            
            # Try DOC if no PDF found
            for pattern in doc_patterns:
                matches = re.findall(pattern, page_source, re.IGNORECASE)
                if matches:
                    url = matches[0] if isinstance(matches[0], str) else matches[0][0]
                    if 'luatvietnam.vn' in url and ('.doc' in url.lower() or '.docx' in url.lower()):
                        return url, 'DOC'
            
            return None, None
            
        except Exception as e:
            print(f"   ⚠️ Error extracting document URL: {e}")
            return None, None
    
    def download_from_url(self, document_url, document_title, document_info):
        """Download document from direct URL"""
        try:
            # Create safe filename
            safe_filename = self.clean_filename(document_title)
            
            # Add URL hash to filename to avoid duplicates
            import hashlib
            url_hash = hashlib.md5(document_info['url'].encode()).hexdigest()[:8]
            
            # Determine file extension from URL
            if '.pdf' in document_url.lower():
                extension = '.pdf'
            elif '.docx' in document_url.lower():
                extension = '.docx'
            elif '.doc' in document_url.lower():
                extension = '.doc'
            else:
                extension = '.pdf'  # Default to PDF
            
            filename = f"{safe_filename}_{url_hash}{extension}"
            filepath = os.path.join(self.download_folder, filename)
            
            document_info['filename'] = filename
            document_info['pdf_url'] = document_url
            
            # Check if file already exists
            if os.path.exists(filepath):
                print(f"   ✅ File already exists: {filename}")
                self.save_progress(document_info['url'])
                return True
            
            print(f"   📥 Downloading: {filename[:50]}...")
            
            # Get cookies from browser for authenticated download
            cookies = self.driver.get_cookies()
            session = requests.Session()
            for cookie in cookies:
                session.cookies.set(cookie['name'], cookie['value'])
            
            # Download with requests
            response = session.get(document_url, stream=True, timeout=30)
            response.raise_for_status()
            
            # Save file
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Verify the downloaded file
            if extension == '.pdf':
                is_valid, verification_msg = self.verify_pdf_content(filepath, document_title)
            else:
                # For DOC files, just check basic file properties
                file_size = os.path.getsize(filepath)
                if file_size < 1024:
                    is_valid, verification_msg = False, f"File too small: {file_size} bytes"
                else:
                    is_valid, verification_msg = True, f"Valid {extension.upper()} ({file_size:,} bytes)"
            
            document_info['file_size'] = os.path.getsize(filepath)
            
            if not is_valid:
                os.remove(filepath)
                error_msg = f"Downloaded invalid file: {verification_msg}"
                self.log_failed_download(document_info, error_msg, {'step': 'verify_downloaded_file'})
                return False
            
            print(f"   ✅ Downloaded: {filename} - {verification_msg}")
            self.save_progress(document_info['url'])
            return True
            
        except Exception as e:
            if 'filepath' in locals() and os.path.exists(filepath):
                os.remove(filepath)
            error_msg = f"Download from URL failed: {str(e)}"
            self.log_failed_download(document_info, error_msg, {'step': 'download_from_url'})
            return False
    
    def download_document(self, document_url, document_title, index, total):
        """Download a single document with error handling"""
        
        document_info = {
            'title': document_title,
            'url': document_url,
            'index': index,
            'total': total
        }
        
        try:
            print(f"\n📄 [{index}/{total}] {document_title[:80]}...")
            
            # Skip if already downloaded
            if document_url in self.downloaded_urls:
                print(f"⏭️ [{index}/{total}] SKIPPED (already downloaded): {document_title[:60]}...")
                return True
            
            # Skip if previously failed (optimization)
            if document_url in self.failed_urls:
                print(f"⚠️ [{index}/{total}] SKIPPED (previously failed): {document_title[:60]}...")
                return False
            
            print("   🌐 Loading page...")
            self.driver.get(document_url)
            time.sleep(1)
            
            # Check for 404 or error pages first
            page_title = self.driver.title.lower()
            page_source = self.driver.page_source.lower()
            
            if ("404" in page_title or "không tìm thấy" in page_title or 
                "page not found" in page_title or "not found" in page_title or
                "không tìm thấy trang" in page_source or 
                "url không tồn tại" in page_source):
                error_msg = "Page not found (404 error)"
                self.log_failed_download(document_info, error_msg, {'step': 'page_load'})
                return False
            
            # Try to find document URLs directly from main content first
            found_url, file_type = self.extract_document_url_from_source(self.driver.page_source)
            
            # If we found a document URL directly, download it
            if found_url:
                print(f"   ✅ Document URL found (already logged in): {file_type}")
                return self.download_from_url(found_url, document_title, document_info)
            
            # Quick check for article pages to skip expensive operations
            if ("-article.html" in document_url.lower() or 
                "chính sách mới" in document_title.lower() or
                "hướng dẫn" in document_title.lower() or
                "chính sách" in document_title.lower() or
                "vb liên quan" in document_title.lower() or
                "thuộc tính" in document_title.lower() or
                "vb được hợp nhất" in document_title.lower()):
                error_msg = "Article/guide/reference page - no downloadable files"
                self.log_failed_download(document_info, error_msg, {'step': 'content_check'})
                return False
            
            # If no document URL found, try to trigger login on this specific page
            login_triggers = [
                "//a[contains(@class, 'lawsVnLogin')]",
                "//span[contains(@class, 'lawsVnLogin')]",
                "//a[contains(text(), 'Tải văn bản')]",
                "//span[contains(text(), 'Tải văn bản')]"
            ]
            
            login_triggered = False
            for trigger_xpath in login_triggers:
                try:
                    trigger_element = self.driver.find_element(By.XPATH, trigger_xpath)
                    # Use JavaScript click for better reliability
                    self.driver.execute_script("arguments[0].click();", trigger_element)
                    login_triggered = True
                    print(f"   🔑 Login popup triggered")
                    time.sleep(1)
                    break
                except:
                    continue
            
            if login_triggered:
                # Handle login popup
                try:
                    print(f"   📝 Entering credentials...")
                    
                    # Wait for login fields
                    username_field = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.ID, "customer_name"))
                    )
                    password_field = self.driver.find_element(By.ID, "password_login")
                    
                    # Use JavaScript to set values for better reliability
                    self.driver.execute_script("arguments[0].value = arguments[1];", username_field, self.username)
                    self.driver.execute_script("arguments[0].value = arguments[1];", password_field, self.password)
                    
                    # Submit form
                    try:
                        self.driver.execute_script("arguments[0].form.submit();", password_field)
                    except:
                        password_field.send_keys('\n')
                    
                    print(f"   ⏳ Waiting for login...")
                    time.sleep(2)
                    
                    # Check for successful login and extract document URL
                    current_url = self.driver.current_url
                    page_source = self.driver.page_source
                    
                    # Check for JSON login success response
                    if "application/json" in self.driver.page_source:
                        print("   ✅ Login successful - detected JSON response")
                        try:
                            import json
                            response_data = json.loads(self.driver.page_source)
                            if response_data.get('success'):
                                # Navigate back to document page to get download links
                                self.driver.get(document_url)
                                time.sleep(1)
                                page_source = self.driver.page_source
                        except:
                            pass
                    
                    # Extract document URL after login
                    found_url, file_type = self.extract_document_url_from_source(page_source)
                    
                    if found_url:
                        print(f"   ✅ Document URL found after login: {file_type}")
                        self.is_logged_in = True  # Mark as logged in for future requests
                        return self.download_from_url(found_url, document_title, document_info)
                    else:
                        error_msg = "No document URL found after login"
                        self.log_failed_download(document_info, error_msg, {'step': 'extract_after_login'})
                        return False
                        
                except Exception as e:
                    error_msg = f"Login process failed: {str(e)}"
                    self.log_failed_download(document_info, error_msg, {'step': 'login_popup'})
                    return False
            else:
                error_msg = "No login trigger found on page"
                self.log_failed_download(document_info, error_msg, {'step': 'find_login_trigger'})
                return False
                
        except Exception as e:
            error_msg = f"Download failed: {str(e)}"
            self.log_failed_download(document_info, error_msg, {'step': 'general_error'})
            return False
            
            # Create safe filename
            safe_filename = self.clean_filename(document_title)
            
            # Add URL hash to filename to avoid duplicates
            import hashlib
            url_hash = hashlib.md5(document_url.encode()).hexdigest()[:8]
            filename = f"{safe_filename}_{url_hash}.pdf"
            filepath = os.path.join(self.download_folder, filename)
            
            document_info['filename'] = filename
            document_info['pdf_url'] = pdf_url
            
            # Check if file already exists
            if os.path.exists(filepath):
                print(f"   ✅ File already exists: {filename}")
                self.save_progress(document_url)
                return True
            
            print(f"   📥 Downloading: {filename[:50]}...")
            
            # Try direct download first if we have PDF URL
            if pdf_url and pdf_url.startswith('http'):
                try:
                    # Get cookies from browser for authenticated download
                    cookies = self.driver.get_cookies()
                    session = requests.Session()
                    for cookie in cookies:
                        session.cookies.set(cookie['name'], cookie['value'])
                    
                    # Download with requests
                    response = session.get(pdf_url, stream=True, timeout=30)
                    response.raise_for_status()
                    
                    # Check content type
                    content_type = response.headers.get('content-type', '').lower()
                    if 'pdf' not in content_type and 'application/octet-stream' not in content_type:
                        raise Exception(f"Invalid content type: {content_type}")
                    
                    # Save file
                    with open(filepath, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    
                    # Verify the downloaded PDF
                    is_valid, verification_msg = self.verify_pdf_content(filepath, document_title)
                    document_info['file_size'] = os.path.getsize(filepath)
                    
                    if not is_valid:
                        os.remove(filepath)
                        error_msg = f"Downloaded invalid PDF: {verification_msg}"
                        self.log_failed_download(document_info, error_msg, {'step': 'verify_pdf'})
                        return False
                    
                    print(f"   ✅ Downloaded: {filename} - {verification_msg}")
                    self.save_progress(document_url)
                    return True
                    
                except Exception as e:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                    print(f"   ⚠️ Direct download failed: {e}")
                    # Fall back to clicking download button
            
            # Click download button/link
            try:
                self.driver.execute_script("arguments[0].click();", download_element)
                print(f"   ⏳ Waiting for download to complete...")
                
                # Wait for file to appear and be fully downloaded
                max_wait_time = 60  # 60 seconds timeout
                start_time = time.time()
                
                while time.time() - start_time < max_wait_time:
                    # Check if file exists and is not being downloaded
                    if os.path.exists(filepath):
                        # Check if download is complete (no .crdownload files)
                        temp_files = [f for f in os.listdir(self.download_folder) 
                                    if f.endswith('.crdownload') and safe_filename in f]
                        
                        if not temp_files:
                            # Verify the downloaded PDF
                            is_valid, verification_msg = self.verify_pdf_content(filepath, document_title)
                            
                            if is_valid:
                                print(f"   ✅ Downloaded: {filename} - {verification_msg}")
                                self.save_progress(document_url)
                                return True
                            else:
                                # Invalid PDF - remove and log error
                                os.remove(filepath)
                                error_msg = f"Downloaded invalid PDF: {verification_msg}"
                                self.log_failed_download(document_info, error_msg, {'step': 'verify_pdf_click'})
                                return False
                    
                    time.sleep(1)
                
                # Timeout - check if any file was downloaded
                downloaded_files = [f for f in os.listdir(self.download_folder) 
                                  if safe_filename in f and f.endswith('.pdf')]
                
                if downloaded_files:
                    # Rename to expected filename
                    actual_file = downloaded_files[0]
                    actual_path = os.path.join(self.download_folder, actual_file)
                    os.rename(actual_path, filepath)
                    
                    file_size = os.path.getsize(filepath)
                    print(f"   ✅ Downloaded: {filename} ({file_size:,} bytes)")
                    self.save_progress(document_url)
                    return True
                else:
                    error_msg = "Download timeout - no file appeared"
                    self.log_failed_download(document_info, error_msg, {'step': 'download_timeout'})
                    return False
                    
            except Exception as e:
                error_msg = f"Download click failed: {str(e)}"
                self.log_failed_download(document_info, error_msg, {'step': 'click_download'})
                return False
                
        except Exception as e:
            error_msg = f"Document processing failed: {str(e)}"
            self.log_failed_download(document_info, error_msg, {'step': 'general_error'})
            return False
    
    def process_all_documents(self, df):
        """Process all documents in the DataFrame"""
        
        if not self.setup_browser():
            print("❌ Failed to setup browser")
            return
        
        # Don't login upfront - login on demand when accessing documents
        
        total_docs = len(df)
        successful_downloads = 0
        failed_downloads = 0
        skipped_downloads = 0
        
        print(f"\n🚀 STARTING BATCH DOWNLOAD")
        print(f"📊 Total documents: {total_docs}")
        print(f"📁 Download folder: {self.download_folder}")
        print("="*80)
        
        try:
            for index, row in df.iterrows():
                document_title = row['title']
                document_url = row['url']
                
                # Show batch info if available
                if 'batch_number' in row:
                    batch_info = f" (Batch {row['batch_number']}/{row.get('total_batches', '?')})"
                else:
                    batch_info = ""
                
                print(f"\n📄 [{index + 1}/{total_docs}]{batch_info} Processing: {document_title[:60]}...")
                
                try:
                    success = self.download_document(document_url, document_title, index + 1, total_docs)
                    
                    if success:
                        successful_downloads += 1
                    elif document_url in self.downloaded_urls:
                        skipped_downloads += 1
                    else:
                        failed_downloads += 1
                    
                    # Show progress summary every 10 documents
                    if (index + 1) % 10 == 0:
                        print(f"\n📊 Progress: {index + 1}/{total_docs} | ✅ {successful_downloads} | ❌ {failed_downloads} | ⏭️ {skipped_downloads}")
                    
                    # Small delay between downloads
                    time.sleep(2)
                    
                except KeyboardInterrupt:
                    print(f"\n⏸️ Download interrupted by user at document {index + 1}")
                    break
                except Exception as e:
                    print(f"❌ Unexpected error processing document {index + 1}: {e}")
                    failed_downloads += 1
                    continue
            
        except Exception as e:
            print(f"❌ Critical error during batch processing: {e}")
        finally:
            # Cleanup browser
            if self.driver:
                self.driver.quit()
        
        # Final summary
        print(f"\n🎯 BATCH DOWNLOAD COMPLETE")
        print("="*50)
        print(f"📊 Total documents: {total_docs}")
        print(f"✅ Successfully downloaded: {successful_downloads}")
        print(f"❌ Failed downloads: {failed_downloads}")
        print(f"⏭️ Skipped (already downloaded): {skipped_downloads}")
        print(f"📁 Files saved to: {self.download_folder}")
        
        if self.failed_downloads:
            print(f"\n⚠️ {len(self.failed_downloads)} failures logged to:")
            print(f"   JSON: {self.error_log_file}")
            print(f"   Excel: {self.excel_error_log_file}")
        
        if failed_downloads > 0:
            print(f"\n💡 TIP: Use 'python batch_crawler.py [excel_file] retry-failed' to retry failures")
    
    def show_failed_downloads(self):
        """Display all failed downloads with details"""
        if not self.failed_downloads:
            print("✅ No failed downloads recorded!")
            return
        
        print(f"\n🚨 FAILED DOWNLOADS REPORT")
        print("="*60)
        print(f"📊 Total failures: {len(self.failed_downloads)}")
        
        # Group by error type
        error_types = {}
        for entry in self.failed_downloads:
            error_type = entry.get('error_type', 'UNKNOWN_ERROR')
            if error_type not in error_types:
                error_types[error_type] = []
            error_types[error_type].append(entry)
        
        print(f"\n📊 ERROR SUMMARY:")
        for error_type, entries in error_types.items():
            print(f"   {error_type}: {len(entries)} failures")
        
        print(f"\n📄 DETAILED FAILURES:")
        for i, entry in enumerate(self.failed_downloads, 1):
            print(f"\n{i:3d}. {entry['title'][:60]}...")
            print(f"     URL: {entry['url']}")
            print(f"     PDF URL: {entry.get('pdf_url', 'Not found')}")
            print(f"     Error Type: {entry.get('error_type', 'UNKNOWN')}")
            print(f"     Error: {entry['error']}")
            print(f"     Retry Count: {entry['retry_count']}")
            print(f"     Last Attempt: {entry['timestamp']}")
            
            # Show additional debug info if available
            additional_fields = ['content_type', 'status_code', 'file_size', 'step']
            for field in additional_fields:
                if field in entry:
                    print(f"     {field.title()}: {entry[field]}")
            
            print("-" * 60)
        
        print(f"\n💡 TIP: Use 'python batch_crawler.py [file] retry-failed' to retry all failures")
    
    def get_error_statistics(self):
        """Get statistics about failed downloads"""
        if not self.failed_downloads:
            return {}
        
        stats = {
            'total_failures': len(self.failed_downloads),
            'error_types': {},
            'retry_counts': {},
            'most_recent_failure': None,
            'oldest_failure': None
        }
        
        timestamps = []
        for entry in self.failed_downloads:
            # Count error types
            error_type = entry.get('error_type', 'UNKNOWN_ERROR')
            stats['error_types'][error_type] = stats['error_types'].get(error_type, 0) + 1
            
            # Count retry attempts
            retry_count = entry.get('retry_count', 0)
            stats['retry_counts'][retry_count] = stats['retry_counts'].get(retry_count, 0) + 1
            
            # Track timestamps
            timestamps.append(entry['timestamp'])
        
        if timestamps:
            stats['most_recent_failure'] = max(timestamps)
            stats['oldest_failure'] = min(timestamps)
        
        return stats
    
    def save_error_report(self, filename=None):
        """Save detailed error report to file"""
        if not self.failed_downloads:
            print("No errors to report!")
            return
        
        if filename is None:
            file_base = os.path.splitext(os.path.basename(self.excel_file))[0]
            filename = f"error_report_{file_base}.txt"
        
        stats = self.get_error_statistics()
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("🚨 BATCH DOWNLOAD ERROR REPORT\n")
            f.write("=" * 50 + "\n\n")
            
            f.write(f"📊 SUMMARY:\n")
            f.write(f"Batch File: {os.path.basename(self.excel_file)}\n")
            f.write(f"Total Failures: {stats['total_failures']}\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write(f"🔍 ERROR TYPE BREAKDOWN:\n")
            for error_type, count in stats['error_types'].items():
                percentage = (count / stats['total_failures']) * 100
                f.write(f"  {error_type}: {count} ({percentage:.1f}%)\n")
            f.write("\n")
            
            f.write(f"🔄 RETRY STATISTICS:\n")
            for retry_count, count in stats['retry_counts'].items():
                f.write(f"  {retry_count} retries: {count} documents\n")
            f.write("\n")
            
            f.write(f"📅 TIME RANGE:\n")
            if stats['oldest_failure'] and stats['most_recent_failure']:
                f.write(f"  First failure: {stats['oldest_failure']}\n")
                f.write(f"  Last failure: {stats['most_recent_failure']}\n\n")
            
            f.write(f"📄 DETAILED FAILURES:\n")
            f.write("-" * 50 + "\n")
            
            for i, entry in enumerate(self.failed_downloads, 1):
                f.write(f"\n{i:3d}. {entry['title']}\n")
                f.write(f"     URL: {entry['url']}\n")
                f.write(f"     PDF URL: {entry.get('pdf_url', 'Not found')}\n")
                f.write(f"     Error Type: {entry.get('error_type', 'UNKNOWN')}\n")
                f.write(f"     Error Message: {entry['error']}\n")
                f.write(f"     Retry Count: {entry['retry_count']}\n")
                f.write(f"     Timestamp: {entry['timestamp']}\n")
                
                # Include additional debug information
                additional_fields = ['content_type', 'status_code', 'file_size', 'step']
                for field in additional_fields:
                    if field in entry:
                        f.write(f"     {field.title()}: {entry[field]}\n")
                
                f.write("\n" + "-" * 40 + "\n")
        
        print(f"📄 Error report saved to: {filename}")
    
    def retry_failed_downloads(self):
        """Retry all previously failed downloads"""
        if not self.failed_downloads:
            print("✅ No failed downloads to retry!")
            return
        
        print(f"🔄 RETRYING {len(self.failed_downloads)} FAILED DOWNLOADS")
        print("="*80)
        
        retry_list = []
        for entry in self.failed_downloads:
            retry_list.append({
                'title': entry['title'],
                'url': entry['url']
            })
        
        # Convert to DataFrame and process
        retry_df = pd.DataFrame(retry_list)
        
        # Clear previous failures to start fresh
        self.failed_downloads = []
        self.failed_urls = set()
        
        # Process retry list
        self.process_all_documents(retry_df)

def choose_excel_file():
    """Let user choose Excel file from batch_files/ directory"""
    
    batch_dir = "batch_files"
    
    # Check if batch_files directory exists
    if not os.path.exists(batch_dir):
        print(f"❌ {batch_dir}/ directory not found!")
        print("💡 Run split_urls_to_excel.py first to create batch files")
        return None
    
    # Get list of Excel files
    excel_files = []
    for file in os.listdir(batch_dir):
        if file.endswith('.xlsx') and not file.startswith('~'):  # Exclude temp files
            excel_files.append(file)
    
    if not excel_files:
        print(f"❌ No Excel files found in {batch_dir}/")
        print("💡 Run split_urls_to_excel.py first to create batch files")
        return None
    
    # Sort files for better display
    excel_files.sort()
    
    print(f"📁 Available batch files in {batch_dir}/:")
    print("="*60)
    
    # Show files with details
    for i, file in enumerate(excel_files, 1):
        filepath = os.path.join(batch_dir, file)
        try:
            df = pd.read_excel(filepath)
            url_count = len(df)
            
            # Try to get batch info
            if 'batch_number' in df.columns and not df.empty:
                batch_num = df.iloc[0]['batch_number']
                total_batches = df.iloc[0].get('total_batches', '?')
                batch_info = f" (Batch {batch_num}/{total_batches})"
            else:
                batch_info = ""
            
            print(f"   {i:2d}. {file}{batch_info}")
            print(f"       {url_count:,} URLs")
            
        except Exception as e:
            print(f"   {i:2d}. {file} (could not read: {e})")
    
    # Let user choose
    while True:
        try:
            choice = input(f"\nChoose file (1-{len(excel_files)}) or 'q' to quit: ").strip()
            
            if choice.lower() == 'q':
                return None
            
            if not choice:
                print("❌ Please enter a number")
                continue
                
            file_idx = int(choice) - 1
            if 0 <= file_idx < len(excel_files):
                chosen_file = os.path.join(batch_dir, excel_files[file_idx])
                print(f"✅ Selected: {excel_files[file_idx]}")
                return chosen_file
            else:
                print(f"❌ Please enter a number between 1 and {len(excel_files)}")
        except ValueError:
            print("❌ Please enter a valid number")

def get_credentials():
    """Get username and password from user"""
    print("\n🔑 Enter your luatvietnam.vn credentials:")
    
    username = input("Username: ").strip()
    if not username:
        print("❌ Username cannot be empty")
        return None, None
    
    password = getpass.getpass("Password: ")
    if not password:
        print("❌ Password cannot be empty")
        return None, None
    
    return username, password

def main():
    """Main function with interactive batch crawler"""
    
    print("🚀 LUATVIETNAM BATCH CRAWLER")
    print("=" * 50)
    print("Modified version of bulk_download_all.py with batch support")
    print("Features:")
    print("- Choose Excel file from batch_files/")
    print("- Input credentials interactively")
    print("- Batch-specific progress tracking")
    print("=" * 50)
    
    # Check command line arguments for special commands
    if len(sys.argv) > 2:
        command = sys.argv[2].lower()
        
        if command in ["show-failed", "retry-failed", "save-report", "stats"]:
            excel_file = sys.argv[1]
            if not os.path.exists(excel_file):
                print(f"❌ Excel file not found: {excel_file}")
                return
            
            # Get credentials for retry operations
            username, password = get_credentials()
            if not username or not password:
                print("❌ Invalid credentials")
                return
            
            # Initialize crawler for commands
            crawler = LuatVietnamBatchCrawler(username, password, excel_file)
            
            if command == "show-failed":
                crawler.show_failed_downloads()
                return
            elif command == "retry-failed":
                crawler.retry_failed_downloads()
                return
            elif command == "save-report":
                crawler.save_error_report()
                return
            elif command == "stats":
                stats = crawler.get_error_statistics()
                if stats:
                    print(f"\n📊 ERROR STATISTICS:")
                    print(f"Total Failures: {stats['total_failures']}")
                    print(f"Error Types: {len(stats['error_types'])}")
                    print(f"Most Common: {max(stats['error_types'], key=stats['error_types'].get) if stats['error_types'] else 'None'}")
                    print(f"Time Range: {stats.get('oldest_failure', 'N/A')} to {stats.get('most_recent_failure', 'N/A')}")
                else:
                    print("✅ No error statistics available - no failures recorded!")
                return
    
    # Interactive mode
    print("\n📂 Step 1: Choose Excel file")
    excel_file = choose_excel_file()
    if not excel_file:
        print("❌ No file selected, exiting...")
        return
    
    # Get credentials
    print("\n🔑 Step 2: Enter credentials")
    username, password = get_credentials()
    if not username or not password:
        print("❌ Invalid credentials, exiting...")
        return
    
    # Load and validate Excel file
    try:
        df = pd.read_excel(excel_file)
        print(f"\n✅ Loaded {len(df)} documents from {os.path.basename(excel_file)}")
        
        # Show batch info if available
        if 'batch_number' in df.columns and not df.empty:
            batch_num = df.iloc[0]['batch_number']
            total_batches = df.iloc[0].get('total_batches', '?')
            start_idx = df.iloc[0].get('batch_start_index', '?')
            end_idx = df.iloc[0].get('batch_end_index', '?')
            print(f"📊 Batch {batch_num}/{total_batches} (indices {start_idx}-{end_idx})")
        
    except Exception as e:
        print(f"❌ Could not load Excel file: {e}")
        return
    
    # Initialize crawler
    print(f"\n🚀 Step 3: Initialize crawler")
    crawler = LuatVietnamBatchCrawler(username, password, excel_file)
    
    # Start download
    print(f"\n🎯 Step 4: Start batch download")
    print("This may take some time depending on the batch size")
    print("Press Ctrl+C to interrupt and resume later")
    
    try:
        crawler.process_all_documents(df)
    except KeyboardInterrupt:
        print("\n⏸️ Download interrupted by user")
        print("💡 You can resume later by running this script again with the same Excel file")

if __name__ == "__main__":
    main()
