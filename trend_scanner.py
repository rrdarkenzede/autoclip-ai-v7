"""
trend_scanner.py — Viral Content Discovery v7.5 (BANGER HUNTER)
ADVANCED EXTRACTION: Optimized for Redlib JSON and resilient scraping.
"""

import re
import json
import time
import random
import logging
from curl_cffi import requests

log = logging.getLogger("AutoClipAI.TrendScanner")

# =====================================================================
# CONFIGURATION
# =====================================================================
REDLIB_INSTANCES = [
    "redlib.pussthecat.org",
    "l.opnxng.com",
    "redlib.catsarch.com",
    "safereddit.com",
    "redlib.net",
    "redlib.ducks.party"
]

DEFAULT_SUBS = [
    "videos", "funny", "Unexpected", "nextfuckinglevel", "TikTokCringe", 
    "facepalm", "therewasanattempt", "WatchPeopleDieInside", "ContagiousLaughter",
    "AbruptChaos", "oddlysatisfying", "Damnthatsinteresting", "HolUp", "meirl"
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
    """
    Scans a JSON object (dict/list) recursively for social media URLs.
    Ensures no URL is missed regardless of the field name.
    """
    found = []
    if isinstance(data, dict):
        for v in data.values():
            found.extend(_recursive_extract_urls(v))
    elif isinstance(data, list):
        for item in data:
            found.extend(_recursive_extract_urls(item))
    elif isinstance(data, str):
        found.extend(_extract_video_urls(data))
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
    """
    Fallback: Scrapes data via Redlib. 
    Verifies that 'data' exists before returning success.
    """
    random.shuffle(REDLIB_INSTANCES)
    for inst in REDLIB_INSTANCES:
        try:
            url = f"https://{inst}/r/{sub}/top/.json?t={time_filter}"
            log.info(f"  [DISCOVERY] Querying: {url}")
            resp = requests.get(url, impersonate="chrome110", timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                # Validate that it's a real Reddit-like listing
                if isinstance(data, dict) and 'data' in data and 'children' in data['data']:
                    log.info(f"  [REDLIB] ✓ Success via {inst} (Found {len(data['data']['children'])} posts)")
                    return data
                else:
                    log.warning(f"  [REDLIB] ⚠ Empty or invalid JSON from {inst}")
        except Exception as e:
            continue
    return None

def scan_reddit_for_viral_videos(custom_subs=None, time_filter="week", limit=30):
    """
    Main Reddit Discovery: Stealth Brute Force v7.5.
    """
    subs = list(DEFAULT_SUBS)
    if custom_subs:
        for s in custom_subs:
            s_clean = s.strip().replace("r/", "")
            if s_clean and s_clean not in subs: subs.append(s_clean)

    found_videos = []
    log.info(f"🕵️ Hunting in {len(subs)} subreddits (Filter: {time_filter})...")

    for sub in subs:
        log.info(f"  [REDDIT] Checking r/{sub}...")
        
        # 🟢 Try Redlib Fallback (Direct Reddit is skipped as it always 403s on GH)
        data = _fetch_via_redlib(sub, time_filter)
            
        if data:
            posts = data.get("data", {}).get("children", [])
            for post in posts:
                pd = post.get("data", {})
                # Use recursive extraction on the entire post object to find ANY hidden URL
                urls = _recursive_extract_urls(pd)
                for u in urls:
                    found_videos.append({
                        "url": _normalize_yt(u),
                        "score": pd.get("score", 0),
                        "title": pd.get("title", "")
                    })
        
        time.sleep(random.uniform(0.5, 1.5))

    # Sort by score
    found_videos.sort(key=lambda x: x["score"], reverse=True)
    unique_urls = list(dict.fromkeys([v["url"] for v in found_videos]))
    
    log.info(f"✅ Reddit Scan Complete: {len(unique_urls)} bangers identified.")
    return {"urls": unique_urls}

def discover_viral_content():
    log.info("\n" + "🎯" * 20)
    log.info("STARTING DISCOVERY: BANGER HUNTER v7.5")
    log.info("🎯" * 20)
    
    all_urls = []
    
    # We focus on Reddit as it's the most reliable source for high-score JSON.
    try:
        reddit_res = scan_reddit_for_viral_videos()
        all_urls.extend(reddit_res["urls"])
    except Exception as e:
        log.error(f"❌ Reddit failure: {e}")
        
    unique_total = list(dict.fromkeys(all_urls))
    log.info(f"\n🏆 GRAND TOTAL: {len(unique_total)} unique links discovered.")
    return unique_total

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    discover_viral_content()
