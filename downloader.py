"""
downloader.py — AutoClipAI v7.2 — RESILIENT DOWNLOADER
Handles YouTube & TikTok downloads with multi-layer bypasses (OMEGA, Phantom, Mirror).
FIXED: Integrated Search Fallback and optimized for GitHub Actions environment.
"""

import os
import requests
import re
import hashlib
import json
import time
import logging
import yt_dlp
import sys
from omega_bypass import omega
from invidious_gateway import gateway

log = logging.getLogger("AutoClipAI.Downloader")

HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "processed_urls.json")
MIN_VIEWS_THRESHOLD = 500_000

# Cache for detection status
_DETECTION_STATE = {"omega_active": False}

def safe_ydl_run(url_or_query, ydl_opts):
    """
    Executes yt-dlp with multi-stage bypasses.
    1. Normal (Mobile/TV fingerprints)
    2. OMEGA Bypass (PO-Token generator)
    3. Mirror (Invidious API)
    """
    # 1. PHANTOM CLOAK (Stealth Clients)
    stealth_opts = ydl_opts.copy()
    stealth_opts.update({
        'extractor_args': {'youtube': {'player_client': ['android', 'ios', 'tv_embedded'], 'skip': ['webpage']}},
        'user_agent': 'com.google.android.youtube/19.05.36 (Linux; U; Android 14; en_US; Pixel 8 Pro) gzip',
        'nocheckcertificate': True,
        'quiet': True
    })

    # Try Normal/Stealth first
    try:
        with yt_dlp.YoutubeDL(stealth_opts) as ydl:
            return ydl.extract_info(url_or_query, download=False)
    except Exception as e:
        err = str(e)
        if any(x in err for x in ["Sign in", "403", "PO Token", "Confirmation"]):
            log.warning("🛡️ YouTube detection triggered. Activating OMEGA Bypass...")
            if not omega.is_running: omega.start_sidecar()
            
            omega_opts = omega.get_ydl_opts(stealth_opts)
            try:
                with yt_dlp.YoutubeDL(omega_opts) as ydl:
                    return ydl.extract_info(url_or_query, download=False)
            except Exception as e2:
                log.error(f"❌ OMEGA Fail: {e2}")
                
    # LAST RESORT: Mirror (if it's a direct URL)
    if "youtube.com" in str(url_or_query) or "youtu.be" in str(url_or_query):
        return _fetch_via_mirror(url_or_query)
        
    return None

def _fetch_via_mirror(url):
    """Last resort metadata fetch via Invidious API."""
    video_id_match = re.search(r"(?:v=|\/|be\/)([\w-]{11})", url)
    if not video_id_match: return None
    video_id = video_id_match.group(1)
    
    # Try the gateway we already defined
    results = gateway.get_trending() # Just to get an instance
    inst = gateway._get_base_url()
    try:
        api_url = f"{inst}/api/v1/videos/{video_id}"
        resp = requests.get(api_url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            log.info(f"✅ Secured metadata via Mirror ({inst})")
            return {
                'id': video_id, 'title': data.get('title'),
                'view_count': data.get('viewCount', 0),
                'duration': data.get('lengthSeconds', 0),
                'webpage_url': f"https://www.youtube.com/watch?v={video_id}"
            }
    except: pass
    return None

def is_already_processed(url):
    if not os.path.exists(HISTORY_FILE): return False
    with open(HISTORY_FILE, "r") as f:
        try: return url in json.load(f)
        except: return False

def mark_as_processed(url):
    history = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            try: history = json.load(f)
            except: pass
    history.append(url)
    with open(HISTORY_FILE, "w") as f: json.dump(list(set(history)), f, indent=2)

def get_video_info(url):
    ydl_opts = {'quiet': True, 'skip_download': True}
    info = safe_ydl_run(url, ydl_opts)
    if info:
        return {
            "id": info.get("id"), "title": info.get("title"),
            "views": info.get("view_count", 0) or 0,
            "duration": info.get("duration", 0) or 0,
            "url": url
        }
    return None

def download_youtube_video(url, output_dir="downloads"):
    if is_already_processed(url): return None
    info = get_video_info(url)
    if not info or info['views'] < MIN_VIEWS_THRESHOLD: 
        mark_as_processed(url); return None
        
    log.info(f"⬇️ Downloading: {info['title']} ({info['views']:,} views)")
    if not os.path.exists(output_dir): os.makedirs(output_dir)
    
    path = os.path.join(output_dir, f"source_{hashlib.md5(url.encode()).hexdigest()[:10]}.mp4")
    ydl_opts = {
        'format': 'bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]',
        'outtmpl': path, 'quiet': True, 'merge_output_format': 'mp4'
    }
    
    # Try OMEGA for download if available
    final_opts = omega.get_ydl_opts(ydl_opts) if omega.is_running else ydl_opts
    try:
        with yt_dlp.YoutubeDL(final_opts) as ydl:
            ydl.download([url])
            return path
    except: return None

def search_trending_videos(search_queries, max_results=5):
    """
    The heart of discovery. Uses the resilient gateway.
    """
    viral_urls = []
    for query in search_queries:
        log.info(f"🔎 Searching viral content for: {query}")
        results = gateway.search_viral(query)
        for v in results:
            url = v['url']
            if is_already_processed(url): continue
            info = get_video_info(url)
            if info and info['views'] >= MIN_VIEWS_THRESHOLD:
                log.info(f"  🔥 Viral Found: {info['title']}")
                viral_urls.append(url)
                if len(viral_urls) >= max_results: return viral_urls
    return viral_urls

def fill_stockpile(url):
    """Wrapper to download and signal readiness."""
    return download_youtube_video(url)

if __name__ == "__main__":
    pass
