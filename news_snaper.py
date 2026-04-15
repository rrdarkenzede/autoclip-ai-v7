try:
    import feedparser
except ImportError:
    print("❌ ERROR: 'feedparser' not found. Run 'pip install feedparser' to enable news sniping.")
    feedparser = None

import os
import json
import logging
import random
from typing import List
from google import genai

# Setup logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("NewsSnaper")

NEWS_FEEDS = [
    "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss?hl=fr&gl=FR&ceid=FR:fr",
    # Could add more niche feeds here
]

def get_trending_news_keywords(limit=10) -> List[str]:
    """
    Fetches the latest headlines and uses AI to extract trending keywords.
    """
    log.info("🔍 Sniping latest trends from news feeds...")
    
    all_headlines = []
    for url in NEWS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:15]:
                all_headlines.append(entry.title)
        except Exception as e:
            log.error(f"Error reading feed {url}: {e}")
            
    if not all_headlines:
        return []
    
    # Shuffle and pick a sample
    sample = random.sample(all_headlines, min(len(all_headlines), 30))
    
    # Use Gemini to extract the 'Viral Potential' keywords
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return [h.split(" - ")[0] for h in sample[:limit]] # Fallback to titles
    
    client = genai.Client(api_key=key)
    prompt = f"""You are a trend analyst. Here are the latest global headlines:
{chr(10).join(sample)}

Your task:
1. Identify the TOP 5 most 'viral' or 'shocking' topics currently breaking.
2. For each topic, create a YouTube Search Query that would find relevant raw footage or interviews.
3. Return ONLY a JSON list of strings (the queries). No markdown."""

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash", contents=[prompt]
        )
        raw = response.text.strip()
        if "```" in raw:
            raw = raw.split("```")[1].strip()
            if raw.startswith("json"): raw = raw[4:].strip()
        
        queries = json.loads(raw)
        log.info(f"✨ AI extracted {len(queries)} news queries: {queries}")
        return queries
    except Exception as e:
        log.error(f"AI news extraction failed: {e}")
        return [h.split(" - ")[0] for h in sample[:limit]]

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    print(get_trending_news_keywords())
