"""
trend_analyzer.py — Meta-Adaptive Evolution for AutoClipAI
Observes viral videos, analyzes their layouts, and learns the 'Meta'.
"""

import os
import subprocess
import json
import logging
from google import genai
from PIL import Image
from strategy import _load_strategy, _save_strategy

log = logging.getLogger("AutoClipAI")

def _get_video_frame(video_url, output_path="trend_frame.jpg"):
    """Extracts a frame from a YouTube/TikTok video URL using ffmpeg + yt-dlp."""
    try:
        # Get streaming URL
        cmd_url = ["yt-dlp", "-g", "-f", "best[ext=mp4]", video_url]
        res = subprocess.run(cmd_url, capture_output=True, text=True, timeout=30)
        stream_url = res.stdout.strip().split("\n")[0]
        
        if not stream_url:
            return None
            
        # Extract frame at 10s
        cmd_frame = [
            "ffmpeg", "-y", "-ss", "00:00:10", 
            "-i", stream_url, 
            "-vframes", "1", 
            "-f", "image2", 
            output_path
        ]
        subprocess.run(cmd_frame, capture_output=True, timeout=60)
        
        if os.path.exists(output_path):
            return output_path
    except Exception as e:
        log.error(f"  [TRENDS] Frame extraction failed: {e}")
    return None

def analyze_meta_DNA(video_url, description=""):
    """
    Analyzes a viral video to detect its 'Visual DNA' and 'Metadata Strategy'.
    Uses Gemini Vision + Text analysis.
    """
    key = os.environ.get("GEMINI_API_KEY")
    if not key: return None

    frame_path = _get_video_frame(video_url)
    if not frame_path:
        log.warning(f"  [TRENDS] Could not extract frame for {video_url}. Skipping vision analysis.")
        frame_path = None

    client = genai.Client(api_key=key)
    
    # --- PHASE 1: VISUAL DNA (If frame exists) ---
    visual_dna = {}
    if frame_path:
        vision_prompt = """Analyze this video frame as a master viral editor.
        Identify the SPECIFIC visual styling used to make it catchy.
        
        Return JSON including:
        1. 'layout': (split_screen_gameplay, split_screen_satisfying, centered_blurred, full_vertical)
        2. 'font_style': (Impact-style, Bold Sans, Handwritten, Comic, Sans-Serif)
        3. 'subtitle_position': (top, middle, bottom-third, bottom)
        4. 'subtitle_colors': { 'text': 'hex_color', 'outline': 'hex_color' }
        5. 'background_asset': (minecraft, subway_surfers, slime, kinetic_sand, none)
        6. 'accent_colors': [list of 2 dominant hex colors for overlays]
        """
        try:
            img = Image.open(frame_path)
            response = client.models.generate_content(
                model="gemini-2.0-flash-lite",
                contents=[vision_prompt, img]
            )
            res_text = response.text.strip()
            if "```json" in res_text:
                res_text = res_text.split("```json")[1].split("```")[0].strip()
            visual_dna = json.loads(res_text)
        except Exception as e:
            log.error(f"  [TRENDS] Vision DNA analysis failed: {e}")

    # --- PHASE 2: METADATA STRATEGY ---
    meta_prompt = f"""Analyze this viral video description/tags.
    VIDEO URL: {video_url}
    DESCRIPTION: {description[:1000]}
    
    Extract the 'Success Strategy' in JSON:
    1. 'hook_style': (Question, Shocking Statement, CLIFFHANGER, How-to)
    2. 'recurring_hashtags': [list of top 5 relevant viral hashtags]
    3. 'call_to_action': (Follow for part 2, Comment your thoughts, link in bio)
    4. 'topic_niche': The specific sub-niche.
    """
    
    metadata_strategy = {}
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash-lite",
            contents=[meta_prompt]
        )
        res_text = response.text.strip()
        if "```json" in res_text:
            res_text = res_text.split("```json")[1].split("```")[0].strip()
        metadata_strategy = json.loads(res_text)
    except Exception as e:
        log.error(f"  [TRENDS] Metadata strategy analysis failed: {e}")

    # Clean up
    if frame_path and os.path.exists(frame_path):
        os.remove(frame_path)

    return {
        "visual": visual_dna,
        "strategy": metadata_strategy,
        "last_updated": os.environ.get("CURRENT_TIME", "")
    }

def update_learned_layouts(viral_info_list):
    """
    Scans viral info (dicts from downloader) to learn and update 
    the trending styles and strategies.
    """
    log.info(f"  [TRENDS] Deep learning from {len(viral_info_list)} viral sources...")
    state = _load_strategy()
    
    learned_styles = state.get("learned_styles", [])
    learned_strategies = state.get("learned_strategies", [])
    
    for info in viral_info_list[:3]: # Deep analysis for top 3
        if isinstance(info, str):
            url = info
            desc = ""
        else:
            url = info.get("url") or f"https://www.youtube.com/watch?v={info.get('id')}"
            desc = info.get("description", "")
        
        dna = analyze_meta_DNA(url, description=desc)
        if dna:
            if dna.get("visual"):
                learned_styles.insert(0, dna["visual"])
            if dna.get("strategy"):
                learned_strategies.insert(0, dna["strategy"])
            
    # Keep it fresh - only last 10
    state["learned_styles"] = learned_styles[:10]
    state["learned_strategies"] = learned_strategies[:10]
    
    _save_strategy(state)
    log.info(f"  [TRENDS] ✓ Absorbed new visual and strategic DNA.")
    return True

if __name__ == "__main__":
    # Test with a known viral short
    test_url = "https://www.youtube.com/shorts/dQw4w9WgXcQ" # Replace with real short for testing
    print(analyze_meta_DNA(test_url))
