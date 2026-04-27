#!/usr/bin/env python3
"""Delete Mirai Pinterest pins by ID list (uses saved Playwright session).

Usage:
  python3 delete_mirai_pins.py --status posted --kind single   # all v1 single-product pins
  python3 delete_mirai_pins.py --pin-ids f900e457,b718426d,63921ec1
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import BROWSER_STATE_DIR, BROWSER_ARGS, PINTEREST_SCHEDULE
from playwright.sync_api import sync_playwright


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", default="mirai")
    ap.add_argument("--pin-ids", default="", help="Comma-separated schedule IDs to delete")
    ap.add_argument("--all-single-product", action="store_true",
                    help="Delete all posted v1 single-product mirai pins (those without _meta.kind=='curation')")
    ap.add_argument("--headless", action="store_true", default=False)
    args = ap.parse_args()

    state = BROWSER_STATE_DIR / f"pinterest-{args.account}" / "state.json"
    if not state.exists():
        print(f"ERROR: no session at {state}", file=sys.stderr)
        return 2

    sched = json.loads(PINTEREST_SCHEDULE.read_text())
    target_ids = set()
    if args.pin_ids:
        target_ids = {x.strip() for x in args.pin_ids.split(",") if x.strip()}
    if args.all_single_product:
        for e in sched:
            if (e.get("site") == "mirai" and e.get("status") == "posted"
                    and (e.get("_meta") or {}).get("kind") != "curation"):
                target_ids.add(e["id"])
    if not target_ids:
        print("nothing to delete (use --pin-ids or --all-single-product)")
        return 0

    targets = [e for e in sched if e["id"] in target_ids]
    print(f"Will delete {len(targets)} pin(s):")
    for t in targets:
        print(f"  - {t['id']}  {t['title'][:70]}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headless, args=BROWSER_ARGS)
        ctx = browser.new_context(
            storage_state=str(state),
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        )
        page = ctx.new_page()

        # Go to profile saved-pins; Pinterest username is the email's local part
        page.goto("https://www.pinterest.com/", wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)

        # Navigate to /pins/ for the user's created pins
        # Pinterest profile URLs are /username/_created/ — but we don't know the username.
        # Easier: visit the pin URL by id from Pinterest's edit pin tool. We need the
        # external pin numeric id (Pinterest's own), which post_pin doesn't capture.
        # Approach: navigate to /pin-builder/ or fall back to user-driven deletion.

        # Cleanest path: go to /[username]/_created/ via the home dropdown profile link
        page.goto("https://www.pinterest.com/", wait_until="domcontentloaded", timeout=30000)
        time.sleep(2)
        # Click profile button (top-right avatar)
        try:
            profile_btn = page.locator('[data-test-id="header-profile"]').first
            profile_btn.click(timeout=10000)
            time.sleep(2)
        except Exception:
            pass
        time.sleep(2)

        # We're now on /username/. Add /_created to URL.
        cur_url = page.url.rstrip("/")
        if not cur_url.endswith("_created"):
            page.goto(cur_url + "/_created/", wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)

        deleted = 0
        for t in targets:
            title_search = (t.get("title") or "")[:50]
            print(f"\n  Searching for pin: {title_search}…")
            try:
                # Find pin tile that contains the title text
                pin_tile = page.locator(f'[data-test-id="pinrep"]:has-text({json.dumps(title_search[:30])})').first
                if pin_tile.count() == 0:
                    print(f"    ✗ pin not found on profile (might be deleted already or different title rendering)")
                    continue
                # Click into pin
                pin_tile.click(timeout=10000)
                time.sleep(3)
                # Click the kebab menu (3-dot) on pin detail
                kebab = page.locator('[data-test-id="pin-menu"], button[aria-label="More options"]').first
                kebab.click(timeout=10000)
                time.sleep(1)
                # Click "Edit pin" or directly look for Delete in the menu
                edit_btn = page.locator('text="Edit Pin"').first
                if edit_btn.count() > 0:
                    edit_btn.click(timeout=5000)
                    time.sleep(2)
                # Click Delete
                page.locator('button:has-text("Delete"), [aria-label="Delete"]').first.click(timeout=10000)
                time.sleep(1)
                # Confirm
                page.locator('button:has-text("Delete"):not([disabled])').first.click(timeout=5000)
                time.sleep(2)
                print(f"    ✓ deleted {t['id']}")
                deleted += 1
                # Update schedule
                t["status"] = "deleted"
                # Back to created pins
                page.go_back()
                time.sleep(2)
            except Exception as e:
                print(f"    ✗ {t['id']}: {e}")

        PINTEREST_SCHEDULE.write_text(json.dumps(sched, indent=2))
        print(f"\nDeleted {deleted}/{len(targets)} pins")
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
