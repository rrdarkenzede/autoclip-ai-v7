import os
import json
import time
import random
import logging
from playwright.sync_api import sync_playwright

log = logging.getLogger("AutoClipAI.Publisher")

def _launch_browser(pw, headless=True):
    browser = pw.chromium.launch(headless=headless, args=["--disable-blink-features=AutomationControlled", "--no-sandbox"])
    context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    context.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
    return browser, context

def _inject_cookies(context, platform="tiktok"):
    secret_key = "TIKTOK_COOKIES" if platform == "tiktok" else "YOUTUBE_COOKIES"
    cookies_json = os.environ.get(secret_key)
    if not cookies_json: return False
    try:
        cookies = json.loads(cookies_json)
        context.add_cookies(cookies)
        return True
    except: return False

def publish_to_tiktok(video_path, metadata):
    log.info(f"🎭 [TIKTOK] Publishing: {metadata.get('title')}")
    with sync_playwright() as pw:
        browser, context = _launch_browser(pw)
        if not _inject_cookies(context, "tiktok"): return False
        page = context.new_page()
        try:
            page.goto("https://www.tiktok.com/creator-center/upload?from=upload", wait_until="networkidle")
            page.wait_for_selector('input[type="file"]').set_input_files(video_path)
            page.wait_for_selector('div[contenteditable="true"]').fill(f"{metadata.get('title')} #viral #autoclip")
            page.wait_for_selector('text="Upload successful"', timeout=300000)
            page.get_by_role("button", name="Post").click()
            time.sleep(5)
            browser.close()
            return True
        except Exception as e:
            log.error(f"TikTok Fail: {e}")
            browser.close()
            return False

def publish_to_youtube_shorts(video_path, metadata):
    log.info(f"🚀 [YOUTUBE] Publishing: {metadata.get('title')}")
    with sync_playwright() as pw:
        browser, context = _launch_browser(pw)
        if not _inject_cookies(context, "youtube"): return False
        page = context.new_page()
        try:
            page.goto("https://studio.youtube.com", wait_until="networkidle")
            page.click("#create-icon")
            page.click("#upload-videos")
            page.wait_for_selector('input[type="file"]').set_input_files(video_path)
            page.wait_for_selector('div#textbox[aria-label*="Add a title"]').fill(metadata.get('title')[:100])
            page.get_by_role("radio", name="No, it's not made for kids").click()
            for _ in range(3): page.click("#next-button"); time.sleep(1)
            page.get_by_role("radio", name="Public").click()
            page.click("#done-button")
            time.sleep(5)
            browser.close()
            return True
        except Exception as e:
            log.error(f"YT Fail: {e}")
            browser.close()
            return False

def prune_youtube_video(video_id): pass
def prune_tiktok_video(video_id): pass
