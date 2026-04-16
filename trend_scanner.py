"""
trend_scanner.py — Viral Content Discovery v7.3 (BRUTE FORCE STEALTH)
Scrapes Reddit and X/Twitter for viral YouTube links WITHOUT API KEYS.

Features:
- Primary: Direct Reddit JSON scraping via curl_cffi (Chrome 110 impersonation).
- Secondary: Automatic fallback to Redlib instances if blocked (403/429).
- Tertiary: Twitter/X scraping via Nitter instances.
"""

import re
import json
import time
import random
import logging
from curl_cffi import requests

log = logging.getLogger("AutoClipAI.TrendScanner")

# =====================================================================
# CONFIGURATION & FRONTENDS
# =====================================================================
REDLIB_INSTANCES = [
    "l.opnxng.com",
    "redlib.catsarch.com",
    "safereddit.com",
    "redlib.net",
    "redlib.ducks.party",
    "libreddit.kavin.rocks",
    "redlib.pussthecat.org"
]

DEFAULT_SUBS = [
    "videos", "funny", "Unexpected", "nextfuckinglevel", "TikTokCringe", 
    "facepalm", "therewasanattempt", "WatchPeopleDieInside", "ContagiousLaughter",
    "AbruptChaos", "oddlysatisfying", "Damnthatsinteresting", "HolUp", "meirl"
]

def _extract_video_urls(text):
    """Cleanly extracts YT and TikTok links."""
    patterns = [
        r'(https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+)',
        r'(https?://youtu\.be/[\w-]+)',
        r'(https?://(?:www\.)?youtube\.com/shorts/[\w-]+)',
        r'(https?://(?:www\.)?tiktok\.com/@[\w.-]+/video/\d+)',
        r'(https?://vm\.tiktok\.com/[\w-]+)',
    ]
    urls = []
    if text:
        for p in patterns:
            urls.extend(re.findall(p, text))
    return list(set(urls))

def _normalize_yt(url):
    match = re.search(r'youtu\.be/([\w-]+)', url)
    if match: return f"https://www.youtube.com/watch?v={match.group(1)}"
    match = re.search(r'youtube\.com/shorts/([\w-]+)', url)
    if match: return f"https://www.youtube.com/watch?v={match.group(1)}"
    return url

# =====================================================================
# REDDIT STEALTH ENGINE
# =====================================================================
def _fetch_with_stealth(url):
    """Fetches a URL using curl_cffi to bypass TLS fingerprinting."""
    try:
        # We impersonate a recent Chrome browser to fool Reddit's anti-bot
        resp = requests.get(url, impersonate="chrome110", timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        log.warning(f"  [STEALTH] Direct access to Reddit failed: {e}")
        return None

def _fetch_via_redlib(sub, time_filter="day"):
    """Fallback: Scrapes data via a Redlib instance (Alternative frontend)."""
    random.shuffle(REDLIB_INSTANCES)
    for inst in REDLIB_INSTANCES:
        try:
            # Redlib supports JSON output via .json suffix
            url = f"https://{inst}/r/{sub}/top/.json?t={time_filter}"
            resp = requests.get(url, impersonate="chrome110", timeout=10)
            if resp.status_code == 200:
                log.info(f"  [REDLIB] ✓ Success via {inst}")
                return resp.json()
        except:
            continue
    return None

def scan_reddit_for_viral_videos(custom_subs=None, time_filter="day", limit=25):
    """
    Main Reddit Discovery: Stealth Scraping (No API Keys).
    """
    subs = list(DEFAULT_SUBS)
    if custom_subs:
        for s in custom_subs:
            s_clean = s.strip().replace("r/", "")
            if s_clean and s_clean not in subs: subs.append(s_clean)

    found_videos = []
    log.info(f"🕵️ Scanning {len(subs)} subreddits for bangers...")

    for sub in subs:
        log.info(f"  [REDDIT] Checking r/{sub}...")
        
        # 🟢 Try Direct Stealth First
        data = _fetch_with_stealth(f"https://www.reddit.com/r/{sub}/top.json?t={time_filter}&limit={limit}")
        
        # 🟡 Fallback to Redlib if Direct is blocked
        if not data:
            log.warning(f"  [REDDIT] 403/Blocked on direct r/{sub}. Trying Redlib Fallback...")
            data = _fetch_via_redlib(sub, time_filter)
            
        if data:
            posts = data.get("data", {}).get("children", [])
            for post in posts:
                pd = post.get("data", {})
                full_text = f"{pd.get('title')} {pd.get('selftext')} {pd.get('url')}"
                urls = _extract_video_urls(full_text)
                for u in urls:
                    found_videos.append({
                        "url": _normalize_yt(u),
                        "score": pd.get("score", 0),
                        "title": pd.get("title", "")
                    })
        
        time.sleep(random.uniform(1.0, 2.5)) # Avoid rate limits

    # Sort by score (Reddit karma)
    found_videos.sort(key=lambda x: x["score"], reverse=True)
    unique_urls = list(dict.fromkeys([v["url"] for v in found_videos]))
    
    log.info(f"✅ Reddit Scan Complete: {len(unique_urls)} bangers found.")
    return {"urls": unique_urls}

# =====================================================================
# X/TWITTER DISCOVERY (NITTER FALLBACK)
# =====================================================================
def scan_x_for_viral_videos(queries=None):
    """Searches X via Nitter instances (Direct X scraping is too hard)."""
    nitter_instances = ["nitter.privacydev.net", "nitter.poast.org", "nitter.1d4.us"]
    search_queries = queries or ["youtube.com viral", "tiktok.com banger"]
    found_urls = []

    for query in search_queries:
        for inst in nitter_instances:
            try:
                url = f"https://{inst}/search?f=tweets&q={requests.utils.quote(query)}"
                resp = requests.get(url, impersonate="chrome110", timeout=10)
                if resp.status_code == 200:
                    found_urls.extend(_extract_video_urls(resp.text))
                    break
            except: continue
            
    final = list(dict.fromkeys([_normalize_yt(u) for u in found_urls]))
    log.info(f"✅ X/Twitter Scan Complete: {len(final)} videos found.")
    return {"urls": final}

# =====================================================================
# MASTER DISCOVERY
# =====================================================================
def discover_viral_content():
    log.info("\n" + "🔥" * 20)
    log.info("STARTING DISCOVERY: BRUTE FORCE v7.3")
    log.info("🔥" * 20)
    
    all_urls = []
    
    # 1. Reddit (Stealth)
    try:
        reddit_res = scan_reddit_for_viral_videos()
        all_urls.extend(reddit_res["urls"])
    except Exception as e:
        log.error(f"❌ Reddit failure: {e}")
        
    # 2. X/Twitter (Nitter)
    try:
        x_res = scan_x_for_viral_videos()
        all_urls.extend(x_res["urls"])
    except Exception as e:
        log.error(f"❌ X failure: {e}")
        
    unique_total = list(dict.fromkeys(all_urls))
    log.info(f"\n🏆 GRAND TOTAL: {len(unique_total)} unique links discovered.")
    return unique_total

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    discover_viral_content()
