"""
invidious_gateway.py - Anonymous Content Discovery for AutoClipAI v7.0
Uses public Invidious instances to fetch viral content metadata without 
exposing the main machine's IP to YouTube's search detection.
"""

import requests
import random
import logging

log = logging.getLogger("AutoClipAI.Gateway")

# STABLE INSTANCES 2024-2026
INSTANCES = [
    "https://invidious.io.lol",
    "https://invidious.privacydev.net",
    "https://vid.puffyan.us",
    "https://inv.tux.pizza",
    "https://invidious.flokinet.to",
    "https://yewtu.be"
]

class DiscoveryGateway:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        self._active_instances = list(INSTANCES)

    def _get_base_url(self):
        if not self._active_instances:
            self._active_instances = list(INSTANCES)
        return random.choice(self._active_instances)

    def get_trending(self, region="FR", type="Music"):
        """Fetches trending videos from a random Invidious instance."""
        url = f"{self._get_base_url()}/api/v1/trending"
        try:
            resp = self.session.get(url, params={"region": region, "type": type}, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return [
                {
                    "title": v.get("title"),
                    "id": v.get("videoId"),
                    "views": v.get("viewCount"),
                    "url": f"https://www.youtube.com/watch?v={v.get('videoId')}"
                }
                for v in data if v.get("videoId")
            ]
        except Exception as e:
            log.warning(f"Invidious instance failed ({url}): {e}")
            return []

    def search_viral(self, query):
        """Searches via Invidious API."""
        url = f"{self._get_base_url()}/api/v1/search"
        try:
            # Sort by views/relevance
            resp = self.session.get(url, params={"q": query, "sort_by": "relevance", "type": "video"}, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return [
                {
                    "title": v.get("title"),
                    "id": v.get("videoId"),
                    "url": f"https://www.youtube.com/watch?v={v.get('videoId')}"
                }
                for v in data if v.get("type") == "video"
            ]
        except Exception as e:
            log.warning(f"Invidious search failed ({url}): {e}")
            return []

if __name__ == "__main__":
    # Test
    gateway = DiscoveryGateway()
    print("Fetching Trending...")
    trending = gateway.get_trending()
    for v in trending[:3]:
        print(f"- {v['title']} ({v['views']} views)")
