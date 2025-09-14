# Batch Crawler Usage Guide

## Overview
This document explains how to use the new batch crawler system that splits large Excel files into manageable chunks and allows selective downloading.

## Files Created
1. **`split_urls_to_excel.py`** - Splits large Excel files into 3000-URL batches
2. **`batch_crawler.py`** - Modified crawler with batch support and interactive features

## Step 1: Split URLs into Batches

### Usage
```bash
python split_urls_to_excel.py
```

### What it does:
- Shows available Excel files with URL counts
- Lets you choose which file to split
- Asks for URLs per file (default: 3000)
- Asks for output prefix (default: "batch")
- Creates `batch_files/` directory with split files
- Creates a summary Excel file

### Example Output:
```
batch_files/
├── batch_01_of_05_1_to_3000.xlsx      (3000 URLs)
├── batch_02_of_05_3001_to_6000.xlsx   (3000 URLs)
├── batch_03_of_05_6001_to_9000.xlsx   (3000 URLs)
├── batch_04_of_05_9001_to_12000.xlsx  (3000 URLs)
├── batch_05_of_05_12001_to_13796.xlsx (1796 URLs)
└── batch_summary.xlsx                  (Overview)
```

## Step 2: Download Batches

### Usage
```bash
python batch_crawler.py
```

### Interactive Mode:
1. **Choose Excel File**: Shows all files in `batch_files/` with URL counts
2. **Enter Credentials**: Username and password for luatvietnam.vn
3. **Start Download**: Processes the selected batch

### What it creates:
- `downloads_batch_XX/` folder for each batch
- `progress_batch_XX.txt` - progress tracking
- `failed_downloads_batch_XX.json` - error tracking
- `failed_downloads_log_batch_XX.xlsx` - Excel error log

### Command Line Usage:
```bash
# Download specific batch
python batch_crawler.py batch_files/batch_01_of_05_1_to_3000.xlsx

# Show failed downloads for a batch
python batch_crawler.py batch_files/batch_01_of_05_1_to_3000.xlsx show-failed

# Retry failed downloads for a batch
python batch_crawler.py batch_files/batch_01_of_05_1_to_3000.xlsx retry-failed

# Save error report for a batch
python batch_crawler.py batch_files/batch_01_of_05_1_to_3000.xlsx save-report

# Show error statistics for a batch
python batch_crawler.py batch_files/batch_01_of_05_1_to_3000.xlsx stats
```

## Features

### Batch Crawler Features:
- ✅ **Interactive Excel file selection** from `batch_files/`
- ✅ **Interactive credential input** (username/password)
- ✅ **Batch-specific progress tracking** - each batch has its own progress files
- ✅ **Batch-specific error logging** - separate error logs per batch
- ✅ **Resume capability** - can resume interrupted downloads
- ✅ **Failed download skipping** - skips known failures to save time
- ✅ **Progress indicators** - shows batch info and progress
- ✅ **Error analysis tools** - detailed error reporting

### URL Splitter Features:
- ✅ **Flexible splitting** - choose URLs per file (default 3000)
- ✅ **Smart naming** - includes range and batch numbers
- ✅ **Batch metadata** - adds batch info to each Excel file
- ✅ **Summary file** - overview of all created batches
- ✅ **Interactive selection** - choose source file from available options

## Example Workflow

### 1. Split Large Excel File
```bash
python split_urls_to_excel.py
# Choose: luatvietnam_complete_collection.xlsx (13796 URLs)
# URLs per file: 3000
# Creates 5 batch files
```

### 2. Download First Batch
```bash
python batch_crawler.py
# Choose: batch_01_of_05_1_to_3000.xlsx
# Enter credentials: username/password
# Downloads 3000 documents to downloads_batch_01_of_05_1_to_3000/
```

### 3. Download Remaining Batches
```bash
python batch_crawler.py
# Choose: batch_02_of_05_3001_to_6000.xlsx
# Continue with remaining batches...
```

### 4. Handle Failures
```bash
# Check failures for a specific batch
python batch_crawler.py batch_files/batch_01_of_05_1_to_3000.xlsx show-failed

# Retry failures for a specific batch
python batch_crawler.py batch_files/batch_01_of_05_1_to_3000.xlsx retry-failed
```

## Advantages of Batch System

1. **Better Control**: Download manageable chunks instead of all 13,796 at once
2. **Risk Management**: If one batch fails, others are unaffected
3. **Parallel Processing**: Can run multiple batches on different machines
4. **Easy Resume**: Resume specific batches without affecting others
5. **Progress Tracking**: Clear progress indicators per batch
6. **Error Isolation**: Failures are isolated to specific batches
7. **Storage Management**: Organize downloads by batch for better file management

## File Organization

```
crawl_law/
├── split_urls_to_excel.py          # URL splitter script
├── batch_crawler.py                # Batch crawler script
├── bulk_download_all.py            # Original crawler (unchanged)
├── batch_files/                    # Batch Excel files
│   ├── batch_01_of_05_1_to_3000.xlsx
│   ├── batch_02_of_05_3001_to_6000.xlsx
│   ├── ...
│   └── batch_summary.xlsx
├── downloads_batch_01_of_05_1_to_3000/  # Batch 1 downloads
├── downloads_batch_02_of_05_3001_to_6000/ # Batch 2 downloads
├── progress_batch_01_of_05_1_to_3000.txt  # Batch 1 progress
├── failed_downloads_batch_01_of_05_1_to_3000.json # Batch 1 errors
└── ...
```

## Notes

- The original `bulk_download_all.py` remains **unchanged** and fully functional
- Each batch is completely independent with its own progress and error tracking
- You can run batches in any order
- Credentials are entered interactively for security
- All batch files include metadata for easy identification
- The system automatically skips already downloaded and previously failed URLs
