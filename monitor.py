"""
monitor.py — AutoClipAI v5 — TikTok Stats Monitor

Uses the same robust browser launch system from publisher.py.
"""

import os
import re
import time
import logging
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from memory import update_post_stats, get_all_posts

log = logging.getLogger("AutoClipAI")

from publisher import (
    _launch_browser, _safe_close_browser, _prepare_session,
    TIKTOK_SESSION_DIR, YOUTUBE_SESSION_DIR, NAVIGATION_TIMEOUT
)

def _parse_tiktok_count(text):
    """Parses TikTok's abbreviated numbers (e.g., '1.2M', '45.3K', '120')."""
    if not text:
        return 0
    text = text.strip().upper()
    try:
        if 'M' in text:
            return int(float(text.replace('M', '')) * 1_000_000)
        elif 'K' in text:
            return int(float(text.replace('K', '')) * 1_000)
        else:
            return int(re.sub(r'[^\d]', '', text))
    except (ValueError, TypeError):
        return 0

def _parse_youtube_count(text):
    """Parses YouTube's abbreviated numbers (e.g., '1,2 k vues', '1.5M views')."""
    if not text:
        return 0
    text = text.strip().upper().replace(',', '.')
    try:
        match = re.search(r'([\d.]+)\s*([KMB]?)', text)
        if not match:
            return int(re.sub(r'[^\d]', '', text)) if re.sub(r'[^\d]', '', text) else 0
        
        num_part = float(match.group(1))
        multiplier = match.group(2)
        
        if multiplier == 'M':
            return int(num_part * 1_000_000)
        elif multiplier == 'K':
            return int(num_part * 1_000)
        elif multiplier == 'B':
            return int(num_part * 1_000_000_000)
        else:
            return int(num_part)
    except Exception:
        return 0


def monitor_tiktok_profile(profile_url):
    """
    Visits the user's TikTok profile page and scrapes stats for each posted video.
    Updates each matching post in the database.
    """
    log.info(f"\n--- MONITOR: Scanning TikTok stats from {profile_url} ---")

    try:
        with sync_playwright() as p:
            browser = _launch_browser(p, TIKTOK_SESSION_DIR, headless=True)
            page = browser.new_page()

            try:
                page.goto(profile_url, timeout=NAVIGATION_TIMEOUT, wait_until="domcontentloaded")
                page.wait_for_load_state("networkidle", timeout=30000)
                time.sleep(3)

                # --- SCRAPE VIDEO CARDS FROM PROFILE ---
                video_cards = page.locator('[data-e2e="user-post-item"]').all()

                if not video_cards:
                    video_cards = page.locator('div[class*="DivItemContainer"]').all()

                log.info(f"  [MONITOR] Found {len(video_cards)} videos on profile.")

                scraped_videos = []
                for card in video_cards[:10]:
                    try:
                        view_text = card.locator('strong[data-e2e="video-views"]').inner_text(timeout=2000)
                        views = _parse_tiktok_count(view_text)
                        scraped_videos.append({"views": views})
                    except Exception:
                        scraped_videos.append({"views": 0})

                # --- SCRAPE INDIVIDUAL VIDEO PAGES FOR LIKES + COMMENTS ---
                video_links = page.locator('[data-e2e="user-post-item"] a').all()
                if not video_links:
                    video_links = page.locator('div[class*="DivItemContainer"] a').all()

                for i, link in enumerate(video_links[:5]):
                    video_page = None
                    try:
                        href = link.get_attribute("href")
                        if not href:
                            continue

                        full_url = href if href.startswith("http") else f"https://www.tiktok.com{href}"
                        video_page = browser.new_page()
                        video_page.goto(full_url, timeout=30000)
                        try:
                            video_page.wait_for_load_state("networkidle", timeout=15000)
                        except Exception:
                            pass
                        time.sleep(2)

                        # Extract likes
                        likes = 0
                        try:
                            like_el = video_page.locator('[data-e2e="like-count"]').first
                            likes = _parse_tiktok_count(like_el.inner_text(timeout=3000))
                        except Exception:
                            pass

                        # Extract comments
                        comments = []
                        try:
                            comment_elements = video_page.locator('[data-e2e="comment-level-1"] p').all()
                            for cel in comment_elements[:20]:
                                txt = cel.inner_text(timeout=1000).strip()
                                if txt:
                                    comments.append(txt)
                        except Exception:
                            pass

                        if i < len(scraped_videos):
                            scraped_videos[i]["likes"] = likes
                            scraped_videos[i]["comments"] = comments

                    except Exception as e:
                        log.debug(f"  [MONITOR] Could not scrape video #{i+1}: {e}")
                    finally:
                        if video_page:
                            video_page.close()

                # --- UPDATE DATABASE ---
                all_posts = get_all_posts()
                for i, stats in enumerate(scraped_videos):
                    if i < len(all_posts):
                        post = all_posts[i]
                        update_post_stats(
                            post_id=post.get("id"),
                            views=stats.get("views", 0),
                            likes=stats.get("likes", 0),
                            comments=stats.get("comments", [])
                        )

                log.info(f"  [MONITOR] Updated stats for {min(len(scraped_videos), len(all_posts))} posts.")

            except Exception as e:
                log.error(f"  [MONITOR] Scraping failed: {e}")
            finally:
                _safe_close_browser(browser)

    except Exception as e:
        log.error(f"  [MONITOR] Browser launch failed: {e}")


def monitor_youtube_channel(channel_url):
    """
    Visits the user's YouTube Shorts page and scrapes stats for each posted video.
    Updates each matching post in the database.
    """
    if channel_url.endswith("/"):
        channel_url = channel_url[:-1]
    if not channel_url.endswith("/shorts"):
        short_url = f"{channel_url}/shorts"
    else:
        short_url = channel_url

    log.info(f"\\n--- MONITOR: Scanning YouTube stats from {short_url} ---")

    try:
        with sync_playwright() as p:
            browser = _launch_browser(p, YOUTUBE_SESSION_DIR, headless=True)
            page = browser.new_page()

            try:
                page.goto(short_url, timeout=NAVIGATION_TIMEOUT, wait_until="domcontentloaded")
                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass
                time.sleep(3)

                # --- SCRAPE VIDEO CARDS FROM PROFILE ---
                video_cards = page.locator('ytd-rich-item-renderer').all()

                log.info(f"  [MONITOR] Found {len(video_cards)} videos on YouTube profile.")

                scraped_videos = []
                for card in video_cards[:10]:
                    try:
                        view_text = card.locator('#metadata-line span').first.inner_text(timeout=2000)
                        views = _parse_youtube_count(view_text)
                        scraped_videos.append({"views": views})
                    except Exception:
                        scraped_videos.append({"views": 0})

                # --- SCRAPE INDIVIDUAL VIDEO PAGES FOR LIKES + COMMENTS ---
                video_links = page.locator('ytd-rich-item-renderer a#thumbnail').all()

                for i, link in enumerate(video_links[:5]):
                    video_page = None
                    try:
                        href = link.get_attribute("href")
                        if not href:
                            continue

                        full_url = href if href.startswith("http") else f"https://www.youtube.com{href}"
                        video_page = browser.new_page()
                        video_page.goto(full_url, timeout=30000)
                        try:
                            video_page.wait_for_load_state("networkidle", timeout=10000)
                        except Exception:
                            pass
                        time.sleep(2)

                        # Extract likes
                        likes = 0
                        try:
                            like_el = video_page.locator('ytd-toggle-button-renderer#like-button').first
                            likes = _parse_youtube_count(like_el.inner_text(timeout=3000))
                        except Exception:
                            pass

                        # Extract comments
                        comments = []
                        try:
                            # Open comments panel on Shorts
                            comment_btn = video_page.locator('ytd-button-renderer#comments-button').first
                            if comment_btn.is_visible():
                                comment_btn.click(timeout=3000)
                                time.sleep(2)

                            comment_elements = video_page.locator('ytd-comment-thread-renderer #content-text').all()
                            for cel in comment_elements[:20]:
                                txt = cel.inner_text(timeout=1000).strip()
                                if txt:
                                    comments.append(txt)
                        except Exception:
                            pass

                        if i < len(scraped_videos):
                            scraped_videos[i]["likes"] = likes
                            scraped_videos[i]["comments"] = comments

                    except Exception as e:
                        log.debug(f"  [MONITOR] Could not scrape YouTube video #{i+1}: {e}")
                    finally:
                        if video_page:
                            video_page.close()

                # --- UPDATE DATABASE ---
                all_posts = get_all_posts()
                youtube_posts = [p for p in all_posts if p.get("platform") == "youtube"]

                for i, stats in enumerate(scraped_videos):
                    if i < len(youtube_posts):
                        post = youtube_posts[i]
                        update_post_stats(
                            post_id=post.get("id"),
                            views=stats.get("views", 0),
                            likes=stats.get("likes", 0),
                            comments=stats.get("comments", [])
                        )

                log.info(f"  [MONITOR] Updated stats for {min(len(scraped_videos), len(youtube_posts))} YouTube posts.")

            except Exception as e:
                log.error(f"  [MONITOR] YouTube Scraping failed: {e}")
            finally:
                _safe_close_browser(browser)

    except Exception as e:
        log.error(f"  [MONITOR] Browser launch failed (YouTube): {e}")


if __name__ == "__main__":
    pass
