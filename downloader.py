"""
downloader.py — AutoClipAI v7.8 (RESILIENT DOWNLOADER)
Handles video extraction using yt-dlp + OMEGA Bypass.
Added: Enhanced client fallback and OMEGA integration.
"""

import os
import subprocess
import logging
import json
import time
from omega_bypass import omega

log = logging.getLogger("AutoClipAI.Downloader")

def download_video(url, output_path):
    """
    Downloads a video using yt-dlp with OMEGA proxy bypass.
    Attempts multiple client signatures if rejected.
    """
    log.info(f"📥 Attempting download: {url}")
    
    # Base command with OMEGA proxy
    cmd = [
        "yt-dlp",
        url,
        "-o", output_path,
        "--no-playlist",
        "--merge-output-format", "mp4",
        "--proxy", omega.get_proxy_url(),
        "--no-warnings"
    ]
    
    # Try different client signatures (Bypass strategy)
    client_args = [
        ["--extractor-args", "youtube:player-client=ios,web,tv"],
        ["--extractor-args", "youtube:player-client=android,web"],
        ["--extractor-args", "youtube:player-client=web"]
    ]
    
    for args in client_args:
        try:
            full_cmd = cmd + args
            log.info(f"  [ATTEMPT] Using clients: {args[-1]}")
            result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                log.info(f"✅ Download SUCCESS: {output_path}")
                return True
            else:
                err_msg = result.stderr.lower()
                if "sign in" in err_msg or "bot" in err_msg:
                    log.warning("🛡️ YouTube detection triggered. Attempting next signature...")
                else:
                    log.error(f"❌ yt-dlp error: {result.stderr.strip()}")
        except Exception as e:
            log.error(f"❌ System error during download: {e}")
            
    return False

def fill_stockpile(url):
    """
    Simulates the analysis and preparation of a video for the stockpile.
    Returns the local path if successful.
    """
    file_id = f"clip_{int(time.time())}"
    local_path = f"downloads/{file_id}.mp4"
    json_path = f"downloads/{file_id}.json"
    
    if not os.path.exists("downloads"): os.makedirs("downloads")
    
    if download_video(url, local_path):
        # Create metadata for the analyzer later
        meta = {
            "title": f"Viral Clip {file_id}",
            "source_url": url,
            "timestamp": time.time(),
            "status": "ready"
        }
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f)
        return local_path
        
    return None

def search_trending_videos(query, limit=5):
    """Wraps the YouTube search logic if needed as a standalone."""
    # This is now integrated in trend_scanner.py v7.7
    pass
