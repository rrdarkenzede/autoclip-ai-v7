import os
import json
import re
import time
import traceback
from google import genai
from google.genai import types
from monetization import get_content_rules, check_monetization_eligibility
from strategy import _load_strategy

def _call_gemini_vision(video_path, insights=None, api_key=None):
    """
    Uploads a video to Gemini and asks it to find the best viral moments.
    Uses a cascade of models (best → cheapest) with automatic fallback.
    Injects full learning data from past performance.
    """
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        print("  [ANALYZER] Error: GEMINI_API_KEY is not set.")
        return []

    client = genai.Client(api_key=key)
    
    file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
    print(f"  [ANALYZER] Uploading {os.path.basename(video_path)} ({file_size_mb:.1f} MB)...")
    
    try:
        video_file = client.files.upload(file=video_path)
        print(f"  [ANALYZER] Uploaded as: {video_file.name}")
        
        # Wait for processing with timeout
        retries = 0
        while video_file.state.name == "PROCESSING":
            retries += 1
            if retries > 60:  # 10 min max
                print("  [ANALYZER] Timeout — video processing took too long.")
                return []
            if retries % 6 == 0:
                print(f"  [ANALYZER] Still processing... ({retries * 10}s)")
            time.sleep(10)
            video_file = client.files.get(name=video_file.name)
            
        if video_file.state.name == "FAILED":
            print("  [ANALYZER] Video processing failed on server side.")
            return []
            
        print("  [ANALYZER] Video ready. Building intelligence prompt...")
        
        # ========== BUILD THE ULTIMATE LEARNING PROMPT ==========
        insights_block = ""
        if insights and insights.get("total_posts_analyzed", 0) > 0:
            tags = insights.get("tags", [])
            comments = insights.get("comments", [])
            best_tags = insights.get("best_tags_by_engagement", [])
            ratio = insights.get("best_engagement_ratio", 0)
            total_views = insights.get("total_views", 0)
            best_hours = insights.get("best_posting_hours", [])
            best_days = insights.get("best_posting_days", [])
            best_duration = insights.get("best_duration_range", "")
            best_descriptions = insights.get("best_descriptions", [])
            best_style = insights.get("best_caption_style", "")
            perf_summary = insights.get("performance_summary", "")
            
            insights_block = "\n\n=== 📊 PERFORMANCE DATA FROM PAST POSTS ===\n"
            insights_block += f"Posts analyzed: {insights.get('total_posts_analyzed', 0)} | Total views: {total_views:,}\n\n"
            
            if perf_summary:
                insights_block += f"⚡ QUICK STRATEGY: {perf_summary}\n\n"
            
            if best_tags and ratio > 0:
                insights_block += f"🏆 BEST TAGS (ratio {ratio:.1%}): {', '.join(best_tags)}\n"
            if tags:
                insights_block += f"📌 All winning tags: {', '.join(tags[:12])}\n"
            if best_duration:
                insights_block += f"⏱ OPTIMAL DURATION: {best_duration}\n"
            if best_hours:
                insights_block += f"🕐 BEST HOURS: {best_hours}\n"
            if best_days:
                insights_block += f"📅 BEST DAYS: {', '.join(str(d) for d in best_days)}\n"
            if best_style:
                insights_block += f"🎭 WINNING STYLE: '{best_style}'\n"
            
            if best_descriptions:
                insights_block += "\n📝 TOP PERFORMING DESCRIPTIONS (copy their energy):\n"
                for i, desc in enumerate(best_descriptions[:3], 1):
                    insights_block += f'  {i}. "{desc[:200]}"\n'
            
            if comments:
                insights_block += "\n💬 REAL AUDIENCE COMMENTS (what makes them engage):\n"
                for c in comments[:8]:
                    insights_block += f'  • "{c}"\n'
            
            insights_block += "\n🎯 Use ALL of this data. Evolve. Outperform your past results.\n"
            insights_block += "=== END DATA ===\n"
        
        # ========== MONETIZATION-AWARE RULES ==========
        if insights:
            check_monetization_eligibility(insights)
        rules = get_content_rules()
        phase = rules["phase"]
        monetization_prompt = rules["prompt_rules"]
        min_dur_tt = rules["min_duration_tiktok"]
        max_dur_tt = rules["max_duration_tiktok"]
        
        # Include visual trends and metadata strategies from strategy engine
        state = _load_strategy()
        learned_layouts = state.get("learned_layouts", [])
        learned_styles = state.get("learned_styles", [])
        learned_strategies = state.get("learned_strategies", [])
        
        trends_block = ""
        if learned_layouts or learned_styles:
            trends_block = "\n=== 🎨 LEARNED VISUAL DNA (Adopt this style) ===\n"
            if learned_layouts:
                trends_block += f"Layouts: {learned_layouts[:3]}\n"
            if learned_styles:
                trends_block += f"Visual Styles: {learned_styles[:2]}\n"
        
        strategy_block = ""
        if learned_strategies:
            strategy_block = "\n=== 🧬 LEARNED METADATA DNA (Copy this energy) ===\n"
            strategy_block += f"Top Strategies: {learned_strategies[:3]}\n"
        
        prompt = f"""You are an elite viral content strategist who has generated billions of views on TikTok and YouTube Shorts.

{monetization_prompt}

MISSION: Watch this entire video frame by frame. Extract the TOP 3 moments that will EXPLODE on social media.

SELECTION CRITERIA (in order of importance):
1. HOOK POWER — The first 2 seconds must make someone stop scrolling (shock, curiosity, humor)
2. EMOTIONAL PAYLOAD — The clip must trigger a strong feeling (laughter, outrage, awe, relatability)
3. SHAREABILITY — Would someone send this to a friend? Would they tag someone?
4. SELF-CONTAINED — A viewer with ZERO context must enjoy this clip on its own
5. REWATCH VALUE — Is it so good people watch it twice?
6. WATCH TIME — The viewer must stay until the END. Build tension, don't resolve too early.

CLIP RULES:
- Duration: {min_dur_tt}-{max_dur_tt} seconds
- Must start on a HIGH ENERGY moment, not a buildup
- Cut BEFORE the energy dies — leave them wanting more
- If someone talks, include the COMPLETE thought (don't cut mid-sentence)
- RETENTION: Structure the clip so the payoff is in the LAST 20% (keeps watch time high)

DESCRIPTION RULES:
- First line: HOOK (question, bold claim, or emotional trigger)
- Include 1 call-to-action ("Follow for more", "Drop a 🔥 if you agree", "Tag someone who...")
- Use emojis strategically (not spam)
- End with hashtags mixed: 3 broad (#fyp #viral #trending) + 4 niche-specific

CAPTION STYLE — classify as one of:
- "humor", "shock", "relatable", "educational", "controversial", "emotional", "hype"

VISUAL TEMPLATE — Select based on current 'Meta' trends or content type:
- "premium_banner": Video in middle, big title banner at top
- "split_screen_gameplay": Video A on top, Video B (gameplay) on bottom
- "split_screen_satisfying": Video A on top, Video B (satisfying clip) on bottom
- "cinematic_movie": Horizontal padded with blurred edges
- "classic_916": Standard center-crop

{insights_block}
{trends_block}
{strategy_block}
GLOBAL VIRALITY — Detect the source video language.
If the content is NOT in English, translate ALL generated captions (title, pov_caption, hook) to English to ensure maximum global reach.

OUTPUT FORMAT — JSON array of objects:
[
  {{
    "start_time": <number>,
    "end_time": <number>,
    "title": "<catchy English caption>",
    "pov_caption": "<headline text in English>",
    "original_language": "<detected language ISO code>",
    "visual_template": "<one of the templates above>",
    "background_type": "<minecraft, subway_surfers, or None>",
    "compilation_category": "<theme>",
    "description": "<hashtags included>",
    "suggested_tags": ["tag1", "tag2", ...],
    "caption_style": "<style>",
    "hook": "<first 2 seconds text translated to English>",
    "reason": "<viral potential>"
  }}
]

Return ONLY the raw JSON. No markdown fences, no extra text."""
        
        # ========== MODEL CASCADE ==========
        models_to_try = [
            "gemini-3.1-flash-lite",
            "gemini-2.5-flash-lite",
            "gemini-3.1-pro",
            "gemini-3-flash",
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-1.5-flash"
        ]
        
        response = None
        used_model = None
        
        for model_name in models_to_try:
            print(f"  [ANALYZER] Trying: {model_name}...")
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[video_file, prompt],
                    config=types.GenerateContentConfig(
                        temperature=0.8,
                        response_mime_type="application/json"
                    )
                )
                
                # Verify the response actually has content
                if response and response.text and len(response.text.strip()) > 10:
                    used_model = model_name
                    print(f"  [ANALYZER] ✓ {model_name} responded ({len(response.text)} chars)")
                    break
                else:
                    print(f"  [ANALYZER] ✗ {model_name} returned empty response")
                    
            except Exception as model_error:
                print(f"  [ANALYZER] ✗ {model_name}: {str(model_error)[:120]}")
                
        if not response or not response.text:
            print("  [ANALYZER] All models failed.")
            return []
        
        # ========== ROBUST JSON PARSING ==========
        raw = response.text.strip()
        
        # Strip markdown code fences if present
        if raw.startswith("```"):
            lines = raw.split("\n")
            # Remove first and last lines (``` markers)
            lines = [l for l in lines if not l.strip().startswith("```")]
            raw = "\n".join(lines).strip()
        
        # Sometimes models prefix with "json\n"
        if raw.startswith("json"):
            raw = raw[4:].strip()
        
        # Try parsing
        results = None
        try:
            results = json.loads(raw)
        except json.JSONDecodeError:
            # Try to find JSON array in the text
            match = re.search(r'\[.*\]', raw, re.DOTALL) if 'import re' or True else None
            import re
            match = re.search(r'\[.*\]', raw, re.DOTALL)
            if match:
                try:
                    results = json.loads(match.group())
                except json.JSONDecodeError:
                    pass
        
        if not results:
            print(f"  [ANALYZER] JSON parse failed. Raw output:\n{raw[:500]}")
            return []
        
        # Validate & clean
        if isinstance(results, list):
            valid = []
            for r in results:
                if isinstance(r, dict) and "start_time" in r and "end_time" in r:
                    # Ensure all fields exist with defaults
                    r.setdefault("title", "Viral Clip 🔥")
                    r.setdefault("pov_caption", r["title"])
                    r.setdefault("visual_template", "premium_banner")
                    r.setdefault("compilation_category", "General")
                    r.setdefault("description", r["title"])
                    r.setdefault("suggested_tags", ["viral", "fyp", "trending"])
                    r.setdefault("caption_style", "unknown")
                    r.setdefault("hook", "")
                    r.setdefault("reason", "")
                    valid.append(r)
            
            print(f"  [ANALYZER] ✅ {len(valid)} viral moments extracted (model: {used_model})")
            return valid
        
        print(f"  [ANALYZER] Unexpected response type: {type(results)}")
        return []
            
    except Exception as e:
        print(f"  [ANALYZER] Critical error: {e}")
        traceback.print_exc()
        return []
    finally:
        try:
            if 'video_file' in locals() and video_file:
                client.files.delete(name=video_file.name)
        except Exception:
            pass

# ==============================================================================
# RECURSIVE CHUNKER & ORCHESTRATOR
# ==============================================================================
import subprocess

def _get_video_duration(path):
    from editor import FFMPEG
    res = subprocess.run([FFMPEG, "-i", path], capture_output=True, text=True)
    match = re.search(r"Duration:\s+(\d+):(\d+):(\d+\.\d+)", res.stderr)
    if match:
        h, m, s = match.groups()
        return float(h)*3600 + float(m)*60 + float(s)
    return 0
    
def _cut_segment(video_path, start_sec, dur_sec, output_path):
    from editor import FFMPEG
    # Use fast seek and stream copy for instant, lossless splitting
    cmd = [FFMPEG, "-y", "-ss", str(start_sec), "-i", video_path, "-t", str(dur_sec), "-c", "copy", output_path]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return output_path

def analyze_video_for_viral_moments(video_path, insights=None, api_key=None, start_offset=0.0, max_duration=600):
    """
    Recursively cuts the video into manageable chunks (e.g. 10 mins) using FFmpeg to bypass
    Gemini quota/size limits. If the API fails on a chunk, cuts it in half and retries.
    """
    duration = _get_video_duration(video_path)
    
    # If the video is longer than the max limit (with a 5 second tolerance for keyframe inaccuracy), split it
    if duration > max_duration + 5:
        print(f"  [ANALYZER] Video is {duration/60:.1f}m long. Splitting into {max_duration/60:.1f}m chunks...")
        all_clips = []
        for start_t in range(0, int(duration), max_duration):
            chunk_dur = min(max_duration, duration - start_t)
            if chunk_dur < 30:  # Skip tiny leftover tails
                continue
            
            chunk_path = f"{video_path}_chunk_{start_t}.mp4"
            print(f"\n  [ANALYZER] -> Processing chunk: {start_t}s to {start_t + chunk_dur}s")
            _cut_segment(video_path, start_t, chunk_dur, chunk_path)
            
            # Recurse on the chunk
            chunk_clips = analyze_video_for_viral_moments(
                chunk_path, 
                insights=insights, 
                api_key=api_key,
                start_offset=start_offset + start_t, 
                max_duration=max_duration
            )
            
            # Clean up the temp chunk
            if os.path.exists(chunk_path):
                try: os.remove(chunk_path)
                except: pass
                
            all_clips.extend(chunk_clips)
            
        print(f"  [ANALYZER] Finished stitching {len(all_clips)} total clips from chunks.")
        return all_clips

    # Try Gemini on this viable chunk
    clips = _call_gemini_vision(video_path, insights, api_key)
    
    # Error fallback: if Gemini fails on this block, cut it in half and recurse
    if not clips and duration > 120:
        print(f"  [ANALYZER] Model failed on {duration/60:.1f}m chunk! Slicing in half to bypass quota...")
        return analyze_video_for_viral_moments(
            video_path, 
            insights=insights, 
            api_key=api_key,
            start_offset=start_offset, 
            max_duration=int(duration / 2)
        )
        
    # Standardize and offset the timestamps relative to the absolute original video
    for c in clips:
        c["start_time"] += start_offset
        c["end_time"] += start_offset
        
    return clips
