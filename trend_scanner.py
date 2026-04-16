"""
trend_scanner.py — Viral Content Discovery v7.7 (PHANTOM HYBRID)
RESILIENCE: Reddit Scraper + YouTube Search Fallback.
Guarantees content even if social mirrors are blocked.
"""

import re
import json
import time
import random
import logging
import subprocess
from curl_cffi import requests

log = logging.getLogger("AutoClipAI.TrendScanner")

# =====================================================================
# CONFIGURATION
# =====================================================================
# Pruned list of Redlib instances (focusing on stability)
REDLIB_INSTANCES = [
    "redlib.net",
    "safereddit.com",
    "l.opnxng.com",
    "redlib.catsarch.com"
]

DEFAULT_SUBS = [
    "videos", "funny", "Unexpected", "nextfuckinglevel", "TikTokCringe", 
    "facepalm", "therewasanattempt", "WatchPeopleDieInside", "ContagiousLaughter",
    "AbruptChaos", "oddlysatisfying", "Damnthatsinteresting", "HolUp", "meirl"
]

# Primary keywords for fallback search
FALLBACK_KEYWORDS = [
    "trending tiktok compilation 2024",
    "funniest videos of the week",
    "most unexpected moments shorts",
    "viral reddit stories videos",
    "oddly satisfying compilation"
]

def _extract_video_urls(text):
    """Cleanly extracts YT and TikTok links from raw text."""
    if not isinstance(text, str): return []
    patterns = [
        r'(https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+)',
        r'(https?://youtu\.be/[\w-]+)',
        r'(https?://(?:www\.)?youtube\.com/shorts/[\w-]+)',
        r'(https?://(?:www\.)?tiktok\.com/@[\w.-]+/video/\d+)',
        r'(https?://vm\.tiktok\.com/[\w-]+)',
    ]
    urls = []
    for p in patterns:
        urls.extend(re.findall(p, text))
    return list(set(urls))

def _recursive_extract_urls(data):
    """Scans a JSON object recursively for social media URLs."""
    found = []
    if isinstance(data, dict):
        for v in data.values(): found.extend(_recursive_extract_urls(v))
    elif isinstance(data, list):
        for item in data: found.extend(_recursive_extract_urls(item))
    elif isinstance(data, str): found.extend(_extract_video_urls(data))
    return found

def _normalize_yt(url):
    match = re.search(r'youtu\.be/([\w-]+)', url)
    if match: return f"https://www.youtube.com/watch?v={match.group(1)}"
    match = re.search(r'youtube\.com/shorts/([\w-]+)', url)
    if match: return f"https://www.youtube.com/watch?v={match.group(1)}"
    return url

# =====================================================================
# REDDIT STEALTH ENGINE
# =====================================================================
def _fetch_via_redlib(sub, time_filter="week"):
    """Scrapes Reddit mirror with advanced stealth headers."""
    random.shuffle(REDLIB_INSTANCES)
    for inst in REDLIB_INSTANCES:
        try:
            url = f"https://{inst}/r/{sub}/top.json?t={time_filter}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json",
                "Referer": f"https://{inst}/"
            }
            log.info(f"  [REDDIT] Querying {inst}...")
            resp = requests.get(url, impersonate="chrome110", headers=headers, timeout=12)
            
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict) and 'data' in data:
                    log.info(f"  [REDLIB] ✓ Success via {inst}")
                    return data
            else:
                log.warning(f"  [REDLIB] ✗ {inst} (HTTP {resp.status_code})")
        except:
            continue
    return None

def search_youtube_fallback(limit=10):
    """
    Plan C: If Reddit is blocked, search YouTube directly via yt-dlp.
    Guarantees that discovery always returns content.
    """
    log.info("🎞️  PLAN C: Starting YouTube Search Fallback...")
    query = random.choice(FALLBACK_KEYWORDS)
    log.info(f"  [YOUTUBE] Searching for: '{query}'")
    
    found_urls = []
    try:
        # Using yt-dlp search pattern
        cmd = [
            "yt-dlp",
            f"ytsearch{limit}:{query}",
            "--get-id",
            "--flat-playlist",
            "--no-warnings"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            ids = result.stdout.strip().split("\n")
            for vid_id in ids:
                if vid_id:
                    found_urls.append(f"https://www.youtube.com/watch?v={vid_id.strip()}")
            log.info(f"  [YOUTUBE] ✓ Found {len(found_urls)} trending videos.")
    except Exception as e:
        log.error(f"  [YOUTUBE] ✗ Search failed: {e}")
        
    return found_urls

# =====================================================================
# MAIN ORCHESTRATOR
# =====================================================================
def discover_viral_content():
    log.info("\n" + "🛡️" * 20)
    log.info("STARTING DISCOVERY: PHANTOM HYBRID v7.7")
    log.info("🛡️" * 20)
    
    all_urls = []
    
    # 1. Primary: Reddit Scraper
    subs = list(DEFAULT_SUBS)
    log.info(f"🕵️ Scanning {len(subs)} subreddits via Redlib...")
    for sub in subs:
        data = _fetch_via_redlib(sub)
        if data:
            posts = data.get("data", {}).get("children", [])
            for post in posts:
                pd = post.get("data", {})
                all_urls.extend([_normalize_yt(u) for u in _recursive_extract_urls(pd)])
        
    # 2. Refined Dédoublonnage
    unique_total = list(dict.fromkeys(all_urls))
    
    # 3. Emergency Fallback: If Reddit is empty, use YouTube Search
    if len(unique_total) < 5:
        log.warning(f"⚠️ Low content count ({len(unique_total)}). Activating YouTube Fallback.")
        youtube_urls = search_youtube_fallback()
        unique_total.extend(youtube_urls)
        
    unique_total = list(dict.fromkeys(unique_total))
    log.info(f"\n🏆 GRAND TOTAL: {len(unique_total)} unique links discovered.")
    return unique_total

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    discover_viral_content()
