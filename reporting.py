"""
reporting.py — The Communication Layer between AI and Human
Generates weekly progress reports in plain text to explain what the AI has learned.
"""

import os
import json
import datetime
from google import genai
from strategy import _load_strategy, _save_strategy

REPORT_FILE = "AI_PROGRESS_REPORT.txt"

def generate_weekly_report(insights):
    """
    Uses Gemini to analyze performance data and write a human-readable report.
    Explains niches, metrics, and 'learned' strategies.
    """
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        print("  [REPORTING] No API key for report generation.")
        return False

    state = _load_strategy()
    client = genai.Client(api_key=key)
    
    # 1. Prepare the context for the 'AI explaining itself'
    total_views = insights.get("total_views", 0)
    avg_views = insights.get("avg_views_per_post", 0)
    best_niche = insights.get("performance_summary", "No clear niche yet")
    evolution_count = state.get("evolution_count", 0)
    
    prompt = f"""You are the AutoClipAI autonomous bot. You work for a human owner.
    
    YOUR TASK: Write a Weekly Progress Report (approx 1 page) for your owner.
    
    === DATA GATHERED BY YOU ===
    Total videos posted: {insights.get('total_posts_analyzed', 0)}
    Total views generated: {total_views:,}
    Average views per post: {avg_views:,}
    Engagement Ratio: {insights.get('best_engagement_ratio', 0):.2%}
    Number of times you have evolved your strategy: {evolution_count}
    
    WINNING NICHES: {insights.get('performance_summary')}
    BEST TAGS: {insights.get('best_tags_by_engagement')}
    AUDIENCE FEEDBACK: {insights.get('comments')[:5]}
    
    === REPORT STRUCTURE ===
    1. Greeting (Professional but with an AI personality)
    2. Executive Summary (The numbers)
    3. What I've Learned (Analyze why certain styles/tags worked. E.g. "I've noticed that movie clips with blurred edges get 40% more watch time")
    4. Strategic Adjustments (Explain why you changed your search queries)
    5. Next Week's Goal (What you plan to focus on)
    
    Write it in a clear, interesting, and insightful way. Use bullet points.
    Language: French (as the owner speaks French).
    """

    try:
        print(f"  [REPORTING] Generating AI report (French)...")
        response = client.models.generate_content(
            model="gemini-2.0-flash-lite", 
            contents=[prompt]
        )
        
        report_text = response.text.strip()
        
        # Add a header with the date
        header = f"==============================================\n"
        header += f"   AUTOCLIP AI — RAPPORT DE PROGRESSION\n"
        header += f"   Généré le: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        header += f"==============================================\n\n"
        
        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            f.write(header + report_text)
            
        # Update last report date
        state["last_report_date"] = datetime.datetime.now().isoformat()
        _save_strategy(state)
        
        print(f"  [REPORTING] ✓ Report saved to {REPORT_FILE}")
        return True
    except Exception as e:
        print(f"  [REPORTING] ✗ Failed to generate report: {e}")
        return False

def should_generate_report():
    """Checks if it's been 7 days since the last report."""
    state = _load_strategy()
    last = state.get("last_report_date")
    if not last:
        return True # First time!
    
    last_dt = datetime.datetime.fromisoformat(last)
    diff = datetime.datetime.now() - last_dt
    return diff.days >= 7

if __name__ == "__main__":
    from memory import get_audience_insights
    generate_weekly_report(get_audience_insights())
