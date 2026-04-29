#!/usr/bin/env python3
"""
Pinterest pin poster using Playwright browser automation.
Posts pins from article hero images to category-mapped boards.
Supports separate Pinterest accounts per satellite site.

Usage:
    python3 pinterest_poster.py --check          # Show pending pins
    python3 pinterest_poster.py --run-due         # Post all due pins (up to daily limit)
    python3 pinterest_poster.py --post 5          # Post specific pin by ID
    python3 pinterest_poster.py --dry-run         # Simulate posting
    python3 pinterest_poster.py --headed          # Run with visible browser (for first login/2FA)
    python3 pinterest_poster.py --site cosmetics  # Only process one site
"""

import argparse
import json
import random
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (
    PINTEREST_ACCOUNTS, PINTEREST_ACCOUNT_MAP, PINTEREST_DAILY_LIMITS,
    PINTEREST_SCHEDULE, PINTEREST_MAX_PER_DAY,
    SITES,
    BROWSER_STATE_DIR, DATA_DIR,
    BROWSER_ARGS, DELAY_SHORT, DELAY_MEDIUM, DELAY_LONG, DELAY_PAGE_LOAD,
)
from tg import notify as tg_notify


def human_delay(delay_range):
    time.sleep(random.uniform(*delay_range))


def load_schedule():
    with open(PINTEREST_SCHEDULE) as f:
        return json.load(f)


def save_schedule(schedule):
    with open(PINTEREST_SCHEDULE, "w") as f:
        json.dump(schedule, f, indent=2)


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    DATA_DIR.mkdir(exist_ok=True)
    with open(DATA_DIR / "pinterest.log", "a") as f:
        f.write(line + "\n")


def get_due_pins(schedule):
    today = datetime.now().date().isoformat()
    # Dedup guard: skip pending pins whose (site, title, image basename) already appears as posted
    import os
    posted_keys = {
        (x.get("site",""), x.get("title",""), os.path.basename(x.get("image_path","")))
        for x in schedule if x.get("status") == "posted"
    }
    out = []
    for p in schedule:
        if p.get("status") != "pending": continue
        if p.get("scheduled_date","") > today: continue
        key = (p.get("site",""), p.get("title",""), os.path.basename(p.get("image_path","")))
        if key in posted_keys:
            # silent skip — schedule cleanup happens in caller
            continue
        out.append(p)
    return out


def get_due_pins_capped(schedule):
    """Return due pins capped by per-site daily limit (5/5/5 by default)."""
    due = get_due_pins(schedule)
    capped = []
    seen = {site: 0 for site in SITES}
    for pin in due:
        site = pin.get("site", "")
        limit = PINTEREST_DAILY_LIMITS.get(site, PINTEREST_MAX_PER_DAY)
        if seen.get(site, 0) >= limit:
            continue
        capped.append(pin)
        seen[site] = seen.get(site, 0) + 1
    return capped


def show_status(schedule):
    pending = [p for p in schedule if p["status"] == "pending"]
    posted = [p for p in schedule if p["status"] == "posted"]
    failed = [p for p in schedule if p["status"] == "failed"]
    due = get_due_pins(schedule)
    capped = get_due_pins_capped(schedule)

    print(f"\nPinterest Schedule Status")
    print(f"{'='*50}")
    print(f"Total: {len(schedule)} | Posted: {len(posted)} | Pending: {len(pending)} | Failed: {len(failed)}")
    print(f"Due today: {len(due)} | After daily caps: {len(capped)}")

    # By site
    for site in SITES:
        site_pins = [p for p in schedule if p["site"] == site]
        site_posted = sum(1 for p in site_pins if p["status"] == "posted")
        site_due = sum(1 for p in due if p["site"] == site)
        site_capped = sum(1 for p in capped if p["site"] == site)
        limit = PINTEREST_DAILY_LIMITS.get(site, PINTEREST_MAX_PER_DAY)
        print(f"  {site}: {site_posted}/{len(site_pins)} posted, {site_due} due, {site_capped}/{limit} runnable")

    if due:
        print(f"\nDue pins:")
        for p in due[:10]:
            print(f"  #{p['id']} [{p['site']}] {p['board']} | {p['title'][:40]}...")

    if pending:
        next_p = min(pending, key=lambda x: x["scheduled_date"])
        print(f"\nNext scheduled: {next_p['scheduled_date']} — {next_p['title'][:50]}")


def dismiss_cookie_banner(page):
    try:
        accept_btn = page.locator('button:has-text("Accept all")').first
        if accept_btn.is_visible(timeout=3000):
            accept_btn.click()
            human_delay(DELAY_SHORT)
            log("Cookie banner dismissed")
    except Exception:
        pass


def is_logged_in(page):
    try:
        page.wait_for_selector(
            '[data-test-id="header-avatar"], '
            '[data-test-id="storyboard-create-header-heading"]',
            timeout=5000,
        )
        return True
    except Exception:
        url = page.url
        if "/business/hub" in url or "/pin-creation-tool" in url:
            return True
        return False


def login_pinterest(page, email, password, site_key):
    """Log into Pinterest for a specific site account."""
    log(f"Logging in for {site_key} ({email})...")

    page.goto("https://www.pinterest.com/")
    human_delay(DELAY_PAGE_LOAD)
    dismiss_cookie_banner(page)

    if is_logged_in(page):
        log("Already logged in (session restored)")
        return True

    log("Not logged in, proceeding...")

    try:
        page.locator('button:has-text("Log in"), a:has-text("Log in")').first.click()
        human_delay(DELAY_MEDIUM)
    except Exception:
        page.goto("https://www.pinterest.com/login/")
        human_delay(DELAY_PAGE_LOAD)
        dismiss_cookie_banner(page)

    try:
        email_input = page.locator('#email').first
        email_input.wait_for(state="visible", timeout=10000)
        email_input.click()
        human_delay(DELAY_SHORT)
        email_input.fill(email)
        human_delay(DELAY_SHORT)

        pass_input = page.locator('#password').first
        pass_input.click()
        human_delay(DELAY_SHORT)
        pass_input.fill(password)
        human_delay(DELAY_SHORT)

        page.locator('button[type="submit"]').first.click()
        log("Credentials submitted...")

        # Handle 2FA
        try:
            code_input = page.locator('input[name="code"]').first
            code_input.wait_for(state="visible", timeout=10000)
            log("2FA required — enter code in browser window...")
            page.wait_for_url("**/business/hub**", timeout=180000)
        except Exception:
            human_delay(DELAY_LONG)

        # Verify
        page.goto("https://www.pinterest.com/")
        human_delay(DELAY_PAGE_LOAD)
        if is_logged_in(page):
            log("Login successful")
            return True

        log("Login verification failed")
        return False

    except Exception as e:
        log(f"Login error: {e}")
        return False


def post_pin(page, pin, dry_run=False):
    """Create a single pin on Pinterest."""
    log(f"Posting pin #{pin['id']}: {pin['title'][:50]}...")

    if dry_run:
        log(f"  [DRY RUN] Board '{pin['board']}' | {Path(pin['image_path']).name}")
        return True

    try:
        page.goto("https://www.pinterest.com/pin-creation-tool/")
        time.sleep(5)
        page.wait_for_selector('[data-test-id="storyboard-upload-input"]', timeout=15000)

        # ── 1. Upload image ──
        image_path = pin["image_path"]
        if not Path(image_path).exists():
            log(f"  Image not found: {image_path}")
            return False

        file_input = page.locator('#storyboard-upload-input')
        file_input.set_input_files(image_path)
        log("  Image uploaded")

        # Wait for image to fully process — board dropdown becomes enabled
        log("  Waiting for image processing...")
        try:
            page.wait_for_function(
                """() => {
                    const btn = document.querySelector('[data-test-id="board-dropdown-select-button"]');
                    return btn && btn.getAttribute('aria-disabled') !== 'true';
                }""",
                timeout=30000,
            )
        except Exception:
            time.sleep(8)  # Fallback wait
        human_delay(DELAY_MEDIUM)

        # ── 2. Fill title ──
        title_input = page.locator('#storyboard-selector-title')
        title_input.fill(pin["title"][:100])
        human_delay(DELAY_SHORT)
        log("  Title filled")

        # ── 3. Fill description ──
        desc_text = pin["description"]
        if pin.get("tags"):
            hashtags = " ".join(f"#{t.replace(' ', '')}" for t in pin["tags"][:5])
            desc_text = f"{desc_text}\n\n{hashtags}"

        try:
            desc_editor = page.locator('[aria-label="Add a detailed description"]').first
            desc_editor.click()
            human_delay(DELAY_SHORT)
            desc_editor.fill(desc_text[:500])
            human_delay(DELAY_SHORT)
            log("  Description filled")
        except Exception:
            try:
                desc_container = page.locator('[data-test-id="storyboard-description-field-container"]')
                desc_container.click()
                human_delay(DELAY_SHORT)
                page.keyboard.type(desc_text[:500], delay=5)
                log("  Description filled (keyboard)")
            except Exception as e:
                log(f"  Description skipped: {e}")

        # ── 4. Fill link ──
        url_input = page.locator('#WebsiteField')
        url_input.fill(pin["url"])
        human_delay(DELAY_SHORT)
        log("  Link filled")

        # ── 5. Select board ──
        try:
            board_btn = page.locator('[data-test-id="board-dropdown-select-button"]').first
            board_btn.click(force=True)
            human_delay(DELAY_MEDIUM)
            time.sleep(2)

            # Type to search for board
            search_input = page.locator('[data-test-id="board-dropdown"] input, input[placeholder="Search"]')
            if search_input.count() > 0:
                search_input.first.fill(pin["board"])
                human_delay(DELAY_MEDIUM)

            # Try to find existing board
            board_found = False
            try:
                board_row = page.locator(f'[data-test-id="board-row"]:has-text("{pin["board"]}")').first
                board_row.wait_for(state="visible", timeout=3000)
                board_row.click(force=True)
                board_found = True
                log(f"  Board selected: {pin['board']}")
            except Exception:
                pass

            if not board_found:
                # Board does NOT exist on Pinterest. Refuse to publish to wrong board.
                log(f"  ABORT: board '{pin['board']}' not found on Pinterest. Create it manually first.")
                page.keyboard.press("Escape")
                human_delay(DELAY_SHORT)
                page.screenshot(path=str(DATA_DIR / f"pin-noboard-{pin['id']}.png"))
                return False

            human_delay(DELAY_SHORT)
        except Exception as e:
            log(f"  Board error: {e}")

        # ── 6. Publish ──
        try:
            publish_btn = page.locator(
                'button:has-text("Publish"), '
                '[data-test-id="storyboard-creation-nav-done-button"]'
            ).first
            publish_btn.wait_for(state="visible", timeout=10000)
            publish_btn.click(force=True)
            human_delay(DELAY_LONG)
            time.sleep(5)

            log(f"  Pin #{pin['id']} published")
            page.screenshot(path=str(DATA_DIR / f"pin-ok-{pin['id']}.png"))
            return True
        except Exception as e:
            log(f"  Publish button not found: {e}")
            page.screenshot(path=str(DATA_DIR / f"pin-fail-{pin['id']}.png"))
            return False

    except Exception as e:
        log(f"  Pin #{pin['id']} failed: {e}")
        try:
            page.screenshot(path=str(DATA_DIR / f"pin-fail-{pin['id']}.png"))
        except Exception:
            pass
        return False


def run_poster(args):
    from playwright.sync_api import sync_playwright

    schedule = load_schedule()

    if args.check:
        show_status(schedule)
        return

    # Determine which pins to post
    if args.post:
        pins_to_post = [p for p in schedule if p["id"] == args.post]
        if not pins_to_post:
            print(f"Pin #{args.post} not found")
            sys.exit(1)
    elif args.run_due:
        pins_to_post = get_due_pins_capped(schedule)
        if not pins_to_post:
            log("No pins due today")
            return
    else:
        print("Specify --check, --run-due, or --post N")
        sys.exit(1)

    # Filter by site if specified
    if args.site:
        pins_to_post = [p for p in pins_to_post if p["site"] == args.site]

    # Group pins by ACCOUNT. Sites with account_key=None (e.g. build-coded
    # before its dedicated account exists) are skipped entirely so we never
    # accidentally post DIY pins through the rooted-glow account.
    accounts = {}
    skipped_no_account = []
    for pin in pins_to_post:
        account_key = PINTEREST_ACCOUNT_MAP.get(pin["site"], pin["site"])
        if account_key is None:
            skipped_no_account.append(pin)
            continue
        accounts.setdefault(account_key, []).append(pin)
    if skipped_no_account:
        skipped_sites = sorted({p["site"] for p in skipped_no_account})
        log(f"Skipping {len(skipped_no_account)} pin(s) from {skipped_sites} — no Pinterest account configured (PINTEREST_ACCOUNT_MAP is None)")

    log(f"Posting {len(pins_to_post)} pin(s) across {len(accounts)} account(s)...")

    with sync_playwright() as pw:
        BROWSER_STATE_DIR.mkdir(exist_ok=True)

        for account_key, account_pins in accounts.items():
            account = PINTEREST_ACCOUNTS.get(account_key, {})
            email = account.get("email", "")
            password = account.get("password", "")

            if not email or not password:
                log(f"No Pinterest credentials for account '{account_key}', skipping {len(account_pins)} pin(s)")
                tg_notify(
                    f"Pinterest: no credentials for '{account_key}' — skipped {len(account_pins)} pin(s)",
                    level="warn",
                )
                continue

            sites_in_batch = sorted({p["site"] for p in account_pins})
            log(f"\n--- Processing account '{account_key}' ({len(account_pins)} pins for {', '.join(sites_in_batch)}) ---")

            state_path = BROWSER_STATE_DIR / f"pinterest-{account_key}"
            state_file = state_path / "state.json"

            browser = pw.chromium.launch(
                headless=not args.headed,
                args=BROWSER_ARGS,
            )

            context = browser.new_context(
                storage_state=str(state_file) if state_file.exists() else None,
                viewport={"width": 1280, "height": 900},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            )

            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            """)

            page = context.new_page()

            if not login_pinterest(page, email, password, account_key):
                log(f"Login failed for account '{account_key}', skipping")
                tg_notify(
                    f"Pinterest login failed for '{account_key}' — {len(account_pins)} pin(s) skipped",
                    level="err",
                )
                browser.close()
                continue

            state_path.mkdir(parents=True, exist_ok=True)
            context.storage_state(path=str(state_file))

            posted_count = 0
            for pin in account_pins:
                success = post_pin(page, pin, dry_run=args.dry_run)

                for entry in schedule:
                    if entry["id"] == pin["id"]:
                        if args.dry_run:
                            break
                        entry["status"] = "posted" if success else "failed"
                        entry["posted_at"] = datetime.now().isoformat()
                        break

                if not args.dry_run:
                    short_title = pin.get("title", "")[:70]
                    if success:
                        tg_notify(
                            f"Pin #{pin['id']} [{pin['site']}] posted to '{pin['board']}'\n"
                            f"{short_title}\n{pin['url']}",
                            level="ok",
                        )
                    else:
                        tg_notify(
                            f"Pin #{pin['id']} [{pin['site']}] FAILED on '{pin['board']}'\n"
                            f"{short_title}",
                            level="err",
                        )

                if success:
                    posted_count += 1

                if not args.dry_run:
                    save_schedule(schedule)

                if pin != account_pins[-1]:
                    delay = random.uniform(30, 90)
                    log(f"Waiting {delay:.0f}s before next pin...")
                    time.sleep(delay)

            context.storage_state(path=str(state_file))
            browser.close()

            log(f"account '{account_key}': Posted {posted_count}/{len(account_pins)}")
            if not args.dry_run and account_pins:
                tg_notify(
                    f"Pinterest '{account_key}': {posted_count}/{len(account_pins)} pins posted",
                    level="report",
                    title="Pinterest poster",
                )


def main():
    parser = argparse.ArgumentParser(description="Pinterest pin poster")
    parser.add_argument("--check", action="store_true", help="Show schedule status")
    parser.add_argument("--run-due", action="store_true", help="Post all due pins")
    parser.add_argument("--post", type=int, help="Post specific pin by ID")
    parser.add_argument("--dry-run", action="store_true", help="Simulate posting")
    parser.add_argument("--headed", action="store_true", help="Show browser window")
    parser.add_argument("--site", choices=list(SITES.keys()), help="Only process one site")
    args = parser.parse_args()

    if not any([args.check, args.run_due, args.post]):
        parser.print_help()
        sys.exit(1)

    run_poster(args)


if __name__ == "__main__":
    main()
