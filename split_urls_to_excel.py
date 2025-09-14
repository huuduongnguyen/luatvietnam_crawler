#!/usr/bin/env python3
"""
URL Splitter - Split large Excel file into smaller chunks of 3000 URLs each
This helps manage downloads in smaller batches for better control
"""

import pandas as pd
import os
import math
from datetime import datetime

def split_excel_file(input_file, urls_per_file=3000, output_prefix="batch", start_from_index=0):
    """
    Split a large Excel file into smaller chunks
    
    Args:
        input_file (str): Path to the input Excel file
        urls_per_file (int): Number of URLs per output file (default: 3000)
        output_prefix (str): Prefix for output files (default: "batch")
        start_from_index (int): Index to start splitting from (default: 0)
    """
    
    try:
        print(f"📊 Loading Excel file: {input_file}")
        df = pd.read_excel(input_file)
        print(f"✅ Loaded {len(df)} total documents")
        
        # Apply start index filter
        if start_from_index > 0:
            if start_from_index >= len(df):
                print(f"❌ Start index {start_from_index} is beyond the total rows ({len(df)})")
                return None, 0
            
            df = df.iloc[start_from_index:].copy().reset_index(drop=True)
            print(f"🎯 Starting from index {start_from_index}, remaining: {len(df)} documents")
        
        # Calculate number of files needed
        total_urls = len(df)
        num_files = math.ceil(total_urls / urls_per_file)
        
        print(f"📁 Will create {num_files} files with {urls_per_file} URLs each")
        print(f"📁 Output folder: batch_files/")
        
        # Create output directory
        output_dir = "batch_files"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"📁 Created directory: {output_dir}")
        
        # Split and save files
        for i in range(num_files):
            start_idx = i * urls_per_file
            end_idx = min((i + 1) * urls_per_file, total_urls)
            
            # Extract chunk
            chunk_df = df.iloc[start_idx:end_idx].copy()
            
            # Add batch information (adjusted for original index)
            actual_start_idx = start_from_index + start_idx
            actual_end_idx = start_from_index + end_idx - 1
            
            chunk_df['batch_number'] = i + 1
            chunk_df['batch_start_index'] = actual_start_idx
            chunk_df['batch_end_index'] = actual_end_idx
            chunk_df['total_batches'] = num_files
            chunk_df['original_start_index'] = start_from_index
            
            # Create filename with actual indices
            if start_from_index > 0:
                filename = f"{output_prefix}_{i+1:02d}_of_{num_files:02d}_{actual_start_idx+1}_to_{actual_end_idx+1}_from_{start_from_index+1}.xlsx"
            else:
                filename = f"{output_prefix}_{i+1:02d}_of_{num_files:02d}_{actual_start_idx+1}_to_{actual_end_idx+1}.xlsx"
            
            filepath = os.path.join(output_dir, filename)
            
            # Save chunk
            chunk_df.to_excel(filepath, index=False)
            
            print(f"✅ Created: {filename} ({len(chunk_df)} URLs, original indices {actual_start_idx+1}-{actual_end_idx+1})")
        
        # Create summary file
        summary_data = []
        for i in range(num_files):
            start_idx = i * urls_per_file
            end_idx = min((i + 1) * urls_per_file, total_urls)
            
            # Calculate actual indices
            actual_start_idx = start_from_index + start_idx
            actual_end_idx = start_from_index + end_idx - 1
            
            if start_from_index > 0:
                filename = f"{output_prefix}_{i+1:02d}_of_{num_files:02d}_{actual_start_idx+1}_to_{actual_end_idx+1}_from_{start_from_index+1}.xlsx"
            else:
                filename = f"{output_prefix}_{i+1:02d}_of_{num_files:02d}_{actual_start_idx+1}_to_{actual_end_idx+1}.xlsx"
            
            summary_data.append({
                'batch_number': i + 1,
                'filename': filename,
                'start_index_original': actual_start_idx + 1,
                'end_index_original': actual_end_idx + 1,
                'start_index_in_batch': start_idx + 1,
                'end_index_in_batch': end_idx,
                'url_count': end_idx - start_idx,
                'original_start_offset': start_from_index,
                'created_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
        
        summary_df = pd.DataFrame(summary_data)
        if start_from_index > 0:
            summary_file = os.path.join(output_dir, f"batch_summary_from_{start_from_index+1}.xlsx")
        else:
            summary_file = os.path.join(output_dir, "batch_summary.xlsx")
        summary_df.to_excel(summary_file, index=False)
        
        print(f"\n📋 Summary:")
        print(f"   Original file URLs: {len(pd.read_excel(input_file))}")
        print(f"   Starting from index: {start_from_index + 1}")
        print(f"   URLs processed: {total_urls}")
        print(f"   Files created: {num_files}")
        print(f"   URLs per file: {urls_per_file}")
        print(f"   Output directory: {output_dir}")
        print(f"   Summary file: {summary_file}")
        
        return output_dir, num_files
        
    except Exception as e:
        print(f"❌ Error splitting file: {e}")
        return None, 0

def main():
    """Split the main Excel file into smaller batches"""
    
    # Available Excel files
    excel_files = [
        "luatvietnam_complete_collection.xlsx",
        "luatvietnam_smart_backup_20250912_231952.xlsx", 
        "luatvietnam_complete_backup_20250912_095329.xlsx"
    ]
    
    print("🔧 URL SPLITTER - Split Excel file into 3000-URL batches")
    print("=" * 60)
    
    # Show available files
    print("📁 Available Excel files:")
    for i, file in enumerate(excel_files, 1):
        if os.path.exists(file):
            try:
                df = pd.read_excel(file)
                print(f"   {i}. {file} ({len(df)} URLs)")
            except:
                print(f"   {i}. {file} (could not read)")
        else:
            print(f"   {i}. {file} (not found)")
    
    # Let user choose file
    while True:
        try:
            choice = input(f"\nChoose file (1-{len(excel_files)}): ").strip()
            if not choice:
                print("❌ Please enter a number")
                continue
                
            file_idx = int(choice) - 1
            if 0 <= file_idx < len(excel_files):
                input_file = excel_files[file_idx]
                if os.path.exists(input_file):
                    break
                else:
                    print(f"❌ File not found: {input_file}")
            else:
                print(f"❌ Please enter a number between 1 and {len(excel_files)}")
        except ValueError:
            print("❌ Please enter a valid number")
    
    # Ask for URLs per file
    while True:
        try:
            urls_input = input("\nURLs per file (default 3000): ").strip()
            if not urls_input:
                urls_per_file = 3000
                break
            else:
                urls_per_file = int(urls_input)
                if urls_per_file > 0:
                    break
                else:
                    print("❌ Please enter a positive number")
        except ValueError:
            print("❌ Please enter a valid number")
    
    # Ask for starting index
    while True:
        try:
            # Show total URLs in selected file
            df_total = pd.read_excel(input_file)
            total_urls = len(df_total)
            
            start_input = input(f"\nStart from index (0-{total_urls-1}, default 0): ").strip()
            if not start_input:
                start_from_index = 0
                break
            else:
                start_from_index = int(start_input)
                if 0 <= start_from_index < total_urls:
                    remaining_urls = total_urls - start_from_index
                    print(f"📊 Starting from index {start_from_index}, remaining URLs: {remaining_urls}")
                    break
                else:
                    print(f"❌ Please enter a number between 0 and {total_urls-1}")
        except ValueError:
            print("❌ Please enter a valid number")
        except Exception as e:
            print(f"❌ Error reading file: {e}")
            start_from_index = 0
            break
    
    # Ask for output prefix
    prefix = input("\nOutput prefix (default 'batch'): ").strip()
    if not prefix:
        prefix = "batch"
    
    print(f"\n🚀 Starting split operation...")
    print(f"   Input file: {input_file}")
    print(f"   Starting from index: {start_from_index}")
    print(f"   URLs per file: {urls_per_file}")
    print(f"   Output prefix: {prefix}")
    
    # Perform split
    output_dir, num_files = split_excel_file(input_file, urls_per_file, prefix, start_from_index)
    
    if output_dir and num_files > 0:
        print(f"\n✅ SUCCESS!")
        print(f"   Created {num_files} batch files in {output_dir}/")
        print(f"   You can now use batch_crawler.py to download specific batches")
    else:
        print(f"\n❌ Split operation failed!")

if __name__ == "__main__":
    main()
