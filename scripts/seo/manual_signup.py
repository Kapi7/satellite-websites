"""
Manual HARO Platform Signup — Visible Browser
Fills forms automatically, user reviews and submits manually.

Usage:
    python3 scripts/seo/manual_signup.py --site glow-coded
    python3 scripts/seo/manual_signup.py --site rooted-glow
"""

import argparse
import random
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, Page

# ── Account data ─────────────────────────────────────────────────────────────

ACCOUNTS = {
    "glow-coded": {
        "email": "info@albert-capital.com",
        "password": "Kapi1988!@",
        "display_name": "Glow Coded",
        "first_name": "Glow",
        "last_name": "Coded",
        "website": "https://glow-coded.com",
        "bio": "K-beauty ingredient research & skincare science",
    },
    "rooted-glow": {
        "email": "avi@albert-capital.com",
        "password": "Kapi1988!@",
        "display_name": "Rooted Glow",
        "first_name": "Rooted",
        "last_name": "Glow",
        "website": "https://rooted-glow.com",
        "bio": "Where nutrition meets skin health",
    },
}

BROWSER_STATE_DIR = Path(__file__).resolve().parent / "browser-state"

BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-first-run",
    "--no-default-browser-check",
]

# ── Helpers ──────────────────────────────────────────────────────────────────

def human_delay(lo=0.5, hi=1.5):
    time.sleep(random.uniform(lo, hi))


def try_fill(page: Page, selectors: list[str], value: str, typing=True):
    """Try multiple selectors to fill a field. Returns True on first success."""
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible(timeout=1500):
                loc.click()
                loc.fill("")
                human_delay(0.1, 0.3)
                if typing:
                    loc.type(value, delay=random.randint(50, 100))
                else:
                    loc.fill(value)
                human_delay(0.3, 0.6)
                return True
        except Exception:
            continue
    return False


def try_fill_textarea(page: Page, selectors: list[str], value: str):
    """Try to fill textarea fields."""
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible(timeout=1500):
                loc.click()
                loc.fill("")
                human_delay(0.1, 0.3)
                loc.type(value, delay=random.randint(30, 70))
                human_delay(0.3, 0.6)
                return True
        except Exception:
            continue
    return False


def try_click(page: Page, selectors: list[str], timeout=2000):
    """Try to click the first visible element from a list of selectors."""
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible(timeout=timeout):
                loc.click()
                human_delay(0.3, 0.8)
                return True
        except Exception:
            continue
    return False


def fill_email(page: Page, email: str):
    return try_fill(page, [
        "input[type='email']",
        "input[name='email']",
        "input[name*='email' i]",
        "input[id*='email' i]",
        "input[placeholder*='email' i]",
        "input[autocomplete='email']",
        "input[data-testid*='email' i]",
    ], email)


def fill_password(page: Page, password: str):
    return try_fill(page, [
        "input[type='password']",
        "input[name='password']",
        "input[name*='password' i]",
        "input[id*='password' i]",
        "input[placeholder*='password' i]",
    ], password)


def fill_confirm_password(page: Page, password: str):
    """Fill password confirmation field if present."""
    return try_fill(page, [
        "input[name*='confirm' i][type='password']",
        "input[name*='password_confirm' i]",
        "input[name*='password2' i]",
        "input[name*='passwordConfirm' i]",
        "input[id*='confirm' i][type='password']",
        "input[placeholder*='confirm' i]",
        "input[placeholder*='re-enter' i]",
        "input[placeholder*='retype' i]",
    ], password)


def fill_name(page: Page, name: str):
    return try_fill(page, [
        "input[name='name']",
        "input[name*='name' i]:not([name*='first' i]):not([name*='last' i]):not([name*='user' i])",
        "input[id*='name' i]:not([id*='first' i]):not([id*='last' i]):not([id*='user' i])",
        "input[placeholder*='full name' i]",
        "input[placeholder*='your name' i]",
        "input[placeholder*='display name' i]",
        "input[autocomplete='name']",
    ], name)


def fill_first_name(page: Page, first: str):
    return try_fill(page, [
        "input[name*='first' i]",
        "input[id*='first' i]",
        "input[placeholder*='first' i]",
        "input[autocomplete='given-name']",
    ], first)


def fill_last_name(page: Page, last: str):
    return try_fill(page, [
        "input[name*='last' i]",
        "input[id*='last' i]",
        "input[placeholder*='last' i]",
        "input[autocomplete='family-name']",
    ], last)


def fill_website(page: Page, url: str):
    return try_fill(page, [
        "input[name*='website' i]",
        "input[name*='url' i]",
        "input[name*='site' i]",
        "input[name*='blog' i]",
        "input[id*='website' i]",
        "input[id*='url' i]",
        "input[placeholder*='website' i]",
        "input[placeholder*='url' i]",
        "input[placeholder*='http' i]",
        "input[type='url']",
    ], url)


def fill_bio(page: Page, bio: str):
    found = try_fill_textarea(page, [
        "textarea[name*='bio' i]",
        "textarea[name*='about' i]",
        "textarea[name*='description' i]",
        "textarea[id*='bio' i]",
        "textarea[id*='about' i]",
        "textarea[placeholder*='bio' i]",
        "textarea[placeholder*='about' i]",
        "textarea[placeholder*='tell us' i]",
    ], bio)
    if not found:
        found = try_fill(page, [
            "input[name*='bio' i]",
            "input[name*='about' i]",
            "input[name*='tagline' i]",
            "input[name*='headline' i]",
            "input[id*='bio' i]",
            "input[placeholder*='bio' i]",
            "input[placeholder*='headline' i]",
        ], bio)
    return found


def fill_company(page: Page, name: str):
    return try_fill(page, [
        "input[name*='company' i]",
        "input[name*='organization' i]",
        "input[name*='outlet' i]",
        "input[id*='company' i]",
        "input[id*='organization' i]",
        "input[placeholder*='company' i]",
        "input[placeholder*='organization' i]",
    ], name)


def fill_title(page: Page, title: str):
    return try_fill(page, [
        "input[name*='title' i]:not([type='hidden'])",
        "input[name*='jobtitle' i]",
        "input[name*='job_title' i]",
        "input[id*='title' i]:not([type='hidden'])",
        "input[placeholder*='title' i]",
        "input[placeholder*='role' i]",
    ], title)


def wait_ready(page: Page, timeout=15000):
    try:
        page.wait_for_load_state("networkidle", timeout=timeout)
    except Exception:
        try:
            page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass


# ── Platform handlers ────────────────────────────────────────────────────────
# Each returns nothing — just fills fields. User submits manually.

def handle_connectively(page: Page, acct: dict):
    """Connectively (formerly HARO) — https://www.connectively.us"""
    print("  Navigating to Connectively signup...")
    page.goto("https://www.connectively.us/signup", wait_until="domcontentloaded")
    wait_ready(page)
    human_delay(2, 4)

    # Try clicking "Source" role if there's a choice screen
    try_click(page, [
        "button:has-text('Source')",
        "a:has-text('Source')",
        "label:has-text('Source')",
        "div:has-text('Source'):not(:has(div))",
        "[data-testid*='source' i]",
    ])
    human_delay(1, 2)

    # Try "Sign up with email" if present
    try_click(page, [
        "button:has-text('Sign up with email')",
        "button:has-text('email')",
        "a:has-text('Sign up with email')",
        "a:has-text('sign up')",
    ])
    human_delay(1, 2)

    fill_email(page, acct["email"])
    fill_password(page, acct["password"])
    fill_confirm_password(page, acct["password"])
    fill_first_name(page, acct["first_name"])
    fill_last_name(page, acct["last_name"])
    fill_name(page, acct["display_name"])
    fill_website(page, acct["website"])
    fill_bio(page, acct["bio"])
    fill_company(page, acct["display_name"])
    fill_title(page, "Editor")


def handle_qwoted(page: Page, acct: dict):
    """Qwoted — https://www.qwoted.com"""
    print("  Navigating to Qwoted signup...")
    page.goto("https://www.qwoted.com/signup", wait_until="domcontentloaded")
    wait_ready(page)
    human_delay(2, 4)

    # Try clicking "Source" role/tab first
    try_click(page, [
        "button:has-text('Source')",
        "a:has-text('Source')",
        "label:has-text('Source')",
        "a:has-text('I am a source')",
        "button:has-text('I am a source')",
        "[role='tab']:has-text('Source')",
    ])
    human_delay(1, 2)

    # Try "sign up with email" if present
    try_click(page, [
        "button:has-text('Sign up with email')",
        "a:has-text('Sign up with email')",
        "button:has-text('email')",
    ])
    human_delay(1, 2)

    fill_first_name(page, acct["first_name"])
    fill_last_name(page, acct["last_name"])
    fill_name(page, acct["display_name"])
    fill_email(page, acct["email"])
    fill_password(page, acct["password"])
    fill_confirm_password(page, acct["password"])
    fill_website(page, acct["website"])
    fill_bio(page, acct["bio"])
    fill_company(page, acct["display_name"])
    fill_title(page, "Editor")


def handle_featured(page: Page, acct: dict):
    """Featured.com — https://featured.com"""
    print("  Navigating to Featured signup...")
    page.goto("https://featured.com/signup", wait_until="domcontentloaded")
    wait_ready(page)
    human_delay(2, 4)

    # Try clicking "Expert" or "Source" role
    try_click(page, [
        "button:has-text('Expert')",
        "a:has-text('Expert')",
        "button:has-text('Source')",
        "a:has-text('Source')",
        "a:has-text('sign up')",
    ])
    human_delay(1, 2)

    fill_email(page, acct["email"])
    fill_password(page, acct["password"])
    fill_confirm_password(page, acct["password"])
    fill_first_name(page, acct["first_name"])
    fill_last_name(page, acct["last_name"])
    fill_name(page, acct["display_name"])
    fill_website(page, acct["website"])
    fill_bio(page, acct["bio"])
    fill_company(page, acct["display_name"])
    fill_title(page, "Editor")


def handle_terkel(page: Page, acct: dict):
    """Terkel — https://terkel.io"""
    print("  Navigating to Terkel signup...")
    page.goto("https://terkel.io/signup", wait_until="domcontentloaded")
    wait_ready(page)
    human_delay(2, 4)

    # Try role selection
    try_click(page, [
        "button:has-text('Expert')",
        "button:has-text('Source')",
        "a:has-text('Expert')",
        "a:has-text('sign up')",
    ])
    human_delay(1, 2)

    fill_email(page, acct["email"])
    fill_password(page, acct["password"])
    fill_confirm_password(page, acct["password"])
    fill_first_name(page, acct["first_name"])
    fill_last_name(page, acct["last_name"])
    fill_name(page, acct["display_name"])
    fill_website(page, acct["website"])
    fill_bio(page, acct["bio"])
    fill_company(page, acct["display_name"])
    fill_title(page, "Editor")


def handle_sourcebottle(page: Page, acct: dict):
    """SourceBottle — https://www.sourcebottle.com"""
    print("  Navigating to SourceBottle signup...")
    page.goto("https://www.sourcebottle.com/register", wait_until="domcontentloaded")
    wait_ready(page)
    human_delay(2, 4)

    # Try clicking "Source/Expert" role
    try_click(page, [
        "button:has-text('Source')",
        "button:has-text('Expert')",
        "a:has-text('Source')",
        "label:has-text('Source')",
        "label:has-text('Expert')",
        "a:has-text('sign up')",
    ])
    human_delay(1, 2)

    fill_first_name(page, acct["first_name"])
    fill_last_name(page, acct["last_name"])
    fill_name(page, acct["display_name"])
    fill_email(page, acct["email"])
    fill_password(page, acct["password"])
    fill_confirm_password(page, acct["password"])
    fill_website(page, acct["website"])
    fill_bio(page, acct["bio"])
    fill_company(page, acct["display_name"])
    fill_title(page, "Editor")


# ── Platforms list (ordered by priority) ─────────────────────────────────────

PLATFORMS = [
    {
        "name": "Connectively",
        "handler": handle_connectively,
    },
    {
        "name": "Qwoted",
        "handler": handle_qwoted,
    },
    {
        "name": "Featured",
        "handler": handle_featured,
    },
    {
        "name": "Terkel",
        "handler": handle_terkel,
    },
    {
        "name": "SourceBottle",
        "handler": handle_sourcebottle,
    },
]


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Manual HARO platform signup helper")
    parser.add_argument(
        "--site",
        required=True,
        choices=["glow-coded", "rooted-glow"],
        help="Which site account to use",
    )
    parser.add_argument(
        "--platform",
        type=int,
        default=None,
        help="Start from platform N (1-5, default: 1)",
    )
    args = parser.parse_args()

    acct = ACCOUNTS[args.site]
    start_idx = (args.platform - 1) if args.platform else 0

    state_dir = BROWSER_STATE_DIR / f"signup-{args.site}"
    state_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  HARO Platform Signup — {acct['display_name']}")
    print(f"  Email: {acct['email']}")
    print(f"  Website: {acct['website']}")
    print(f"  Browser state: {state_dir}")
    print(f"{'='*60}\n")
    print(f"  Platforms to sign up for ({len(PLATFORMS) - start_idx} remaining):")
    for i, p in enumerate(PLATFORMS[start_idx:], start=start_idx + 1):
        print(f"    {i}. {p['name']}")
    print()

    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            user_data_dir=str(state_dir),
            headless=False,
            args=BROWSER_ARGS,
            viewport={"width": 1280, "height": 900},
            locale="en-US",
            timezone_id="America/New_York",
            slow_mo=50,
        )
        page = context.pages[0] if context.pages else context.new_page()

        for i, platform in enumerate(PLATFORMS[start_idx:], start=start_idx + 1):
            print(f"\n{'─'*60}")
            print(f"  [{i}/{len(PLATFORMS)}] {platform['name']}")
            print(f"{'─'*60}")

            try:
                platform["handler"](page, acct)

                print(f"\n  >>> Form filled for {platform['name']}.")
                print(f"  >>> Please review the browser, solve any CAPTCHA, and click Submit.")
                print(f"  >>> Then press Enter here to continue to the next platform...")
                input()

                # Small pause after user confirms
                human_delay(1, 2)

            except Exception as e:
                print(f"\n  !!! Error on {platform['name']}: {e}")
                print(f"  >>> Please complete this signup manually in the browser.")
                print(f"  >>> Press Enter when done to continue...")
                input()

        print(f"\n{'='*60}")
        print(f"  All {len(PLATFORMS)} platforms processed for {acct['display_name']}!")
        print(f"  Press Enter to close the browser...")
        input()

        context.close()

    print("\n  Done. Browser closed.\n")


if __name__ == "__main__":
    main()
