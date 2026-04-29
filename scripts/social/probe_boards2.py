#!/usr/bin/env python3
"""Better Pinterest board probe — use modern selectors + dump cleanly."""
import sys, json
from pathlib import Path
from playwright.sync_api import sync_playwright

REPO = Path("/Users/agentdavid/mirai-seo/satellite-websites")
STATE_DIR = REPO / "scripts/social/browser-state"


def list_boards(page, username_hint=""):
    """Navigate to user's profile -> Created tab -> scrape board names."""
    page.goto("https://www.pinterest.com/", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(3000)
    # Find the user's profile URL from the avatar
    profile_url = page.evaluate("""
        () => {
          const a = document.querySelector('[data-test-id="header-profile"] a, a[data-test-id="header-profile-button"], header a[href*=".com/"]:not([href*="/business"]):not([href*="/_create/"])');
          return a ? a.href : null;
        }
    """)
    if not profile_url:
        # Try clicking avatar and reading new URL
        try:
            page.click('[data-test-id="header-profile"]', timeout=5000)
            page.wait_for_timeout(3000)
            profile_url = page.url
        except Exception:
            pass
    if not profile_url:
        return []
    # Navigate to /Created tab
    if not profile_url.endswith("/_created/"):
        if profile_url.endswith("/_saved/"):
            profile_url = profile_url.rsplit("/_saved/")[0] + "/_created/"
        else:
            profile_url = profile_url.rstrip("/") + "/_created/"
    page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(4000)
    # Scroll to load
    for _ in range(3):
        page.evaluate("window.scrollBy(0, 1000)")
        page.wait_for_timeout(800)
    # Scrape board names
    boards = page.evaluate("""
        () => {
          const out = new Set();
          // Strategy 1: data-test-id board cards
          document.querySelectorAll('[data-test-id="board-card"], [data-test-id="boardCard"]').forEach(c => {
            const t = c.querySelector('[data-test-id="board-card-name"], h3, [data-test-id="board-name"]');
            if (t && t.innerText.trim()) out.add(t.innerText.trim().split('\\n')[0]);
          });
          // Strategy 2: links to /<user>/<slug>/
          const userPath = location.pathname.replace('/_created/', '/').replace('/_saved/','/');
          document.querySelectorAll('a').forEach(a => {
            try {
              const u = new URL(a.href);
              if (u.pathname.startsWith(userPath) && u.pathname !== userPath) {
                const slugPart = u.pathname.slice(userPath.length).replace(/\\/$/, '');
                if (slugPart && !slugPart.includes('/') && !slugPart.startsWith('_')) {
                  // try aria-label / inner text
                  const label = a.getAttribute('aria-label') || a.innerText || '';
                  if (label.trim()) out.add(label.trim().split('\\n')[0]);
                }
              }
            } catch(e){}
          });
          return [...out].filter(s => s && !['Created','Saved','All Pins','Messages','Notifications'].includes(s));
        }
    """)
    return sorted(set(boards))


def main():
    accounts = sys.argv[1:] or ["mirai", "cosmetics", "wellness"]
    out = {}
    with sync_playwright() as p:
        for account in accounts:
            state = STATE_DIR / f"pinterest-{account}" / "state.json"
            if not state.exists():
                print(f"=== {account} === NO SESSION", file=sys.stderr)
                out[account] = []
                continue
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(storage_state=str(state), viewport={"width":1280,"height":900})
            page = ctx.new_page()
            try:
                boards = list_boards(page)
                out[account] = boards
                print(f"=== {account} ===", file=sys.stderr)
                for b in boards:
                    print(f"  {b}", file=sys.stderr)
            finally:
                ctx.close()
                browser.close()
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
