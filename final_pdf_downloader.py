#!/usr/bin/env python3
"""
Final PDF Downloader - Extract actual PDF URLs after login
Based on our discovery that actual PDF URLs are in the page source after authentication
"""

import time
import os
import re
import requests
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

class LuatVietnamPDFDownloader:
    def __init__(self, username, password, download_folder="final_downloads"):
        self.username = username
        self.password = password
        self.download_folder = download_folder
        
        # Ensure download folder exists
        if not os.path.exists(download_folder):
            os.makedirs(download_folder)
        
        print(f"📁 Download folder: {download_folder}")
    
    def setup_driver(self):
        """Setup Chrome driver with proper configuration"""
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        return driver
    
    def login_and_extract_pdf_url(self, document_url):
        """Login and extract the actual PDF URL from page source"""
        
        driver = self.setup_driver()
        wait = WebDriverWait(driver, 20)
        
        try:
            print(f"🔍 Processing: {document_url}")
            
            # Navigate to document page
            driver.get(document_url)
            time.sleep(3)
            
            # Look for login trigger element and click it
            login_triggers = [
                "//a[contains(@class, 'lawsVnLogin')]",
                "//span[contains(@class, 'lawsVnLogin')]",
                "//a[contains(text(), 'Tải văn bản')]",
                "//span[contains(text(), 'Tải văn bản')]"
            ]
            
            login_triggered = False
            for trigger_xpath in login_triggers:
                try:
                    trigger_element = driver.find_element(By.XPATH, trigger_xpath)
                    driver.execute_script("arguments[0].click();", trigger_element)
                    print(f"✅ Triggered login with: {trigger_xpath}")
                    login_triggered = True
                    time.sleep(2)
                    break
                except:
                    continue
            
            if not login_triggered:
                print("⚠️ Could not find login trigger, attempting direct access...")
            
            # Handle login popup
            try:
                username_field = wait.until(EC.presence_of_element_located((By.ID, "customer_name")))
                password_field = driver.find_element(By.ID, "password_login")
                
                username_field.clear()
                username_field.send_keys(self.username)
                password_field.clear()
                password_field.send_keys(self.password)
                password_field.send_keys('\n')
                
                print("✅ Login credentials submitted")
                time.sleep(5)  # Wait for login to complete
                
            except Exception as e:
                print(f"❌ Login failed: {e}")
                return None
            
            # Extract PDF URL from page source
            page_source = driver.page_source
            
            # Multiple patterns to find PDF URLs
            patterns = [
                r'https://static\.luatvietnam\.vn/tai-file-[^"\']*\.pdf',  # Download URLs
                r'https://static\.luatvietnam\.vn/[^"\']*\.pdf'  # Any PDF URL
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, page_source)
                if matches:
                    # Return the first match
                    pdf_url = matches[0]
                    print(f"✅ Found PDF URL: {pdf_url}")
                    return pdf_url
            
            print("❌ No PDF URL found in page source")
            return None
            
        except Exception as e:
            print(f"❌ Error processing {document_url}: {e}")
            return None
            
        finally:
            driver.quit()
    
    def download_pdf(self, pdf_url, filename):
        """Download PDF directly using requests"""
        
        filepath = os.path.join(self.download_folder, filename)
        
        try:
            print(f"📥 Downloading: {filename}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            response = requests.get(pdf_url, headers=headers, stream=True, timeout=30)
            response.raise_for_status()
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            file_size = os.path.getsize(filepath)
            print(f"✅ Downloaded: {filename} ({file_size:,} bytes)")
            return True
            
        except Exception as e:
            print(f"❌ Download failed for {filename}: {e}")
            return False
    
    def process_documents(self, documents_df, limit=None):
        """Process documents from DataFrame and download PDFs"""
        
        if limit:
            documents_df = documents_df.head(limit)
        
        print(f"📋 Processing {len(documents_df)} documents")
        print("="*60)
        
        success_count = 0
        failed_count = 0
        
        for index, row in documents_df.iterrows():
            document_title = row['title']
            document_url = row['url']
            
            print(f"\n📄 [{index+1}/{len(documents_df)}] {document_title[:80]}...")
            
            # Create safe filename
            safe_filename = re.sub(r'[^\w\s-]', '', document_title)
            safe_filename = re.sub(r'[-\s]+', '_', safe_filename)
            safe_filename = safe_filename[:100] + ".pdf"  # Limit filename length
            
            # Extract PDF URL
            pdf_url = self.login_and_extract_pdf_url(document_url)
            
            if pdf_url:
                # Download PDF
                if self.download_pdf(pdf_url, safe_filename):
                    success_count += 1
                else:
                    failed_count += 1
            else:
                failed_count += 1
            
            # Brief pause between documents
            time.sleep(2)
        
        print(f"\n🎯 SUMMARY:")
        print(f"✅ Successfully downloaded: {success_count}")
        print(f"❌ Failed: {failed_count}")
        print(f"📁 Files saved to: {self.download_folder}")

def main():
    """Test with a few documents first"""
    
    # Load the document list
    try:
        df = pd.read_excel("luatvietnam_partial_results.xlsx")
        print(f"📊 Loaded {len(df)} documents from Excel file")
    except Exception as e:
        print(f"❌ Could not load Excel file: {e}")
        return
    
    # Initialize downloader
    downloader = LuatVietnamPDFDownloader(
        username="duongnguyen18",
        password="huuduong2004",
        download_folder="final_downloads"
    )
    
    # Test with first 3 documents
    print("🧪 TESTING WITH FIRST 3 DOCUMENTS")
    downloader.process_documents(df, limit=3)

if __name__ == "__main__":
    main()
