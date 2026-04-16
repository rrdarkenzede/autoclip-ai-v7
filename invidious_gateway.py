"""
invidious_gateway.py - Anonymous Content Discovery v7.2
Uses Invidious for initial search, but includes a CRITICAL FALLBACK (Plan B)
using yt-dlp internal search if instances are down (502/Timeout).
"""

import requests
import random
import logging
import yt_dlp
from omega_bypass import omega

log = logging.getLogger("AutoClipAI.Gateway")

INSTANCES = [
    "https://invidious.io.lol",
    "https://invidious.privacydev.net",
    "https://vid.puffyan.us",
    "https://inv.tux.pizza",
    "https://yewtu.be"
]

class DiscoveryGateway:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        self._active_instances = list(INSTANCES)

    def _get_base_url(self):
        if not self._active_instances: self._active_instances = list(INSTANCES)
        return random.choice(self._active_instances)

    def search_viral(self, query):
        """
        Main search entry. Tries Invidious first, then Fallback.
        """
        # Try up to 3 instances
        for _ in range(3):
            base = self._get_base_url()
            url = f"{base}/api/v1/search"
            try:
                resp = self.session.get(url, params={"q": query, "type": "video"}, timeout=8)
                resp.raise_for_status()
                data = resp.json()
                results = [
                    {"title": v.get("title"), "url": f"https://www.youtube.com/watch?v={v.get('videoId')}"}
                    for v in data if v.get("videoId")
                ]
                if results:
                    log.info(f"✅ Search successful via Invidious ({base})")
                    return results
            except Exception:
                if base in self._active_instances: self._active_instances.remove(base)
                continue

        # PLAN B: Internal yt-dlp Search (Silent & Stealth)
        log.warning(f"⚠️ Invidious Dead. Activating Silent Search Fallback for: {query}")
        return self._yt_dlp_search_fallback(query)

    def _yt_dlp_search_fallback(self, query):
        """
        Uses yt-dlp to search directly with mobile/TV fingerprints.
        """
        search_query = f"ytsearch10:{query}"
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'force_generic_extractor': False,
            # Use OMEGA if running, or just stealth clients
            'extractor_args': {'youtube': {'player_client': ['android', 'ios'], 'skip': ['webpage']}},
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(search_query, download=False)
                if 'entries' in info:
                    return [
                        {"title": e.get("title"), "url": f"https://www.youtube.com/watch?v={e.get('id')}"}
                        for e in info['entries'] if e.get('id')
                    ]
        except Exception as e:
            log.error(f"❌ Fallback search failed: {e}")
        return []

    def get_trending(self, region="FR"):
        """Fetches trending via Invidious (No fallback for trending as it's less critical)."""
        url = f"{self._get_base_url()}/api/v1/trending"
        try:
            resp = self.session.get(url, params={"region": region}, timeout=10)
            data = resp.json()
            return [{"title": v.get("title"), "url": f"https://www.youtube.com/watch?v={v.get('videoId')}"} for v in data]
        except: return []

gateway = DiscoveryGateway()
