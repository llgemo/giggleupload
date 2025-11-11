#!/usr/bin/env python3
"""
Booru to Szurubooru Uploader (Real-time upload version)
Downloads images from booru sites using gallery-dl and uploads them to Szurubooru instantly
"""

import json
import os
import subprocess
import requests
from pathlib import Path
import time
from threading import Thread, Event
from queue import Queue

# Configuration
SZURU_URL = "YOUR_SZURUBOORU_URL_HERE"  # e.g., "https://lboorus.lmms.wtf"
SZURU_USER = "YOUR_SZURUBOORU_USERNAME_HERE"
SZURU_TOKEN = "YOUR_SZURUBOORU_API_TOKEN_HERE"  # e.g., "396ec236-80b6-4232-861e-39d613db3ffc"
DOWNLOAD_DIR = "./booru_downloads"

# Rule34 API credentials
RULE34_API_KEY = "YOUR_RULE34_API_KEY_HERE"
RULE34_USER_ID = "YOUR_RULE34_USER_ID_HERE"

# Szurubooru API headers
import base64

auth_string = f"{SZURU_USER}:{SZURU_TOKEN}"
auth_token = base64.b64encode(auth_string.encode()).decode('ascii')

headers = {
    "Authorization": f"Token {auth_token}",
    "Accept": "application/json"
}

# Track processed files
processed_files = set()
stop_event = Event()
upload_stats = {"uploaded": 0, "failed": 0, "total": 0}

def setup_gallery_dl_config():
    """Setup gallery-dl configuration with Rule34 API credentials"""
    config_dir = Path.home() / ".config" / "gallery-dl"
    if os.name == 'nt':  # Windows
        config_dir = Path(os.environ.get('APPDATA', '')) / "gallery-dl"
    
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.json"
    
    # Create or update config
    config = {}
    if config_file.exists():
        with open(config_file, 'r') as f:
            try:
                config = json.load(f)
            except:
                config = {}
    
    # Add Rule34 credentials
    if "extractor" not in config:
        config["extractor"] = {}
    if "rule34" not in config["extractor"]:
        config["extractor"]["rule34"] = {}
    
    config["extractor"]["rule34"]["api-key"] = RULE34_API_KEY
    config["extractor"]["rule34"]["user-id"] = RULE34_USER_ID
    
    # Save config
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"û Gallery-dl config updated")

def get_file_token(filepath):
    """Upload file and get token from Szurubooru"""
    try:
        with open(filepath, 'rb') as f:
            files = {'content': f}
            response = requests.post(
                f"{SZURU_URL}/api/uploads",
                headers=headers,
                files=files,
                timeout=60
            )
            
            if response.status_code == 200:
                return response.json()['token']
            else:
                print(f"Upload error: {response.status_code} - {response.text}")
                return None
    except Exception as e:
        print(f"Error uploading file: {e}")
        return None

def create_post(token, tags, safety="safe", source=None):
    """Create a post in Szurubooru"""
    try:
        data = {
            "tags": tags,
            "safety": safety,
            "contentToken": token
        }
        
        if source:
            data["source"] = source
        
        response = requests.post(
            f"{SZURU_URL}/api/posts",
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Post creation error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Error creating post: {e}")
        return None

def upload_file(filepath, metadata_path):
    """Upload a single file to Szurubooru"""
    filename = filepath.name
    print(f"\n?? Uploading ({upload_stats['uploaded'] + upload_stats['failed'] + 1}/{upload_stats['total']}): {filename}")
    
    # Read metadata if available
    tags = []
    source = None
    safety = "safe"
    
    if metadata_path.exists():
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
                
                # Extract tags
                if 'tags' in metadata:
                    if isinstance(metadata['tags'], list):
                        tags = metadata['tags']
                    elif isinstance(metadata['tags'], str):
                        tags = metadata['tags'].split()
                elif 'tag_string' in metadata:
                    tags = metadata['tag_string'].split()
                
                # Get source URL
                if 'source' in metadata:
                    source = metadata['source']
                elif 'file_url' in metadata:
                    source = metadata['file_url']
                
                # Determine safety rating
                rating = metadata.get('rating', 's')
                if rating in ['e', 'explicit']:
                    safety = "unsafe"
                elif rating in ['q', 'questionable']:
                    safety = "sketchy"
        except Exception as e:
            print(f"Warning: Could not read metadata: {e}")
    
    # Upload file
    token = get_file_token(filepath)
    
    if not token:
        upload_stats['failed'] += 1
        print(f"? Failed to upload: {filename}")
        return False
    
    # Create post
    post = create_post(token, tags, safety, source)
    
    if post:
        upload_stats['uploaded'] += 1
        print(f"û Successfully uploaded: {filename} ({len(tags)} tags)")
        return True
    else:
        upload_stats['failed'] += 1
        print(f"? Failed to create post: {filename}")
        return False

def count_files_to_process(directory):
    """Count how many files need to be processed"""
    count = 0
    if os.path.exists(directory):
        for root, dirs, files in os.walk(directory):
            for filename in files:
                if not filename.endswith('.json'):
                    count += 1
    return count

def monitor_and_upload():
    """Monitor download directory and upload files as they appear"""
    print("?? Upload monitor started")
    
    while not stop_event.is_set():
        # Check for new files
        if os.path.exists(DOWNLOAD_DIR):
            for root, dirs, files in os.walk(DOWNLOAD_DIR):
                for filename in files:
                    # Skip metadata files
                    if filename.endswith('.json'):
                        continue
                    
                    filepath = Path(root) / filename
                    file_key = str(filepath)
                    
                    # Skip if already processed or being processed
                    if file_key in processed_files:
                        continue
                    
                    # Check if file is completely downloaded (not being written to)
                    try:
                        # Check if file exists and is readable
                        if not filepath.exists():
                            continue
                        
                        initial_size = filepath.stat().st_size
                        
                        # Make sure file is not empty
                        if initial_size == 0:
                            continue
                        
                        # Wait and check if still being written
                        time.sleep(1)
                        
                        if not filepath.exists():
                            continue
                            
                        final_size = filepath.stat().st_size
                        
                        if initial_size != final_size:
                            continue  # Still being written
                        
                        # Extra check: try to open the file
                        try:
                            with open(filepath, 'rb') as test_file:
                                test_file.read(1)
                        except (PermissionError, IOError):
                            continue  # File still locked
                            
                    except Exception as e:
                        print(f"Warning: Could not check file {filename}: {e}")
                        continue
                    
                    # Mark as processed BEFORE uploading to prevent double-processing
                    processed_files.add(file_key)
                    
                    # Upload immediately
                    metadata_path = filepath.with_suffix(filepath.suffix + '.json')
                    upload_file(filepath, metadata_path)
        
        time.sleep(0.5)  # Check twice per second
    
    print(f"\n{'='*50}")
    print(f"Upload complete!")
    print(f"  Uploaded: {upload_stats['uploaded']}")
    print(f"  Failed: {upload_stats['failed']}")
    print(f"  Total: {upload_stats['total']}")
    print(f"{'='*50}")

def download_from_booru(url, limit=None):
    """Download images using gallery-dl"""
    print(f"Downloading from: {url}")
    
    # Reset state
    processed_files.clear()
    stop_event.clear()
    upload_stats['uploaded'] = 0
    upload_stats['failed'] = 0
    upload_stats['total'] = 0
    
    # Setup gallery-dl config first
    setup_gallery_dl_config()
    
    # Create download directory
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    
    # Start upload monitor in background
    print("\n?? Starting real-time upload monitor...")
    monitor_thread = Thread(target=monitor_and_upload, daemon=False)
    monitor_thread.start()
    
    # gallery-dl command
    cmd = [
        "gallery-dl",
        "--write-metadata",
        "--destination", DOWNLOAD_DIR,
        url
    ]
    
    if limit:
        cmd.extend(["--range", f"1-{limit}"])
    
    try:
        print("\n??  Starting download...\n")
        subprocess.run(cmd, check=True)
        print("\nû Download complete! Processing remaining files...")
        
        # Count total files
        upload_stats['total'] = count_files_to_process(DOWNLOAD_DIR)
        print(f"Found {upload_stats['total']} files to upload")
        
        # Process any files that were missed during download
        print("\n?? Checking for any missed files...")
        catch_up_count = 0
        for root, dirs, files in os.walk(DOWNLOAD_DIR):
            for filename in files:
                if filename.endswith('.json'):
                    continue
                
                filepath = Path(root) / filename
                file_key = str(filepath)
                
                if file_key not in processed_files:
                    processed_files.add(file_key)
                    metadata_path = filepath.with_suffix(filepath.suffix + '.json')
                    upload_file(filepath, metadata_path)
                    catch_up_count += 1
        
        if catch_up_count > 0:
            print(f"û Processed {catch_up_count} missed files")
        
        # Give time for all files to be uploaded
        print("? Waiting for all uploads to complete...")
        last_count = 0
        no_change_count = 0
        
        while True:
            current_count = upload_stats['uploaded'] + upload_stats['failed']
            
            if current_count >= upload_stats['total'] and upload_stats['total'] > 0:
                print("\nû All files processed!")
                break
            
            # Check if we're making progress
            if current_count == last_count:
                no_change_count += 1
                if no_change_count >= 20:  # 20 seconds with no progress
                    print(f"\n??  No progress for 20 seconds. Checking for remaining files...")
                    remaining = upload_stats['total'] - current_count
                    if remaining > 0:
                        print(f"   Still {remaining} files remaining, continuing to wait...")
                        no_change_count = 0  # Reset counter
                    else:
                        break
            else:
                no_change_count = 0
                last_count = current_count
            
            print(f"Progress: {current_count}/{upload_stats['total']} processed...", end='\r')
            time.sleep(1)
        
        # Stop the monitor
        stop_event.set()
        monitor_thread.join(timeout=5)
        
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error downloading: {e}")
        stop_event.set()
        monitor_thread.join(timeout=5)
        return False
    except KeyboardInterrupt:
        print("\n\n??  Interrupted by user!")
        stop_event.set()
        monitor_thread.join(timeout=5)
        return False

def main():
    print("Booru to Szurubooru Uploader (Real-time)")
    print("="*50)
    
    # Get URL from user
    url = input("Enter booru URL (post URL, tag search, or user page): ").strip()
    
    # Optional: limit number of downloads
    limit_input = input("Limit number of downloads? (press Enter for no limit, or enter a number): ").strip()
    limit = int(limit_input) if limit_input.isdigit() else None
    
    # Download and upload
    download_from_booru(url, limit)

if __name__ == "__main__":
    main()#!/usr/bin/env python3
"""
Booru to Szurubooru Uploader (Real-time upload version)
Downloads images from booru sites using gallery-dl and uploads them to Szurubooru instantly
"""

import json
import os
import subprocess
import requests
from pathlib import Path
import time
from threading import Thread, Event
from queue import Queue

# Configuration
SZURU_URL = "YOUR_SZURUBOORU_URL_HERE"  # e.g., "https://lboorus.lmms.wtf"
SZURU_USER = "YOUR_SZURUBOORU_USERNAME_HERE"
SZURU_TOKEN = "YOUR_SZURUBOORU_API_TOKEN_HERE"  # e.g., "396ec236-80b6-4232-861e-39d613db3ffc"
DOWNLOAD_DIR = "./booru_downloads"

# Rule34 API credentials
RULE34_API_KEY = "YOUR_RULE34_API_KEY_HERE"
RULE34_USER_ID = "YOUR_RULE34_USER_ID_HERE"

# Szurubooru API headers
import base64

auth_string = f"{SZURU_USER}:{SZURU_TOKEN}"
auth_token = base64.b64encode(auth_string.encode()).decode('ascii')

headers = {
    "Authorization": f"Token {auth_token}",
    "Accept": "application/json"
}

# Track processed files
processed_files = set()
stop_event = Event()
upload_stats = {"uploaded": 0, "failed": 0, "total": 0}

def setup_gallery_dl_config():
    """Setup gallery-dl configuration with Rule34 API credentials"""
    config_dir = Path.home() / ".config" / "gallery-dl"
    if os.name == 'nt':  # Windows
        config_dir = Path(os.environ.get('APPDATA', '')) / "gallery-dl"
    
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.json"
    
    # Create or update config
    config = {}
    if config_file.exists():
        with open(config_file, 'r') as f:
            try:
                config = json.load(f)
            except:
                config = {}
    
    # Add Rule34 credentials
    if "extractor" not in config:
        config["extractor"] = {}
    if "rule34" not in config["extractor"]:
        config["extractor"]["rule34"] = {}
    
    config["extractor"]["rule34"]["api-key"] = RULE34_API_KEY
    config["extractor"]["rule34"]["user-id"] = RULE34_USER_ID
    
    # Save config
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"û Gallery-dl config updated")

def get_file_token(filepath):
    """Upload file and get token from Szurubooru"""
    try:
        with open(filepath, 'rb') as f:
            files = {'content': f}
            response = requests.post(
                f"{SZURU_URL}/api/uploads",
                headers=headers,
                files=files,
                timeout=60
            )
            
            if response.status_code == 200:
                return response.json()['token']
            else:
                print(f"Upload error: {response.status_code} - {response.text}")
                return None
    except Exception as e:
        print(f"Error uploading file: {e}")
        return None

def create_post(token, tags, safety="safe", source=None):
    """Create a post in Szurubooru"""
    try:
        data = {
            "tags": tags,
            "safety": safety,
            "contentToken": token
        }
        
        if source:
            data["source"] = source
        
        response = requests.post(
            f"{SZURU_URL}/api/posts",
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Post creation error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Error creating post: {e}")
        return None

def upload_file(filepath, metadata_path):
    """Upload a single file to Szurubooru"""
    filename = filepath.name
    print(f"\n?? Uploading ({upload_stats['uploaded'] + upload_stats['failed'] + 1}/{upload_stats['total']}): {filename}")
    
    # Read metadata if available
    tags = []
    source = None
    safety = "safe"
    
    if metadata_path.exists():
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
                
                # Extract tags
                if 'tags' in metadata:
                    if isinstance(metadata['tags'], list):
                        tags = metadata['tags']
                    elif isinstance(metadata['tags'], str):
                        tags = metadata['tags'].split()
                elif 'tag_string' in metadata:
                    tags = metadata['tag_string'].split()
                
                # Get source URL
                if 'source' in metadata:
                    source = metadata['source']
                elif 'file_url' in metadata:
                    source = metadata['file_url']
                
                # Determine safety rating
                rating = metadata.get('rating', 's')
                if rating in ['e', 'explicit']:
                    safety = "unsafe"
                elif rating in ['q', 'questionable']:
                    safety = "sketchy"
        except Exception as e:
            print(f"Warning: Could not read metadata: {e}")
    
    # Upload file
    token = get_file_token(filepath)
    
    if not token:
        upload_stats['failed'] += 1
        print(f"? Failed to upload: {filename}")
        return False
    
    # Create post
    post = create_post(token, tags, safety, source)
    
    if post:
        upload_stats['uploaded'] += 1
        print(f"û Successfully uploaded: {filename} ({len(tags)} tags)")
        return True
    else:
        upload_stats['failed'] += 1
        print(f"? Failed to create post: {filename}")
        return False

def count_files_to_process(directory):
    """Count how many files need to be processed"""
    count = 0
    if os.path.exists(directory):
        for root, dirs, files in os.walk(directory):
            for filename in files:
                if not filename.endswith('.json'):
                    count += 1
    return count

def monitor_and_upload():
    """Monitor download directory and upload files as they appear"""
    print("?? Upload monitor started")
    
    while not stop_event.is_set():
        # Check for new files
        if os.path.exists(DOWNLOAD_DIR):
            for root, dirs, files in os.walk(DOWNLOAD_DIR):
                for filename in files:
                    # Skip metadata files
                    if filename.endswith('.json'):
                        continue
                    
                    filepath = Path(root) / filename
                    file_key = str(filepath)
                    
                    # Skip if already processed or being processed
                    if file_key in processed_files:
                        continue
                    
                    # Check if file is completely downloaded (not being written to)
                    try:
                        # Check if file exists and is readable
                        if not filepath.exists():
                            continue
                        
                        initial_size = filepath.stat().st_size
                        
                        # Make sure file is not empty
                        if initial_size == 0:
                            continue
                        
                        # Wait and check if still being written
                        time.sleep(1)
                        
                        if not filepath.exists():
                            continue
                            
                        final_size = filepath.stat().st_size
                        
                        if initial_size != final_size:
                            continue  # Still being written
                        
                        # Extra check: try to open the file
                        try:
                            with open(filepath, 'rb') as test_file:
                                test_file.read(1)
                        except (PermissionError, IOError):
                            continue  # File still locked
                            
                    except Exception as e:
                        print(f"Warning: Could not check file {filename}: {e}")
                        continue
                    
                    # Mark as processed BEFORE uploading to prevent double-processing
                    processed_files.add(file_key)
                    
                    # Upload immediately
                    metadata_path = filepath.with_suffix(filepath.suffix + '.json')
                    upload_file(filepath, metadata_path)
        
        time.sleep(0.5)  # Check twice per second
    
    print(f"\n{'='*50}")
    print(f"Upload complete!")
    print(f"  Uploaded: {upload_stats['uploaded']}")
    print(f"  Failed: {upload_stats['failed']}")
    print(f"  Total: {upload_stats['total']}")
    print(f"{'='*50}")

def download_from_booru(url, limit=None):
    """Download images using gallery-dl"""
    print(f"Downloading from: {url}")
    
    # Reset state
    processed_files.clear()
    stop_event.clear()
    upload_stats['uploaded'] = 0
    upload_stats['failed'] = 0
    upload_stats['total'] = 0
    
    # Setup gallery-dl config first
    setup_gallery_dl_config()
    
    # Create download directory
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    
    # Start upload monitor in background
    print("\n?? Starting real-time upload monitor...")
    monitor_thread = Thread(target=monitor_and_upload, daemon=False)
    monitor_thread.start()
    
    # gallery-dl command
    cmd = [
        "gallery-dl",
        "--write-metadata",
        "--destination", DOWNLOAD_DIR,
        url
    ]
    
    if limit:
        cmd.extend(["--range", f"1-{limit}"])
    
    try:
        print("\n??  Starting download...\n")
        subprocess.run(cmd, check=True)
        print("\nû Download complete! Processing remaining files...")
        
        # Count total files
        upload_stats['total'] = count_files_to_process(DOWNLOAD_DIR)
        print(f"Found {upload_stats['total']} files to upload")
        
        # Process any files that were missed during download
        print("\n?? Checking for any missed files...")
        catch_up_count = 0
        for root, dirs, files in os.walk(DOWNLOAD_DIR):
            for filename in files:
                if filename.endswith('.json'):
                    continue
                
                filepath = Path(root) / filename
                file_key = str(filepath)
                
                if file_key not in processed_files:
                    processed_files.add(file_key)
                    metadata_path = filepath.with_suffix(filepath.suffix + '.json')
                    upload_file(filepath, metadata_path)
                    catch_up_count += 1
        
        if catch_up_count > 0:
            print(f"û Processed {catch_up_count} missed files")
        
        # Give time for all files to be uploaded
        print("? Waiting for all uploads to complete...")
        last_count = 0
        no_change_count = 0
        
        while True:
            current_count = upload_stats['uploaded'] + upload_stats['failed']
            
            if current_count >= upload_stats['total'] and upload_stats['total'] > 0:
                print("\nû All files processed!")
                break
            
            # Check if we're making progress
            if current_count == last_count:
                no_change_count += 1
                if no_change_count >= 20:  # 20 seconds with no progress
                    print(f"\n??  No progress for 20 seconds. Checking for remaining files...")
                    remaining = upload_stats['total'] - current_count
                    if remaining > 0:
                        print(f"   Still {remaining} files remaining, continuing to wait...")
                        no_change_count = 0  # Reset counter
                    else:
                        break
            else:
                no_change_count = 0
                last_count = current_count
            
            print(f"Progress: {current_count}/{upload_stats['total']} processed...", end='\r')
            time.sleep(1)
        
        # Stop the monitor
        stop_event.set()
        monitor_thread.join(timeout=5)
        
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error downloading: {e}")
        stop_event.set()
        monitor_thread.join(timeout=5)
        return False
    except KeyboardInterrupt:
        print("\n\n??  Interrupted by user!")
        stop_event.set()
        monitor_thread.join(timeout=5)
        return False

def main():
    print("Booru to Szurubooru Uploader (Real-time)")
    print("="*50)
    
    # Get URL from user
    url = input("Enter booru URL (post URL, tag search, or user page): ").strip()
    
    # Optional: limit number of downloads
    limit_input = input("Limit number of downloads? (press Enter for no limit, or enter a number): ").strip()
    limit = int(limit_input) if limit_input.isdigit() else None
    
    # Download and upload
    download_from_booru(url, limit)

if __name__ == "__main__":
    main()
