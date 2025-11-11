# Booru to Szurubooru Uploader (Real-time)

This Python script facilitates the automatic and real-time uploading of content from various booru sites (like Rule34.net) to your personal [Szurubooru](https://szurubooru.xyz/) instance. It leverages the powerful download capabilities of `gallery-dl` and uploads files instantly as they finish downloading, along with their associated metadata (tags, source, safety rating).

## 🚀 Features

* **Real-time Uploading:** Files are uploaded to Szurubooru immediately after `gallery-dl` finishes downloading them.
* **Metadata Preservation:** Downloads associated `.json` metadata files and uses them to automatically populate tags, source URL, and safety rating (`safe`, `sketchy`, or `unsafe`) for the Szurubooru post.
* **Credential Handling:** Securely sets up `gallery-dl` configuration with API credentials for sites like Rule34.net to handle private downloads or rate limits.
* **Progress Monitoring:** Provides status updates during the download and upload phases.

## 🛠️ Prerequisites

Before running the script, ensure you have the following installed and configured:

1.  **Python 3:** The script requires Python 3.6 or newer.
2.  **Required Python Libraries:**
    ```bash
    pip install requests
    ```
3.  **gallery-dl:** The command-line downloader used to fetch content and metadata.
    * Installation instructions can be found on the [gallery-dl website](https://github.com/mikf/gallery-dl).

## ⚙️ Configuration

You must replace the placeholder values at the beginning of the `booruupfart.py` script with your actual credentials.

```python
# Configuration
SZURU_URL = "https://YOUR_SZURUBOORU_INSTANCE_URL_HERE"
SZURU_USER = "YOUR_SZURUBOORU_USERNAME_HERE"
SZURU_TOKEN = "YOUR_SZURUBOORU_API_TOKEN_HERE"
DOWNLOAD_DIR = "./booru_downloads" # Local directory where files are temporarily stored

# Rule34 API credentials (Used by gallery-dl)
RULE34_API_KEY = "YOUR_RULE34.NET_API_KEY_HERE"
RULE34_USER_ID = "YOUR_RULE34.NET_USER_ID_HERE"
