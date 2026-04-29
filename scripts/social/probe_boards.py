#!/usr/bin/env python3
"""Probe each Pinterest account: list all existing boards + print one-line summary."""
import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

REPO = Path("/Users/agentdavid/mirai-seo/satellite-websites")
STATE_DIR = REPO / "scripts/social/browser-state"

ACCOUNTS = ["mirai", "cosmetics", "wellness"]


def probe_account(p, account):
    state = STATE_DIR / f"pinterest-{account}" / "state.json"
    if not state.exists():
        print(f"\n=== {account} === NO SESSION FILE")
        return
    print(f"\n=== {account} ===")
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(storage_state=str(state), viewport={"width":1280,"height":900})
    page = ctx.new_page()
    try:
        page.goto("https://www.pinterest.com/", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)
        # Click avatar / profile link
        try:
            page.click('[data-test-id="header-profile"], a[data-test-id="profile-button"]', timeout=8000)
        except Exception:
            page.goto("https://www.pinterest.com/settings/", wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            page.goto("https://www.pinterest.com/", wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            try:
                page.click('a[href*="/me/"], header a[href*=".com/"]:not([href*="/business/"])', timeout=5000)
            except Exception:
                pass
        page.wait_for_timeout(4000)
        # Click Boards tab on the user profile
        try:
            page.click('text="Saved"', timeout=4000)
        except Exception:
            pass
        page.wait_for_timeout(3000)
        # Extract board names visible on the page
        board_titles = page.evaluate("""
            () => {
              const sel = 'div[data-test-id="board-card-name"], a[data-test-id="board-card"] h3, a[data-test-id="board-card"] [data-test-id="board-card-name"]';
              const nodes = document.querySelectorAll(sel);
              const out = [];
              nodes.forEach(n => out.push(n.innerText.trim()));
              if (out.length) return out;
              // Fallback: any link to /<user>/<board>/
              const re = /^https?:\\/\\/(www\\.)?pinterest\\.com\\/[^/]+\\/[^/]+\\/?$/;
              const links = document.querySelectorAll('a');
              const seen = new Set();
              links.forEach(a => {
                if (re.test(a.href) && !a.href.includes('/business/') && !a.href.includes('/_create/')) {
                  const t = a.getAttribute('aria-label') || a.innerText || '';
                  if (t.trim()) seen.add(t.trim());
                }
              });
              return [...seen];
            }
        """)
        # Also: dump current URL so we know which user
        url = page.url
        print(f"  current URL: {url}")
        print(f"  boards found ({len(board_titles)}):")
        for t in sorted(set(board_titles)):
            print(f"    {t}")
        page.screenshot(path=f"/tmp/pinterest-{account}-boards.png", full_page=True)
        print(f"  screenshot: /tmp/pinterest-{account}-boards.png")
    finally:
        ctx.close()
        browser.close()


def main():
    accounts = sys.argv[1:] or ACCOUNTS
    with sync_playwright() as p:
        for a in accounts:
            try:
                probe_account(p, a)
            except Exception as e:
                print(f"  ERROR: {e}")


if __name__ == "__main__":
    main()
