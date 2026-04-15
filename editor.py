import os
import subprocess
import platform
import time

def _get_ffmpeg_path():
    """Finds FFmpeg anywhere: local dir, pip package, or system PATH."""
    # Check local project directory
    local_paths = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg", "bin", "ffmpeg.exe"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg.exe"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg", "ffmpeg.exe"),
    ]
    for p in local_paths:
        if os.path.exists(p):
            return p
    # Try pip-installed ffmpeg (imageio-ffmpeg)
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        pass
    # Fallback to system PATH
    return "ffmpeg"

FFMPEG = _get_ffmpeg_path()
CLIPS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "clips")
os.makedirs(CLIPS_DIR, exist_ok=True)

def _get_preferred_style():
    """Fetch the latest learned styles from the strategy engine."""
    try:
        from strategy import _load_strategy
        state = _load_strategy()
        learned = state.get("learned_styles", [])
        if learned:
            # We take the most recent one for now
            return learned[0]
    except:
        pass
    return {}

def _resolve_font(style_name):
    """Maps a genetic font name (Bold Sans, Impact) to a system font file."""
    if platform.system() != "Windows": return ""
    
    mapping = {
        "impact-style": [r"C\:/Windows/Fonts/impact.ttf", r"C\:/Windows/Fonts/arialbd.ttf"],
        "bold sans": [r"C\:/Windows/Fonts/arialbd.ttf", r"C\:/Windows/Fonts/segoeui.ttf"],
        "handwritten": [r"C\:/Windows/Fonts/comic.ttf", r"C\:/Windows/Fonts/segoeprb.ttf"],
        "comic": [r"C\:/Windows/Fonts/comic.ttf", r"C\:/Windows/Fonts/arial.ttf"],
        "sans-serif": [r"C\:/Windows/Fonts/arial.ttf", r"C\:/Windows/Fonts/segoeui.ttf"]
    }
    
    candidates = mapping.get(style_name.lower(), [r"C\:/Windows/Fonts/arialbd.ttf"])
    for fc in candidates:
        if os.path.exists(fc.replace(r"\:", ":")):
            return fc.replace("\\", "/")
    return ""

def create_short_clip(video_path, start_sec, end_sec, output_filename="clip", pov_text=None, template="premium_banner", background_path=None):
    """
    Extracts a segment from the source video and applies a dynamic visual layout.
    Can combine a main video with a background 'hook' asset (e.g. gameplay).
    """
    output_path = os.path.join(CLIPS_DIR, f"{output_filename}.mp4")
    duration = end_sec - start_sec
    
    if duration < 5:
        print("  [EDITOR] Clip too short (< 5s), skipping.")
        return None
    
    fade_in = 0.3
    fade_out = 0.5
    
    # --- META-ADAPTIVE STACK ENGINE ---
    if template in ["split_screen_gameplay", "split_screen_satisfying"] and background_path and os.path.exists(background_path):
        # 2-layer Stack: Main Video on Top, Background Hook on Bottom
        # We also need to loop or trim the background to match duration
        vf = (
            f"[0:v]scale=1080:1080:force_original_aspect_ratio=increase,crop=1080:1080[top];"
            f"[1:v]scale=1080:840:force_original_aspect_ratio=increase,crop=1080:840[bottom];"
            f"[top][bottom]vstack=inputs=2"
        )
        input_args = ["-ss", str(start_sec), "-i", video_path, "-stream_loop", "-1", "-i", background_path]
    
    elif template == "premium_banner":
        # Classic centered video with blurred background
        vf = (
            f"split[v1][v2];"
            f"[v1]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:10[bg];"
            f"[v2]scale=1080:-2[vid];"
            f"[bg][vid]overlay=(W-w)/2:(H-h)/2"
        )
        input_args = ["-ss", str(start_sec), "-i", video_path]
        
    elif template == "cinematic_movie":
        vf = f"scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black"
        input_args = ["-ss", str(start_sec), "-i", video_path]
        
    else: # classic_916 or unknown
        vf = f"scale=-2:1920:flags=bitexact,crop=1080:1920:(iw-1080)/2:0"
        input_args = ["-ss", str(start_sec), "-i", video_path]
    
    # Add transitions & duration limit
    vf += f",fade=t=in:st=0:d={fade_in},fade=t=out:st={duration - fade_out}:d={fade_out}"
    
    af = f"loudnorm=I=-16:TP=-1.5:LRA=11,afade=t=out:st={duration - fade_out}:d={fade_out}"
    
    cmd = [
        FFMPEG, "-y"
    ] + input_args + [
        "-t", str(duration),
        "-vf", vf,
        "-af", af,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        output_path
    ]
    
    try:
        print(f"  [EDITOR] Encoding [{template}]: {start_sec}s → {end_sec}s")
        subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if template == "premium_banner" and pov_text and os.path.exists(output_path):
            add_pov_banner(output_path, pov_text)
            
        return output_path
    except Exception as e:
        print(f"  [EDITOR] Clip creation error: {e}")
        return None

def add_pov_banner(clip_path, text):
    """Adds a large, stylized POV/Headline banner at the top of the video."""
    if not text: return
    
    temp_output = clip_path.replace(".mp4", "_pov_temp.mp4")
    clean_text = text.upper().strip()
    
    # Font path logic (reused from subtitles)
    font_path = ""
    if platform.system() == "Windows":
        font_candidates = [r"C\:/Windows/Fonts/impact.ttf", r"C\:/Windows/Fonts/arialbd.ttf"]
        for fc in font_candidates:
            if os.path.exists(fc.replace(r"\:", ":")):
                font_path = fc.replace("\\", "/")
                break
    
    font_config = f":fontfile='{font_path}'" if font_path else ""
    
    # drawtext for the top banner
    # Center text horizontally, put it at 8% height
    drawtext = (
        f"drawtext=text='{clean_text}'"
        f"{font_config}"
        f":fontsize=72:fontcolor=white:borderw=4:bordercolor=black"
        f":x=(w-text_w)/2:y=h*0.08"
    )
    
    cmd = [
        FFMPEG, "-y",
        "-i", clip_path,
        "-vf", drawtext,
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20",
        "-c:a", "copy",
        temp_output
    ]
    
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if os.path.exists(temp_output):
            os.remove(clip_path)
            os.rename(temp_output, clip_path)
    except:
        pass

def merge_clips(clip_paths, output_filename="compilation"):
    """
    Merges multiple clips into a single video with simple cuts.
    Standardizes all clips to 1080x1920 before merging.
    """
    if not clip_paths: return None
    
    output_path = os.path.join(CLIPS_DIR, f"{output_filename}_{int(time.time())}.mp4")
    
    # Create a list file for FFmpeg concat demuxer
    list_file = os.path.join(CLIPS_DIR, "concat_list.txt")
    with open(list_file, "w") as f:
        for p in clip_paths:
            # Use absolute path and escape it
            abs_p = os.path.abspath(p).replace("\\", "/")
            f.write(f"file '{abs_p}'\n")
            
    cmd = [
        FFMPEG, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", list_file,
        "-c", "copy", # Fast merge if all properties are same
        output_path
    ]
    
    try:
        print(f"  [EDITOR] Merging {len(clip_paths)} clips into compilation...")
        subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if os.path.exists(list_file): os.remove(list_file)
        
        if os.path.exists(output_path):
            print(f"  [EDITOR] ✓ Compilation saved: {output_path}")
            return output_path
    except Exception as e:
        print(f"  [EDITOR] Merge error: {e}")
        
    return None

def add_subtitles_to_clip(clip_path, subtitle_text, position="bottom"):
    """
    Burns stylized subtitles onto a clip using FFmpeg's drawtext filter.
    
    Features:
    - Bold white text with black outline
    - Semi-transparent background box
    - Word wrapping for long text
    - Configurable position (top/center/bottom)
    """
    if not subtitle_text or not subtitle_text.strip():
        return clip_path
    
    # Clean text for FFmpeg (escape special chars)
    clean_text = subtitle_text.strip()
    clean_text = clean_text.replace("'", "'")
    clean_text = clean_text.replace(":", "\\:")
    clean_text = clean_text.replace("\\", "\\\\")
    clean_text = clean_text.replace("%", "%%")
    
    # Wrap long text
    max_chars_per_line = 30
    words = clean_text.split()
    lines = []
    current_line = ""
    for word in words:
        if len(current_line + " " + word) > max_chars_per_line:
            lines.append(current_line.strip())
            current_line = word
        else:
            current_line += " " + word
    if current_line.strip():
        lines.append(current_line.strip())
    wrapped = "\n".join(lines[:3])  # Max 3 lines
    
    # Position mapping
    y_positions = {
        "top": "h*0.08",
        "center": "(h-text_h)/2",
        "bottom": "h*0.80",
    }
    # --- ADAPTIVE STYLE LOADING ---
    styled_font = ""
    text_color = "white"
    stroke_color = "black"
    learned_style = _get_preferred_style()
    
    if learned_style:
        # Resolve font
        styled_font = _resolve_font(learned_style.get("font_style", ""))
        
        # Colors
        colors = learned_style.get("subtitle_colors", {})
        text_color = colors.get("text") or "white"
        stroke_color = colors.get("outline") or "black"
        
        # Position mapping
        y_pos_map = {
            "top": "h*0.08",
            "middle": "(h-text_h)/2",
            "bottom-third": "h*0.70",
            "bottom": "h*0.80",
        }
        y_pos_learned = y_pos_map.get(learned_style.get("subtitle_position"), "h*0.80")
        y_pos = y_positions.get(position, y_pos_learned)
    else:
        y_pos = y_positions.get(position, y_positions["bottom"])

    # Final drawtext filter construction
    font_path = styled_font or font_path # Use learned if available
    if font_path:
        font_config = f":fontfile='{font_path}'"
    else:
        font_config = ""

    # Double escape backslashes for FFmpeg
    drawtext_text = wrapped.replace("\\", "\\\\").replace("'", "'").replace(":", "\\:")
    
    drawtext = (
        f"drawtext=text='{drawtext_text}'"
        f"{font_config}"
        f":fontsize=52:fontcolor={text_color}:borderw=3:bordercolor={stroke_color}"
        f":box=1:boxcolor=black@0.4:boxborderw=8"
        f":x=(w-text_w)/2:y={y_pos}:line_spacing=8"
    )
    
    # Define missing output_path for temporary subbed video
    output_path = clip_path.replace(".mp4", "_subbed.mp4")
    
    cmd = [
        FFMPEG, "-y",
        "-i", clip_path,
        "-vf", drawtext,
        "-c:v", "libx264",
        "-preset", "ultrafast",  # Subtitles should be fast
        "-crf", "20",
        "-c:a", "copy",
        "-movflags", "+faststart",
        output_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode != 0:
            print(f"  [EDITOR] Subtitle burn failed (FFmpeg exit {result.returncode})")
            # Log first few lines of stderr if error
            if result.stderr:
                print(f"  [EDITOR] FFmpeg Error: {result.stderr.splitlines()[0] if result.stderr.splitlines() else ''}")
            return clip_path
        
        # Replace original with subtitled version
        if os.path.exists(output_path):
            os.remove(clip_path)
            os.rename(output_path, clip_path)
            print(f"  [EDITOR] ✓ Subtitles burned successfully")
        return clip_path
        
    except Exception as e:
        print(f"  [EDITOR] Subtitle error: {e}")
        return clip_path

if __name__ == "__main__":
    pass
