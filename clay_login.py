#!/usr/bin/env python3
"""
One-time interactive login for Clay (app.clay.com).

Opens a real (headed) browser, lets you log in by hand, then saves the
authenticated session to .clay_session.json so create_table.py can reuse it
without logging in again.

Usage:
  python clay_login.py

Re-run this whenever create_table.py reports the session has expired.

SECURITY: .clay_session.json contains live login cookies — it is equivalent
to your password. It is gitignored; never commit, share, or upload it.
"""
from playwright.sync_api import sync_playwright

from clay_auth import SESSION_PATH, UA

CLAY_URL = "https://app.clay.com"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(user_agent=UA)
        ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
        )
        page = ctx.new_page()
        page.goto(CLAY_URL)

        print("\nA browser window has opened at app.clay.com.")
        print("Log in fully (until you can see your Clay workspace), then")
        input("come back here and press Enter to save the session... ")

        ctx.storage_state(path=SESSION_PATH)
        browser.close()

    print(f"\nSaved session to: {SESSION_PATH}")
    print("WARNING: this file contains live login cookies — treat it like a")
    print("password. It is gitignored; never commit, share, or upload it.")


if __name__ == "__main__":
    main()
