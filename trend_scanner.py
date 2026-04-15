"""
trend_scanner.py — Social Media Intelligence Scanner

Scrapes Reddit and X/Twitter for viral YouTube links.
ADAPTIVE: Uses the strategy engine's discovered subreddits and follows
leads found in X posts (if someone says "this channel is fire", the AI
remembers and scans that channel).
"""

import re
import time
import json
import os
import urllib.request
import urllib.parse
from datetime import datetime

def _extract_social_urls(text):
    """Extracts YouTube and TikTok URLs from any text."""
    patterns = [
        r'(https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+)',
        r'(https?://youtu\.be/[\w-]+)',
        r'(https?://(?:www\.)?youtube\.com/shorts/[\w-]+)',
        r'(https?://(?:www\.)?tiktok\.com/@[\w.-]+/video/\d+)',
        r'(https?://vm\.tiktok\.com/[\w-]+)',
        r'(https?://(?:www\.)?tiktok\.com/t/[\w-]+)',
    ]
    urls = []
    for pattern in patterns:
        urls.extend(re.findall(pattern, text))
    return list(set(urls))

def _extract_youtube_channels(text):
    """Extracts YouTube channel URLs from text."""
    patterns = [
        r'(https?://(?:www\.)?youtube\.com/@[\w-]+)',
        r'(https?://(?:www\.)?youtube\.com/c/[\w-]+)',
        r'(https?://(?:www\.)?youtube\.com/channel/[\w-]+)',
    ]
    channels = []
    for pattern in patterns:
        channels.extend(re.findall(pattern, text))
    return list(set(channels))

def _normalize_youtube_url(url):
    """Converts any YouTube URL to standard watch?v= format."""
    match = re.search(r'youtu\.be/([\w-]+)', url)
    if match:
        return f"https://www.youtube.com/watch?v={match.group(1)}"
    match = re.search(r'youtube\.com/shorts/([\w-]+)', url)
    if match:
        return f"https://www.youtube.com/watch?v={match.group(1)}"
    return url

def scan_reddit_for_viral_videos(custom_subreddits=None, time_filter="week", limit=30):
    """
    Scrapes Reddit's public JSON API for YouTube links in top posts.
    Uses both default subreddits AND any discovered by the strategy engine.
    """
    default_subs = [
        "videos", "PublicFreakout", "funny", "Unexpected",
        "nextfuckinglevel", "CrazyFuckingVideos", "MadeMeSmile",
        "interestingasfuck", "TikTokCringe", "facepalm",
        "therewasanattempt", "WatchPeopleDieInside", "ContagiousLaughter",
        "AbruptChaos", "oddlysatisfying", "Damnthatsinteresting",
        "HolUp", "meirl", "BetterEveryLoop", "IdiotsFightingThings",
        "youtube", "Shorts", "YouTube_startups", "NewTubers",
        "MrBeast", "PewdiepieSubmissions", "mildlyinteresting",
    ]
    
    # Merge with strategy-discovered subreddits
    if custom_subreddits:
        for s in custom_subreddits:
            s_clean = s.strip().replace("r/", "")
            if s_clean and s_clean not in default_subs:
                default_subs.append(s_clean)
    
    found_urls = []
    discovered_channels = []
    discovered_leads = []  # Textual leads to analyze
    
    for sub in default_subs:
        print(f"  [REDDIT] Scanning r/{sub}...")
        api_url = f"https://www.reddit.com/r/{sub}/top.json?t={time_filter}&limit={limit}"
        
        try:
            req = urllib.request.Request(api_url, headers={
                "User-Agent": "AutoClipAI/3.0 (Viral Content Discovery Engine)"
            })
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode())
            
            posts = data.get("data", {}).get("children", [])
            
            for post in posts:
                pd = post.get("data", {})
                url = pd.get("url", "")
                selftext = pd.get("selftext", "")
                title = pd.get("title", "")
                score = pd.get("score", 0)
                full_text = f"{title} {selftext} {url}"
                
                # Extract Social video links
                social_urls = _extract_social_urls(full_text)
                for s_url in social_urls:
                    normalized = _normalize_youtube_url(s_url) if "youtube" in s_url or "youtu.be" in s_url else s_url
                    if normalized not in [u["url"] for u in found_urls]:
                        found_urls.append({
                            "url": normalized,
                            "score": score,
                            "title": title[:100],
                            "source": f"r/{sub}"
                        })
                
                # Extract YouTube channel mentions
                channels = _extract_youtube_channels(full_text)
                for ch in channels:
                    if ch not in discovered_channels:
                        discovered_channels.append(ch)
                
                # Look for LEADS — posts that describe a source of viral content
                # e.g. "this channel is insane", "go watch X's videos"
                lead_patterns = [
                    r'check out (?:this )?(?:channel|page|account|user|creator)\s*[:\-]?\s*@?([\w-]+)',
                    r'(?:his|her|their|this) (?:channel|content|videos) (?:is|are|has) (?:fire|insane|crazy|amazing|the best|gold)',
                    r'(?:subscribe to|follow|watch)\s+@?([\w-]+)',
                    r'best (?:channel|creator|youtuber|tiktok)\s+(?:for|about)\s+([\w\s]+)',
                    r'this (?:sub|subreddit|page|community) (?:is|has) (?:fire|insane|bangers|gold|amazing|the best)',
                    r'(?:go to|check out|visit|browse)\s+r/([\w-]+)',
                    r'r/([\w-]+)\s+(?:is|has)\s+(?:fire|insane|bangers|gold|amazing|the best|full of|nothing but)',
                    r'source\s*[:\-]?\s*@?([\w-]+)',
                ]
                for pattern in lead_patterns:
                    matches = re.findall(pattern, selftext + " " + title, re.IGNORECASE)
                    for m in matches:
                        if m and len(m) > 2:
                            discovered_leads.append({
                                "text": m,
                                "context": title[:80],
                                "source": f"r/{sub}",
                                "score": score
                            })
                
                # Discover subreddit mentions (r/something) 
                subreddit_mentions = re.findall(r'(?:^|[\s/])r/([\w]{3,25})\b', full_text)
                for mentioned_sub in subreddit_mentions:
                    if mentioned_sub not in default_subs and mentioned_sub not in [l.get("text") for l in discovered_leads]:
                        discovered_leads.append({
                            "text": mentioned_sub,
                            "type": "subreddit",
                            "context": title[:80],
                            "source": f"r/{sub}",
                            "score": score
                        })
            
            time.sleep(0.8)  # Rate limit
            
        except Exception as e:
            if "429" in str(e):
                print(f"  [REDDIT] Rate limited. Waiting 15s...")
                time.sleep(15)
            else:
                print(f"  [REDDIT] Error r/{sub}: {str(e)[:60]}")
            time.sleep(1)
    
    # Sort by Reddit score
    found_urls.sort(key=lambda x: x["score"], reverse=True)
    
    result = {
        "urls": [u["url"] for u in found_urls],
        "channels": discovered_channels,
        "leads": discovered_leads,
    }
    
    print(f"\n  [REDDIT] Found: {len(result['urls'])} videos, {len(discovered_channels)} channels, {len(discovered_leads)} leads")
    return result

def scan_x_for_viral_videos(search_queries=None):
    """
    Searches X/Twitter for YouTube links via Nitter.
    Also extracts channel recommendations and leads.
    """
    if search_queries is None:
        search_queries = [
            "youtube.com viral thread",
            "youtu.be \"best video I've watched\"",
            "youtube.com banger",
            "this clip is gold youtube",
            "youtube best moments compilation",
            "must watch youtube drama",
            "tiktok trends youtube",
            "viral shorts youtube",
        ]
    
    found_urls = []
    discovered_channels = []
    
    nitter_instances = [
        "nitter.privacydev.net",
        "nitter.poast.org",
        "nitter.1d4.us",
    ]
    
    for query in search_queries:
        print(f"  [X] Searching: '{query}'")
        
        for instance in nitter_instances:
            try:
                encoded = urllib.parse.quote(query)
                url = f"https://{instance}/search?f=tweets&q={encoded}"
                
                req = urllib.request.Request(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                })
                with urllib.request.urlopen(req, timeout=10) as resp:
                    html = resp.read().decode('utf-8', errors='ignore')
                
                # Extract Social video URLs
                social_urls = _extract_social_urls(html)
                for s_url in social_urls:
                    norm = _normalize_youtube_url(s_url) if "youtube" in s_url or "youtu.be" in s_url else s_url
                    if norm not in found_urls:
                        found_urls.append(norm)
                
                # Extract YouTube channels
                channels = _extract_youtube_channels(html)
                for ch in channels:
                    if ch not in discovered_channels:
                        discovered_channels.append(ch)
                
                break  # Success
                
            except Exception as e:
                continue
        
        time.sleep(1.5)
    
    result = {
        "urls": found_urls,
        "channels": discovered_channels,
    }
    
    print(f"\n  [X] Found: {len(found_urls)} videos, {len(discovered_channels)} channels")
    return result

def discover_viral_content():
    """
    Master discovery function.
    Combines Reddit + X scanning.
    Feeds discoveries back to the strategy engine.
    """
    print("\n" + "=" * 55)
    print("SEARCH VIRAL CONTENT -- Reddit + X/Twitter")
    print("=" * 55)
    
    all_urls = []
    
    # Get strategy-discovered subreddits
    try:
        from strategy import get_discovered_subreddits, add_discovered_lead
        extra_subs = get_discovered_subreddits()
    except Exception:
        extra_subs = []
        add_discovered_lead = None
    
    # Reddit scan
    try:
        reddit_result = scan_reddit_for_viral_videos(custom_subreddits=extra_subs)
        all_urls.extend(reddit_result["urls"])
        
        # Feed discoveries back to strategy
        if add_discovered_lead:
            for ch in reddit_result.get("channels", []):
                add_discovered_lead("channel", ch, source="reddit")
            for lead in reddit_result.get("leads", []):
                if lead.get("type") == "subreddit":
                    add_discovered_lead("subreddit", lead["text"], source=f"reddit/{lead.get('source','')}")
                else:
                    add_discovered_lead("query", lead["text"], source=f"reddit/{lead.get('source','')}")
                
    except Exception as e:
        print(f"  [DISCOVERY] Reddit failed: {e}")
    
    # X/Twitter scan
    try:
        x_result = scan_x_for_viral_videos()
        all_urls.extend(x_result["urls"])
        
        if add_discovered_lead:
            for ch in x_result.get("channels", []):
                add_discovered_lead("channel", ch, source="x_twitter")
                
    except Exception as e:
        print(f"  [DISCOVERY] X/Twitter failed: {e}")
    
    # Deduplicate
    all_urls = list(dict.fromkeys(all_urls))
    
    print(f"\nDISCOVERY COMPLETE -- {len(all_urls)} unique YouTube URLs")
    return all_urls

if __name__ == "__main__":
    urls = discover_viral_content()
    for u in urls:
        print(u)
