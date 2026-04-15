"""
monetization.py — Monetization Intelligence Module

Manages two phases of the account lifecycle:
  PHASE 1 (GROWTH):  Post anything viral, any length, max volume. Goal = followers.
  PHASE 2 (MONETIZED): Respect platform rules, longer clips, no copyright risk.

Thresholds for switching to PHASE 2:
  - TikTok:  10,000 followers + 100,000 views in 30 days → Creator Fund eligible
  - YouTube: 1,000 subscribers + 10M Shorts views in 90 days → YPP eligible

The system auto-detects when to switch based on stats from memory.
"""

import os
import json
import datetime

MONETIZATION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "monetization_state.json")

# =====================================================================
# PLATFORM MONETIZATION REQUIREMENTS
# =====================================================================
PLATFORM_RULES = {
    "tiktok": {
        "min_followers": 10_000,
        "min_views_30d": 100_000,
        "min_clip_duration": 61,     # 1min01 minimum for Creator Fund
        "max_clip_duration": 180,    # 3 min sweet spot
        "copyright_strict": True,    # Must avoid copyrighted audio
        "requires_original_audio": False,  # Can use trending sounds
    },
    "youtube": {
        "min_subscribers": 1_000,
        "min_views_90d": 10_000_000,
        "min_clip_duration": 30,     # Shorts can be short but longer = more $
        "max_clip_duration": 60,     # Max 60s for Shorts
        "copyright_strict": True,    # YouTube is very strict
        "requires_original_audio": True,   # Original or licensed audio only
    }
}

def _load_state():
    if os.path.exists(MONETIZATION_FILE):
        with open(MONETIZATION_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "phase": "growth",   # "growth" or "monetized"
        "tiktok_monetized": False,
        "youtube_monetized": False,
        "phase_switched_at": None,
        "estimated_followers_tiktok": 0,
        "estimated_followers_youtube": 0,
        "manual_override": None,  # User can force "monetized" mode
    }

def _save_state(state):
    with open(MONETIZATION_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

def get_current_phase():
    """Returns 'growth' or 'monetized'."""
    state = _load_state()
    if state.get("manual_override"):
        return state["manual_override"]
    return state.get("phase", "growth")

def check_monetization_eligibility(insights):
    """
    Checks if we've hit monetization thresholds based on performance data.
    Auto-switches to monetized phase when ready.
    """
    state = _load_state()
    total_views = insights.get("total_views", 0)
    total_posts = insights.get("total_posts_analyzed", 0)
    
    # Rough estimates (refined by monitor over time)
    estimated_tiktok_followers = total_views // 200   # ~1 follower per 200 views
    estimated_youtube_subs = total_views // 500        # Harder to gain subs
    
    state["estimated_followers_tiktok"] = estimated_tiktok_followers
    state["estimated_followers_youtube"] = estimated_youtube_subs
    
    # Check TikTok
    if estimated_tiktok_followers >= PLATFORM_RULES["tiktok"]["min_followers"]:
        if not state["tiktok_monetized"]:
            state["tiktok_monetized"] = True
            print(f"  [MONETIZATION] 🎉 TikTok monetization likely eligible! ({estimated_tiktok_followers:,} est. followers)")
    
    # Check YouTube
    if estimated_youtube_subs >= PLATFORM_RULES["youtube"]["min_subscribers"]:
        if not state["youtube_monetized"]:
            state["youtube_monetized"] = True
            print(f"  [MONETIZATION] 🎉 YouTube monetization likely eligible! ({estimated_youtube_subs:,} est. subs)")
    
    # Switch phase if ANY platform is monetized
    if (state["tiktok_monetized"] or state["youtube_monetized"]) and state["phase"] == "growth":
        state["phase"] = "monetized"
        state["phase_switched_at"] = datetime.datetime.now().isoformat()
        print(f"  [MONETIZATION] ⚡ PHASE SWITCH → MONETIZED MODE ACTIVATED")
    
    _save_state(state)
    return state

def get_clip_duration_range(platform="tiktok"):
    """Returns (min_seconds, max_seconds) based on current phase."""
    phase = get_current_phase()
    
    if phase == "growth":
        # Growth phase: any length that's viral (15-60s)
        return (15, 60)
    else:
        # Monetized: respect platform minimums
        rules = PLATFORM_RULES.get(platform, PLATFORM_RULES["tiktok"])
        return (rules["min_clip_duration"], rules["max_clip_duration"])

def get_content_rules():
    """
    Returns a dict of rules that the analyzer/editor must follow.
    These rules CHANGE based on the current phase.
    """
    phase = get_current_phase()
    state = _load_state()
    
    if phase == "growth":
        return {
            "phase": "growth",
            "min_duration_tiktok": 15,
            "max_duration_tiktok": 60,
            "min_duration_youtube": 15,
            "max_duration_youtube": 60,
            "copyright_strict": False,   # Growth: don't worry too much
            "must_add_value": False,     # Raw clips are fine
            "must_add_branding": False,
            "prompt_rules": (
                "PHASE: GROWTH MODE — Maximum virality, any content type. "
                "Priority is views and followers. Short punchy clips (15-60s)."
            ),
        }
    else:
        return {
            "phase": "monetized",
            "min_duration_tiktok": 61,   # 1min01 minimum
            "max_duration_tiktok": 180,
            "min_duration_youtube": 30,
            "max_duration_youtube": 59,   # Must stay under 60s for Shorts
            "copyright_strict": True,
            "must_add_value": True,       # Must transform content
            "must_add_branding": True,
            "prompt_rules": (
                "PHASE: MONETIZED MODE — Content must be ORIGINAL ENOUGH to avoid copyright claims. "
                f"TikTok clips MUST be 61-180 seconds (1min01 minimum for Creator Fund). "
                f"YouTube clips must be 30-59 seconds. "
                "Add commentary context, unique framing, or educational value. "
                "Avoid using copyrighted music segments. "
                "Focus on WATCH TIME (keep people watching until the end) over just hooks."
            ),
            "tiktok_monetized": state.get("tiktok_monetized", False),
            "youtube_monetized": state.get("youtube_monetized", False),
        }

def force_phase(phase):
    """Manually override the phase ('growth' or 'monetized')."""
    state = _load_state()
    state["manual_override"] = phase
    _save_state(state)
    print(f"  [MONETIZATION] Phase forced to: {phase}")

if __name__ == "__main__":
    print(f"Current phase: {get_current_phase()}")
    print(f"Rules: {json.dumps(get_content_rules(), indent=2)}")
