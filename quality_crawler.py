import requests
import pandas as pd
from bs4 import BeautifulSoup
import time
import logging
from datetime import datetime
import os

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('quality_crawler.log'),
        logging.StreamHandler()
    ]
)

def is_auxiliary_content(title):
    """Filter out auxiliary/navigation content"""
    auxiliary_keywords = [
        'VB liên quan', 'Thuộc tính', 'Tải về', 'Tóm tắt', 
        'Hiệu lực', 'Lược đồ', 'Tiếng Anh', 'Văn bản được hợp nhất',
        'VB được hợp nhất', 'Related documents', 'Properties'
    ]
    
    title_clean = title.strip()
    
    # Check if it's auxiliary content
    if any(keyword in title_clean for keyword in auxiliary_keywords):
        return True
    
    # Check if it's too short to be a real document title
    if len(title_clean) < 10:
        return True
    
    # Check if it's just navigation text
    if title_clean.lower() in ['xem thêm', 'chi tiết', 'more', 'details']:
        return True
        
    return False

def crawl_quality_documents():
    """Crawl with quality filtering to get only real legal documents"""
    print("🎯 QUALITY CRAWLER: Finding real legal documents only")
    print("=" * 60)
    
    # Load existing data
    try:
        existing_df = pd.read_excel('luatvietnam_complete_collection.xlsx')
        existing_documents = set(existing_df['title'].tolist())
        print(f"✅ Loaded {len(existing_documents):,} existing documents")
    except:
        existing_documents = set()
        print("📝 Starting fresh collection")
    
    new_documents = []
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    
    # Start from where we left off, but focus on earlier pages that might have more content
    print("🔍 Scanning pages 1-50 for missed quality documents...")
    
    for page in range(1, 51):  # Focus on content-rich early pages
        urls_to_try = [
            f"https://luatvietnam.vn/giao-thong-28-f1.html?page={page}",
            f"https://luatvietnam.vn/giao-thong-28-f2.html?page={page}",
        ]
        
        for url in urls_to_try:
            try:
                print(f"📋 Scanning page {page}: {url.split('/')[-1]}")
                response = session.get(url, timeout=10)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Find all document links
                doc_links = soup.find_all('a', href=True)
                page_documents = 0
                
                for link in doc_links:
                    title = link.get_text(strip=True)
                    href = link.get('href', '')
                    
                    # Skip if no title or href
                    if not title or not href:
                        continue
                    
                    # Skip auxiliary content
                    if is_auxiliary_content(title):
                        continue
                    
                    # Skip if already exists
                    if title in existing_documents:
                        continue
                    
                    # Skip if not a document link
                    if not any(pattern in href for pattern in ['.html', 'id=', 'van-ban']):
                        continue
                    
                    # This looks like a real legal document
                    full_url = href if href.startswith('http') else f"https://luatvietnam.vn{href}"
                    
                    doc_data = {
                        'title': title,
                        'url': full_url,
                        'publication_date': '',
                        'document_type': 'Legal Document',
                        'source_page': url,
                        'crawled_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    
                    new_documents.append(doc_data)
                    existing_documents.add(title)  # Prevent duplicates within this session
                    page_documents += 1
                    
                    print(f"   ✅ Found: {title[:60]}...")
                
                print(f"   📊 Found {page_documents} quality documents on this page")
                time.sleep(1)  # Be respectful
                
            except Exception as e:
                print(f"   ❌ Error on {url}: {str(e)}")
                continue
        
        # Save progress every 10 pages
        if page % 10 == 0 and new_documents:
            save_progress(new_documents, existing_df if 'existing_df' in locals() else None)
            print(f"💾 Progress saved at page {page}: {len(new_documents)} new documents")
    
    # Final save
    if new_documents:
        final_df = save_progress(new_documents, existing_df if 'existing_df' in locals() else None)
        print(f"\n🎉 QUALITY CRAWLING COMPLETE!")
        print(f"📊 Found {len(new_documents)} new quality documents")
        print(f"📁 Total collection: {len(final_df)} documents")
        print(f"📈 Quality ratio: {len(final_df)/(len(final_df)+2380)*100:.1f}% real documents")
    else:
        print("\n📋 No new quality documents found")

def save_progress(new_documents, existing_df):
    """Save progress to Excel file"""
    new_df = pd.DataFrame(new_documents)
    
    if existing_df is not None:
        # Combine with existing data
        final_df = pd.concat([existing_df, new_df], ignore_index=True)
    else:
        final_df = new_df
    
    # Remove any duplicates that might have slipped through
    final_df = final_df.drop_duplicates(subset=['title'], keep='first')
    
    # Save to Excel
    backup_filename = f"luatvietnam_quality_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    final_df.to_excel(backup_filename, index=False)
    final_df.to_excel('luatvietnam_complete_collection.xlsx', index=False)
    
    print(f"💾 Saved {len(final_df)} documents to Excel")
    return final_df

if __name__ == "__main__":
    crawl_quality_documents()
