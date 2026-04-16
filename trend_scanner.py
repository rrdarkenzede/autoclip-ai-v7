"""
trend_scanner.py — Viral Content Discovery v7.6 (SYNTAX STABILIZED)
URL FIX: Corrected .json path and added verbose HTTP logging.
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
    FIXED: Corrected URL path from /top/.json to /top.json
    """
    random.shuffle(REDLIB_INSTANCES)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    
    for inst in REDLIB_INSTANCES:
        try:
            # CORRECT SYNTAX: r/sub/top.json?t=week
            url = f"https://{inst}/r/{sub}/top.json?t={time_filter}"
            log.info(f"  [DISCOVERY] Calling: {url}")
            
            resp = requests.get(
                url, 
                impersonate="chrome110", 
                headers=headers,
                timeout=15
            )
            
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    if isinstance(data, dict) and 'data' in data:
                        log.info(f"  [REDLIB] ✓ Success via {inst}")
                        return data
                except:
                    log.warning(f"  [REDLIB] ⚠ {inst} returned non-JSON content.")
            else:
                log.warning(f"  [REDLIB] ✗ {inst} failed with HTTP {resp.status_code}")
                
        except Exception as e:
            log.debug(f"  [REDLIB] ✗ {inst} error: {str(e)}")
            continue
            
    return None

def scan_reddit_for_viral_videos(custom_subs=None, time_filter="week", limit=30):
    """
    Main Reddit Discovery: Stealth Brute Force v7.6.
    """
    subs = list(DEFAULT_SUBS)
    if custom_subs:
        for s in custom_subs:
            s_clean = s.strip().replace("r/", "")
            if s_clean and s_clean not in subs: subs.append(s_clean)

    found_videos = []
    log.info(f"🕵️ Total Hunting Ground: {len(subs)} subreddits (Filter: {time_filter})")

    for sub in subs:
        log.info(f"  [REDDIT] Checking r/{sub}...")
        data = _fetch_via_redlib(sub, time_filter)
            
        if data:
            posts = data.get("data", {}).get("children", [])
            log.info(f"    - Found {len(posts)} posts in r/{sub}.")
            for post in posts:
                pd = post.get("data", {})
                urls = _recursive_extract_urls(pd)
                for u in urls:
                    found_videos.append({
                        "url": _normalize_yt(u),
                        "score": pd.get("score", 0),
                        "title": pd.get("title", "")
                    })
        
        time.sleep(random.uniform(1.0, 2.0))

    # Sort
    found_videos.sort(key=lambda x: x["score"], reverse=True)
    unique_urls = list(dict.fromkeys([v["url"] for v in found_videos]))
    
    log.info(f"✅ FINAL Discovery result: {len(unique_urls)} bangers identified.")
    return {"urls": unique_urls}

def discover_viral_content():
    log.info("\n" + "🎯" * 20)
    log.info("STARTING DISCOVERY: BANGER HUNTER v7.6")
    log.info("🎯" * 20)
    
    all_urls = []
    try:
        reddit_res = scan_reddit_for_viral_videos()
        all_urls.extend(reddit_res["urls"])
    except Exception as e:
        log.error(f"❌ Master Discovery failed: {e}")
        
    unique_total = list(dict.fromkeys(all_urls))
    log.info(f"\n🏆 GRAND TOTAL: {len(unique_total)} unique links discovered.")
    return unique_total

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    discover_viral_content()
