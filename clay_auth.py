"""
Shared Playwright session handling for Clay automation in this repo.

Two ways to connect, in order of preference:

  1. CDP: drive a real, already-logged-in Chrome. Clay bot-blocks a
     Playwright-*launched* browser (serves the logged-out marketing page
     even with valid cookies), so this is the reliable path. Launch Chrome
     yourself first:

       chrome.exe --remote-debugging-port=9222 --user-data-dir=C:\\clay-debug
                  --window-size=1720,1000

     log into Clay in it, then run this tool with CLAY_USE_CDP=1 set.

  2. Saved session: a bundled Chromium reusing cookies saved by
     clay_login.py (.clay_session.json). Simpler (no manual Chrome launch)
     but more likely to get bot-blocked.

Ported from clay-icp-pipeline's automation/build_automation/browser_session.py,
trimmed to just the connection logic — the Interphex-specific workbook/table
helpers that used to live alongside it are replaced by clay_nav.py /
clay_tables.py in this repo.
"""
import contextlib
import os

from playwright.sync_api import sync_playwright

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SESSION_PATH = os.path.join(SCRIPT_DIR, ".clay_session.json")

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

CDP_ENDPOINT = os.environ.get("CLAY_CDP", "http://127.0.0.1:9222")


@contextlib.contextmanager
def clay_page(headless: bool = True):
    """Yield a Clay page: CDP-connected real Chrome if CLAY_USE_CDP is set
    and reachable, else a bundled browser restored from the saved session."""
    with sync_playwright() as p:
        browser = None
        if os.environ.get("CLAY_USE_CDP"):
            try:
                browser = p.chromium.connect_over_cdp(CDP_ENDPOINT, timeout=5000)
            except Exception:
                browser = None

        if browser is not None:
            ctx = browser.contexts[0] if browser.contexts else browser.new_context()
            page = ctx.new_page()
            try:
                page.set_viewport_size({"width": 1720, "height": 980})
            except Exception:
                pass
            try:
                yield page
            finally:
                try:
                    page.close()  # close only our tab; leave the real Chrome open
                except Exception:
                    pass
                # NOTE: never call browser.close() on a CDP connection — it can
                # terminate the user's real Chrome. Just let the driver detach.
            return

        if not os.path.exists(SESSION_PATH):
            raise SystemExit(
                f"No Clay session at {SESSION_PATH}; run: python clay_login.py")
        browser = p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled",
                  "--disable-dev-shm-usage", "--disable-gpu",
                  "--disable-extensions", "--disable-background-networking",
                  "--disable-features=site-per-process,TranslateUI",
                  # app.clay.com intermittently throws ERR_QUIC_PROTOCOL_ERROR;
                  # forcing HTTP/2 avoids it.
                  "--disable-quic",
                  "--renderer-process-limit=2"])
        ctx = browser.new_context(storage_state=SESSION_PATH, user_agent=UA,
                                   viewport={"width": 1720, "height": 980})
        ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        page = ctx.new_page()
        try:
            yield page
        finally:
            browser.close()
