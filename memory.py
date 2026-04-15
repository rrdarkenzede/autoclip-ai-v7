import os
import json
import datetime
from dotenv import load_dotenv

load_dotenv()

# =====================================================================
# AUTO-DETECT BACKEND (Supabase > Local JSON)
# =====================================================================
def _supabase_available():
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY", "")
    return bool(url and key and len(url) > 10)

def _init_supabase():
    from supabase import create_client
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

LOCAL_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "local_memory.json")

def _load_local_db():
    if os.path.exists(LOCAL_DB_PATH):
        with open(LOCAL_DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"posts": [], "patterns": {}}

def _save_local_db(db):
    with open(LOCAL_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

# =====================================================================
# LOG A POST (called after every publish)
# =====================================================================
def log_post(clip_data, platform="tiktok"):
    """
    Saves extensive metadata about a published clip.
    Tracks everything needed for the AI learning loop.
    """
    now = datetime.datetime.now()
    post_record = {
        "title": clip_data.get("title", ""),
        "description": clip_data.get("description", ""),
        "tags": clip_data.get("suggested_tags", []),
        "platform": platform,
        "status": "posted",
        "source_url": clip_data.get("source_url", ""),
        "clip_path": clip_data.get("path", ""),
        "clip_duration_sec": clip_data.get("duration", 0),
        "caption_style": clip_data.get("caption_style", "unknown"),
        "hook_text": clip_data.get("hook", ""),
        "post_hour": now.hour,
        "post_day": now.strftime("%A"),
        "views": 0,
        "likes": 0,
        "shares": 0,
        "comments": [],
        "comment_count": 0,
        "engagement_ratio": 0.0,
        "created_at": now.isoformat()
    }
    
    if _supabase_available():
        try:
            supabase = _init_supabase()
            supabase.table('posts_history').insert(post_record).execute()
            print("  [MEMORY] ✓ Post logged to Supabase.")
            return True
        except Exception as e:
            print(f"  [MEMORY] Supabase insert failed ({e}), saving locally.")
    
    # Local fallback
    db = _load_local_db()
    post_record["id"] = len(db["posts"]) + 1
    db["posts"].append(post_record)
    _save_local_db(db)
    print("  [MEMORY] ✓ Post logged locally.")
    return True

# =====================================================================
# UPDATE POST STATS (called by monitor)
# =====================================================================
def update_post_stats(post_id=None, views=0, likes=0, shares=0, comments=None):
    """Updates a post's performance metrics after monitoring."""
    comments = comments or []
    engagement_ratio = (likes / views) if views > 0 else 0
    
    if _supabase_available() and post_id:
        try:
            supabase = _init_supabase()
            supabase.table('posts_history').update({
                "views": views,
                "likes": likes,
                "shares": shares,
                "comments": comments,
                "comment_count": len(comments),
                "engagement_ratio": round(engagement_ratio, 4),
                "stats_updated_at": datetime.datetime.now().isoformat()
            }).eq("id", post_id).execute()
            return True
        except Exception as e:
            print(f"  [MEMORY] Supabase update failed: {e}")
    
    # Local fallback
    db = _load_local_db()
    for post in db["posts"]:
        if post.get("id") == post_id:
            post["views"] = views
            post["likes"] = likes
            post["shares"] = shares
            post["comments"] = comments
            post["comment_count"] = len(comments)
            post["engagement_ratio"] = round(engagement_ratio, 4)
            post["stats_updated_at"] = datetime.datetime.now().isoformat()
            break
    _save_local_db(db)
    return True

# =====================================================================
# AUDIENCE INSIGHTS — The AI's Brain
# =====================================================================
def get_audience_insights():
    """
    Deep multi-dimensional analysis of all past performance data.
    Returns actionable insights for the AI to evolve its strategy.
    
    Dimensions analyzed:
    - Tags (which hashtags drive engagement)
    - Description patterns (which phrasings work)
    - Caption styles (humor vs shock vs relatable etc.)
    - Posting hours (when to post)
    - Posting days (which weekdays perform best)
    - Clip durations (optimal length)
    - Hook effectiveness (what stops the scroll)
    """
    posts = []
    
    if _supabase_available():
        try:
            supabase = _init_supabase()
            response = supabase.table('posts_history').select('*').order('views', desc=True).limit(50).execute()
            posts = response.data
        except Exception as e:
            print(f"  [MEMORY] Supabase query failed: {e}")
    
    if not posts:
        db = _load_local_db()
        posts = sorted(db["posts"], key=lambda x: x.get("views", 0), reverse=True)[:50]
    
    empty_result = {
        "tags": [], "comments": [], "total_posts_analyzed": 0, "total_views": 0,
        "best_engagement_ratio": 0, "best_tags_by_engagement": [],
        "best_posting_hours": [], "best_posting_days": [],
        "best_duration_range": "", "best_descriptions": [],
        "best_caption_style": "", "best_hooks": [],
        "avg_views_per_post": 0, "performance_summary": "",
        "worst_tags": [], "worst_style": "",
    }
    
    if not posts:
        print("  [MEMORY] No past data. Starting from scratch.")
        return empty_result
    
    # ---- Accumulators ----
    all_tags = []
    all_comments = []
    total_views = 0
    total_likes = 0
    best_ratio = 0
    best_tags_by_ratio = []
    
    # Multi-dimensional tracking
    tag_performance = {}        # tag -> [ratios]
    hour_performance = {}       # hour -> [ratios]
    day_performance = {}        # day -> [ratios]
    duration_performance = {}   # bucket -> [ratios]
    style_performance = {}      # style -> [ratios]
    top_descriptions = []       # (desc, ratio, views)
    top_hooks = []              # (hook, ratio, views)
    
    for post in posts:
        tags = post.get('tags', [])
        comments = post.get('comments', [])
        views = post.get('views', 0) or 0
        likes = post.get('likes', 0) or 0
        
        if tags: all_tags.extend(tags)
        if comments:
            if isinstance(comments, list):
                all_comments.extend([c for c in comments if isinstance(c, str)])
        total_views += views
        total_likes += likes
        
        ratio = (likes / views) if views > 0 else 0
        
        if views > 0 and ratio > best_ratio:
            best_ratio = ratio
            best_tags_by_ratio = tags
        
        # Tag-level performance
        if tags and views > 0:
            for tag in tags:
                tag_performance.setdefault(tag, []).append(ratio)
        
        # Hour
        hour = post.get('post_hour')
        if hour is not None and views > 0:
            hour_performance.setdefault(int(hour), []).append(ratio)
        
        # Day
        day = post.get('post_day', '')
        if day and views > 0:
            day_performance.setdefault(day, []).append(ratio)
        
        # Duration buckets (15s intervals)
        dur = post.get('clip_duration_sec', 0) or 0
        if dur > 0 and views > 0:
            bucket = f"{int(dur//15)*15}-{int(dur//15)*15+15}s"
            duration_performance.setdefault(bucket, []).append(ratio)
        
        # Caption style
        style = post.get('caption_style', '')
        if style and style != 'unknown' and views > 0:
            style_performance.setdefault(style, []).append(ratio)
        
        # Top descriptions
        desc = post.get('description', '')
        if desc and views > 100:
            top_descriptions.append((desc, ratio, views))
        
        # Top hooks
        hook = post.get('hook_text', '')
        if hook and views > 100:
            top_hooks.append((hook, ratio, views))
    
    # ---- Calculate best/worst for each dimension ----
    def _top_n(perf_dict, n=3):
        sorted_items = sorted(perf_dict.items(), 
            key=lambda x: sum(x[1])/len(x[1]) if x[1] else 0, reverse=True)
        return [k for k, _ in sorted_items[:n]]
    
    def _bottom_n(perf_dict, n=3):
        sorted_items = sorted(perf_dict.items(), 
            key=lambda x: sum(x[1])/len(x[1]) if x[1] else 0)
        return [k for k, _ in sorted_items[:n]]
    
    best_posting_hours = _top_n(hour_performance)
    best_posting_days = _top_n(day_performance)
    best_duration_range = _top_n(duration_performance, 1)[0] if duration_performance else ""
    best_caption_style = _top_n(style_performance, 1)[0] if style_performance else ""
    worst_style = _bottom_n(style_performance, 1)[0] if style_performance else ""
    
    best_individual_tags = _top_n(tag_performance, 8)
    worst_tags = _bottom_n(tag_performance, 5)
    
    # Top descriptions & hooks by engagement
    top_descriptions.sort(key=lambda x: x[1], reverse=True)
    top_hooks.sort(key=lambda x: x[1], reverse=True)
    best_descriptions = [d[0] for d in top_descriptions[:5]]
    best_hooks = [h[0] for h in top_hooks[:5]]
    
    avg_views = total_views / len(posts) if posts else 0
    
    # Platform specific stats
    yt_posts = [p for p in posts if p.get('platform') == 'youtube']
    tt_posts = [p for p in posts if p.get('platform') == 'tiktok']
    yt_views = sum(p.get('views', 0) or 0 for p in yt_posts)
    tt_views = sum(p.get('views', 0) or 0 for p in tt_posts)
    
    yt_avg = (yt_views / len(yt_posts)) if yt_posts else 0
    tt_avg = (tt_views / len(tt_posts)) if tt_posts else 0
    
    # ---- Build summary ----
    parts = []
    if best_posting_hours: parts.append(f"Best hours: {best_posting_hours}")
    if best_posting_days: parts.append(f"Best days: {', '.join(str(d) for d in best_posting_days)}")
    if best_duration_range: parts.append(f"Best duration: {best_duration_range}")
    if best_caption_style: parts.append(f"Best style: {best_caption_style}")
    if worst_style: parts.append(f"AVOID style: {worst_style}")
    if avg_views > 0: parts.append(f"Avg views/post: {avg_views:,.0f} (YT: {yt_avg:,.0f} | TT: {tt_avg:,.0f})")
    performance_summary = " | ".join(parts)
    
    dedupe_tags = list(set(all_tags))
    
    result = {
        "tags": dedupe_tags[:20],
        "best_individual_tags": best_individual_tags,
        "worst_tags": worst_tags,
        "comments": all_comments[:50],  # Send up to 50 comments so Gemini sees viewer sentiment
        "total_posts_analyzed": len(posts),
        "total_views": total_views,
        "total_likes": total_likes,
        "avg_views_per_post": round(avg_views),
        "youtube_avg_views_per_post": round(yt_avg),
        "tiktok_avg_views_per_post": round(tt_avg),
        "best_engagement_ratio": round(best_ratio, 4),
        "best_tags_by_engagement": best_tags_by_ratio,
        "best_posting_hours": best_posting_hours,
        "best_posting_days": best_posting_days,
        "best_duration_range": best_duration_range,
        "best_descriptions": best_descriptions,
        "best_hooks": best_hooks,
        "best_caption_style": best_caption_style,
        "worst_style": worst_style,
        "performance_summary": performance_summary,
    }
    
    print(f"  [MEMORY] 🧠 {len(posts)} posts analyzed ({total_views:,} views) | {performance_summary}")
    return result

# =====================================================================
# PRUNING INTELLIGENCE (The Janitor)
# =====================================================================
def get_pruning_candidates(views_threshold=100, age_hours=48):
    """
    Identifies videos that failed to reach the threshold after the grace period.
    Returns a list of dicts with {id, title, platform}.
    """
    all_posts = get_all_posts()
    now = datetime.datetime.now()
    candidates = []
    
    for post in all_posts:
        # Only consider videos that are 'posted' and not yet pruned
        if post.get("status") != "posted":
            continue
            
        created_at_str = post.get("created_at")
        if not created_at_str:
            continue
            
        try:
            created_at = datetime.datetime.fromisoformat(created_at_str)
            age = (now - created_at).total_seconds() / 3600
            
            views = post.get("views", 0) or 0
            
            # CRITERIA: View count < threshold AND age > minimum grace period
            if views < views_threshold and age > age_hours:
                candidates.append({
                    "id": post.get("id"),
                    "title": post.get("title"),
                    "platform": post.get("platform"),
                    "views": views,
                    "age_hours": round(age, 1)
                })
        except Exception:
            continue
            
    return candidates

def mark_as_pruned(post_id):
    """Marks a post as pruned in the database."""
    if _supabase_available() and post_id:
        try:
            supabase = _init_supabase()
            supabase.table('posts_history').update({"status": "pruned"}).eq("id", post_id).execute()
            return True
        except Exception:
            pass
            
    db = _load_local_db()
    for post in db["posts"]:
        if post.get("id") == post_id:
            post["status"] = "pruned"
            break
    _save_local_db(db)
    return True

def get_all_posts():
    """Retrieves all posts from Supabase or Local DB."""
    if _supabase_available():
        try:
            supabase = _init_supabase()
            response = supabase.table('posts_history').select('*').order('created_at', desc=True).execute()
            return response.data
        except Exception:
            pass
    db = _load_local_db()
    return db["posts"]

if __name__ == "__main__":
    pass
