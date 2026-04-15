"""
assets_manager.py — Managing 'Hook Backgrounds' for trending layouts.
Downloads and caches Minecraft, Subway Surfers, and other satisfying clips.
"""

import os
import random
import logging
import glob
import subprocess
import yt_dlp

log = logging.getLogger("AutoClipAI")

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "backgrounds")
os.makedirs(ASSETS_DIR, exist_ok=True)

def download_background_hook(hook_type):
    """
    Searches YouTube for a 'no copyright' loop of the requested type
    and downloads a high-quality snippet.
    """
    log.info(f"  [ASSETS] Searching for new hook background: {hook_type}")
    
    query = f"no copyright {hook_type} gameplay loop 4k"
    if "minecraft" in hook_type.lower():
        query = "no copyright minecraft parkour gameplay loop 4k"
    elif "subway" in hook_type.lower():
        query = "no copyright subway surfers gameplay loop 4k"
        
    ydl_opts = {
        'format': 'bestvideo[height<=1080][ext=mp4]/best[ext=mp4]',
        'outtmpl': os.path.join(ASSETS_DIR, f"{hook_type.replace(' ', '_')}_temp.%(ext)s"),
        'max_filesize': 50 * 1024 * 1024, # 50MB max for a background
        'quiet': True,
        'noplaylist': True,
        'default_search': 'ytsearch1',
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([query])
            
        # Rename to final file if downloader added extension
        temp_files = glob.glob(os.path.join(ASSETS_DIR, f"{hook_type.replace(' ', '_')}_temp.*"))
        if temp_files:
            final_path = os.path.join(ASSETS_DIR, f"{hook_type.replace(' ', '_')}.mp4")
            if os.path.exists(final_path): os.remove(final_path)
            os.rename(temp_files[0], final_path)
            log.info(f"  [ASSETS] ✓ Downloaded {hook_type} hook.")
            return final_path
    except Exception as e:
        log.error(f"  [ASSETS] Failed to download {hook_type}: {e}")
    return None

def get_random_background(hook_type=None):
    """Returns the path to a background clip, downloading it if necessary."""
    if not hook_type:
        # Pick whatever we have
        existing = glob.glob(os.path.join(ASSETS_DIR, "*.mp4"))
        if existing:
            return random.choice(existing)
        hook_type = "minecraft_parkour" # Default
        
    path = os.path.join(ASSETS_DIR, f"{hook_type.replace(' ', '_')}.mp4")
    if not os.path.exists(path):
        return download_background_hook(hook_type)
        
    return path

if __name__ == "__main__":
    # Test
    print(get_random_background("minecraft parkour"))
