#!/usr/bin/env python3
"""Create missing Pinterest boards on each account.

For each account, create the boards listed in BOARDS_TO_CREATE if they don't already exist.
"""
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

REPO = Path("/Users/agentdavid/mirai-seo/satellite-websites")
STATE_DIR = REPO / "scripts/social/browser-state"

# Account → list of boards that should exist
BOARDS_TO_CREATE = {
    "wellness": ["Nutrition & Recipes", "Fitness & Movement"],
    "cosmetics": ["Skincare Routines", "K-Beauty Ingredients", "Skincare Tips"],
}


def get_existing_boards(page):
    """Return set of existing board names by scraping the profile page."""
    page.goto("https://www.pinterest.com/", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(3000)
    # Click profile / avatar
    try:
        page.click('[data-test-id="header-profile"]', timeout=8000)
    except Exception:
        try:
            page.click('a[data-test-id="profile-button"]', timeout=8000)
        except Exception:
            pass
    page.wait_for_timeout(4000)
    # Click "Saved" tab — shows all boards
    try:
        page.click('text="Saved"', timeout=4000)
    except Exception:
        pass
    page.wait_for_timeout(3000)
    # Get board names from card titles
    names = page.evaluate("""
        () => {
          const cards = document.querySelectorAll('[data-test-id="board-card"], [data-test-id="boardCard"]');
          const out = new Set();
          cards.forEach(c => {
            const title = c.querySelector('h3, [data-test-id="board-card-name"], div[role="link"]');
            if (title && title.innerText) out.add(title.innerText.trim().split('\\n')[0]);
          });
          return [...out];
        }
    """)
    return set(names)


def create_board(page, board_name):
    """Create a board via the Pinterest UI. Returns True if successful or already exists."""
    print(f"  Creating: {board_name}")
    try:
        # Navigate to board creation
        page.goto("https://www.pinterest.com/board/create/", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)
        # Fill board name
        name_input = page.locator('input[id="boardEditName"], input[name="boardName"], input[placeholder*="Travel"], input[placeholder*="Recipes"]').first
        name_input.wait_for(state="visible", timeout=10000)
        name_input.fill(board_name)
        page.wait_for_timeout(1000)
        # Click Create
        page.locator('button:has-text("Create")').first.click()
        page.wait_for_timeout(5000)
        # Verify URL changed (board created → /<user>/<slug>/)
        url = page.url
        if "/board/create/" in url:
            print(f"    [WARN] still on create page after submit — board may already exist")
            return False
        print(f"    [OK] {url}")
        return True
    except Exception as e:
        print(f"    [ERROR] {e}")
        return False


def process_account(p, account):
    state = STATE_DIR / f"pinterest-{account}" / "state.json"
    if not state.exists():
        print(f"\n=== {account} === NO SESSION FILE")
        return
    boards_wanted = BOARDS_TO_CREATE.get(account, [])
    if not boards_wanted:
        print(f"\n=== {account} === nothing to do")
        return
    print(f"\n=== {account} ===")
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(storage_state=str(state), viewport={"width": 1280, "height": 900})
    page = ctx.new_page()
    try:
        existing = get_existing_boards(page)
        print(f"  Existing boards: {sorted(existing)}")
        for board in boards_wanted:
            if board in existing:
                print(f"  [SKIP] '{board}' already exists")
                continue
            create_board(page, board)
            page.wait_for_timeout(2000)
        # Save updated session state
        ctx.storage_state(path=str(state))
    finally:
        ctx.close()
        browser.close()


def main():
    accounts = sys.argv[1:] or list(BOARDS_TO_CREATE.keys())
    with sync_playwright() as p:
        for a in accounts:
            try:
                process_account(p, a)
            except Exception as e:
                print(f"  FATAL: {e}")


if __name__ == "__main__":
    main()
