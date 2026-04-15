import os
import requests
import re
import hashlib
import json
import time
import logging
import yt_dlp
from editor import FFMPEG
from omega_bypass import omega
from invidious_gateway import DiscoveryGateway

log = logging.getLogger("AutoClipAI.Downloader")
gateway = DiscoveryGateway()

HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "processed_urls.json")

# =====================================================================
# MINIMUM VIEW THRESHOLD — We ONLY clip videos that already went viral
# =====================================================================
MIN_VIEWS_THRESHOLD = 500_000  # Minimum 500K views to even consider a video

# Global state to avoid re-trying cookies if DPAPI is locked
_COOKIE_FAILURE_CACHE = {"locked": False, "last_fail": 0}

def safe_ydl_run(url_or_query, ydl_opts):
    """
    Executes a yt-dlp call with automatic DPAPI fallback and Titanium Bypass.
    """
    global _COOKIE_FAILURE_CACHE
    browser = get_best_browser()
    
    # OMEGA PHANTOM CLOAK: Priority to TV and Embedded clients (harder to bot-detect)
    potential_clients = [
        ('tv_embedded', 'Mozilla/5.0 (PlayStation 5; 7.40) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.4 Safari/605.1.15'),
        ('tv', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 (SmartHub; SMART-TV; Sony; 2023)'),
        ('web_embedded', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'),
        ('android', 'com.google.android.youtube/19.05.36 (Linux; U; Android 14; en_US; Pixel 8 Pro) gzip'),
        ('ios', 'com.google.ios.youtube/19.05.36 (iPhone16,2; U; CPU iOS 17_3 like Mac OS X; en_US)'),
    ]

    # OMEGA BYPASS: If we hit a block, we activate the sidecar and use improved opts
    if _COOKIE_FAILURE_CACHE["locked"] and (time.time() - _COOKIE_FAILURE_CACHE["last_fail"] < 600): # 10 min lock
        if not omega.is_running:
            omega.start_sidecar()
        
        omega_opts = omega.get_ydl_opts(ydl_opts)
        try:
            with yt_dlp.YoutubeDL(omega_opts) as ydl:
                return ydl.extract_info(url_or_query, download=False)
        except Exception as e:
            log.warning(f"  [OMEGA] Bypass failed: {e}")
            return _run_titanium_bypass(url_or_query, ydl_opts, potential_clients)

    ydl_opts_with_cookies = ydl_opts.copy()
    ydl_opts_with_cookies['cookiesfrombrowser'] = (browser,)
    
    try:
        # First attempt: Try with cookies (normal mode)
        with yt_dlp.YoutubeDL(ydl_opts_with_cookies) as ydl:
            return ydl.extract_info(url_or_query, download=False)
    except Exception as e:
        err = str(e)
        if "Sign in" in err or "403" in err or "PO Token" in err:
            log.warning(f"  [DOWNLOADER] 🛡️ YouTube detection detected. Activating OMEGA Bypass...")
            _COOKIE_FAILURE_CACHE["locked"] = True
            _COOKIE_FAILURE_CACHE["last_fail"] = time.time()
            # Retry immediately with OMEGA
            if not omega.is_running:
                omega.start_sidecar()
            omega_opts = omega.get_ydl_opts(ydl_opts)
            try:
                with yt_dlp.YoutubeDL(omega_opts) as ydl:
                    return ydl.extract_info(url_or_query, download=False)
            except:
                return _run_titanium_bypass(url_or_query, ydl_opts, potential_clients)
        elif "DPAPI" in err or "cookies" in err.lower():
            # Browser cookie lock
            return _run_titanium_bypass(url_or_query, ydl_opts, potential_clients)
        else:
            return None

def _run_titanium_bypass(url_or_query, ydl_opts, clients):
    label = "SEARCH" if "ytsearch" in str(url_or_query) else "DOWNLOADER"
    print(f"  [{label}] 👻 Phantom Bypass (TV Mode)...")
    
    for client_name, ua in clients:
        try:
            bypass_opts = ydl_opts.copy()
            bypass_opts.update({
                'quiet': True,
                'no_warnings': True,
                'extractor_args': {'youtube': {'player_client': [client_name], 'skip': ['webpage']}},
                'user_agent': ua,
                'nocheckcertificate': True,
            })
            # Explicitly remove cookies
            if 'cookiesfrombrowser' in bypass_opts: del bypass_opts['cookiesfrombrowser']
            
            with yt_dlp.YoutubeDL(bypass_opts) as ydl:
                return ydl.extract_info(url_or_query, download=False)
        except Exception:
            continue
            
    # NUCLEAR FALLBACK: If yt-dlp fails metadata, try Invidious API (only for IDs, not search)
    if "youtube.com" in str(url_or_query) or "youtu.be" in str(url_or_query):
        return _fetch_via_phantom_mirror(url_or_query)

    return None

def _fetch_via_phantom_mirror(url):
    """Last resort metadata fetch via public Invidious instances."""
    import requests
    import re
    
    video_id_match = re.search(r"(?:v=|\/|be\/)([\w-]{11})", url)
    if not video_id_match: return None
    video_id = video_id_match.group(1)
    
    instances = ["yewtu.be", "inv.tux.rs", "invidious.io.lol", "invidious.flokinet.to"]
    for inst in instances:
        try:
            api_url = f"https://{inst}/api/v1/videos/{video_id}"
            resp = requests.get(api_url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                print(f"  [PHANTOM] ✓ Secured metadata via Mirror ({inst})")
                return {
                    'id': video_id,
                    'title': data.get('title', 'Unknown'),
                    'view_count': data.get('viewCount', 0),
                    'duration': data.get('lengthSeconds', 0),
                    'channel': data.get('author', ''),
                    'webpage_url': f"https://www.youtube.com/watch?v={video_id}"
                }
        except:
            continue
    return None

def get_best_browser():
    """Detects which browser is installed and has cookies available."""
    # Common browsers on Windows
    appdata = os.environ.get('APPDATA', '')
    localappdata = os.environ.get('LOCALAPPDATA', '')
    
    potential_paths = {
        'opera': os.path.join(appdata, 'Opera Software', 'Opera Stable'),
        'chrome': os.path.join(localappdata, 'Google', 'Chrome', 'User Data'),
        'edge': os.path.join(localappdata, 'Microsoft', 'Edge', 'User Data'),
        'brave': os.path.join(localappdata, 'BraveSoftware', 'Brave-Browser', 'User Data'),
        'vivaldi': os.path.join(localappdata, 'Vivaldi', 'User Data'),
    }
    
    for browser, path in potential_paths.items():
        if os.path.exists(path):
            return browser
            
    # Try generic names if detection fails
    return 'chrome' 

def _load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return set(json.load(f))
    return set()

def _save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(list(history), f, indent=2)

def is_already_processed(url):
    return url in _load_history()

def mark_as_processed(url):
    history = _load_history()
    history.add(url)
    _save_history(history)

def get_video_info(url):
    """
    Fetches metadata about a video. Uses standardized safe runner.
    """
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'geo_bypass': True,
    }
    info = safe_ydl_run(url, ydl_opts)
    if info:
        return _format_info(info, url)
    return None

def _format_info(info, url):
    full_description = info.get("description", "")
    return {
        "id": info.get("id", ""),
        "title": info.get("title", ""),
        "views": info.get("view_count", 0) or 0,
        "likes": info.get("like_count", 0) or 0,
        "duration": info.get("duration", 0) or 0,
        "channel": info.get("channel", info.get("uploader", "")),
        "upload_date": info.get("upload_date", ""),
        "categories": info.get("categories", []),
        "description": full_description,
        "tags": info.get("tags", []),
        "platform": "tiktok" if "tiktok.com" in url else "youtube"
    }

def download_youtube_video(url, output_dir="downloads"):
    """
    Downloads a YouTube video ONLY if it meets the viral threshold.
    Returns None if the video is too small or already processed.
    """
    if is_already_processed(url):
        print(f"  [DOWNLOADER] SKIP — Already processed: {url}")
        return None
    
    # Check view count BEFORE downloading to save bandwidth
    print(f"  [DOWNLOADER] Checking video stats for {url}...")
    info = get_video_info(url)
    
    if not info:
        return None
    
    views = info.get("views", 0)
    title = info.get("title", "Unknown")
    duration = info.get("duration", 0)
    
    print(f"  [DOWNLOADER] '{title}' — {views:,} views, {duration}s")
    
    if views < MIN_VIEWS_THRESHOLD:
        print(f"  [DOWNLOADER] REJECTED — Only {views:,} views (need {MIN_VIEWS_THRESHOLD:,}+)")
        mark_as_processed(url)  # Don't check again
        return None
        
    if duration <= 65:
        print(f"  [DOWNLOADER] REJECTED — YouTube Shorts are ignored (duration {duration}s)")
        mark_as_processed(url)
        return None
    
    # No duration filter — we clip from ANY length video.
    # Short videos might already be clips we can repost.
    # Long videos (1h+) just have MORE viral moments to extract.
    
    print(f"  [DOWNLOADER] ✓ VIRAL VIDEO DETECTED — Downloading...")
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    url_hash = hashlib.md5(url.encode()).hexdigest()[:10]
    filename = f"source_{url_hash}.mp4"
    output_path = os.path.join(output_dir, filename)
    
    ydl_opts = {
        'format': 'bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]',
        'outtmpl': output_path,
        'quiet': True,
        'no_warnings': True,
        'merge_output_format': 'mp4',
        'geo_bypass': True,
        'ffmpeg_location': FFMPEG,
        'cookiesfrombrowser': (get_best_browser(),),
    }
    
    try:
        # Download needs special handling since extracts_info download=False isn't used
        browser = get_best_browser()
        complete_ydl_opts = ydl_opts.copy()
        complete_ydl_opts['cookiesfrombrowser'] = (browser,)
        
        with yt_dlp.YoutubeDL(complete_ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        if "DPAPI" in str(e) or "cookies" in str(e).lower():
            print(f"  [DOWNLOADER] Cookie error during download. Retrying CLEAN...")
            if 'cookiesfrombrowser' in ydl_opts: del ydl_opts['cookiesfrombrowser']
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
            except Exception as e2:
                print(f"  [DOWNLOADER] Massive failure: {e2}")
                return None
        else:
            print(f"  [DOWNLOADER] Download error: {e}")
            return None
    print(f"  [DOWNLOADER] Download complete: {output_path}")
    return output_path

def scan_trending_from_channels(channel_urls, max_per_channel=5):
    """
    Scans multiple YouTube channels and returns only URLs that pass the viral threshold.
    """
    viral_urls = []
    
    for channel_url in channel_urls:
        print(f"\n  [SCANNER] Scanning channel: {channel_url}")
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'playlistend': max_per_channel * 2,
        }
        
        try:
            result = safe_ydl_run(channel_url, ydl_opts)
            if not result or 'entries' not in result:
                continue
                
            for entry in result['entries']:
                 if not entry or not entry.get('id'):
                     continue
                 
                 video_url = f"https://www.youtube.com/watch?v={entry['id']}"
                 
                 if is_already_processed(video_url):
                     continue
                 
                 # Quick view check from flat extraction
                 view_count = entry.get('view_count', 0) or 0
                 duration = entry.get('duration', 0) or 0
                 title = entry.get('title', '')
                 
                 if duration <= 65:
                     continue # Skip shorts
                 
                 if view_count >= MIN_VIEWS_THRESHOLD:
                     print(f"  [SCANNER] ✓ VIRAL: '{title}' ({view_count:,} views)")
                     viral_urls.append(video_url)
                 else:
                     print(f"  [SCANNER] ✗ Skip: '{title}' ({view_count:,} views)")
                 
                 if len(viral_urls) >= max_per_channel:
                     break
        except Exception as e:
            print(f"  [SCANNER] Channel scan error: {e}")
    
    print(f"\n  [SCANNER] Found {len(viral_urls)} viral videos across all channels.")
    return viral_urls

def scan_recent_buzzing_videos(channel_urls, max_per_channel=2):
    """
    SNIPER MODE: Scans discovered channels for videos published in the last 48h 
    that are performing well (lowers threshold for fresh content).
    """
    sniper_urls = []
    # Dynamic threshold for fresh content: 50k views if < 24h, 100k if < 48h
    # (Much lower than the global 500k threshold)
    
    import datetime
    now_str = datetime.datetime.now().strftime("%Y%m%d")
    yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y%m%d")
    two_days_ago = (datetime.datetime.now() - datetime.timedelta(days=2)).strftime("%Y%m%d")
    
    for channel_url in channel_urls:
        print(f"\n  [SNIPER] Checking fresh leads on: {channel_url}")
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'playlistend': 5,
        }
        
        try:
            result = safe_ydl_run(channel_url, ydl_opts)
            if not result or 'entries' not in result:
                continue
                
            for entry in result['entries']:
                 if not entry or not entry.get('id'):
                     continue
                 
                 # Fetch full info for exact date and views
                 video_url = f"https://www.youtube.com/watch?v={entry['id']}"
                 if is_already_processed(video_url):
                     continue
                     
                 info = get_video_info(video_url)
                 if not info: continue
                 
                 upload_date = info.get("upload_date", "")
                 views = info.get("views", 0)
                 duration = info.get("duration", 0)
                 
                 # Criteria: Published in last 2 days
                 is_recent = upload_date in [now_str, yesterday, two_days_ago]
                 
                 if is_recent and duration > 65:
                     # Velocity check: 20k views minimum for fresh content to be considered "buzzing"
                     if views >= 20_000:
                         print(f"  [SNIPER] ✓ BUZZ DETECTED: '{info['title']}' ({views:,} views, uploaded {upload_date})")
                         sniper_urls.append(video_url)
                     else:
                         print(f"  [SNIPER] ✗ Low velocity: '{info['title']}' ({views:,} views)")
                 
                 if len(sniper_urls) >= max_per_channel:
                     break
        except Exception as e:
            print(f"  [SNIPER] Sniper scan error: {e}")
            
    return sniper_urls

def search_trending_videos(search_queries, max_results=5):
    """
    Searches YouTube for trending/viral videos matching given queries.
    Only returns videos above the viral view threshold.
    This is the MAIN content discovery engine.
    """
    viral_urls = []
    # OMEGA DISCOVERY: Use Invidious gateway to bypass YouTube search detection
    print(f"  [SEARCH] [PHANTOM OMEGA] Searching via Anonymized Gateway...")
    for query in search_queries:
        results = gateway.search_viral(query)
        for v in results:
            if is_already_processed(v['url']): continue
            # Check views silently
            info = get_video_info(v['url'])
            if info and info['views'] >= MIN_VIEWS_THRESHOLD:
                print(f"  [SEARCH] ✓ VIRAL FOUND: '{info['title']}' ({info['views']:,} views)")
                viral_urls.append(v['url'])
                if len(viral_urls) >= max_results:
                    return viral_urls
    return viral_urls

def get_trending_videos(channel_url, max_results=3):
    """Legacy compat wrapper."""
    return scan_trending_from_channels([channel_url], max_per_channel=max_results)

if __name__ == "__main__":
    pass
