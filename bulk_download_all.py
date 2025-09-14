#!/usr/bin/env python3
"""
Bulk PDF Downloader - Download all 109 traffic law documents
Run this to download all documents from the crawled list
"""

import time
import os
import re
import sys
import requests
import pandas as pd
import json
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

class LuatVietnamBulkDownloader:
    def __init__(self, username, password, download_folder="all_traffic_law_pdfs"):
        self.username = username
        self.password = password
        self.download_folder = download_folder
        
        # Ensure download folder exists
        if not os.path.exists(download_folder):
            os.makedirs(download_folder)
        
        # Track progress
        self.progress_file = "download_progress.txt"
        self.downloaded_urls = self.load_progress()
        
        # Error logging
        self.error_log_file = "failed_downloads.json"
        self.failed_downloads = self.load_failed_downloads()
        
        # Create fast lookup set for failed URLs (optimization)
        self.failed_urls = {failure['url'] for failure in self.failed_downloads}
        
        # Excel error logging
        self.excel_error_log_file = "failed_downloads_log.xlsx"
        self.failed_downloads_df = self.load_failed_downloads_excel()
        
        # Initialize browser once for all downloads
        self.driver = None
        self.is_logged_in = False
        
        print(f"📁 Download folder: {download_folder}")
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
            df = pd.read_excel("luatvietnam_smart_backup_20250912_231952.xlsx")
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
                'total': document_info.get('total', 0),
                'file_type': document_info.get('file_type', 'unknown')
            }
            
            # Add additional info if provided
            if additional_info:
                for key, value in additional_info.items():
                    if key not in new_row:  # Don't overwrite existing keys
                        new_row[key] = str(value)
            
            # Check if this is an existing failure (update retry count)
            existing_mask = self.failed_downloads_df['url'] == document_info.get('url', 'Unknown')
            if existing_mask.any():
                # Update existing entry
                existing_index = self.failed_downloads_df[existing_mask].index[0]
                # Increment retry count if it exists, otherwise set to 1
                current_retry = self.failed_downloads_df.loc[existing_index, 'retry_count'] if 'retry_count' in self.failed_downloads_df.columns else 0
                new_row['retry_count'] = current_retry + 1
                # Update the row
                for key, value in new_row.items():
                    self.failed_downloads_df.loc[existing_index, key] = value
            else:
                # Add new entry
                new_row['retry_count'] = 1
                # Convert to DataFrame and append
                new_df = pd.DataFrame([new_row])
                self.failed_downloads_df = pd.concat([self.failed_downloads_df, new_df], ignore_index=True)
            
            # Save to Excel file
            self.failed_downloads_df.to_excel(self.excel_error_log_file, index=False)
            
        except Exception as e:
            print(f"⚠️ Could not save Excel error log: {e}")
    
    def save_excel_summary(self, success_count, failed_count, skipped_count, total_size):
        """Save final summary to Excel error log"""
        try:
            # Add summary information to the Excel file
            if not self.failed_downloads_df.empty:
                # Count error types
                error_summary = self.failed_downloads_df['error_type'].value_counts().to_dict()
                
                # Create summary row
                summary_row = {
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'title': '=== DOWNLOAD SESSION SUMMARY ===',
                    'url': f'Success: {success_count} | Failed: {failed_count} | Skipped: {skipped_count}',
                    'error_message': f'Total size: {total_size / 1024 / 1024:.1f} MB',
                    'error_type': 'SUMMARY',
                    'file_size_attempted': total_size,
                    'retry_count': 0
                }
                
                # Add error breakdown
                for error_type, count in error_summary.items():
                    summary_row[f'errors_{error_type.lower()}'] = count
                
                # Add summary row
                summary_df = pd.DataFrame([summary_row])
                self.failed_downloads_df = pd.concat([self.failed_downloads_df, summary_df], ignore_index=True)
                
                # Save updated Excel file
                self.failed_downloads_df.to_excel(self.excel_error_log_file, index=False)
                
                print(f"📊 Excel error log saved: {self.excel_error_log_file}")
                print(f"   Total failed entries: {len(self.failed_downloads_df) - 1}")  # -1 for summary row
                
        except Exception as e:
            print(f"⚠️ Could not save Excel summary: {e}")
    
    def _categorize_error(self, error_message):
        """Categorize error type for easier analysis"""
        error_lower = error_message.lower()
        
        if '404' in error_lower or 'page not found' in error_lower or 'not found' in error_lower:
            return 'PAGE_NOT_FOUND'
        elif 'article' in error_lower or 'guide page' in error_lower or 'reference page' in error_lower:
            return 'ARTICLE_PAGE'
        elif 'no downloadable content' in error_lower:
            return 'NO_CONTENT'
        elif 'login' in error_lower or 'authentication' in error_lower:
            return 'AUTHENTICATION_ERROR'
        elif 'pdf url' in error_lower or 'extract' in error_lower:
            return 'PDF_URL_EXTRACTION_ERROR'
        elif 'download' in error_lower or 'request' in error_lower or 'connection' in error_lower:
            return 'NETWORK_ERROR'
        elif 'timeout' in error_lower:
            return 'TIMEOUT_ERROR'
        elif 'file size' in error_lower or 'size 0' in error_lower:
            return 'EMPTY_FILE_ERROR'
        elif 'permission' in error_lower or 'access' in error_lower:
            return 'ACCESS_ERROR'
        else:
            return 'UNKNOWN_ERROR'
    
    def setup_driver(self):
        """Setup Chrome driver with proper configuration"""
        chrome_options = Options()
        
        # Disable automation detection
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Additional stability options
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--allow-running-insecure-content")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-plugins")
        chrome_options.add_argument("--disable-popup-blocking")
        chrome_options.add_argument("--disable-default-apps")
        chrome_options.add_argument("--disable-sync")
        chrome_options.add_argument("--disable-translate")
        chrome_options.add_argument("--mute-audio")
        
        # Set user agent
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Set download preferences
        prefs = {
            "download.default_directory": self.download_folder,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
            "profile.default_content_settings.popups": 0,
            "profile.default_content_setting_values.notifications": 2,
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Set timeouts for better reliability
        driver.set_page_load_timeout(60)
        driver.implicitly_wait(10)
        
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        return driver
    
    def initialize_browser_and_login(self):
        """Initialize browser once and perform login"""
        if self.driver is not None:
            return  # Already initialized
            
        print("🚀 Initializing browser and logging in...")
        self.driver = self.setup_driver()
        self.wait = WebDriverWait(self.driver, 20)
        
        # Navigate to login page to establish session
        try:
            self.driver.get("https://luatvietnam.vn")
            time.sleep(3)
            self.is_logged_in = False  # Will be set to True after successful login
            print("✅ Browser initialized and ready")
        except Exception as e:
            print(f"⚠️ Browser initialization warning: {e}")
            self.is_logged_in = False
    
    def verify_login_status(self):
        """Check if we're actually logged in by looking for user-specific elements"""
        if not self.driver:
            return False
            
        try:
            # Check for elements that appear when logged in
            # These are common indicators of being logged in on luatvietnam.vn
            login_indicators = [
                "//a[contains(@href, '/tai-khoan/')]",  # Account link
                "//a[contains(text(), 'Tài khoản')]",   # Account text
                "//div[contains(@class, 'user-info')]", # User info div
                "//span[contains(@class, 'username')]", # Username span
            ]
            
            for indicator in login_indicators:
                try:
                    element = self.driver.find_element(By.XPATH, indicator)
                    if element.is_displayed():
                        return True
                except:
                    continue
                    
            # If no login indicators found, we're probably not logged in
            return False
            
        except Exception:
            return False
    
    def force_login_if_needed(self):
        """Force a fresh login if we're not properly logged in"""
        if not self.verify_login_status():
            print("   🔄 Session lost, forcing fresh login...")
            self.is_logged_in = False
            
            # Navigate to a page that requires login to trigger login popup
            try:
                self.driver.get("https://luatvietnam.vn/tai-khoan")
                time.sleep(3)  # Increased wait time
                
                # Look for login popup triggers
                login_triggers = [
                    "//a[contains(@class, 'lawsVnLogin')]",
                    "//span[contains(@class, 'lawsVnLogin')]",
                    "//a[contains(text(), 'Đăng nhập')]",
                    "//button[contains(text(), 'Đăng nhập')]"
                ]
                
                for trigger_xpath in login_triggers:
                    try:
                        # Wait for element to be clickable
                        trigger_element = WebDriverWait(self.driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, trigger_xpath))
                        )
                        
                        # Scroll into view and wait
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", trigger_element)
                        time.sleep(1)
                        
                        # Use JavaScript click for reliability
                        self.driver.execute_script("arguments[0].click();", trigger_element)
                        print(f"   🔑 Login trigger activated")
                        time.sleep(3)  # Wait for form to load
                        
                        # Enter credentials with better waits
                        username_field = WebDriverWait(self.driver, 15).until(
                            EC.element_to_be_clickable((By.ID, "customer_name"))
                        )
                        
                        # Clear and enter username with JS to ensure reliability
                        self.driver.execute_script("arguments[0].value = '';", username_field)
                        time.sleep(0.5)
                        username_field.send_keys(self.username)
                        
                        # Find password field
                        password_field = WebDriverWait(self.driver, 10).until(
                            EC.element_to_be_clickable((By.ID, "password_login"))
                        )
                        
                        # Clear and enter password
                        self.driver.execute_script("arguments[0].value = '';", password_field)
                        time.sleep(0.5)
                        password_field.send_keys(self.password)
                        
                        # Submit with Enter key
                        password_field.send_keys('\n')
                        
                        print(f"   ⏳ Completing login...")
                        time.sleep(5)
                        
                        # Verify login worked
                        if self.verify_login_status():
                            self.is_logged_in = True
                            print(f"   ✅ Fresh login successful")
                            return True
                        break
                        
                    except Exception as e:
                        print(f"   ⚠️ Login trigger {trigger_xpath} failed: {str(e)}")
                        continue
                        
            except Exception as e:
                print(f"   ❌ Force login failed: {e}")
                
        return self.is_logged_in
    
    def cleanup_browser(self):
        """Clean up browser session"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None
            self.is_logged_in = False
    
    def login_and_extract_pdf_url(self, document_url, document_title="Unknown"):
        """Login and extract the actual document URL (PDF or Word) from page source"""
        
        # Ensure browser is initialized
        if self.driver is None:
            self.initialize_browser_and_login()
        
    def login_and_extract_pdf_url(self, document_url, document_title="Unknown"):
        """Login and extract the actual document URL (PDF or Word) from page source"""
        
        # Ensure browser is initialized
        if self.driver is None:
            self.initialize_browser_and_login()
        
        try:
            # Navigate to document page using existing session
            print(f"   🌐 Loading page...")
            self.driver.get(document_url)
            time.sleep(1)  # Reduced from 3 to 1 second
            
            # Check for 404 or error pages first
            page_title = self.driver.title.lower()
            page_source = self.driver.page_source.lower()
            
            if ("404" in page_title or "không tìm thấy" in page_title or 
                "page not found" in page_title or "not found" in page_title or
                "không tìm thấy trang" in page_source or 
                "url không tồn tại" in page_source):
                print(f"   ❌ Page not found (404 error)")
                return None, "Page not found (404 error)", None
            
            # First, try to find document URLs directly from main content
            found_url, file_type = self.extract_document_url_from_source(self.driver.page_source)
            
            # If we found a document URL directly, we're done
            if found_url:
                print(f"   ✅ Document URL found (already logged in)")
                return found_url, None, file_type
            
            # Quick check for article pages to skip expensive tab searches
            if ("-article.html" in document_url.lower() or 
                "chính sách mới" in document_title.lower() or
                "hướng dẫn" in document_title.lower() or
                "chính sách" in document_title.lower() or
                "vb liên quan" in document_title.lower() or
                "thuộc tính" in document_title.lower() or
                "vb được hợp nhất" in document_title.lower()):
                print("   ℹ️ Article/guide/reference page - no downloadable content expected")
                return None, "Article/guide/reference page - no downloadable files", None
            
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
                    time.sleep(1)  # Reduced from 2 to 1 second
                    break
                except:
                    continue
            
            if login_triggered:
                # Handle login popup - use more robust method
                try:
                    print(f"   📝 Entering credentials...")
                    
                    # Wait for login fields and use JavaScript for reliability
                    username_field = WebDriverWait(self.driver, 5).until(  # Reduced from 10 to 5 seconds
                        EC.presence_of_element_located((By.ID, "customer_name"))
                    )
                    password_field = self.driver.find_element(By.ID, "password_login")
                    
                    # Use JavaScript to set values for better reliability
                    self.driver.execute_script("arguments[0].value = arguments[1];", username_field, self.username)
                    self.driver.execute_script("arguments[0].value = arguments[1];", password_field, self.password)
                    
                    # Submit with JavaScript or Enter key
                    try:
                        self.driver.execute_script("arguments[0].form.submit();", password_field)
                    except:
                        password_field.send_keys('\n')
                    
                    print(f"   ⏳ Waiting for login...")
                    time.sleep(2)  # Reduced from 5 to 2 seconds
                    
                    # Check if we got a JSON login success response
                    try:
                        current_url = self.driver.current_url
                        page_source = self.driver.page_source
                        
                        # Check for JSON login success response
                        if ('LoginSuccess' in page_source and 'ReturnUrl' in page_source):
                            print(f"   ✅ Login successful - detected JSON response")
                            # Extract ReturnUrl from JSON response if available
                            import json
                            try:
                                # Try to parse the JSON response
                                json_start = page_source.find('{"Completed"')
                                if json_start >= 0:
                                    json_end = page_source.find('}', json_start) + 1
                                    json_str = page_source[json_start:json_end]
                                    login_response = json.loads(json_str)
                                    if login_response.get('ReturnUrl'):
                                        return_url = login_response['ReturnUrl']
                                        if not return_url.startswith('http'):
                                            return_url = 'https://luatvietnam.vn' + return_url
                                        print(f"   🔄 Following return URL: {return_url[:50]}...")
                                        self.driver.get(return_url)
                                        time.sleep(2)
                            except:
                                pass
                        
                        # Check if we're already on the target page after login
                        elif document_url in current_url or current_url.endswith('.html'):
                            print(f"   ✅ Already on document page after login")
                        else:
                            print(f"   🔄 Navigating back to document page...")
                            self.driver.get(document_url)
                            time.sleep(1)
                            
                    except Exception as e:
                        print(f"   ⚠️ Post-login navigation issue: {str(e)[:50]}")
                    
                    # Update login status
                    self.is_logged_in = True
                    
                except Exception as e:
                    # Don't fail completely if login popup fails - many pages work without it
                    print(f"   ⚠️ Login popup failed, trying to access content anyway: {str(e)[:100]}")
            
            # After potential login, try to find document URLs again
            found_url, file_type = self.extract_document_url_from_source(self.driver.page_source)
            if found_url:
                print(f"   ✅ Document URL found after login")
                return found_url, None, file_type
            
            # Now try to find and click "Tải về" (Download) tab if no URLs found yet
            print(f"   📁 Looking for Download tab...")
            download_tab_found = False
            download_tab_selectors = [
                "//a[contains(text(), 'Tải về')]",  # Download tab
                "//span[contains(text(), 'Tải về')]",
                "//div[contains(text(), 'Tải về')]", 
                "//li[contains(text(), 'Tải về')]",
                "//button[contains(text(), 'Tải về')]",
                # Also try with different text patterns
                "//a[contains(@title, 'Tải về')]",
                "//a[contains(@href, 'tai')]",
                "//*[contains(@class, 'tab') and contains(text(), 'Tải')]",
                "//*[contains(@class, 'nav') and contains(text(), 'Tải')]"
            ]
            
            for tab_selector in download_tab_selectors:
                try:
                    download_tab = self.driver.find_element(By.XPATH, tab_selector)
                    if download_tab.is_displayed():
                        # Use JavaScript click for reliability
                        self.driver.execute_script("arguments[0].click();", download_tab)
                        print(f"   📁 Clicked on Download tab")
                        time.sleep(1)  # Reduced from 3 to 1 second
                        download_tab_found = True
                        
                        # Try to extract URLs from the new tab content
                        found_url, file_type = self.extract_document_url_from_source(self.driver.page_source)
                        if found_url:
                            print(f"   ✅ Document URL found in Download tab")
                            return found_url, None, file_type
                        break
                except:
                    continue
            
            if not download_tab_found:
                print(f"   ⚠️ No Download tab found")
            
            # Final attempt: check if this might be an article page or page without downloadable content
            if not login_triggered and not download_tab_found:
                if ("-article.html" in document_url.lower() or 
                    "hướng dẫn" in document_title.lower() or
                    "chính sách" in document_title.lower()):
                    print("   ℹ️ Article/guide page - no downloadable content expected")
                    return None, "Article/guide page - no downloadable files", None
                else:
                    print("   ⚠️ No login trigger or download tab found - page may not have downloadable content")
                    return None, "No downloadable content found on page", None
            
            # After all attempts, extract document URL from updated page source
            print(f"   🔍 Final search for document URL...")
            page_source = self.driver.page_source
            found_url, file_type = self.extract_document_url_from_source(page_source)
            
            # Debug output for failed searches
            if not found_url:
                print(f"   ⚠️ No URLs found matching any pattern")
                error_msg = "Document URL not found in page source (no PDF or Word files)"
                print(f"   ❌ {error_msg}")
                return None, error_msg, None
            
            return found_url, None, file_type
            
        except Exception as e:
            error_msg = f"Error processing page: {str(e)}"
            print(f"   ❌ {error_msg}")
            return None, error_msg, None
            
        finally:
            # Don't quit the driver - we're reusing it
            pass
    
    def extract_document_url_from_source(self, page_source):
        """Extract document URL from page source"""
        # More specific patterns to find actual document URLs (avoid account/login PDFs)
        patterns = [
            # PDF patterns (priority) - look for actual document download links
            r'https://static\.luatvietnam\.vn/tai-file-[^"\']*-\d+\.pdf',  # With ID suffix
            r'https://static\.luatvietnam\.vn/tai-file-vanban-[^"\']*\.pdf',  # Document specific
            r'https://static\.luatvietnam\.vn/tai-file-[^"\']*\.pdf(?!\?|\#)',  # Clean PDF URLs
            
            # ZIP patterns (for compressed documents)
            r'https://static\.luatvietnam\.vn/tai-file-[^"\']*-\d+\.zip',  # With ID suffix
            r'https://static\.luatvietnam\.vn/tai-file-vanban-[^"\']*\.zip',  # Document specific
            r'https://static\.luatvietnam\.vn/tai-file-[^"\']*\.zip(?!\?|\#)',  # Clean ZIP URLs
            
            # Word document patterns (fallback)  
            r'https://static\.luatvietnam\.vn/tai-file-[^"\']*-\d+\.docx?',  # With ID suffix
            r'https://static\.luatvietnam\.vn/tai-file-vanban-[^"\']*\.docx?',  # Document specific
            r'https://static\.luatvietnam\.vn/tai-file-[^"\']*\.docx?(?!\?|\#)',  # Clean Word URLs
            
            # Broader patterns as last resort
            r'https://static\.luatvietnam\.vn/[^"\']*\.pdf',  # Any PDF URL
            r'https://static\.luatvietnam\.vn/[^"\']*\.zip',  # Any ZIP URL
            r'https://static\.luatvietnam\.vn/[^"\']*\.docx?',  # Any Word URL
        ]
        
        found_url = None
        file_type = None
        all_found_urls = []  # Debug: collect all found URLs
        
        for pattern in patterns:
            matches = re.findall(pattern, page_source)
            if matches:
                for match in matches:
                    document_url = match
                    
                    # Clean up URL if it's from href pattern
                    if document_url.startswith('"') or document_url.startswith("'"):
                        document_url = document_url.strip('"\'')
                    
                    all_found_urls.append(document_url)
                    
                    # Skip known account/login/generic PDFs (very specific patterns only)
                    skip_patterns = [
                        '/account/', '/login/', '/user/', '/profile/', '/tai-khoan/',
                        '/user-guide/', '/terms/', '/privacy/', '/contact/'
                    ]
                    
                    should_skip = False
                    for skip_pattern in skip_patterns:
                        if skip_pattern in document_url.lower():
                            should_skip = True
                            break
                    
                    if should_skip:
                        continue
                    
                    # Determine file type
                    if '.pdf' in document_url.lower():
                        found_url = document_url
                        file_type = 'pdf'
                        print(f"   ✅ Found PDF URL: {document_url}")
                        break
                    elif '.zip' in document_url.lower():
                        found_url = document_url  
                        file_type = 'zip'
                        print(f"   ✅ Found ZIP file URL: {document_url}")
                        break
                    elif '.doc' in document_url.lower():
                        found_url = document_url  
                        file_type = 'word'
                        print(f"   ✅ Found Word document URL: {document_url}")
                        break
                    elif '.rtf' in document_url.lower():
                        found_url = document_url  
                        file_type = 'rtf'
                        print(f"   ✅ Found RTF document URL: {document_url}")
                        break
                    elif 'tai-file' in document_url:
                        # For generic tai-file, we'll detect type from response
                        found_url = document_url
                        file_type = 'unknown'
                        print(f"   ✅ Found document URL (type to be determined): {document_url}")
                        break
            
            if found_url:
                break
        
        return found_url, file_type
    
    def download_document(self, document_url, filename, document_info, file_type='pdf'):
        """Download PDF directly using requests with enhanced error logging"""
        
        filepath = os.path.join(self.download_folder, filename)
        
        try:
            print(f"   📥 Downloading {file_type.upper() if file_type != 'unknown' else 'document'}...")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/pdf,application/x-pdf,application/zip,application/x-zip-compressed,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,*/*',
                'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Referer': 'https://luatvietnam.vn/'
            }
            
            response = requests.get(document_url, headers=headers, stream=True, timeout=60)
            response.raise_for_status()
            
            # Determine file extension based on actual content type, not URL
            content_type = response.headers.get('content-type', '').lower()
            
            # Remove any existing extension from filename first
            base_filename = filename
            for ext in ['.pdf', '.docx', '.doc', '.rtf', '.zip']:
                if base_filename.endswith(ext):
                    base_filename = base_filename[:-len(ext)]
                    break
            
            # Add correct extension - prioritize file_type for ZIP files
            if file_type == 'zip':
                # ZIP files detected from URL should always use .zip extension
                # regardless of content-type (server often sends wrong content-type)
                filename = base_filename + '.zip'
            elif 'application/pdf' in content_type:
                filename = base_filename + '.pdf'
            elif 'application/zip' in content_type or 'application/x-zip-compressed' in content_type:
                filename = base_filename + '.zip'
            elif 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' in content_type:
                filename = base_filename + '.docx'
            elif 'application/msword' in content_type:
                filename = base_filename + '.doc'
            elif 'application/rtf' in content_type or 'text/rtf' in content_type:
                # Save RTF content as .doc for easier handling
                filename = base_filename + '.doc'
            elif file_type == 'word':
                # Fallback to URL-based detection
                filename = base_filename + '.doc'
            elif file_type == 'pdf':
                # Fallback to URL-based detection
                filename = base_filename + '.pdf'
            else:
                # Default based on content type - prefer .doc for text content
                if 'text' in content_type or 'rtf' in content_type:
                    filename = base_filename + '.doc'
                else:
                    filename = base_filename + '.pdf'
            
            pdf_path = os.path.join(self.download_folder, filename)
            
            # Validate content type (allow PDF, Word, RTF, and other document types)
            valid_types = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 
                          'application/msword', 'application/rtf', 'text/rtf', 'application/octet-stream',
                          'text/plain', 'application/x-msdownload']  # Be more lenient for Vietnamese legal docs
            if not any(valid_type in content_type for valid_type in valid_types):
                error_msg = f"Invalid content type: {content_type} (expected document format)"
                print(f"   ❌ {error_msg}")
                self.log_failed_download(
                    {**document_info, 'document_url': document_url}, 
                    error_msg,
                    {'content_type': content_type, 'status_code': response.status_code}
                )
                return 0, error_msg
            
            # Download with progress tracking
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            
            with open(pdf_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
            
            # Verify file was created and has content
            if not os.path.exists(pdf_path):
                error_msg = "File was not created after download"
                print(f"   ❌ {error_msg}")
                self.log_failed_download(
                    {**document_info, 'document_url': document_url}, 
                    error_msg,
                    {'expected_size': total_size, 'downloaded_size': downloaded_size}
                )
                return 0, error_msg
            
            file_size = os.path.getsize(pdf_path)
            
            # Check if the downloaded file has wrong extension
            if filename.endswith('.doc'):
                try:
                    with open(pdf_path, 'rb') as f:
                        first_4_bytes = f.read(4)
                    
                    # Check for ZIP magic number (DOCX files are ZIP archives)
                    if (len(first_4_bytes) >= 4 and 
                        first_4_bytes[0] == 0x50 and first_4_bytes[1] == 0x4B and 
                        first_4_bytes[2] == 0x03 and first_4_bytes[3] == 0x04):
                        
                        # This is actually a DOCX file, rename it
                        docx_filename = filename.replace('.doc', '.docx')
                        docx_path = os.path.join(self.download_folder, docx_filename)
                        
                        os.rename(pdf_path, docx_path)
                        pdf_path = docx_path  # Update the path for further processing
                        filename = docx_filename  # Update filename for logging
                        print(f"   🔄 Corrected extension: .doc → .docx (detected ZIP/DOCX format)")
                        
                    # Check for PDF magic number (%PDF)
                    elif (len(first_4_bytes) >= 4 and 
                          first_4_bytes[0] == 0x25 and first_4_bytes[1] == 0x50 and 
                          first_4_bytes[2] == 0x44 and first_4_bytes[3] == 0x46):
                        
                        # This is actually a PDF file, rename it
                        pdf_filename = filename.replace('.doc', '.pdf')
                        corrected_pdf_path = os.path.join(self.download_folder, pdf_filename)
                        
                        os.rename(pdf_path, corrected_pdf_path)
                        pdf_path = corrected_pdf_path  # Update the path for further processing
                        filename = pdf_filename  # Update filename for logging
                        print(f"   🔄 Corrected extension: .doc → .pdf (detected PDF format)")
                        
                except Exception as e:
                    print(f"   ⚠️ Could not check file format: {e}")
            
            # Enhanced content validation
            try:
                with open(pdf_path, 'rb') as f:
                    first_bytes = f.read(512)  # Read more bytes for better detection
                
                # Check for HTML content (error pages)
                if b'<html' in first_bytes.lower() or b'<!doctype' in first_bytes.lower():
                    error_msg = "Downloaded file contains HTML content (likely error page)"
                    print(f"   ❌ {error_msg}")
                    os.remove(pdf_path)
                    self.log_failed_download(
                        {**document_info, 'document_url': document_url}, 
                        error_msg,
                        {'file_size': file_size, 'content_preview': first_bytes[:100].decode('utf-8', errors='ignore')}
                    )
                    return 0, error_msg
                
                # Check for valid file signatures
                valid_file = False
                if first_bytes.startswith(b'%PDF'):
                    valid_file = True  # PDF file
                elif first_bytes.startswith((b'PK\x03\x04', b'PK\x05\x06', b'PK\x07\x08')):
                    valid_file = True  # ZIP-based files (docx, etc.)
                elif b'\\rtf1' in first_bytes or first_bytes.startswith(b'{\\rtf'):
                    valid_file = True  # RTF file (will be saved as .doc)
                elif first_bytes.startswith((b'\xd0\xcf\x11\xe0', b'\x09\x08\x06\x00')):
                    valid_file = True  # MS Office files (.doc)
                elif len(first_bytes) > 0:
                    # For other files, be more lenient since Vietnamese legal docs come in various formats
                    try:
                        text_content = first_bytes.decode('utf-8', errors='ignore')
                        # Only reject if it's clearly HTML or error content
                        if ('<html' in text_content.lower() or 
                            '<body' in text_content.lower() or
                            'error' in text_content.lower() and 'http' in text_content.lower()):
                            valid_file = False  # Likely HTML/error page
                        else:
                            valid_file = True  # Accept as valid document
                    except:
                        valid_file = True  # Binary file, likely valid
                
                if not valid_file:
                    error_msg = "Downloaded file does not appear to be a valid document"
                    print(f"   ❌ {error_msg}")
                    os.remove(pdf_path)
                    self.log_failed_download(
                        {**document_info, 'document_url': document_url}, 
                        error_msg,
                        {'file_size': file_size, 'content_preview': first_bytes[:100].hex()}
                    )
                    return 0, error_msg
                    
            except Exception as e:
                print(f"   ⚠️ Could not validate file content: {e}")
            
            # Check if file is too small (likely an error page)
            if file_size < 1024:  # Less than 1KB is suspicious for a document
                error_msg = f"Downloaded file too small: {file_size} bytes (likely error page)"
                print(f"   ❌ {error_msg}")
                
                self.log_failed_download(
                    {**document_info, 'document_url': document_url}, 
                    error_msg,
                    {'file_size': file_size, 'expected_size': total_size}
                )
                
                # Remove the invalid file
                try:
                    os.remove(pdf_path)
                except:
                    pass
                    
                return 0, error_msg
            
            print(f"   ✅ Download successful ({file_size:,} bytes)")
            return file_size, None
            
        except requests.exceptions.Timeout:
            error_msg = "Download timeout (60 seconds exceeded)"
            print(f"   ❌ {error_msg}")
            self.log_failed_download(
                {**document_info, 'document_url': document_url}, 
                error_msg,
                {'timeout_duration': 60}
            )
            return 0, error_msg
            
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Connection error: {str(e)}"
            print(f"   ❌ {error_msg}")
            self.log_failed_download(
                {**document_info, 'document_url': document_url}, 
                error_msg,
                {'error_type': 'ConnectionError'}
            )
            return 0, error_msg
            
        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP error {response.status_code}: {str(e)}"
            print(f"   ❌ {error_msg}")
            self.log_failed_download(
                {**document_info, 'document_url': document_url}, 
                error_msg,
                {'status_code': response.status_code, 'error_type': 'HTTPError'}
            )
            return 0, error_msg
            
        except Exception as e:
            error_msg = f"Unexpected download error: {str(e)}"
            print(f"   ❌ {error_msg}")
            self.log_failed_download(
                {**document_info, 'document_url': document_url}, 
                error_msg,
                {'error_type': type(e).__name__}
            )
            return 0, error_msg
    
    def process_all_documents(self, documents_df):
        """Process all documents from DataFrame and download PDFs"""
        
        print(f"📋 Processing {len(documents_df)} documents")
        print("="*80)
        
        # Initialize browser once for all downloads
        self.initialize_browser_and_login()
        
        try:
            success_count = 0
            failed_count = 0
            skipped_count = 0
            total_size = 0
            
            for index, row in documents_df.iterrows():
                document_title = row['title']
                document_url = row['url']
                
                # Skip if already downloaded (primary resume logic)
                if document_url in self.downloaded_urls:
                    print(f"⏭️ [{index+1}/{len(documents_df)}] SKIPPED (already downloaded): {document_title[:60]}...")
                    skipped_count += 1
                    continue
                
                # SKIP PREVIOUSLY FAILED DOWNLOADS - Don't waste time retrying 
                if document_url in self.failed_urls:
                    print(f"⚠️ [{index+1}/{len(documents_df)}] SKIPPED (previously failed): {document_title[:60]}...")
                    skipped_count += 1
                    continue
                
                # Skip reference/attribute pages that are duplicates (avoid unnecessary processing)
                if (document_title.lower().strip() in ['vb liên quan', 'thuộc tính', 'vb được hợp nhất'] or
                    'liên quan' in document_title.lower() and len(document_title.strip()) < 20):
                    print(f"⏭️ [{index+1}/{len(documents_df)}] SKIPPED (reference page): {document_title[:60]}...")
                    skipped_count += 1
                    continue
                
                print(f"\n📄 [{index+1}/{len(documents_df)}] {document_title[:80]}...")
                
                # Create safe filename with unique identifier to prevent overwriting
                safe_filename = re.sub(r'[^\w\s-]', '', document_title)
                safe_filename = re.sub(r'[-\s]+', '_', safe_filename)
                safe_filename = safe_filename[:90]  # Leave space for unique ID
                
                # Add unique identifier based on URL hash to prevent filename collisions
                import hashlib
                url_hash = hashlib.md5(document_url.encode()).hexdigest()[:8]
                safe_filename = f"{safe_filename}_{url_hash}"  # Don't add extension yet, will be determined by file type
                
                # Extract document URL and determine file type
                document_url_extracted, extraction_error, file_type = self.login_and_extract_pdf_url(document_url, document_title)
                
                if document_url_extracted:
                    # Add appropriate extension based on file type
                    if file_type == 'word':
                        full_filename = safe_filename + '.docx'
                    elif file_type == 'rtf':
                        full_filename = safe_filename + '.rtf'
                    elif file_type == 'zip':
                        full_filename = safe_filename + '.zip'
                    elif file_type == 'pdf':
                        full_filename = safe_filename + '.pdf'
                    else:
                        full_filename = safe_filename + '.pdf'  # Default to PDF
                    
                    # Check if file already exists as secondary safeguard
                    filepath = os.path.join(self.download_folder, full_filename)
                    if os.path.exists(filepath):
                        print(f"   ⏭️ File already exists, updating progress...")
                        self.save_progress(document_url)
                        skipped_count += 1
                        continue
                    
                    # Prepare document info for error logging
                    document_info = {
                        'title': document_title,
                        'url': document_url,
                        'filename': full_filename,
                        'index': index + 1,
                        'total': len(documents_df),
                        'file_type': file_type
                    }
                    
                    # Download document
                    file_size, download_error = self.download_document(document_url_extracted, full_filename, document_info, file_type)
                    if file_size > 0 and not download_error:
                        print(f"✅ Downloaded: {full_filename} ({file_size:,} bytes)")
                        success_count += 1
                        total_size += file_size
                        self.save_progress(document_url)
                    else:
                        print(f"❌ Download failed")
                        failed_count += 1
                        # Error already logged in download_document function
                else:
                    print(f"❌ Could not extract document URL")
                    failed_count += 1
                    # Log detailed failure information
                    document_info = {
                        'title': document_title,
                        'url': document_url,
                        'filename': safe_filename,
                        'index': index + 1,
                        'total': len(documents_df)
                    }
                    self.log_failed_download(
                        document_info, 
                        extraction_error or "Could not extract document URL - login or page structure issue",
                        {'step': 'document_url_extraction'}
                    )
                
                # Brief pause between documents to be respectful
                time.sleep(3)
                
                # Progress update every 10 documents
                if (index + 1) % 10 == 0:
                    print(f"\n📊 PROGRESS UPDATE:")
                    print(f"   ✅ Success: {success_count}")
                    print(f"   ❌ Failed: {failed_count}")
                    print(f"   ⏭️ Skipped: {skipped_count}")
                    print(f"   📁 Total size: {total_size / 1024 / 1024:.1f} MB")
                    print("-" * 60)
            
            print(f"\n🎯 FINAL SUMMARY:")
            print(f"✅ Successfully downloaded: {success_count}")
            print(f"❌ Failed: {failed_count}")
            print(f"⏭️ Skipped: {skipped_count}")
            print(f"📁 Total size: {total_size / 1024 / 1024:.1f} MB")
            print(f"📂 Files saved to: {self.download_folder}")
            
            # Show failed downloads summary
            if self.failed_downloads:
                print(f"\n📝 FAILED DOWNLOADS LOG:")
                print(f"JSON log: {self.error_log_file}")
                print(f"Excel log: {self.excel_error_log_file}")
                print(f"You can use these files to analyze and retry failed downloads")
            
            # Save Excel summary with final statistics
            self.save_excel_summary(success_count, failed_count, skipped_count, total_size)
        
        finally:
            # Clean up browser session
            print(f"\n🧹 Cleaning up browser session...")
            self.cleanup_browser()
    
    def show_failed_downloads(self):
        """Display all failed downloads for review"""
        if not self.failed_downloads:
            print("✅ No failed downloads found!")
            return
        
        print(f"\n📋 FAILED DOWNLOADS ({len(self.failed_downloads)} items):")
        print("="*80)
        
        # Group by error type for better analysis
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
        
        print(f"\n💡 TIP: Use 'python bulk_download_all.py [file] retry-failed' to retry all failures")
    
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
    
    def save_error_report(self, filename="error_report.txt"):
        """Save detailed error report to file"""
        if not self.failed_downloads:
            print("No errors to report!")
            return
        
        stats = self.get_error_statistics()
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("🚨 DOWNLOAD ERROR REPORT\n")
            f.write("=" * 50 + "\n\n")
            
            f.write(f"📊 SUMMARY:\n")
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
        
        # Process retry list
        self.process_all_documents(retry_df)

def main():
    """Download all traffic law documents"""
    
    # Check command line arguments
    if len(sys.argv) > 2:
        command = sys.argv[2].lower()
        
        # Initialize downloader for commands
        downloader = LuatVietnamBulkDownloader(
            username="duongng18",
            password="huuduong2004",
            download_folder="all_traffic_law_pdfs"
        )
        
        if command == "show-failed":
            downloader.show_failed_downloads()
            return
        elif command == "retry-failed":
            downloader.retry_failed_downloads()
            return
        elif command == "save-report":
            downloader.save_error_report()
            return
        elif command == "stats":
            stats = downloader.get_error_statistics()
            if stats:
                print(f"\n📊 ERROR STATISTICS:")
                print(f"Total Failures: {stats['total_failures']}")
                print(f"Error Types: {len(stats['error_types'])}")
                print(f"Most Common: {max(stats['error_types'], key=stats['error_types'].get) if stats['error_types'] else 'None'}")
                print(f"Time Range: {stats.get('oldest_failure', 'N/A')} to {stats.get('most_recent_failure', 'N/A')}")
            else:
                print("✅ No error statistics available - no failures recorded!")
            return
        else:
            print("❌ Unknown command. Available commands:")
            print("   show-failed  - Display all failed downloads")
            print("   retry-failed - Retry all previously failed downloads")
            print("   save-report  - Save detailed error report to file")
            print("   stats        - Show error statistics summary")
            return
    
    # Load the document list
    try:
        if len(sys.argv) > 1:
            excel_file = sys.argv[1]
        else:
            excel_file = "luatvietnam_smart_backup_20250912_231952.xlsx"
            
        df = pd.read_excel(excel_file)
        print(f"📊 Loaded {len(df)} documents from Excel file")
    except Exception as e:
        print(f"❌ Could not load Excel file: {e}")
        return
        print("Usage: python bulk_download_all.py [excel_file] [command]")
        print("Commands:")
        print("  show-failed  - Show all failed downloads")
        print("  retry-failed - Retry all failed downloads")
        return
    
    # Initialize downloader
    downloader = LuatVietnamBulkDownloader(
        username="duongng18",
        password="huuduong2004",
        download_folder="all_traffic_law_pdfs"
    )
    
    # Download all documents
    print("🚀 STARTING BULK DOWNLOAD OF ALL DOCUMENTS")
    print("This will take approximately 30-45 minutes to complete")
    print("Press Ctrl+C to interrupt and resume later")
    
    try:
        downloader.process_all_documents(df)
    except KeyboardInterrupt:
        print("\n⏸️ Download interrupted by user")
        print("💡 You can resume later by running this script again")

if __name__ == "__main__":
    main()
