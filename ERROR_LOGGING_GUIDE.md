# Error Logging and Failed Downloads/URLs Tracking

Both the crawler and bulk downloader now include comprehensive error logging to track and retry failures.

## Error Logging Features

### 1. Crawler Error Logging (`luatvietnam_crawler.py`)
- Failed URLs during crawling logged to `crawler_failed_urls.json`
- Tracks three types of failures:
  - **"crawling"**: Network issues, timeouts, HTTP errors
  - **"parsing"**: Document extraction failures from pages  
  - **"pagination"**: Failed to find next page links

### 2. Bulk Downloader Error Logging (`bulk_download_all.py`)
- Failed downloads logged to `failed_downloads.json`
- Tracks two types of failures:
  - **"Could not extract PDF URL"**: Authentication or page structure issues
  - **"PDF download failed"**: Network/file download issues

### 3. Error Log File Structures

**Crawler Errors** (`crawler_failed_urls.json`):
```json
[
  {
    "timestamp": "2025-01-09T19:20:15.123456",
    "url": "https://luatvietnam.vn/page-url",
    "error": "Timeout error description",
    "error_type": "crawling",
    "retry_count": 0
  }
]
```

**Download Errors** (`failed_downloads.json`):
```json
[
  {
    "timestamp": "2025-01-09T19:20:15.123456",
    "title": "Document Title",
    "url": "https://luatvietnam.vn/document-url",
    "error": "Could not extract PDF URL - login or page structure issue",
    "retry_count": 0
  }
]
```

## Using the Error Logging System

### Check Crawler Failed URLs
```bash
# Quick check of crawler failed URLs
python check_crawler_failed_urls.py

# Show detailed failed URLs through crawler
python luatvietnam_crawler.py show-failed
```

### Retry Crawler Failed URLs
```bash
# Retry all previously failed URLs during crawling
python luatvietnam_crawler.py retry-failed
```

### Check Download Failed URLs  
```bash
# Quick check of failed downloads
python check_failed_downloads.py

# Show detailed failed downloads through bulk downloader
python bulk_download_all.py luatvietnam_partial_results.xlsx show-failed
```

### Retry Failed Downloads
```bash
# Retry all previously failed downloads
python bulk_download_all.py luatvietnam_partial_results.xlsx retry-failed
```

### Normal Operations
```bash
# Normal crawling (logs new URL failures)
python luatvietnam_crawler.py

# Normal bulk download (skips downloaded, logs new failures)
python bulk_download_all.py luatvietnam_partial_results.xlsx
```

## Files Created

1. **`crawler_failed_urls.json`** - Detailed log of URLs that failed during crawling
2. **`failed_downloads.json`** - Detailed log of documents that failed to download
3. **`download_progress.txt`** - List of successfully downloaded URLs (for resume capability)
4. **`check_crawler_failed_urls.py`** - Quick script to view crawler failed URLs
5. **`check_failed_downloads.py`** - Quick script to view failed downloads summary

## Example Usage Workflow

### Full Process Workflow
1. **Start crawling**: `python luatvietnam_crawler.py`
2. **Check crawler failures**: `python check_crawler_failed_urls.py`
3. **Retry crawler failures**: `python luatvietnam_crawler.py retry-failed`
4. **Start bulk download**: `python bulk_download_all.py luatvietnam_partial_results.xlsx`
5. **Check download failures**: `python check_failed_downloads.py` 
6. **Retry download failures**: `python bulk_download_all.py luatvietnam_partial_results.xlsx retry-failed`

### Resume Interrupted Operations
- **Resume crawling**: `python luatvietnam_crawler.py` (automatically resumes)
- **Resume downloads**: `python bulk_download_all.py luatvietnam_partial_results.xlsx`

## Benefits

- **Complete failure tracking**: Both crawling and downloading failures are recorded
- **No lost progress**: Every failure is recorded with detailed context for retry
- **Easy retry mechanisms**: Can retry just failures without re-processing successful items
- **Debugging assistance**: Error messages help identify if issues are network, authentication, or structural
- **Comprehensive recovery**: Can interrupt and resume any operation without losing progress
- **Failure analysis**: Error logs help identify patterns and systemic issues

## Error Analysis

### Crawler Error Patterns
- Many "crawling" errors → Network issues or site blocking
- Many "parsing" errors → Site structure changes or content variations  
- Many "pagination" errors → Site navigation changes

### Download Error Patterns  
- Many "login failed" errors → Credential issues or authentication changes
- Many "download failed" errors → Network issues, rate limiting, or file access problems
- Mixed errors → Individual document issues that may resolve on retry

## Troubleshooting

### If Crawler Keeps Failing
1. Check `crawler_failed_urls.json` for error patterns
2. Run `python luatvietnam_crawler.py show-failed` for details
3. Check if site structure changed by manually visiting failed URLs
4. Retry with `python luatvietnam_crawler.py retry-failed`

### If Downloads Keep Failing  
1. Check `failed_downloads.json` for error patterns
2. Run `python bulk_download_all.py luatvietnam_partial_results.xlsx show-failed`
3. Verify credentials are still valid
4. Check if site authentication changed
5. Retry with `python bulk_download_all.py luatvietnam_partial_results.xlsx retry-failed`
