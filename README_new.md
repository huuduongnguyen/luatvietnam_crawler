# LuatVietnam.vn Traffic Law Crawler

A clean and focused web crawler designed to extract traffic law documents from luatvietnam.vn.

## 🎯 Purpose

This crawler extracts traffic law documents from the "Giao thông" (Traffic) section of luatvietnam.vn, specifically targeting:
- https://luatvietnam.vn/giao-thong-28-f1.html

## ✨ Features

- **Clean Extraction**: Extracts document titles, URLs, publication dates, and document types
- **Pagination Handling**: Automatically follows pagination links to crawl multiple pages
- **Anti-Detection**: Uses realistic browser headers and rate limiting
- **Excel Export**: Saves results to Excel format with document categorization
- **Duplicate Removal**: Automatically removes duplicate documents
- **Progress Logging**: Detailed logging of crawling progress

## 📋 Document Types Extracted

- Laws (Luật)
- Decrees (Nghị định)
- Circulars (Thông tư)
- Decisions (Quyết định)
- Official Letters (Công văn)
- Directives (Chỉ thị)

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the Crawler

```bash
python luatvietnam_crawler.py
```

### 3. Results

The crawler will:
- Extract all traffic law documents from luatvietnam.vn
- Save results to `luatvietnam_traffic_laws.xlsx`
- Display summary statistics

## 📊 Output Format

The Excel file contains these columns:
- **title**: Document title
- **url**: Full URL to the document
- **publication_date**: Publication date (DD/MM/YYYY format)
- **document_type**: Type of document (Luật, Nghị định, etc.)
- **source_page**: Page where the document was found
- **crawled_date**: When the document was crawled

## 🛠️ Configuration

Key settings in the crawler:
- Rate limiting: 1-3 seconds between requests
- Page limit: Maximum 50 pages to prevent infinite crawling
- Timeout: 30 seconds per request
- User-Agent: Mimics Chrome browser

## 📁 Project Structure

```
crawl_law/
├── luatvietnam_crawler.py     # Main crawler script
├── requirements.txt           # Python dependencies
├── README.md                 # This file
├── luatvietnam_crawler.log   # Crawler logs (generated)
└── luatvietnam_traffic_laws.xlsx  # Results (generated)
```

## 🔍 Example Usage

```python
from luatvietnam_crawler import LuatVietnamCrawler

# Create crawler instance
crawler = LuatVietnamCrawler()

# Crawl all pages
documents = crawler.crawl_all_pages()

# Save to Excel
crawler.save_to_excel("my_results.xlsx")
```

## 📝 Sample Output

The crawler typically finds hundreds of traffic law documents including:

- Nghị định 168/2024/NĐ-CP về xử phạt vi phạm hành chính giao thông đường bộ
- Luật Đường sắt 2025, số 95/2025/QH15
- Thông tư 14/2025/TT-BXD về đào tạo lái xe và cấp chứng chỉ giao thông
- And many more...

## ⚠️ Important Notes

- The crawler respects luatvietnam.vn's robots.txt
- Uses rate limiting to avoid overloading the server
- Designed for educational and research purposes
- Please respect the website's terms of service

## 🔧 Troubleshooting

If you encounter issues:

1. **Network errors**: Check your internet connection
2. **Missing dependencies**: Run `pip install -r requirements.txt`
3. **Empty results**: The website structure may have changed
4. **Rate limiting**: The crawler includes built-in delays

## 📞 Support

For issues or questions, check the log file `luatvietnam_crawler.log` for detailed error information.
