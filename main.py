# -*- coding: utf-8 -*-
"""
main.py — AutoClipAI v7.0 — PHANTOM OMEGA

Features:
- Adaptive strategy engine (no hardcoded queries — AI evolves them)
- Video stockpile (30 clips ready at all times)
- Reddit + X/Twitter discovery
- YouTube search with evolved queries
- Anti-ban posting with randomized delays
- Self-improvement loop every 6 hours
- Auto-start compatible (just run this file)
- v6.1: Resilient & Self-Cleaning (Checkpoint system + auto-cleanup)
"""

import os
import json
import re
import time
import sys
import traceback
import argparse
import random
import logging
import schedule
import glob
from datetime import datetime
from dotenv import load_dotenv

from downloader import (
    download_youtube_video, mark_as_processed, get_video_info,
    scan_trending_from_channels, search_trending_videos,
    scan_recent_buzzing_videos
)
from analyzer import analyze_video_for_viral_moments
from editor import create_short_clip, add_subtitles_to_clip, merge_clips
from publisher import publish_to_tiktok, publish_to_youtube_shorts, prune_youtube_video, prune_tiktok_video
from memory import log_post, get_audience_insights, get_pruning_candidates, mark_as_pruned
from monitor import monitor_tiktok_profile, monitor_youtube_channel
from trend_scanner import discover_viral_content
from strategy import (
    get_active_queries, get_discovered_channels,
    log_query_result, evolve_strategy, add_discovered_lead
)
from reporting import generate_weekly_report, should_generate_report
from trend_analyzer import update_learned_layouts
from assets_manager import get_random_background
from monetization import get_content_rules, get_clip_duration_range
from cloud_storage import drive_manager

# =====================================================================
# LOGGING
# =====================================================================
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
log_file = os.path.join(LOG_DIR, f"autoclip_{datetime.now().strftime('%Y-%m-%d')}.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger("AutoClipAI")

# =====================================================================
# CONFIG
# =====================================================================
TIKTOK_PROFILE_URL = os.environ.get("TIKTOK_PROFILE_URL", "")
YOUTUBE_CHANNEL_URL = os.environ.get("YOUTUBE_CHANNEL_URL", "")
PUBLISH_TO_TIKTOK = True
PUBLISH_TO_YOUTUBE = True

# Posting volume
MAX_TIKTOK_POSTS_PER_DAY = 30
MAX_YOUTUBE_POSTS_PER_DAY = 50
MIN_DELAY_BETWEEN_POSTS = 60    # 1 min
MAX_DELAY_BETWEEN_POSTS = 180   # 3 min
CLIPS_PER_VIDEO = 5

# Stockpile config
STOCKPILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stockpile")
STOCKPILE_TARGET = 30  # Always maintain 30 ready clips
os.makedirs(STOCKPILE_DIR, exist_ok=True)

CHECKPOINT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "checkpoint.json")

# =====================================================================
# RESILIENCE & CLEANUP HELPERS
# =====================================================================
def _save_checkpoint(url, stage, meta=None):
    try:
        data = {"url": url, "stage": stage, "meta": meta or {}, "timestamp": time.time()}
        with open(CHECKPOINT_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        log.error(f"Checkpoint Error: {e}")

def _get_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, "r") as f:
                return json.load(f)
        except:
            return None
    return None

def _clear_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        try:
            os.remove(CHECKPOINT_FILE)
        except:
            pass

def wipe_temp_folders():
    """Wipes downloads and clips folders to reclaim space on startup."""
    log.info("🧹 Nettoyage des dossiers temporaires...")
    for folder in ["downloads", "clips"]:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), folder)
        if os.path.exists(path):
            files = glob.glob(os.path.join(path, "*"))
            count = 0
            for f in files:
                try:
                    if os.path.isfile(f):
                        os.remove(f)
                        count += 1
                except:
                    pass
            if count > 0:
                log.info(f"   - {folder}: {count} fichiers supprimés")

# Pruning threshold
PRUNE_VIEWS_THRESHOLD = int(os.environ.get("PRUNE_VIEWS_THRESHOLD", 100))
PRUNE_AGE_HOURS = int(os.environ.get("PRUNE_AGE_HOURS", 48))

# Daily counters
_daily_counts = {"tiktok": 0, "youtube": 0, "date": ""}

def _reset_daily_counts():
    today = datetime.now().strftime("%Y-%m-%d")
    if _daily_counts["date"] != today:
        _daily_counts["tiktok"] = 0
        _daily_counts["youtube"] = 0
        _daily_counts["date"] = today

def _can_post(platform):
    _reset_daily_counts()
    if platform == "tiktok":
        return _daily_counts["tiktok"] < MAX_TIKTOK_POSTS_PER_DAY
    return _daily_counts["youtube"] < MAX_YOUTUBE_POSTS_PER_DAY

def _human_delay():
    delay = random.randint(MIN_DELAY_BETWEEN_POSTS, MAX_DELAY_BETWEEN_POSTS)
    log.info(f"  ⏳ Delay: {delay}s")
    time.sleep(delay)

# =====================================================================
# STOCKPILE SYSTEM — Pre-edited clips ready to publish
# =====================================================================
def create_compilation_from_stockpile(target_category=None):
    """
    Groups clips from the stockpile by category and merges them into a single video.
    If no category is specified, it picks the largest one with 3+ clips.
    """
    log.info("🎬 COMPILATION ENGINE : Searching for groupable clips...")
    
    # 1. Group stockpile clips by category
    categories = {}
    metadata_files = glob.glob(os.path.join(STOCKPILE_DIR, "*.json"))
    
    for meta_p in metadata_files:
        try:
            with open(meta_p, "r") as f:
                meta = json.load(f)
                cat = meta.get("compilation_category", "General")
                if cat not in categories: categories[cat] = []
                # Check if video file exists
                vid_p = meta_p.replace(".json", ".mp4")
                if os.path.exists(vid_p):
                    categories[cat].append({"path": vid_p, "meta": meta, "meta_path": meta_p})
        except: continue
        
    # 2. Select category
    selected_cat = target_category
    if not selected_cat:
        # Find category with most clips (min 3)
        sorted_cats = sorted(categories.items(), key=lambda x: len(x[1]), reverse=True)
        if sorted_cats and len(sorted_cats[0][1]) >= 3:
            selected_cat = sorted_cats[0][0]
        else:
            log.info("  [COMPILER] ✗ Not enough clips for a compilation yet (need 3+ in same category)")
            return None
            
    clips_to_merge = categories[selected_cat][:5] # Max 5 clips for compilation
    log.info(f"  [COMPILER] ✓ Found {len(clips_to_merge)} clips for: '{selected_cat}'")
    
    # 3. Merge
    paths = [c["path"] for c in clips_to_merge]
    comp_path = merge_clips(paths, output_filename=f"compilation_{selected_cat.lower().replace(' ', '_')}")
    
    if comp_path:
        # Create metadata for the compilation
        comp_meta = {
            "title": f"BEST OF: {selected_cat} Moments! 🔥",
            "description": f"The most viral {selected_cat} moments compiled for you! #compilation #{selected_cat.lower().replace(' ', '')}",
            "tags": ["compilation", "viral", selected_cat.lower()],
            "source_url": "Multiple Sources",
            "duration": sum(c["meta"].get("duration", 0) for c in clips_to_merge)
        }
        
        # Optionally remove the original clips from stockpile or mark them
        # For now, we'll keep them but you might want to delete them to avoid duplicates
        # _add_to_stockpile(comp_path, comp_meta) 
        # (Actually we might want to publish this immediately)
        return comp_path, comp_meta
        
    return None, None

def _get_stockpile_count():
    """How many clips are ready in the stockpile."""
    return len(glob.glob(os.path.join(STOCKPILE_DIR, "*.mp4")))

def _get_stockpile_metadata():
    """Returns metadata for all stockpiled clips."""
    meta_path = os.path.join(STOCKPILE_DIR, "stockpile_meta.json")
    if os.path.exists(meta_path):
        import json
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def _save_stockpile_metadata(meta):
    import json
    meta_path = os.path.join(STOCKPILE_DIR, "stockpile_meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

def _add_to_stockpile(clip_path, clip_data):
    """Moves a clip to the stockpile with its metadata."""
    import shutil, json
    
    filename = os.path.basename(clip_path)
    dest = os.path.join(STOCKPILE_DIR, filename)
    shutil.move(clip_path, dest)
    
    meta = _get_stockpile_metadata()
    meta.append({
        "filename": filename,
        "path": dest,
        "title": clip_data.get("title", ""),
        "description": clip_data.get("description", ""),
        "tags": clip_data.get("suggested_tags", []),
        "caption_style": clip_data.get("caption_style", "unknown"),
        "hook": clip_data.get("hook", ""),
        "source_url": clip_data.get("source_url", ""),
        "duration": clip_data.get("duration", 0),
        "created_at": datetime.now().isoformat(),
    })
    _save_stockpile_metadata(meta)
    log.info(f"  📦 Added to stockpile: {filename} ({_get_stockpile_count()} total)")
    
    # CLOUD SYNC: Upload to Drive immediately to save space
    drive_manager.upload_file(dest)

def _pop_from_stockpile():
    """
    Takes the oldest clip from the stockpile and returns its data.
    This is used when Gemini quota is exhausted but we still need to post.
    """
    meta = _get_stockpile_metadata()
    if not meta:
        # If local meta empty, check Drive
        drive_files = drive_manager.list_files()
        if drive_files:
            log.info("  ☁️ Local stockpile empty. Syncing from Drive...")
            for df in drive_files[:5]: # Fetch a batch
                local_path = os.path.join(STOCKPILE_DIR, df['name'])
                if not os.path.exists(local_path):
                    drive_manager.download_file(df['id'], local_path)
            # Re-read meta after download (assuming we'd have a meta sync too)
            # For now, we simple download the file and let the next loop find it.
        return None, None
    
    clip_info = meta.pop(0)  # FIFO — oldest first
    _save_stockpile_metadata(meta)
    
    path = clip_info.get("path", "")
    if not os.path.exists(path):
        # Check if we can download it from cloud
        # (This assumes clip_info had a drive_id, which we should add)
        return _pop_from_stockpile()  # Skip missing for now
    
    return path, clip_info

def fill_stockpile(youtube_url):
    """
    Downloads, analyzes, and edits clips but saves them to stockpile
    instead of publishing immediately.
    """
    log.info(f"  📦 STOCKPILE MODE — Saving clips for later")
    
    insights = get_audience_insights()
    video_path = download_youtube_video(youtube_url)
    if not video_path:
        return 0
    
    clips_data = analyze_video_for_viral_moments(video_path, insights=insights)
    
    if not clips_data:
        log.warning("  [FALLBACK] Gemini API failed. Skipping this video entirely as per strict AI-only requirement.")
        _cleanup_file(video_path)
        mark_as_processed(youtube_url)
        return 0
    
    _save_checkpoint(youtube_url, "filling_stockpile")
    
    saved = 0
    for i, clip in enumerate(clips_data[:CLIPS_PER_VIDEO]):
        start = clip.get('start_time', 0)
        end = clip.get('end_time', start + 30)
        duration = end - start
        min_dur, max_dur = get_clip_duration_range("tiktok")
        if duration < min_dur: end, duration = start + min_dur, min_dur
        elif duration > max_dur: end, duration = start + max_dur, max_dur
        
        clip_name = f"stock_{int(time.time())}_{i}"
        pov_text = clip.get('pov_caption')
        template = clip.get('visual_template', 'premium_banner')
        
        bg_path = None
        if "split_screen" in template:
            bg_type = clip.get('background_type', 'minecraft_parkour')
            bg_path = get_random_background(bg_type)
            
        clip_path = create_short_clip(video_path, start, end, output_filename=clip_name, pov_text=pov_text, template=template, background_path=bg_path)
        if not clip_path:
            continue
        
        hook_text = clip.get('hook', clip.get('title', ''))
        if hook_text:
            clip_path = add_subtitles_to_clip(clip_path, hook_text)
        
        clip["source_url"] = youtube_url
        clip["duration"] = duration
        _add_to_stockpile(clip_path, clip)
        saved += 1
    
    _cleanup_file(video_path)
    mark_as_processed(youtube_url)
    _clear_checkpoint()
    return saved

def publish_from_stockpile():
    """Publishes clips from the stockpile (no Gemini needed)."""
    log.info("📦 PUBLISHING FROM STOCKPILE")
    
    published = 0
    insights = get_audience_insights()
    memory_tags = insights.get("best_tags_by_engagement", [])
    
    while _get_stockpile_count() > 0:
        if not _can_post("tiktok") and not _can_post("youtube"):
            log.info("  Daily limits reached.")
            break
        
        clip_path, clip_info = _pop_from_stockpile()
        if not clip_path or not clip_info:
            break
        
        title = clip_info.get("title", "Viral Clip 🔥")
        description = clip_info.get("description", title)
        tags = list(set(clip_info.get("tags", []) + memory_tags))
        
        if PUBLISH_TO_TIKTOK and _can_post("tiktok"):
            try:
                res = publish_to_tiktok(clip_path, description, tags)
                if res == "SUCCESS":
                    _daily_counts["tiktok"] += 1
                elif res == "LIMIT_REACHED":
                    log.warning("  [TIKTOK] Daily limit reached (stockpile).")
                    _daily_counts["tiktok"] = MAX_TIKTOK_POSTS_PER_DAY
            except Exception as e:
                log.error(f"  TikTok: {e}")
        
        if PUBLISH_TO_YOUTUBE and _can_post("youtube"):
            try:
                res = publish_to_youtube_shorts(clip_path, title, tags)
                if res == "SUCCESS":
                    _daily_counts["youtube"] += 1
                elif res == "LIMIT_REACHED":
                    log.warning("  [YOUTUBE] Daily limit reached (stockpile).")
                    _daily_counts["youtube"] = MAX_YOUTUBE_POSTS_PER_DAY
            except Exception as e:
                log.error(f"  YouTube: {e}")
        
        log_post({
            "title": title,
            "description": description,
            "suggested_tags": tags,
            "path": clip_path,
            "source_url": clip_info.get("source_url", ""),
            "duration": clip_info.get("duration", 0),
            "caption_style": clip_info.get("caption_style", "unknown"),
            "hook": clip_info.get("hook", ""),
        })
        published += 1
        _human_delay()
    
    log.info(f"  Published {published} clips from stockpile.")
    return published

# =====================================================================
# CORE PIPELINE — Download → Analyze → Edit → Publish
# =====================================================================
def run_pipeline(youtube_url):
    """Full pipeline for a single video. Returns number of clips published."""
    log.info(f"🚀 Pipeline: {youtube_url}")
    
    insights = get_audience_insights()
    
    _save_checkpoint(youtube_url, "downloading")
    video_path = download_youtube_video(youtube_url)
    if not video_path:
        _clear_checkpoint()
        return 0
    
    _save_checkpoint(youtube_url, "analyzing", {"video_path": video_path})
    clips_data = analyze_video_for_viral_moments(video_path, insights=insights)
    if not clips_data:
        _cleanup_file(video_path)
        mark_as_processed(youtube_url)
        _clear_checkpoint()
        return 0
    
    _save_checkpoint(youtube_url, "processing_clips", {"video_path": video_path})
    
    log.info(f"  AI found {len(clips_data)} viral moments!")
    published_count = 0
    
    for i, clip in enumerate(clips_data[:CLIPS_PER_VIDEO]):
        title = clip.get('title', f'Clip #{i+1}')
        description = clip.get('description', title)
        caption_style = clip.get('caption_style', 'unknown')
        
        start = clip.get('start_time', 0)
        end = clip.get('end_time', start + 30)
        duration = end - start
        # Monetization-aware duration clamping
        min_dur, max_dur = get_clip_duration_range("tiktok")
        if duration < min_dur: end, duration = start + min_dur, min_dur
        elif duration > max_dur: end, duration = start + max_dur, max_dur
        
        clip_name = f"clip_{int(time.time())}_{i}"
        pov_text = clip.get('pov_caption')
        template = clip.get('visual_template', 'premium_banner')
        
        bg_path = None
        if "split_screen" in template:
            bg_type = clip.get('background_type', 'minecraft_parkour')
            bg_path = get_random_background(bg_type)
            
        clip_path = create_short_clip(video_path, start, end, output_filename=clip_name, pov_text=pov_text, template=template, background_path=bg_path)
        if not clip_path:
            continue
        
        hook_text = clip.get('hook', clip.get('title', ''))
        if hook_text:
            clip_path = add_subtitles_to_clip(clip_path, hook_text)
        
        # Save clip checkpoint to resume this specific clip if needed
        _save_checkpoint(youtube_url, "publishing_clip", {"video_path": video_path, "clip_index": i, "clip_path": clip_path})
        
        ai_tags = clip.get('suggested_tags', [])
        memory_tags = insights.get("best_tags_by_engagement", [])
        combined_tags = list(set(ai_tags + memory_tags))
        publish_caption = description if description != title else title
        
        # If we can still post, publish immediately
        if _can_post("tiktok") or _can_post("youtube"):
            if PUBLISH_TO_TIKTOK and _can_post("tiktok"):
                try:
                    res = publish_to_tiktok(clip_path, publish_caption, combined_tags)
                    if res == "SUCCESS":
                        _daily_counts["tiktok"] += 1
                    elif res == "LIMIT_REACHED":
                        log.warning("  [TIKTOK] Daily limit reached. Stopping TikTok for today.")
                        _daily_counts["tiktok"] = MAX_TIKTOK_POSTS_PER_DAY
                except Exception as e:
                    log.error(f"  TikTok: {e}")
            
            if PUBLISH_TO_YOUTUBE and _can_post("youtube"):
                try:
                    res = publish_to_youtube_shorts(clip_path, title, combined_tags)
                    if res == "SUCCESS":
                        _daily_counts["youtube"] += 1
                    elif res == "LIMIT_REACHED":
                        log.warning("  [YOUTUBE] Daily limit reached. Stopping YouTube for today.")
                        _daily_counts["youtube"] = MAX_YOUTUBE_POSTS_PER_DAY
                except Exception as e:
                    log.error(f"  YouTube: {e}")
            
            log_post({
                "title": title, "description": publish_caption,
                "suggested_tags": combined_tags, "path": clip_path,
                "source_url": youtube_url, "duration": duration,
                "caption_style": caption_style, "hook": hook_text,
                "pov_caption": pov_text, "compilation_category": clip.get('compilation_category', 'General'),
                "visual_template": template
            })
            published_count += 1
        else:
            # Daily limit reached — save to stockpile instead
            clip["source_url"] = youtube_url
            clip["duration"] = duration
            _add_to_stockpile(clip_path, clip)
        
        # CLEANUP CLIP after it's been published or stockpiled
        _cleanup_file(clip_path)
        
        if i < min(len(clips_data), CLIPS_PER_VIDEO) - 1:
            _human_delay()
    
    _cleanup_file(video_path)
    mark_as_processed(youtube_url)
    _clear_checkpoint()
    return published_count

# =====================================================================
# MASTER RUN — The main automated cycle
# =====================================================================
def run_full_cycle():
    """
    One complete cycle of the viral machine:
    1. Evolve strategy (if enough data)
    2. Discover content (Reddit + X + YouTube)
    3. Fill stockpile if below target
    4. Publish clips
    5. Monitor stats
    """
    log.info("=" * 60)
    log.info("🌌 AUTOCLIP AI — PHANTOM OMEGA v7.0")
    log.info(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log.info(f"   Security: OMEGA Sidecar Active (Port 4416)")
    log.info(f"   Stockpile: {_get_stockpile_count()}/{STOCKPILE_TARGET}")
    log.info("=" * 60)
    
    _reset_daily_counts()
    
    # STEP 0: Trend Analysis (Meta-Adaptive Visuals)
    log.info("\n--- STEP 0: ANALYZING VISUAL TRENDS ---")
    try:
        # Find some viral URLs to analyze
        sample_queries = get_active_queries()[:3]
        viral_samples = search_trending_videos(sample_queries, max_results=5)
        update_learned_layouts(viral_samples)
    except Exception as e:
        log.error(f"  Trend analysis failed: {e}")
    
    # STEP 1: Evolve strategy with Gemini
    log.info("\n--- STEP 1: EVOLVING STRATEGY ---")
    try:
        insights = get_audience_insights()
        if insights.get("total_posts_analyzed", 0) >= 3:
            evolve_strategy(insights)
        else:
            log.info("  Not enough data yet for evolution (need 3+ posts)")
    except Exception as e:
        log.error(f"  Strategy evolution failed: {e}")
    
    # STEP 2: Discover viral content from all sources
    log.info("\n--- STEP 2: CONTENT DISCOVERY ---")
    viral_urls = []
    
    # PHANTOM PIVOT: If YouTube is failing, double down on Socials
    from downloader import _COOKIE_FAILURE_CACHE
    yt_failed = _COOKIE_FAILURE_CACHE.get("locked", False)
    social_boost = 2 if yt_failed else 1
    if yt_failed:
        log.warning("  🛡️ [PHANTOM] YouTube detection detected. Pivoting to Social Discovery...")

    # 2a: Reddit + X/Twitter
    try:
        social_urls = discover_viral_content()
        # If we need to pivot, we can run discovery multiple times or with higher limits
        viral_urls.extend(social_urls)
        if yt_failed:
            # Secondary social burst
            extra_leads = discover_viral_content() 
            viral_urls.extend(extra_leads)
    except Exception as e:
        log.error(f"  Social scan failed: {e}")
    
    # 2b: OMEGA DISCOVERY PIVOT
    active_queries = get_active_queries()
    log.info(f"  Using {len(active_queries)} evolved search queries")
    try:
        # search_trending_videos now handles Invidious pivot internally
        yt_urls = search_trending_videos(active_queries[:15], max_results=10)
        viral_urls.extend(yt_urls)
    except Exception as e:
        log.error(f"  YouTube discovery failed: {e}")
    
    # 2c: Discovered channels (Traditional scan)
    discovered_channels = get_discovered_channels()
    if discovered_channels:
        log.info(f"  Scanning {len(discovered_channels)} discovered channels (Deep Scan)")
        try:
            ch_urls = scan_trending_from_channels(discovered_channels[:10], max_per_channel=3)
            viral_urls.extend(ch_urls)
        except Exception as e:
            log.error(f"  Channel scan failed: {e}")
    
    # 2d: SNIPER MODE — Hunt for ultra-fresh viral clips (published < 48h)
    if discovered_channels:
        log.info("\n--- STEP 2d: SNIPER MODE (Fresh Hits) ---")
        try:
            sniper_urls = scan_recent_buzzing_videos(discovered_channels[:10])
            # Prepend sniper URLs so they are processed FIRST
            viral_urls = sniper_urls + viral_urls
        except Exception as e:
            log.error(f"  Sniper mode failed: {e}")

    # Deduplicate
    viral_urls = list(dict.fromkeys(viral_urls))
    log.info(f"\n  📊 Total unique viral URLs: {len(viral_urls)}")
    
    # TITANIUM SAFETY: If discovery failed completely, take a "tactical pause"
    ckpt = _get_checkpoint() or {}
    if not viral_urls and (time.time() - ckpt.get("timestamp", 0) > 300):
        log.warning("  ⚠️ [TITANIUM] No viral content found in ANY source.")
        log.warning("  🛡️ Taking a 15-minute COOL-OFF break to avoid IP lock.")
        time.sleep(900) # 15 min
        return 0
    
    # STEP 3: Fill stockpile first (if below target)
    stockpile_count = _get_stockpile_count()
    if stockpile_count < STOCKPILE_TARGET:
        needed = STOCKPILE_TARGET - stockpile_count
        log.info(f"\n--- STEP 3: FILLING STOCKPILE ({stockpile_count}/{STOCKPILE_TARGET}, need {needed}) ---")
        
        stockpile_urls = viral_urls[:needed // CLIPS_PER_VIDEO + 2]  # Roughly how many videos we need
        for url in stockpile_urls:
            if _get_stockpile_count() >= STOCKPILE_TARGET:
                break
            
            saved = 0
            try:
                saved = fill_stockpile(url)
            except Exception as e:
                log.error(f"  Stockpile fill error: {e}")
            
            if saved and saved > 0:
                time.sleep(random.randint(30, 60))
        
        log.info(f"  Stockpile now: {_get_stockpile_count()}/{STOCKPILE_TARGET}")
    else:
        log.info(f"\n--- STEP 3: STOCKPILE FULL ({stockpile_count}/{STOCKPILE_TARGET}) ✓ ---")
    
    # STEP 4: Publish — prioritize fresh clips, fall back to stockpile
    log.info("\n--- STEP 4: PUBLISHING ---")
    total_published = 0
    
    # 4a: Process remaining viral URLs (clips published live)
    remaining_urls = [u for u in viral_urls if u not in []]  # All urls we haven't stockpiled
    for i, url in enumerate(remaining_urls):
        if not _can_post("tiktok") and not _can_post("youtube"):
            log.warning("  🛑 All daily limits reached.")
            break
        
        clips = 0
        try:
            clips = run_pipeline(url)
            total_published += (clips or 0)
        except Exception as e:
            log.error(f"  Pipeline error: {e}")
        
        if clips and clips > 0 and i < len(remaining_urls) - 1:
            cooldown = random.randint(120, 300)
            log.info(f"  ⏳ Source cooldown: {cooldown}s")
            time.sleep(cooldown)
    
    # 4b: If we still have quota, publish from stockpile
    if _can_post("tiktok") or _can_post("youtube"):
        sp = publish_from_stockpile()
        total_published += sp
    
    # STEP 5: Monitor stats
    log.info("\n--- STEP 5: STATS MONITOR ---")
    run_monitor()
    
    log.info(f"\n{'='*60}")
    log.info(f"✅ CYCLE COMPLETE — {total_published} clips published")
    log.info(f"   Stockpile: {_get_stockpile_count()}/{STOCKPILE_TARGET}")
    log.info(f"   TikTok today: {_daily_counts['tiktok']}/{MAX_TIKTOK_POSTS_PER_DAY}")
    log.info(f"   YouTube today: {_daily_counts['youtube']}/{MAX_YOUTUBE_POSTS_PER_DAY}")
    log.info(f"{'='*60}")

# =====================================================================
# MONITOR
# =====================================================================
def run_monitor():
    if TIKTOK_PROFILE_URL:
        try:
            monitor_tiktok_profile(TIKTOK_PROFILE_URL)
        except Exception as e:
            log.error(f"TikTok Monitor: {e}")
            
    if YOUTUBE_CHANNEL_URL:
        try:
            monitor_youtube_channel(YOUTUBE_CHANNEL_URL)
        except Exception as e:
            log.error(f"YouTube Monitor: {e}")

# =====================================================================
# HELPERS
# =====================================================================
def _cleanup_file(path):
    try:
        if path and os.path.exists(path):
            sz = os.path.getsize(path) / (1024*1024)
            os.remove(path)
            log.info(f"  🗑 Deleted {os.path.basename(path)} ({sz:.1f} MB)")
    except Exception:
        pass

# =====================================================================
# PRUNING CYCLE
# =====================================================================
def run_pruning_cycle():
    """
    Finds and deletes 'flops' (videos with low views after grace period).
    Essential for high-authority accounts.
    """
    log.info("\n" + "!" * 55)
    log.info("🧹 THE JANITOR — Running Auto-Pruning Cycle")
    log.info("!" * 55)
    
    candidates = get_pruning_candidates(
        views_threshold=PRUNE_VIEWS_THRESHOLD, 
        age_hours=PRUNE_AGE_HOURS
    )
    
    if not candidates:
        log.info("  ✓ No pruning candidates found. The channel is clean.")
        return
        
    log.info(f"  ⚠ Found {len(candidates)} videos below {PRUNE_VIEWS_THRESHOLD} views after {PRUNE_AGE_HOURS}h.")
    
    pruned_count = 0
    for c in candidates:
        title = c["title"]
        platform = c["platform"]
        success = False
        
        if platform == "youtube":
            success = prune_youtube_video(title)
        elif platform == "tiktok":
            success = prune_tiktok_video(title)
            
        if success:
            mark_as_pruned(c["id"])
            pruned_count += 1
            
    log.info(f"✅ PRUNING COMPLETE — {pruned_count} videos removed.")
    log.info("!" * 55 + "\n")
# =====================================================================
# ENTRY POINT
# =====================================================================
if __name__ == "__main__":
    # PID management for notifier stability
    pid_file = "main.pid"
    try:
        with open(pid_file, "w") as f:
            f.write(str(os.getpid()))
    except:
        pass

    # 1. Parse Arguments (CLI support)
    parser = argparse.ArgumentParser(description="AutoClipAI v6.1")
    parser.add_argument("--mode", type=str, help="1-8: Mode to launch")
    parser.add_argument("--url", type=str, help="YouTube URL for manual mode")
    args = parser.parse_args()

    # 2. Welcome Banner
    print(r"""
    +-------------------------------------------------------+
    |     _         _         ____ _ _            _    ___  |
    |    / \  _   _| |_ ___  / ___| (_)_ __      / \  |_ _| |
    |   / _ \| | | | __/ _ \| |   | | | '_ \    / _ \  | | |
    |  / ___ \ |_| | || (_) | |___| | | |_) |  / ___ \  | | |
    | /_/   \_\__,_|\__\___/ \____|_|_| .__/  /_/   \_\___| |
    |                                 |_| v7.0 PHANTOM OMEGA|
    +-------------------------------------------------------+
    |  * OMEGA Bypass  * PO-Token Proof  * Invidious Gateway |
    +-------------------------------------------------------+
    """)

    
    # 3. Mode selection
    if args.mode:
        choice = args.mode
        print(f"🤖 [CLI] Démarrage en Mode {choice}")
    else:
        print("Modes:")
        print("  1. Single URL       — Clip one specific video")
        print("  2. Full Cycle       — Run one complete discovery+publish cycle")
        print("  3. AUTOPILOT        — Run forever, 3x per day (RECOMMENDED)")
        print("  4. Stockpile Only   — Build up clip stockpile without publishing")
        print("  5. Publish Stockpile— Publish all stockpiled clips now")
        print("  6. Monitor Only     — Check TikTok stats")
        print("  7. NUCLEAR DELETE   — ☢️ Wipe everything from YouTube + TikTok")
        print("  8. PRUNE FLOPS      — 🧹 Remove videos with < 100 views")
        print()
        choice = input("Mode (1-8): ").strip()
    
    # Start OMEGA Sidecar
    from omega_bypass import omega
    omega.start_sidecar()
    try:
        # Main Logic...
    ckpt = _get_checkpoint()
    if ckpt and choice in ["1", "2", "3", "4", "5"]:
        # Auto-resume in CLI mode or choice 3
        if args.mode or choice == "3":
            print(f"\n🤖 [RESILIENT] Auto-resuming unfinished task: {ckpt['url']}")
            run_pipeline(ckpt['url'])
        else:
            ans = input(f"\n⚠️ Unfinished task detected. Resume {ckpt['url']}? (Y/n): ").strip().lower()
            if ans != 'n':
                run_pipeline(ckpt['url'])
    
    # 5. Execute Mode
    if choice == "1":
        url = args.url if args.url else input("YouTube URL: ").strip()
        if url: run_pipeline(url)
    
    elif choice == "2":
        run_full_cycle()
    
    elif choice == "3":
        log.info("🤖 AUTOPILOT CONTINU — L'IA tourne non-stop")
        log.info("   Pas de cycles fixes. L'IA poste dès qu'elle peut.")
        log.info("   Press Ctrl+C to stop\n")
        
        cycle_count = 0
        
        while True:
            try:
                cycle_count += 1
                log.info(f"\n{'='*55}")
                log.info(f"🔄 CYCLE #{cycle_count} — {datetime.now().strftime('%H:%M')}")
                log.info(f"{'='*55}")
                
                _reset_daily_counts()
                
                # If we still have posting quota today, run a full cycle
                if _can_post("tiktok") or _can_post("youtube"):
                    run_full_cycle()
                else:
                    log.info("  📛 Quota atteint pour aujourd'hui.")
                    # Fill stockpile while waiting for tomorrow
                    if _get_stockpile_count() < STOCKPILE_TARGET:
                        log.info("  📦 Remplissage du stockpile en attendant demain...")
                        try:
                            # 0. News Sniping (Urgent Trends)
                            try:
                                from news_snaper import get_trending_news_keywords
                                news_queries = get_trending_news_keywords(limit=5)
                                if news_queries:
                                    log.info(f"  🌊 SURFING THE NEWS WAVE: {news_queries}")
                                    n_urls = search_trending_videos(news_queries, max_results=5)
                                    for url in n_urls:
                                        if _get_stockpile_count() >= STOCKPILE_TARGET: break
                                        fill_stockpile(url)
                            except Exception as e:
                                log.error(f"  News sniping failed: {e}")

                            # 1. Sniper Mode (Fresh hits from discovered channels)
                            chans = get_discovered_channels()
                            if chans:
                                s_urls = scan_recent_buzzing_videos(chans[:5])
                                for url in s_urls:
                                    if _get_stockpile_count() >= STOCKPILE_TARGET: break
                                    fill_stockpile(url)

                            # 2. General Trend Scanner
                            queries = get_active_queries()
                            urls = search_trending_videos(queries[:5], max_results=5)
                            for url in urls:
                                if _get_stockpile_count() >= STOCKPILE_TARGET:
                                    break
                                fill_stockpile(url)
                        except Exception as e:
                            log.error(f"  Stockpile fill error (Sniper/Search): {e}")
                
                # 4. Check for Compilation potential!
                # If we have 10+ clips in stockpile, try to make a compilation
                if _get_stockpile_count() >= 10:
                    log.info("\n--- STEP 4: COMPILATION CHECK ---")
                    comp_path, comp_meta = create_compilation_from_stockpile()
                    if comp_path:
                        log.info(f"  🔥 NEW COMPILATION READY: {comp_meta['title']}")
                        # We save it back to stockpile with 'compilation' flag
                        _add_to_stockpile(comp_path, comp_meta)
                
                    # 5. Weekly AI Progress Report
                    if should_generate_report():
                        log.info("\n--- STEP 5: WEEKLY AI REPORT ---")
                        insights = get_audience_insights()
                        generate_weekly_report(insights)
                    
                    # 6. Maintenance: Auto-Pruning
                    run_pruning_cycle()

                # Adaptive pause between cycles:
                # - If we still have quota: short pause (10-20 min)
                # - If quota exhausted: wait until midnight reset
                if _can_post("tiktok") or _can_post("youtube"):
                    pause = random.randint(600, 1200)  # 10-20 min
                    log.info(f"  ⏳ Prochain cycle dans {pause//60} min...")
                else:
                    # Calculate seconds until midnight
                    now = datetime.now()
                    midnight = now.replace(hour=0, minute=5, second=0, microsecond=0)
                    if midnight <= now:
                        midnight = midnight.replace(day=now.day + 1)
                    pause = int((midnight - now).total_seconds())
                    log.info(f"  💤 Quota épuisé. Reprise dans {pause//3600}h{(pause%3600)//60}min")
                
                time.sleep(pause)
                
            except KeyboardInterrupt:
                log.info("\n🛑 Autopilot arrêté par l'utilisateur.")
                break
            except Exception as e:
                log.error(f"  Cycle error: {e}")
                time.sleep(300)  # Wait 5 min on error
    
    elif choice == "4":
        queries = get_active_queries()
        urls = search_trending_videos(queries[:10], max_results=8)
        for url in urls:
            if _get_stockpile_count() >= STOCKPILE_TARGET:
                break
            fill_stockpile(url)
        log.info(f"Stockpile: {_get_stockpile_count()}/{STOCKPILE_TARGET}")
    
    elif choice == "5":
        publish_from_stockpile()
    
    elif choice == "7":
        print("\n" + "!"*40)
        print("!!! WARNING: NUCLEAR DELETE INITIATED !!!")
        print("This will PERMANENTLY delete ALL videos from:")
        print("  - YouTube Studio (All uploads)")
        print("  - TikTok Creator Center (Last 100 uploads)")
        print("!"*40 + "\n")
        
        confirm = input("Type 'DELETE_EVERYTHING_PERMANENTLY' to confirm: ").strip()
        if confirm == 'DELETE_EVERYTHING_PERMANENTLY':
            import publisher
            print("\n☢️ Starting YouTube Wiping...")
            publisher.nuclear_delete_youtube()
            print("\n☢️ Starting TikTok Wiping...")
            publisher.nuclear_delete_tiktok()
            print("\n✅ Targeted erasure complete.")
        else:
            print("❌ Confirmation failed. Aborting nuclear option.")
            
    elif choice == "8":
        run_pruning_cycle()

    else:
        print("Invalid.")

    # Cleanup PID file on exit
    try:
        pid_file = "main.pid"
        if os.path.exists(pid_file):
            os.remove(pid_file)
    except:
        pass
