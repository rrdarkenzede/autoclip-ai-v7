"""
strategy.py — The Adaptive Brain of AutoClipAI

This module replaces ALL hardcoded search queries with a self-evolving strategy.
It uses Gemini to analyze what's working and generate NEW search queries,
follow leads from Reddit/X, and continuously refine the content discovery.

The strategy file (strategy_state.json) evolves over time.
There is NO hardcoded content niche — the AI discovers what works.
"""

import os
import json
import time
import datetime
from dotenv import load_dotenv

load_dotenv()

STRATEGY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "strategy_state.json")

# =====================================================================
# INITIAL SEED — Only used the VERY FIRST time. After that, the AI
# generates its own queries based on what works.
# =====================================================================
SEED_QUERIES = [
    "viral video thread reddit",
    "best youtube banger 2024",
    "must watch shorts compilation",
    "trending tiktok banger",
    "insane interview moments",
    "caught on camera unbelievable reels",
    "podcast moments we all needed",
    "funniest thing you'll see today",
    "world breaking news raw footage",
    "this video is going viral",
]

SEED_NICHES = [
    "humor", "drama", "sports", "podcasts", "reactions",
    "fails", "animals", "motivation", "gaming", "cringe"
]

def _load_strategy():
    """Loads the current strategy state or creates a fresh one."""
    if os.path.exists(STRATEGY_FILE):
        with open(STRATEGY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    
    # First-time initialization
    return {
        "version": 1,
        "created_at": datetime.datetime.now().isoformat(),
        "last_evolved": None,
        "active_queries": SEED_QUERIES[:],
        "active_niches": SEED_NICHES[:],
        "niche_scores": {n: 0.0 for n in SEED_NICHES},
        "discovered_channels": [],
        "discovered_subreddits": [],
        "discovered_leads": [],     # URLs/channels found on X/Reddit to follow
        "last_report_date": None,   # Handled by reporting system
        "learned_layouts": [],      # Dynamic layout patterns (YouTube/TikTok)
        "learned_styles": [],       # Visual DNA (Fonts, Colors, Positioning)
        "learned_strategies": [],   # Metadata DNA (Hooks, Hashtags, CTA)
        "banned_queries": [],       # Queries that never find good content
        "query_history": {},        # query -> {times_used, total_views, avg_ratio}
        "avoidance_rules": [],      # Negative patterns to stop doing
        "meta_patterns": [],        # High-level winning principles
        "evolution_count": 0,
    }

def _save_strategy(state):
    with open(STRATEGY_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def get_active_queries():
    """Returns the current list of search queries the system should use."""
    state = _load_strategy()
    return state["active_queries"]

def get_active_niches():
    """Returns the current ranked list of content niches."""
    state = _load_strategy()
    # Sort by score, highest first
    scored = sorted(state["niche_scores"].items(), key=lambda x: x[1], reverse=True)
    return [n for n, _ in scored]

def get_discovered_channels():
    """Returns channels the AI has discovered through Reddit/X/performance."""
    state = _load_strategy()
    return state.get("discovered_channels", [])

def get_discovered_subreddits():
    """Returns subreddits the AI has discovered as good sources."""
    state = _load_strategy()
    return state.get("discovered_subreddits", [])

def log_query_result(query, views_generated, clips_published, avg_engagement):
    """
    Called after using a search query. Updates the strategy with performance data.
    Bad queries get deprioritized. Great queries get amplified.
    """
    state = _load_strategy()
    
    if query not in state["query_history"]:
        state["query_history"][query] = {"times_used": 0, "total_views": 0, "avg_ratio": 0}
    
    history = state["query_history"][query]
    history["times_used"] += 1
    history["total_views"] += views_generated
    
    # Running average of engagement ratio
    old_ratio = history["avg_ratio"]
    history["avg_ratio"] = (old_ratio * (history["times_used"] - 1) + avg_engagement) / history["times_used"]
    
    # If a query has been used 3+ times with 0 results, ban it
    if history["times_used"] >= 3 and history["total_views"] == 0:
        if query not in state["banned_queries"]:
            state["banned_queries"].append(query)
            if query in state["active_queries"]:
                state["active_queries"].remove(query)
            print(f"  [STRATEGY] ❌ Banned dead query: '{query}'")
    
    _save_strategy(state)

def add_discovered_lead(lead_type, value, source="unknown"):
    """
    Called when the AI discovers a new content source.
    lead_type: 'channel', 'subreddit', 'query', 'url'
    """
    state = _load_strategy()
    
    lead = {"type": lead_type, "value": value, "source": source, 
            "discovered_at": datetime.datetime.now().isoformat()}
    
    if lead_type == "channel" and value not in state["discovered_channels"]:
        state["discovered_channels"].append(value)
        print(f"  [STRATEGY] 🆕 Discovered channel: {value} (via {source})")
    
    elif lead_type == "subreddit" and value not in state["discovered_subreddits"]:
        state["discovered_subreddits"].append(value)
        print(f"  [STRATEGY] 🆕 Discovered subreddit: r/{value} (via {source})")
    
    elif lead_type == "query" and value not in state["active_queries"]:
        state["active_queries"].append(value)
        print(f"  [STRATEGY] 🆕 New search query: '{value}' (via {source})")
    
    state["discovered_leads"].append(lead)
    _save_strategy(state)

def update_niche_score(niche, views, engagement_ratio):
    """Updates how well a niche is performing."""
    state = _load_strategy()
    
    if niche not in state["niche_scores"]:
        state["niche_scores"][niche] = 0.0
    
    # Weighted score: views matter, but engagement matters more
    score_delta = (views / 10000) + (engagement_ratio * 100)
    state["niche_scores"][niche] += score_delta
    
    _save_strategy(state)

def evolve_strategy(insights):
    """
    THE CORE EVOLUTION FUNCTION.
    Uses Gemini to analyze performance data and generate new search queries.
    This is what makes the AI truly adaptive — it rewrites its own search strategy.
    """
    from google import genai
    
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        print("  [STRATEGY] No API key — skipping evolution.")
        return
    
    state = _load_strategy()
    client = genai.Client(api_key=key)
    
    # Build the context for Gemini
    top_niches = get_active_niches()[:5]
    worst_niches = get_active_niches()[-3:]
    
    best_queries = sorted(
        state["query_history"].items(),
        key=lambda x: x[1].get("total_views", 0),
        reverse=True
    )[:10]
    
    dead_queries = [q for q, data in state["query_history"].items() 
                    if data["times_used"] >= 2 and data["total_views"] == 0]
    
    prompt = f"""You are the strategy brain of a viral content machine.

YOUR ROLE: Analyze what's working and generate NEW YouTube search queries to find viral videos.

=== CURRENT PERFORMANCE DATA ===
Total posts analyzed: {insights.get('total_posts_analyzed', 0)}
Total views accumulated: {insights.get('total_views', 0):,}
Avg views per post (GLOBAL): {insights.get('avg_views_per_post', 0):,}
Avg views per post (YOUTUBE): {insights.get('youtube_avg_views_per_post', 0):,}
Avg views per post (TIKTOK): {insights.get('tiktok_avg_views_per_post', 0):,}
Best engagement ratio: {insights.get('best_engagement_ratio', 0):.2%}

Top performing niches (ranked): {top_niches}
Worst performing niches: {worst_niches}

Best search queries by views generated:
{json.dumps([(q, d) for q, d in best_queries], indent=2) if best_queries else "No data yet"}

Dead queries (never found good content):
{dead_queries if dead_queries else "None yet"}

Best tags: {insights.get('best_individual_tags', insights.get('best_tags_by_engagement', []))}
Best caption style: {insights.get('best_caption_style', 'unknown')}
Best clip duration: {insights.get('best_duration_range', 'unknown')}

Audience comments that got the most engagement:
{insights.get('comments', [])}

=== YOUR TASK ===
Based on ALL of this data, generate:

1. "new_queries": 15 NEW YouTube search queries that you predict will find viral videos.
   - Double down on what's working (if drama gets views, search MORE drama variations)
   - Explore adjacent niches (if podcast clips work, try interview clips, debate clips)
   - Include trending topics and current events
   - Include creator names that are trending NOW
   - Be SPECIFIC (not "funny videos" but "funniest couple arguments caught on camera")

2. "kill_queries": queries from the active list that should be removed (not working)

3. "new_niches": any new content niches worth exploring

4. "new_subreddits": Reddit subreddits that might have viral YouTube links

5. "avoidance_rules": A list of specific things the AI should STOP doing (e.g., "Don't use neon green text", "Avoid clips longer than 60s for this niche") based on comment sentiment or poor data.

6. "meta_patterns": Any recurring winning pattern you've identified (e.g., "Interviews with X creator always buzz", "POV style hooks work best").

7. "strategy_note": a 1-sentence summary of what the AI should focus on next

Return ONLY a JSON object with these 7 keys. No markdown, no explanation."""

    models = [
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-flash-8b", # Huge quota fallback
        "gemini-1.5-pro",
    ]
    
    for model in models:
        try:
            print(f"  [STRATEGY] Evolving with {model} + Google Search Grounding...")
            response = client.models.generate_content(
                model=model, contents=[prompt],
                config=genai.types.GenerateContentConfig(
                    temperature=0.9, 
                    tools=[{"google_search": {}}]
                )
            )
            
            raw = response.text.strip()
            if raw.startswith("```"):
                lines = raw.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                raw = "\n".join(lines).strip()
            if raw.startswith("json"):
                raw = raw[4:].strip()
            
            result = json.loads(raw)
            
            # Apply new queries
            new_queries = result.get("new_queries", [])
            for q in new_queries:
                if q and q not in state["active_queries"] and q not in state["banned_queries"]:
                    state["active_queries"].append(q)
            
            # Kill bad queries
            kill_queries = result.get("kill_queries", [])
            for q in kill_queries:
                if q in state["active_queries"]:
                    state["active_queries"].remove(q)
                    state["banned_queries"].append(q)
            
            # Add new niches
            new_niches = result.get("new_niches", [])
            for n in new_niches:
                if n not in state["niche_scores"]:
                    state["niche_scores"][n] = 0.5  # Slight head start
            
            # Add new subreddits
            new_subs = result.get("new_subreddits", [])
            for s in new_subs:
                if s not in state["discovered_subreddits"]:
                    state["discovered_subreddits"].append(s)
            
            # Add avoidance rules
            state["avoidance_rules"] = result.get("avoidance_rules", [])
            
            # Add meta patterns
            state["meta_patterns"] = result.get("meta_patterns", [])
            
            strategy_note = result.get("strategy_note", "")
            
            state["evolution_count"] += 1
            state["last_evolved"] = datetime.datetime.now().isoformat()
            
            # Keep active queries manageable (max 40)
            if len(state["active_queries"]) > 40:
                # Keep the 40 best-performing + newest
                scored = []
                for q in state["active_queries"]:
                    h = state["query_history"].get(q, {})
                    scored.append((q, h.get("total_views", 0)))
                scored.sort(key=lambda x: x[1], reverse=True)
                state["active_queries"] = [q for q, _ in scored[:40]]
            
            _save_strategy(state)
            
            print(f"  [STRATEGY] ✅ Evolution #{state['evolution_count']} complete!")
            print(f"  [STRATEGY] +{len(new_queries)} queries, -{len(kill_queries)} killed")
            print(f"  [STRATEGY] Active queries: {len(state['active_queries'])}")
            if strategy_note:
                print(f"  [STRATEGY] 🧠 Focus: {strategy_note}")
            
            return
            
        except Exception as e:
            err_msg = str(e)
            if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                # If limit is 0 (hard block), don't retry, move to next model
                if "limit: 0" in err_msg:
                    print(f"  [STRATEGY] 🛑 Hard quota limit (0) for {model}. Switching model...")
                    continue
                
                # Quota hit? Retry THIS model 3 times before moving on
                for retry_i in range(1, 4):
                    print(f"  [STRATEGY] 📛 Quota hit. Retry {retry_i}/3 for {model} in 30s...")
                    time.sleep(30)
                    try:
                        response = client.models.generate_content(
                            model=model, contents=[prompt],
                            config=genai.types.GenerateContentConfig(temperature=0.9, tools=[{"google_search": {}}])
                        )
                        if response: break # Success!
                    except Exception as fatal_e:
                        if "limit: 0" in str(fatal_e): break # Don't retry if hard-blocked during retry
                        if retry_i == 3: 
                            print(f"  [STRATEGY] {model} exhausted after 3 retries.")
                
                if 'response' not in locals() or not response:
                    continue # Try next model if retries failed
                
                pass
            
            else:
                print(f"  [STRATEGY] {model} failed: {err_msg[:100]}")
                continue # Try next model
    
    print("  [STRATEGY] Evolution failed — keeping current strategy.")

if __name__ == "__main__":
    state = _load_strategy()
    print(f"Active queries: {len(state['active_queries'])}")
    print(f"Niches: {state['niche_scores']}")
    print(f"Evolutions: {state['evolution_count']}")
