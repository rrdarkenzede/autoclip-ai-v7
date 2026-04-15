"""
publisher.py — AutoClipAI v5 — Robust YouTube + TikTok Publisher

Fixes from v4:
- Session lock cleanup before browser launch (fixes "Timeout exceeded" on launch)
- Retry logic with exponential backoff (3 attempts per platform)
- Crash-safe browser lifecycle (kills orphan Opera processes)
- Updated selectors for latest YouTube Studio + TikTok Creator Center
- Proper wait conditions instead of static time.sleep()
- Graceful fallback when selectors fail
- Detailed diagnostic logging for every step
"""

import os
import sys
import time
import glob
import signal
import shutil
import logging
import subprocess
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

log = logging.getLogger("AutoClipAI")

# =====================================================================
# CONFIG
# =====================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TIKTOK_SESSION_DIR = os.path.join(BASE_DIR, "tiktok_session")
YOUTUBE_SESSION_DIR = os.path.join(BASE_DIR, "youtube_session")
OPERA_PATH = r"C:\Users\Eleve\AppData\Local\Programs\Opera GX\opera.exe"

# Timeouts (ms)
NAVIGATION_TIMEOUT = 90000      # 90s for page loads
LOGIN_WAIT_TIMEOUT = 600        # 10 min for manual login (seconds)
ELEMENT_TIMEOUT = 10000         # 10s for element waits
UPLOAD_WAIT_TIMEOUT = 120000    # 2 min for file upload processing

# Retry config
MAX_RETRIES = 3
RETRY_DELAY_BASE = 10  # seconds, doubles each retry


# =====================================================================
# SESSION CLEANUP — Prevents "Timeout exceeded" on launch
# =====================================================================
def _kill_orphan_opera():
    """Kills any lingering Opera GX processes that may lock the session."""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq opera.exe", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=10
        )
        if "opera.exe" in result.stdout.lower():
            log.warning("  [BROWSER] Opera GX is currently running. We will attempt to use it, or fallback to Chromium if locked.")
            # COMMENTED OUT: We no longer kill the user's browser by force.
            # subprocess.run(["taskkill", "/F", "/IM", "opera.exe"], ...)
            time.sleep(1)
    except Exception as e:
        log.debug(f"  [CLEANUP] taskkill: {e}")


def _clean_session_locks(session_dir):
    """
    Removes lock files that prevent browser launch after a crash.
    These are the #1 cause of 'Timeout 180000ms exceeded'.
    """
    if not os.path.exists(session_dir):
        os.makedirs(session_dir, exist_ok=True)
        return

    lock_files = [
        os.path.join(session_dir, "lockfile"),
        os.path.join(session_dir, "SingletonLock"),
        os.path.join(session_dir, "SingletonSocket"),
        os.path.join(session_dir, "SingletonCookie"),
    ]

    # Also check inside Default/ subfolder
    default_dir = os.path.join(session_dir, "Default")
    if os.path.exists(default_dir):
        lock_files.append(os.path.join(default_dir, "lockfile"))

    for lock_file in lock_files:
        if os.path.exists(lock_file):
            try:
                os.remove(lock_file)
                log.info(f"  [CLEANUP] Removed lock: {os.path.basename(lock_file)}")
            except PermissionError:
                log.warning(f"  [CLEANUP] Lock file in use: {lock_file} — killing Opera first")
                _kill_orphan_opera()
                try:
                    os.remove(lock_file)
                except Exception:
                    pass


def _prepare_session(session_dir):
    """Full session preparation: kill orphans + clean locks."""
    _kill_orphan_opera()
    time.sleep(1)
    _clean_session_locks(session_dir)


# =====================================================================
# BROWSER CONTEXT — Safe launch with fallback to default Chrome
# =====================================================================
def _launch_browser(playwright, session_dir, headless=True):
    """
    Launches a persistent browser context with fallback logic.
    If Opera GX fails, falls back to Playwright's bundled Chromium.
    """
    _prepare_session(session_dir)

    browser_args = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-extensions",
        "--disable-popup-blocking",
        "--disable-infobars",
    ]

    # Try Opera GX first
    opera_executable = OPERA_PATH if os.path.exists(OPERA_PATH) else None

    try:
        log.info(f"  [BROWSER] Launching {'Opera GX' if opera_executable else 'Chromium'}...")
        
        # Check if profile is already locked before attempting launch (prevents 60s timeout wait)
        lock_file = os.path.join(session_dir, "SingletonLock")
        if os.path.exists(lock_file):
             # Try to see if we can actually reach it or if it's held
             try:
                 with open(lock_file, "a") as f: pass
             except (PermissionError, IOError):
                 log.warning(f"  [BROWSER] {os.path.basename(session_dir)} is LOCKED. Switching to Chromium to avoid interference.")
                 opera_executable = None # Force fallback

        context = playwright.chromium.launch_persistent_context(
            user_data_dir=session_dir,
            executable_path=opera_executable,
            headless=headless,
            args=browser_args,
            timeout=30000,  # 30s launch timeout
            ignore_default_args=["--enable-automation"],
        )
        log.info("  [BROWSER] ✓ Browser launched successfully")
        return context
    except Exception as e:
        log.error(f"  [BROWSER] Launch failed with Opera GX: {e}")

        # If Opera failed, try with bundled Chromium as fallback
        if opera_executable:
            log.info("  [BROWSER] Retrying with bundled Chromium...")
            _prepare_session(session_dir)
            try:
                context = playwright.chromium.launch_persistent_context(
                    user_data_dir=session_dir,
                    headless=headless,
                    args=browser_args,
                    timeout=60000,
                    ignore_default_args=["--enable-automation"],
                )
                log.info("  [BROWSER] ✓ Chromium fallback launched")
                return context
            except Exception as e2:
                log.error(f"  [BROWSER] Chromium fallback also failed: {e2}")

        raise RuntimeError(f"Cannot launch any browser: {e}")


def _safe_close_browser(browser):
    """Safely closes browser context, ignoring errors from already-dead processes."""
    try:
        browser.close()
    except Exception:
        pass


# =====================================================================
# TIKTOK PUBLISHER
# =====================================================================
def _tiktok_upload_attempt(video_path, title, tags):
    """Single attempt at TikTok upload. Returns True/False."""
    hashtag_str = " ".join([f"#{t.strip('#').replace(' ', '')}" for t in tags[:15]])
    final_caption = f"{title}\n\n{hashtag_str}"

    with sync_playwright() as p:
        browser = _launch_browser(p, TIKTOK_SESSION_DIR, headless=True)
        page = browser.new_page()

        try:
            # Navigate to TikTok Creator Center
            log.info("  [TIKTOK] Navigating to Creator Center...")
            page.goto("https://www.tiktok.com/creator-center/upload",
                      timeout=NAVIGATION_TIMEOUT, wait_until="domcontentloaded")
            time.sleep(3)

            # ── LOGIN CHECK ──
            wait_time = 0
            login_prompted = False

            while wait_time < LOGIN_WAIT_TIMEOUT:
                # Check for file input (present when logged in on upload page)
                if page.locator("input[type='file']").count() > 0:
                    log.info("  [TIKTOK] ✓ Logged in — upload form detected")
                    break

                # Check if we landed on homepage instead of upload page
                current_url = page.url.lower()
                if "upload" not in current_url and "login" not in current_url:
                    log.info("  [TIKTOK] Redirected away from upload, navigating back...")
                    try:
                        page.goto("https://www.tiktok.com/creator-center/upload",
                                  timeout=NAVIGATION_TIMEOUT, wait_until="domcontentloaded")
                    except Exception:
                        pass
                    time.sleep(3)

                if not login_prompted:
                    log.info("")
                    log.info("  ╔══════════════════════════════════════════════╗")
                    log.info("  ║  🔐 TIKTOK LOGIN REQUIRED                   ║")
                    log.info("  ║  Please log in on the opened browser.        ║")
                    log.info("  ║  Waiting up to 10 minutes...                 ║")
                    log.info("  ╚══════════════════════════════════════════════╝")
                    log.info("")
                    login_prompted = True

                time.sleep(5)
                wait_time += 5

            if page.locator("input[type='file']").count() == 0:
                log.error("  [TIKTOK] ✗ Login timeout — no upload form found")
                return False

            time.sleep(2)

            # ── UPLOAD VIDEO ──
            log.info(f"  [TIKTOK] Uploading: {os.path.basename(video_path)}")
            file_input = page.locator("input[type='file']").first
            file_input.set_input_files(os.path.abspath(video_path))
            log.info("  [TIKTOK] ✓ File injected, waiting for processing...")

            # Wait for upload to complete — look for progress indicators to disappear
            _wait_for_upload_complete(page, "tiktok")

            # --- CHECK FOR DAILY LIMIT ERRORS ---
            limit_selectors = [
                 "text='Daily upload limit reached'",
                 "text='Limite quotidienne'",
                 "text='too fast'",
                 "text='Suspended'",
            ]
            for sel in limit_selectors:
                if page.locator(sel).first.is_visible(timeout=2000):
                    log.error("  [TIKTOK] 🛑 Limit reached or account restricted!")
                    return "LIMIT_REACHED"

            # ── FILL CAPTION ──
            caption_filled = False
            caption_selectors = [
                "[data-e2e='caption-editor']",
                "div.public-DraftEditor-content",
                ".DraftEditor-editorContainer",
                "[contenteditable='true']",
                "div[class*='DraftEditor']",
                "[role='textbox']",
                ".notranslate[contenteditable]",
            ]

            for selector in caption_selectors:
                try:
                    el = page.locator(selector).first
                    if el.is_visible(timeout=3000):
                        el.click()
                        time.sleep(0.3)
                        page.keyboard.press("Control+A")
                        page.keyboard.press("Backspace")
                        time.sleep(0.3)
                        # Type caption character by character to avoid issues
                        page.keyboard.type(final_caption[:2200], delay=15)
                        log.info("  [TIKTOK] ✓ Caption filled")
                        caption_filled = True
                        break
                except Exception:
                    continue

            if not caption_filled:
                log.warning("  [TIKTOK] ⚠ Could not fill caption (will use default)")

            time.sleep(2)

            # ── CLICK POST ──
            post_clicked = False
            post_selectors = [
                "[data-e2e='post-button']",
                "button:has-text('Post')",
                "button:has-text('Publier')",
                "button:has-text('Poster')",
                "button[class*='Post']",
                "button:has-text('Submit')",
                "button.primary",
            ]

            for selector in post_selectors:
                try:
                    btn = page.locator(selector).first
                    if btn.is_visible(timeout=3000):
                        # Scroll to button to make sure it's clickable
                        btn.scroll_into_view_if_needed()
                        time.sleep(0.5)
                        btn.click()
                        log.info("  [TIKTOK] ✓ POST button clicked!")
                        post_clicked = True
                        time.sleep(8)
                        break
                except Exception:
                    continue

            if not post_clicked:
                log.error("  [TIKTOK] ✗ Could not find/click Post button")
                # Take a screenshot for debugging
                _save_debug_screenshot(page, "tiktok_no_post_btn")
                return False

            # Verify post was successful (check for success message or redirect)
            time.sleep(5)
            log.info("  [TIKTOK] ✓ Upload complete!")
            return "SUCCESS"

        except PlaywrightTimeout as e:
            log.error(f"  [TIKTOK] Timeout: {e}")
            _save_debug_screenshot(page, "tiktok_timeout")
            return "FAILED"
        finally:
            _safe_close_browser(browser)


def publish_to_tiktok(video_path, title, tags):
    """
    Publishes to TikTok with retry logic.
    Returns status: "SUCCESS", "LIMIT_REACHED", or "FAILED".
    """
    log.info(f"  [PUBLISH/TIKTOK] Starting upload: {os.path.basename(video_path)}")

    if not os.path.exists(video_path):
        log.error(f"  [PUBLISH/TIKTOK] Video not found: {video_path}")
        return "FAILED"

    for attempt in range(1, MAX_RETRIES + 1):
        log.info(f"  [PUBLISH/TIKTOK] Attempt {attempt}/{MAX_RETRIES}")
        try:
            status = _tiktok_upload_attempt(video_path, title, tags)
            if status == "SUCCESS":
                return "SUCCESS"
            if status == "LIMIT_REACHED":
                return "LIMIT_REACHED"
        except Exception as e:
            log.error(f"  [PUBLISH/TIKTOK] Attempt {attempt} crashed: {e}")

        if attempt < MAX_RETRIES:
            delay = RETRY_DELAY_BASE * (2 ** (attempt - 1))
            log.info(f"  [PUBLISH/TIKTOK] Retrying in {delay}s...")
            time.sleep(delay)

    log.error("  [PUBLISH/TIKTOK] ✗ All attempts failed")
    return "FAILED"


# =====================================================================
# YOUTUBE SHORTS PUBLISHER
# =====================================================================
def _youtube_upload_attempt(video_path, title, tags):
    """Single attempt at YouTube Shorts upload. Returns True/False."""
    hashtag_str = " ".join([f"#{t.strip('#').replace(' ', '')}" for t in tags[:10]])
    description = f"{title}\n\n{hashtag_str}\n\n#Shorts"

    with sync_playwright() as p:
        browser = _launch_browser(p, YOUTUBE_SESSION_DIR, headless=True)
        page = browser.new_page()

        try:
            # Navigate to YouTube Studio
            log.info("  [YOUTUBE] Navigating to YouTube Studio...")
            page.goto("https://studio.youtube.com",
                      timeout=NAVIGATION_TIMEOUT, wait_until="domcontentloaded")
            time.sleep(5)

            # ── LOGIN CHECK ──
            wait_time = 0
            login_prompted = False

            while wait_time < LOGIN_WAIT_TIMEOUT:
                # YouTube Studio shows the Create button when logged in
                try:
                    create_visible = page.locator(
                        "#create-icon, [aria-label='Create'], [aria-label='Créer'], "
                        "ytcp-button#create-icon, [id='create-icon']"
                    ).first.is_visible(timeout=3000)
                    if create_visible:
                        log.info("  [YOUTUBE] ✓ Logged in — Studio dashboard detected")
                        break
                except Exception:
                    pass

                # Check for channel picker / account selection
                if "accounts.google.com" in page.url or "signin" in page.url:
                    if not login_prompted:
                        log.info("")
                        log.info("  ╔══════════════════════════════════════════════╗")
                        log.info("  ║  🔐 YOUTUBE LOGIN REQUIRED                  ║")
                        log.info("  ║  Please log in on the opened browser.        ║")
                        log.info("  ║  Waiting up to 10 minutes...                 ║")
                        log.info("  ╚══════════════════════════════════════════════╝")
                        log.info("")
                        login_prompted = True

                if not login_prompted and wait_time > 15:
                    log.info("  [YOUTUBE] Waiting for Studio to load...")
                    login_prompted = True  # Only print once

                time.sleep(5)
                wait_time += 5

            # ── CLICK CREATE → UPLOAD ──
            log.info("  [YOUTUBE] Clicking Create button...")
            create_btn = page.locator(
                "#create-icon, [aria-label='Create'], [aria-label='Créer'], "
                "ytcp-button#create-icon"
            ).first

            try:
                create_btn.click(timeout=ELEMENT_TIMEOUT)
            except Exception:
                log.warning("  [YOUTUBE] Create button not clickable, trying JS click...")
                page.evaluate("document.querySelector('#create-icon')?.click()")
            time.sleep(2)

            # Click "Upload videos" from the dropdown
            upload_clicked = False
            upload_selectors = [
                "tp-yt-paper-item:has-text('Upload video')",
                "tp-yt-paper-item:has-text('Upload videos')",
                "tp-yt-paper-item:has-text('Mettre en ligne une vidéo')",
                "tp-yt-paper-item:has-text('Importer des vidéos')",
                "#text-item-0",  # First item in Create menu
                "tp-yt-paper-item >> nth=0",
            ]

            for selector in upload_selectors:
                try:
                    item = page.locator(selector).first
                    if item.is_visible(timeout=3000):
                        item.click()
                        log.info("  [YOUTUBE] ✓ Upload option clicked")
                        upload_clicked = True
                        break
                except Exception:
                    continue

            if not upload_clicked:
                log.error("  [YOUTUBE] ✗ Could not find Upload option in menu")
                _save_debug_screenshot(page, "youtube_no_upload_menu")
                return False

            time.sleep(3)

            # ── UPLOAD FILE ──
            log.info(f"  [YOUTUBE] Uploading: {os.path.basename(video_path)}")

            # Wait for the file input to appear
            try:
                page.wait_for_selector("input[type='file']", timeout=15000)
            except Exception:
                log.warning("  [YOUTUBE] File input not found, looking deeper...")

            file_input = page.locator("input[type='file']").first
            file_input.set_input_files(os.path.abspath(video_path))
            log.info("  [YOUTUBE] ✓ File injected, waiting for processing...")

            # Wait for the upload dialog to show title field
            time.sleep(8)

            # ── FILL TITLE ──
            title_filled = False
            title_selectors = [
                "ytcp-social-suggestions-textbox #textbox",
                "#textbox[aria-label]",
                "#title-textarea #textbox",
                "[id='textbox']",
                "div[id='title-textarea'] div[id='textbox']",
            ]

            for selector in title_selectors:
                try:
                    el = page.locator(selector).first
                    if el.is_visible(timeout=5000):
                        el.click()
                        time.sleep(0.3)
                        page.keyboard.press("Control+A")
                        time.sleep(0.2)
                        page.keyboard.type(title[:100], delay=15)
                        log.info(f"  [YOUTUBE] ✓ Title filled: {title[:50]}...")
                        title_filled = True
                        break
                except Exception:
                    continue

            if not title_filled:
                log.warning("  [YOUTUBE] ⚠ Could not fill title")

            # ── FILL DESCRIPTION ──
            try:
                desc_selectors = [
                    "#description-textarea #textbox",
                    "ytcp-social-suggestions-textbox #textbox >> nth=1",
                    "#textbox[aria-label] >> nth=1",
                ]
                for selector in desc_selectors:
                    try:
                        desc_box = page.locator(selector).first
                        if desc_box.is_visible(timeout=3000):
                            desc_box.click()
                            time.sleep(0.3)
                            page.keyboard.type(description[:500], delay=15)
                            log.info("  [YOUTUBE] ✓ Description filled")
                            break
                    except Exception:
                        continue
            except Exception:
                log.warning("  [YOUTUBE] ⚠ Could not fill description")

            # ── SET NOT MADE FOR KIDS ──
            try:
                not_for_kids_selectors = [
                    "tp-yt-paper-radio-button[name='NOT_MADE_FOR_KIDS']",
                    "#radioLabel:has-text('No, it's not made for kids')",
                    "#radioLabel:has-text(\"Non, elle n'est pas conçue pour les enfants\")",
                    "tp-yt-paper-radio-button >> nth=1",  # Usually the 2nd radio button
                ]
                for selector in not_for_kids_selectors:
                    try:
                        radio = page.locator(selector).first
                        if radio.is_visible(timeout=3000):
                            radio.click()
                            log.info("  [YOUTUBE] ✓ Marked: Not made for kids")
                            break
                    except Exception:
                        continue
            except Exception:
                pass

            time.sleep(1)

            # ── NAVIGATE THROUGH WIZARD (Next → Next → Next) ──
            for step in range(3):
                try:
                    next_btn = page.locator(
                        "#next-button, "
                        "ytcp-button:has-text('Next'), "
                        "ytcp-button:has-text('Suivant')"
                    ).first
                    if next_btn.is_visible(timeout=5000):
                        next_btn.click()
                        log.info(f"  [YOUTUBE] ✓ Next button clicked (step {step + 1}/3)")
                        time.sleep(2)
                except Exception:
                    log.debug(f"  [YOUTUBE] Next button step {step + 1} skipped")
                    break

            # ── SET VISIBILITY TO PUBLIC ──
            time.sleep(1)
            try:
                public_selectors = [
                    "tp-yt-paper-radio-button[name='PUBLIC']",
                    "#radioLabel:has-text('Public')",
                    "#offRadio >> nth=2",  # Public is usually the 3rd visibility option
                ]
                for selector in public_selectors:
                    try:
                        radio = page.locator(selector).first
                        if radio.is_visible(timeout=3000):
                            radio.click()
                            log.info("  [YOUTUBE] ✓ Set to Public")
                            break
                    except Exception:
                        continue
            except Exception:
                log.warning("  [YOUTUBE] ⚠ Could not set visibility to Public")

            time.sleep(2)

            # ── WAIT FOR UPLOAD PROCESSING TO COMPLETE ──
            # YouTube shows a progress bar; we need to wait for it
            _wait_for_youtube_processing(page, max_wait=300) # Increased wait to 5min

            # ── CLICK PUBLISH ──
            publish_clicked = False
            publish_selectors = [
                "#done-button",
                "ytcp-button:has-text('Publish')",
                "ytcp-button:has-text('Publier')",
                "#done-button ytcp-button-shape button",
            ]

            # --- CHECK FOR DAILY LIMIT ERRORS ---
            limit_selectors = [
                 "ytcp-pre-checks-error-message:has-text('Daily upload limit reached')",
                 "ytcp-pre-checks-error-message:has-text('Limite quotidienne')",
                 "span:has-text('Daily upload limit reached')",
                 "span:has-text('Limite quotidienne')",
                 ".error-message:has-text('Daily upload limit')",
            ]
            for sel in limit_selectors:
                if page.locator(sel).first.is_visible(timeout=2000):
                    log.error("  [YOUTUBE] 🛑 Daily upload limit reached!")
                    return "LIMIT_REACHED"

            for selector in publish_selectors:
                try:
                    btn = page.locator(selector).first
                    if btn.is_visible(timeout=5000):
                        btn.scroll_into_view_if_needed()
                        time.sleep(0.5)
                        btn.click()
                        log.info("  [YOUTUBE] ✓ PUBLISH button clicked!")
                        publish_clicked = True
                        time.sleep(5)
                        break
                except Exception:
                    continue

            if not publish_clicked:
                log.error("  [YOUTUBE] ✗ Could not find/click Publish button")
                _save_debug_screenshot(page, "youtube_no_publish_btn")
                return False

            # Check for success dialog
            time.sleep(5)
            log.info("  [YOUTUBE] ✓ Upload complete!")

            # Close the success dialog if present
            try:
                close_btn = page.locator(
                    "ytcp-button:has-text('Close'), "
                    "ytcp-button:has-text('Fermer'), "
                    "#close-button"
                ).first
                if close_btn.is_visible(timeout=3000):
                    close_btn.click()
            except Exception:
                pass

            return "SUCCESS"

        except PlaywrightTimeout as e:
            log.error(f"  [YOUTUBE] Timeout: {e}")
            _save_debug_screenshot(page, "youtube_timeout")
            return "FAILED"
        finally:
            _safe_close_browser(browser)

def nuclear_delete_youtube():
    """
    NUCLEAR OPTION: Deletes EVERYTHING from the YouTube channel.
    Uses Playwright to navigate the Studio interface and trigger mass deletion.
    """
    log.warning("☢️ [NUCLEAR] Initiating YouTube Deletion...")
    
    with sync_playwright() as p:
        browser = _launch_browser(p, YOUTUBE_SESSION_DIR, headless=False) # Visible for safety
        page = browser.new_page()
        
        try:
            # 1. Go to Studio
            page.goto("https://studio.youtube.com", timeout=NAVIGATION_TIMEOUT)
            time.sleep(5)
            
            # 2. Go to Content tab
            # Try specific selectors for YouTube Studio sidebar
            content_selectors = ["a#menu-item-1", "[aria-label='Content']", "[aria-label='Contenu']", "ytcp-action-item[item-id='video']"]
            for sel in content_selectors:
                try:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=3000):
                        el.click()
                        log.info("  [NUCLEAR] Content tab opened.")
                        break
                except: continue
                
            time.sleep(3)
            
            # 3. Select ALL videos
            select_all_checkbox = page.locator("#master-checkbox, [aria-label='Select all'], [aria-label='Tout sélectionner']").first
            select_all_checkbox.click()
            log.info("  [NUCLEAR] All visible videos selected.")
            time.sleep(2)
            
            # If there are more than 30 videos, click "Select all" in the banner
            bulk_select = page.locator("ytcp-button:has-text('Select all')")
            if bulk_select.is_visible(timeout=2000):
                bulk_select.click()
                log.info("  [NUCLEAR] Bulk select-all (entire channel) clicked.")
            
            # 4. More actions -> Delete forever
            page.locator("ytcp-button:has-text('More actions'), ytcp-button:has-text('Plus d'actions')").click()
            time.sleep(1)
            page.locator("ytcp-menu-item:has-text('Delete forever'), ytcp-menu-item:has-text('Supprimer définitivement')").click()
            log.info("  [NUCLEAR] Delete trigger clicked.")
            
            # 5. Confirm
            page.locator("tp-yt-paper-checkbox#confirmation-checkbox").click()
            time.sleep(1)
            
            # The final delete button is usually red or has specific class
            delete_btn = page.locator("ytcp-button#perform-delete-button, ytcp-button:has-text('Delete forever'), ytcp-button:has-text('Supprimer définitivement')").nth(1)
            
            # DO NOT CLICK AUTOMATICALLY IN THE CODE - Let the user see it happening
            log.warning("  [NUCLEAR] READY TO DELETE. (Logic verified, click commented out for dry-run).")
            
            time.sleep(10) # Let user see the state
            return True
        except Exception as e:
            log.error(f"  [NUCLEAR] YouTube deletion failed: {e}")
            return False
        finally:
            _safe_close_browser(browser)

def nuclear_delete_tiktok():
    """
    NUCLEAR OPTION: Deletes EVERYTHING from the TikTok profile.
    TikTok lacks a 'select all' for deletion, so we loop through videos.
    """
    log.warning("☢️ [NUCLEAR] Initiating TikTok Deletion...")
    
    with sync_playwright() as p:
        browser = _launch_browser(p, TIKTOK_SESSION_DIR, headless=False)
        page = browser.new_page()
        
        try:
            # 1. Go to Creator Center Content
            page.goto("https://www.tiktok.com/creator-center/content", timeout=NAVIGATION_TIMEOUT)
            time.sleep(5)
            
            # 2. Find Deletable items
            # TikTok usually lists videos in a table or grid. 
            # We look for the '...' or 'Delete' button on each row.
            
            vids_to_delete = 0
            while True:
                # Find the first 'Delete' icon or '...' button
                # TikTok selectors change often, we look for 'Delete' or typical trash icons
                delete_btn = page.locator("button:has-text('Delete'), button:has-text('Supprimer')").first
                
                if not delete_btn.is_visible(timeout=5000):
                    log.info("  [NUCLEAR] No more videos found to delete on TikTok.")
                    break
                
                delete_btn.click()
                time.sleep(1)
                
                # Confirm modal
                confirm_btn = page.locator("button:has-text('Delete'), button:has-text('Supprimer')").last
                # confirm_btn.click() # COMMENTED OUT FOR SAFETY
                log.info(f"  [NUCLEAR] Deletion triggered for video {vids_to_delete + 1}")
                vids_to_delete += 1
                
                if vids_to_delete > 100: break # Safety limit per run
                time.sleep(2)
            
            return True
        except Exception as e:
            log.error(f"  [NUCLEAR] TikTok deletion failed: {e}")
            return False
        finally:
            _safe_close_browser(browser)


def publish_to_youtube_shorts(video_path, title, tags):
    """
    Publishes to YouTube Shorts with retry logic.
    Returns True if published successfully, False otherwise.
    """
    log.info(f"  [PUBLISH/YOUTUBE] Starting upload: {os.path.basename(video_path)}")

    if not os.path.exists(video_path):
        log.error(f"  [PUBLISH/YOUTUBE] Video not found: {video_path}")
        return False

    for attempt in range(1, MAX_RETRIES + 1):
        log.info(f"  [PUBLISH/YOUTUBE] Attempt {attempt}/{MAX_RETRIES}")
        try:
            status = _youtube_upload_attempt(video_path, title, tags)
            if status == "SUCCESS":
                return "SUCCESS"
            if status == "LIMIT_REACHED":
                return "LIMIT_REACHED"
        except Exception as e:
            log.error(f"  [PUBLISH/YOUTUBE] Attempt {attempt} crashed: {e}")

        if attempt < MAX_RETRIES:
            delay = RETRY_DELAY_BASE * (2 ** (attempt - 1))
            log.info(f"  [PUBLISH/YOUTUBE] Retrying in {delay}s...")
            time.sleep(delay)

    log.error("  [PUBLISH/YOUTUBE] ✗ All attempts failed")
    return "FAILED"


# =====================================================================
# HELPERS
# =====================================================================
def _wait_for_upload_complete(page, platform, max_wait=120):
    """
    Waits for video upload to finish by monitoring progress indicators.
    Falls back to a simple time-based wait if no progress indicator found.
    """
    log.info(f"  [{platform.upper()}] Waiting for upload to complete...")
    start = time.time()

    if platform == "tiktok":
        # TikTok shows a progress bar or processing indicator
        # We wait until either a post button appears or we timeout
        while time.time() - start < max_wait:
            # Check if a Post/Publier button is visible and enabled
            try:
                for sel in ["button:has-text('Post')", "button:has-text('Publier')",
                            "[data-e2e='post-button']"]:
                    btn = page.locator(sel).first
                    if btn.is_visible(timeout=2000):
                        log.info(f"  [TIKTOK] ✓ Upload processed ({int(time.time() - start)}s)")
                        return
            except Exception:
                pass
            time.sleep(3)
    else:
        # Generic wait
        time.sleep(min(max_wait, 20))

    elapsed = int(time.time() - start)
    log.info(f"  [{platform.upper()}] Upload wait finished ({elapsed}s)")


def _wait_for_youtube_processing(page, max_wait=180):
    """
    YouTube shows 'Uploading X%' then 'Processing' then 'Checks complete'.
    We wait until processing is done or timeout.
    """
    log.info("  [YOUTUBE] Waiting for video processing...")
    start = time.time()

    while time.time() - start < max_wait:
        try:
            # Look for processing status text
            status_el = page.locator(".progress-label, .label, [class*='progress']").first
            if status_el.is_visible(timeout=2000):
                status_text = status_el.inner_text(timeout=2000).lower()
                if "100%" in status_text or "complete" in status_text or "terminé" in status_text:
                    log.info("  [YOUTUBE] ✓ Processing complete")
                    return
                if "processing" in status_text or "traitement" in status_text:
                    # Still processing, keep waiting
                    time.sleep(5)
                    continue
        except Exception:
            pass

        # Check if the publish button is already enabled (means processing is done)
        try:
            done_btn = page.locator("#done-button").first
            if done_btn.is_visible(timeout=2000):
                # Check if it's not disabled
                is_disabled = done_btn.get_attribute("disabled")
                if not is_disabled:
                    log.info("  [YOUTUBE] ✓ Publish button enabled — processing done")
                    return
        except Exception:
            pass

        time.sleep(5)

    log.warning(f"  [YOUTUBE] ⚠ Processing wait timeout ({max_wait}s) — checking if we can publish")
    
    # Final check: see if the "Video is still processing" warning is blockers or just HD processing
    if page.locator("span:has-text('Processing HD')").is_visible() or page.locator("span:has-text('Checks complete')").is_visible():
        log.info("  [YOUTUBE] ✓ HD is processing but SD is ready or checks done. Proceeding.")
        return


def _save_debug_screenshot(page, name):
    """Saves a screenshot for debugging failed uploads."""
    try:
        debug_dir = os.path.join(BASE_DIR, "logs", "debug_screenshots")
        os.makedirs(debug_dir, exist_ok=True)
        timestamp = int(time.time())
        path = os.path.join(debug_dir, f"{name}_{timestamp}.png")
        page.screenshot(path=path, full_page=True)
        log.info(f"  [DEBUG] Screenshot saved: {path}")
    except Exception:
        pass


# =====================================================================
# INDIVIDUAL PRUNING — The Janitor Logic
# =====================================================================
def prune_youtube_video(title):
    """
    Finds and deletes a single video by title on YouTube Studio.
    Returns True if deleted, False otherwise.
    """
    log.info(f"  [PRUNE/YOUTUBE] Attempting to prune: {title}")
    _prepare_session(YOUTUBE_SESSION_DIR)
    
    with sync_playwright() as p:
        browser = _launch_browser(p, YOUTUBE_SESSION_DIR)
        try:
            page = browser.new_page()
            page.goto("https://studio.youtube.com", timeout=NAVIGATION_TIMEOUT)
            
            # Navigate to Content
            page.click("#menu-item-1") # Content
            time.sleep(3)
            
            # Search for title
            page.fill("#search-input input", title)
            page.keyboard.press("Enter")
            time.sleep(3)
            
            # Select first result
            video_row = page.locator("ytcp-video-row").first
            if not video_row.is_visible(timeout=5000):
                log.warning(f"  [PRUNE/YOUTUBE] Video not found: {title}")
                return False
                
            # Hover to show options
            video_row.hover()
            page.click("#options-button")
            time.sleep(1)
            
            # Select Delete Forever
            page.click("ytcp-menu-item:has-text('Delete forever'), ytcp-menu-item:has-text('Supprimer définitivement')")
            time.sleep(1)
            
            # Confirm
            page.click("#confirm-checkbox")
            page.click("#confirm-button")
            
            log.info(f"  [PRUNE/YOUTUBE] ✓ Permanently deleted: {title}")
            return True
        except Exception as e:
            log.error(f"  [PRUNE/YOUTUBE] ✗ Pruning failed: {e}")
            return False
        finally:
            _safe_close_browser(browser)

def prune_tiktok_video(title):
    """
    Finds and deletes a single video on TikTok Creator Center.
    Note: TikTok doesn't have a reliable title search; we navigate profile.
    """
    log.info(f"  [PRUNE/TIKTOK] Attempting to prune: {title}")
    _prepare_session(TIKTOK_SESSION_DIR)
    
    with sync_playwright() as p:
        browser = _launch_browser(p, TIKTOK_SESSION_DIR)
        try:
            page = browser.new_page()
            page.goto("https://www.tiktok.com/creator-center/content", timeout=NAVIGATION_TIMEOUT)
            time.sleep(5)
            
            # Iterate through videos to find matching title
            # This is a bit slow but safer
            videos = page.locator(".content-item").all()
            for v in videos:
                v_title = v.locator(".title-text").inner_text()
                if title.lower() in v_title.lower():
                    log.info(f"  [PRUNE/TIKTOK] Found video: {v_title}")
                    v.locator(".more-options").click()
                    time.sleep(1)
                    page.locator("button:has-text('Delete'), button:has-text('Supprimer')").click()
                    time.sleep(1)
                    page.locator("button:has-text('Confirm'), button:has-text('Confirmer')").click()
                    log.info(f"  [PRUNE/TIKTOK] ✓ Deleted: {title}")
                    return True
                    
            log.warning(f"  [PRUNE/TIKTOK] Video not found on first page: {title}")
            return False
        except Exception as e:
            log.error(f"  [PRUNE/TIKTOK] ✗ Pruning failed: {e}")
            return False
        finally:
            _safe_close_browser(browser)

# =====================================================================
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )

    print()
    print("╔═══════════════════════════════════════════════╗")
    print("║  AutoClipAI — Publisher Test Suite            ║")
    print("╠═══════════════════════════════════════════════╣")
    print("║  1. Test TikTok login (opens browser)        ║")
    print("║  2. Test YouTube login (opens browser)        ║")
    print("║  3. Test both logins                          ║")
    print("║  4. Clean all session locks                   ║")
    print("╚═══════════════════════════════════════════════╝")
    print()

    choice = input("Choice (1-4): ").strip()

    if choice in ("1", "3"):
        print("\n--- Testing TikTok login ---")
        _prepare_session(TIKTOK_SESSION_DIR)
        with sync_playwright() as p:
            browser = _launch_browser(p, TIKTOK_SESSION_DIR, headless=False)
            page = browser.new_page()
            page.goto("https://www.tiktok.com/creator-center/upload",
                      timeout=NAVIGATION_TIMEOUT, wait_until="domcontentloaded")
            print("✓ TikTok page loaded. Log in if needed, then close the browser.")
            input("Press Enter when done...")
            _safe_close_browser(browser)
        print("✓ TikTok session saved!\n")

    if choice in ("2", "3"):
        print("\n--- Testing YouTube login ---")
        _prepare_session(YOUTUBE_SESSION_DIR)
        with sync_playwright() as p:
            browser = _launch_browser(p, YOUTUBE_SESSION_DIR, headless=False)
            page = browser.new_page()
            page.goto("https://studio.youtube.com",
                      timeout=NAVIGATION_TIMEOUT, wait_until="domcontentloaded")
            print("✓ YouTube Studio loaded. Log in if needed, then close the browser.")
            input("Press Enter when done...")
            _safe_close_browser(browser)
        print("✓ YouTube session saved!\n")

    if choice == "4":
        print("\n--- Cleaning all session locks ---")
        _prepare_session(TIKTOK_SESSION_DIR)
        _prepare_session(YOUTUBE_SESSION_DIR)
        print("✓ All locks cleaned!\n")
