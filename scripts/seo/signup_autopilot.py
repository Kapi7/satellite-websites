"""
SEO Backlink Automation — Signup Autopilot
Automates account creation on 12 platforms for glow-coded.com and rooted-glow.com.

Usage:
    python3 scripts/seo/signup_autopilot.py --site glow-coded --platform connectively
    python3 scripts/seo/signup_autopilot.py --site rooted-glow
    python3 scripts/seo/signup_autopilot.py --all
"""

import asyncio
import json
import sys
import argparse
import random
import time
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright, Page, BrowserContext

# ── Config imports ────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (
    ACCOUNTS,
    SITES,
    SIGNUP_PLATFORMS,
    BROWSER_STATE_DIR,
    BROWSER_ARGS,
    DELAY_SHORT,
    DELAY_MEDIUM,
    DELAY_LONG,
    DELAY_PAGE_LOAD,
    SIGNUP_STATUS,
)


# ── Utility helpers ───────────────────────────────────────────────────────────

async def human_delay(bounds: tuple[float, float] = DELAY_SHORT):
    """Sleep a random duration within the given bounds."""
    await asyncio.sleep(random.uniform(*bounds))


async def human_type(page: Page, selector: str, text: str, *, clear: bool = True):
    """Type into a field with human-like delays between keystrokes."""
    el = page.locator(selector).first
    if clear:
        await el.click()
        await el.fill("")
        await human_delay((0.1, 0.3))
    await el.type(text, delay=random.randint(30, 90))
    await human_delay(DELAY_SHORT)


async def safe_click(page: Page, selector: str, timeout: int = 5000):
    """Click a button/element if it exists within the timeout."""
    try:
        el = page.locator(selector).first
        await el.wait_for(state="visible", timeout=timeout)
        await el.click()
        await human_delay(DELAY_SHORT)
        return True
    except Exception:
        return False


async def wait_for_navigation(page: Page, timeout: float = 10000):
    """Wait for navigation or network idle."""
    try:
        await page.wait_for_load_state("networkidle", timeout=timeout)
    except Exception:
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass


# ── Status tracking ───────────────────────────────────────────────────────────

def load_status() -> dict:
    """Load signup_status.json or return empty dict."""
    if SIGNUP_STATUS.exists():
        return json.loads(SIGNUP_STATUS.read_text())
    return {}


def save_status(status: dict):
    """Persist status to signup_status.json."""
    SIGNUP_STATUS.write_text(json.dumps(status, indent=2))


def update_status(status: dict, platform: str, site_key: str, result: str):
    """Update a single platform+site entry in the status dict and save."""
    if platform not in status:
        status[platform] = {}
    status[platform][site_key] = {
        "site": site_key,
        "status": result,
        "timestamp": datetime.now().isoformat(),
    }
    save_status(status)


def is_completed(status: dict, platform: str, site_key: str) -> bool:
    """Check if a signup is already completed."""
    return (
        status.get(platform, {}).get(site_key, {}).get("status") == "completed"
    )


# ── CAPTCHA detection ─────────────────────────────────────────────────────────

async def detect_captcha(page: Page) -> bool:
    """Check if the page contains a visible CAPTCHA widget."""
    captcha_selectors = [
        "iframe[src*='recaptcha']",
        "iframe[src*='hcaptcha']",
        "iframe[title*='reCAPTCHA']",
        "iframe[title*='hCaptcha']",
        "[class*='captcha']",
        "[id*='captcha']",
        "[class*='g-recaptcha']",
        "[class*='h-captcha']",
        "#g-recaptcha",
        ".g-recaptcha",
        ".h-captcha",
        "[data-sitekey]",
    ]
    for sel in captcha_selectors:
        try:
            count = await page.locator(sel).count()
            if count > 0:
                return True
        except Exception:
            pass
    return False


async def handle_captcha(page: Page):
    """If a CAPTCHA is detected, pause and wait for the user to solve it."""
    if await detect_captcha(page):
        print("\n\u23f8  CAPTCHA detected \u2014 please solve it manually in the browser.")
        print("   Press Enter here once you\u2019ve completed it...")
        await asyncio.get_event_loop().run_in_executor(None, input)
        await human_delay(DELAY_MEDIUM)
        print("   Resuming.\n")
        return True
    return False


# ── Generic form helpers ──────────────────────────────────────────────────────

async def fill_email(page: Page, email: str):
    """Find and fill an email field."""
    selectors = [
        "input[type='email']",
        "input[name*='email' i]",
        "input[id*='email' i]",
        "input[placeholder*='email' i]",
        "input[autocomplete='email']",
    ]
    for sel in selectors:
        try:
            count = await page.locator(sel).count()
            if count > 0:
                await human_type(page, sel, email)
                return True
        except Exception:
            pass
    return False


async def fill_password(page: Page, password: str):
    """Find and fill a password field."""
    selectors = [
        "input[type='password']",
        "input[name*='password' i]",
        "input[id*='password' i]",
        "input[placeholder*='password' i]",
    ]
    for sel in selectors:
        try:
            count = await page.locator(sel).count()
            if count > 0:
                await human_type(page, sel, password)
                return True
        except Exception:
            pass
    return False


async def fill_name(page: Page, name: str, *, field_hint: str = "name"):
    """Find and fill a name field.  field_hint can be 'name', 'first', 'last', 'username'."""
    selectors = [
        f"input[name*='{field_hint}' i]",
        f"input[id*='{field_hint}' i]",
        f"input[placeholder*='{field_hint}' i]",
        f"input[autocomplete*='{field_hint}' i]",
    ]
    for sel in selectors:
        try:
            count = await page.locator(sel).count()
            if count > 0:
                await human_type(page, sel, name)
                return True
        except Exception:
            pass
    return False


async def fill_field(page: Page, value: str, hints: list[str]):
    """Try to fill a form field matching any of the hint strings."""
    for hint in hints:
        selectors = [
            f"input[name*='{hint}' i]",
            f"input[id*='{hint}' i]",
            f"input[placeholder*='{hint}' i]",
            f"textarea[name*='{hint}' i]",
            f"textarea[id*='{hint}' i]",
        ]
        for sel in selectors:
            try:
                count = await page.locator(sel).count()
                if count > 0:
                    await human_type(page, sel, value)
                    return True
            except Exception:
                pass
    return False


async def click_submit(page: Page):
    """Click the most likely submit button."""
    selectors = [
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Sign up')",
        "button:has-text('Sign Up')",
        "button:has-text('Create')",
        "button:has-text('Register')",
        "button:has-text('Join')",
        "button:has-text('Get started')",
        "button:has-text('Submit')",
        "button:has-text('Continue')",
        "a:has-text('Sign up')",
        "a:has-text('Create account')",
    ]
    for sel in selectors:
        if await safe_click(page, sel, timeout=3000):
            return True
    return False


async def check_success(page: Page) -> bool:
    """Heuristic check for successful signup."""
    success_indicators = [
        "welcome",
        "dashboard",
        "verify your email",
        "check your email",
        "confirmation",
        "account created",
        "successfully",
        "thank you",
        "get started",
        "complete your profile",
        "onboarding",
    ]
    try:
        body_text = (await page.inner_text("body")).lower()
        for indicator in success_indicators:
            if indicator in body_text:
                return True
    except Exception:
        pass
    # URL-based heuristics
    url = page.url.lower()
    if any(kw in url for kw in ["dashboard", "welcome", "onboarding", "verify", "confirm", "home"]):
        return True
    return False


# ── Platform-specific handlers ────────────────────────────────────────────────
# Each handler receives (page, site_key, account_info, site_info) and returns
# a result string: "completed", "needs_verification", or "failed".

async def signup_connectively(page: Page, site_key: str, acct: dict, site: dict) -> str:
    """Connectively (ex-HARO) signup: email + password + name + role."""
    await page.goto("https://www.connectively.us/signup", wait_until="domcontentloaded")
    await human_delay(DELAY_PAGE_LOAD)
    await handle_captcha(page)

    await fill_email(page, acct["email"])
    await fill_password(page, acct["password"])
    await fill_name(page, acct["display_name"])

    # Try to select "Source/Expert" role
    role_selectors = [
        "select[name*='role' i]",
        "select[id*='role' i]",
        "select[name*='type' i]",
    ]
    for sel in role_selectors:
        try:
            count = await page.locator(sel).count()
            if count > 0:
                await page.locator(sel).first.select_option(label="Source/Expert")
                await human_delay(DELAY_SHORT)
                break
        except Exception:
            pass

    # Also try radio/button for role
    try:
        await safe_click(page, "label:has-text('Source')", timeout=2000)
    except Exception:
        pass
    try:
        await safe_click(page, "button:has-text('Source')", timeout=2000)
    except Exception:
        pass

    await handle_captcha(page)
    await click_submit(page)
    await wait_for_navigation(page)
    await human_delay(DELAY_MEDIUM)

    if await check_success(page):
        return "completed"
    if await detect_captcha(page):
        await handle_captcha(page)
        await click_submit(page)
        await wait_for_navigation(page)
        if await check_success(page):
            return "completed"
    return "needs_verification"


async def signup_qwoted(page: Page, site_key: str, acct: dict, site: dict) -> str:
    """Qwoted signup: email + password + first/last name."""
    await page.goto("https://www.qwoted.com/signup", wait_until="domcontentloaded")
    await human_delay(DELAY_PAGE_LOAD)
    await handle_captcha(page)

    # Split display name for first/last
    parts = acct["display_name"].split(" ", 1)
    first = parts[0]
    last = parts[1] if len(parts) > 1 else ""

    await fill_name(page, first, field_hint="first")
    await fill_name(page, last, field_hint="last")
    await fill_email(page, acct["email"])
    await fill_password(page, acct["password"])

    # Qwoted may ask for role — try to pick "Source"
    try:
        await safe_click(page, "label:has-text('Source')", timeout=2000)
    except Exception:
        pass

    await handle_captcha(page)
    await click_submit(page)
    await wait_for_navigation(page)
    await human_delay(DELAY_MEDIUM)

    return "completed" if await check_success(page) else "needs_verification"


async def signup_featured(page: Page, site_key: str, acct: dict, site: dict) -> str:
    """Featured.com signup: email + password + name."""
    await page.goto("https://featured.com/signup", wait_until="domcontentloaded")
    await human_delay(DELAY_PAGE_LOAD)
    await handle_captcha(page)

    await fill_email(page, acct["email"])
    await fill_password(page, acct["password"])
    await fill_name(page, acct["display_name"])

    await handle_captcha(page)
    await click_submit(page)
    await wait_for_navigation(page)
    await human_delay(DELAY_MEDIUM)

    return "completed" if await check_success(page) else "needs_verification"


async def signup_terkel(page: Page, site_key: str, acct: dict, site: dict) -> str:
    """Terkel signup: email + password + name + website."""
    await page.goto("https://terkel.io/signup", wait_until="domcontentloaded")
    await human_delay(DELAY_PAGE_LOAD)
    await handle_captcha(page)

    await fill_email(page, acct["email"])
    await fill_password(page, acct["password"])
    await fill_name(page, acct["display_name"])
    await fill_field(page, f"https://{site['domain']}", ["website", "url", "site", "blog"])

    await handle_captcha(page)
    await click_submit(page)
    await wait_for_navigation(page)
    await human_delay(DELAY_MEDIUM)

    return "completed" if await check_success(page) else "needs_verification"


async def signup_sourcebottle(page: Page, site_key: str, acct: dict, site: dict) -> str:
    """SourceBottle signup: email + password + name + website URL."""
    await page.goto("https://www.sourcebottle.com/register", wait_until="domcontentloaded")
    await human_delay(DELAY_PAGE_LOAD)
    await handle_captcha(page)

    await fill_email(page, acct["email"])
    await fill_password(page, acct["password"])
    await fill_name(page, acct["display_name"])
    await fill_field(page, f"https://{site['domain']}", ["website", "url", "site"])

    # Try to pick role "Blogger / Writer"
    try:
        await safe_click(page, "label:has-text('Blogger')", timeout=2000)
    except Exception:
        pass

    await handle_captcha(page)
    await click_submit(page)
    await wait_for_navigation(page)
    await human_delay(DELAY_MEDIUM)

    return "completed" if await check_success(page) else "needs_verification"


async def signup_medium(page: Page, site_key: str, acct: dict, site: dict) -> str:
    """Medium signup: email-based (may need email link verification)."""
    await page.goto("https://medium.com/m/signin", wait_until="domcontentloaded")
    await human_delay(DELAY_PAGE_LOAD)

    # Medium uses a modal — look for "Sign up with email"
    try:
        await safe_click(page, "a:has-text('Sign up')", timeout=5000)
        await human_delay(DELAY_MEDIUM)
    except Exception:
        pass

    # Try the email option
    try:
        await safe_click(page, "button:has-text('Sign up with email')", timeout=3000)
        await human_delay(DELAY_MEDIUM)
    except Exception:
        pass

    await fill_email(page, acct["email"])
    await handle_captcha(page)
    await click_submit(page)
    await wait_for_navigation(page)
    await human_delay(DELAY_MEDIUM)

    print(f"   Medium uses email link verification. Check {acct['email']} inbox.")
    return "needs_verification"


async def signup_flipboard(page: Page, site_key: str, acct: dict, site: dict) -> str:
    """Flipboard signup: email + password + name."""
    await page.goto("https://flipboard.com/signup", wait_until="domcontentloaded")
    await human_delay(DELAY_PAGE_LOAD)
    await handle_captcha(page)

    # Flipboard may ask to "Sign up with email" first
    try:
        await safe_click(page, "button:has-text('email')", timeout=3000)
        await human_delay(DELAY_MEDIUM)
    except Exception:
        pass

    await fill_name(page, acct["display_name"])
    await fill_email(page, acct["email"])
    await fill_password(page, acct["password"])

    await handle_captcha(page)
    await click_submit(page)
    await wait_for_navigation(page)
    await human_delay(DELAY_MEDIUM)

    return "completed" if await check_success(page) else "needs_verification"


async def signup_bloglovin(page: Page, site_key: str, acct: dict, site: dict) -> str:
    """Bloglovin signup: email + password + username."""
    await page.goto("https://www.bloglovin.com/register", wait_until="domcontentloaded")
    await human_delay(DELAY_PAGE_LOAD)
    await handle_captcha(page)

    # Username = site key without dash
    username = site_key.replace("-", "")
    await fill_name(page, username, field_hint="username")
    await fill_email(page, acct["email"])
    await fill_password(page, acct["password"])

    await handle_captcha(page)
    await click_submit(page)
    await wait_for_navigation(page)
    await human_delay(DELAY_MEDIUM)

    return "completed" if await check_success(page) else "needs_verification"


async def signup_blogarama(page: Page, site_key: str, acct: dict, site: dict) -> str:
    """Blogarama signup: email + blog URL + blog name + description + category."""
    await page.goto("https://www.blogarama.com/register", wait_until="domcontentloaded")
    await human_delay(DELAY_PAGE_LOAD)
    await handle_captcha(page)

    await fill_email(page, acct["email"])
    await fill_password(page, acct["password"])
    await fill_field(page, f"https://{site['domain']}", ["blog_url", "url", "website", "blog"])
    await fill_field(page, site["name"], ["blog_name", "blogname", "title", "name"])
    await fill_field(page, acct["bio"], ["description", "desc", "about", "bio"])

    # Try to select a category
    category_map = {
        "glow-coded": "Beauty",
        "rooted-glow": "Health",
    }
    cat = category_map.get(site_key, "Lifestyle")
    cat_selectors = ["select[name*='category' i]", "select[id*='category' i]", "select[name*='cat' i]"]
    for sel in cat_selectors:
        try:
            count = await page.locator(sel).count()
            if count > 0:
                await page.locator(sel).first.select_option(label=cat)
                await human_delay(DELAY_SHORT)
                break
        except Exception:
            pass

    await handle_captcha(page)
    await click_submit(page)
    await wait_for_navigation(page)
    await human_delay(DELAY_MEDIUM)

    return "completed" if await check_success(page) else "needs_verification"


async def signup_feedspot(page: Page, site_key: str, acct: dict, site: dict) -> str:
    """Feedspot signup: email + blog URL (submit for review)."""
    await page.goto("https://www.feedspot.com/signup", wait_until="domcontentloaded")
    await human_delay(DELAY_PAGE_LOAD)
    await handle_captcha(page)

    await fill_email(page, acct["email"])
    await fill_password(page, acct["password"])
    await fill_field(page, f"https://{site['domain']}", ["url", "blog", "website", "feed"])

    await handle_captcha(page)
    await click_submit(page)
    await wait_for_navigation(page)
    await human_delay(DELAY_MEDIUM)

    # After account creation, try to submit blog
    try:
        await safe_click(page, "a:has-text('Add Blog')", timeout=3000)
        await human_delay(DELAY_MEDIUM)
        await fill_field(page, f"https://{site['domain']}", ["url", "blog", "website", "feed"])
        await click_submit(page)
        await wait_for_navigation(page)
    except Exception:
        pass

    return "completed" if await check_success(page) else "needs_verification"


async def signup_gravatar(page: Page, site_key: str, acct: dict, site: dict) -> str:
    """Gravatar signup: email + password (WordPress account)."""
    await page.goto("https://gravatar.com/signup", wait_until="domcontentloaded")
    await human_delay(DELAY_PAGE_LOAD)
    await handle_captcha(page)

    await fill_email(page, acct["email"])

    # Gravatar/WordPress may have a two-step flow — submit email first
    await click_submit(page)
    await wait_for_navigation(page)
    await human_delay(DELAY_MEDIUM)

    # Now fill password if on a new page
    await fill_password(page, acct["password"])
    await fill_name(page, acct["display_name"], field_hint="username")

    await handle_captcha(page)
    await click_submit(page)
    await wait_for_navigation(page)
    await human_delay(DELAY_MEDIUM)

    return "completed" if await check_success(page) else "needs_verification"


async def signup_aboutme(page: Page, site_key: str, acct: dict, site: dict) -> str:
    """About.me signup: email + password + name."""
    await page.goto("https://about.me/signup", wait_until="domcontentloaded")
    await human_delay(DELAY_PAGE_LOAD)
    await handle_captcha(page)

    # about.me may have "Sign up with email"
    try:
        await safe_click(page, "button:has-text('email')", timeout=3000)
        await human_delay(DELAY_MEDIUM)
    except Exception:
        pass

    parts = acct["display_name"].split(" ", 1)
    first = parts[0]
    last = parts[1] if len(parts) > 1 else ""

    await fill_name(page, first, field_hint="first")
    await fill_name(page, last, field_hint="last")
    # Fallback: single name field
    await fill_name(page, acct["display_name"])
    await fill_email(page, acct["email"])
    await fill_password(page, acct["password"])

    await handle_captcha(page)
    await click_submit(page)
    await wait_for_navigation(page)
    await human_delay(DELAY_MEDIUM)

    return "completed" if await check_success(page) else "needs_verification"


# ── Generic fallback handler ─────────────────────────────────────────────────

async def signup_generic(page: Page, site_key: str, acct: dict, site: dict, platform: str) -> str:
    """Fallback handler for any unknown platform."""
    url = SIGNUP_PLATFORMS[platform]["url"]
    await page.goto(url, wait_until="domcontentloaded")
    await human_delay(DELAY_PAGE_LOAD)
    await handle_captcha(page)

    await fill_email(page, acct["email"])
    await fill_password(page, acct["password"])
    await fill_name(page, acct["display_name"])
    await fill_field(page, f"https://{site['domain']}", ["website", "url", "site", "blog"])

    await handle_captcha(page)
    await click_submit(page)
    await wait_for_navigation(page)
    await human_delay(DELAY_MEDIUM)

    return "completed" if await check_success(page) else "needs_verification"


# ── Handler dispatch ──────────────────────────────────────────────────────────

PLATFORM_HANDLERS = {
    "connectively": signup_connectively,
    "qwoted": signup_qwoted,
    "featured": signup_featured,
    "terkel": signup_terkel,
    "sourcebottle": signup_sourcebottle,
    "medium": signup_medium,
    "flipboard": signup_flipboard,
    "bloglovin": signup_bloglovin,
    "blogarama": signup_blogarama,
    "feedspot": signup_feedspot,
    "gravatar": signup_gravatar,
    "aboutme": signup_aboutme,
}


# ── Core runner ───────────────────────────────────────────────────────────────

async def run_signup(site_key: str, platform: str, status: dict):
    """Run signup for a single platform+site combo."""
    if is_completed(status, platform, site_key):
        print(f"  \u2714 {platform} / {site_key} — already completed, skipping.")
        return

    acct = ACCOUNTS[site_key]
    site = SITES[site_key]

    if not acct["password"]:
        print(f"  \u26a0 {platform} / {site_key} — no password configured, skipping.")
        update_status(status, platform, site_key, "failed")
        return

    print(f"\n  \u25b6 {platform} / {site_key} ({acct['email']})")
    print(f"    URL: {SIGNUP_PLATFORMS[platform]['url']}")

    # Set up persistent browser context
    state_dir = BROWSER_STATE_DIR / f"signup-{site_key}"
    state_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as pw:
        context = await pw.chromium.launch_persistent_context(
            user_data_dir=str(state_dir),
            headless=False,
            args=BROWSER_ARGS,
            viewport={"width": 1280, "height": 900},
            locale="en-US",
            timezone_id="America/New_York",
        )
        page = context.pages[0] if context.pages else await context.new_page()

        try:
            handler = PLATFORM_HANDLERS.get(platform)
            if handler:
                result = await handler(page, site_key, acct, site)
            else:
                result = await signup_generic(page, site_key, acct, site, platform)

            update_status(status, platform, site_key, result)
            icon = "\u2714" if result == "completed" else "\u2709" if result == "needs_verification" else "\u2718"
            print(f"    {icon} Result: {result}")

        except Exception as exc:
            print(f"    \u2718 Error: {exc}")
            update_status(status, platform, site_key, "failed")

        finally:
            # Give user a moment to inspect the browser if needed
            await human_delay(DELAY_SHORT)
            await context.close()


async def run_all(site_keys: list[str], platforms: list[str]):
    """Run signups for the given sites and platforms."""
    status = load_status()

    total = len(site_keys) * len(platforms)
    done = 0

    for platform in platforms:
        for site_key in site_keys:
            done += 1
            print(f"\n{'='*60}")
            print(f"  [{done}/{total}] {platform} / {site_key}")
            print(f"{'='*60}")

            await run_signup(site_key, platform, status)

            # Delay between signups to look human
            if done < total:
                wait = random.uniform(*DELAY_LONG)
                print(f"  Waiting {wait:.1f}s before next signup...")
                await asyncio.sleep(wait)

    # Summary
    status = load_status()
    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")
    for platform in platforms:
        for site_key in site_keys:
            entry = status.get(platform, {}).get(site_key, {})
            st = entry.get("status", "not started")
            icon = "\u2714" if st == "completed" else "\u2709" if st == "needs_verification" else "\u2718" if st == "failed" else "\u2022"
            print(f"  {icon} {platform:20s} {site_key:15s} {st}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Automate account signups for SEO backlink platforms."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--site",
        choices=["glow-coded", "rooted-glow"],
        help="Run signups for one site.",
    )
    group.add_argument(
        "--all",
        action="store_true",
        dest="all_sites",
        help="Run signups for both sites.",
    )
    parser.add_argument(
        "--platform",
        choices=list(SIGNUP_PLATFORMS.keys()),
        help="Run signup for a single platform only.",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print current signup status and exit.",
    )
    args = parser.parse_args()

    # Status-only mode
    if args.status:
        status = load_status()
        if not status:
            print("No signups recorded yet.")
            return
        for plat, sites in sorted(status.items()):
            for sk, entry in sorted(sites.items()):
                st = entry.get("status", "?")
                ts = entry.get("timestamp", "")
                icon = "\u2714" if st == "completed" else "\u2709" if st == "needs_verification" else "\u2718"
                print(f"  {icon} {plat:20s} {sk:15s} {st:22s} {ts}")
        return

    # Determine sites
    if args.all_sites:
        site_keys = ["glow-coded", "rooted-glow"]
    else:
        site_keys = [args.site]

    # Determine platforms
    if args.platform:
        platforms = [args.platform]
    else:
        platforms = list(SIGNUP_PLATFORMS.keys())

    print(f"\nSignup Autopilot")
    print(f"  Sites:     {', '.join(site_keys)}")
    print(f"  Platforms: {', '.join(platforms)}")
    print(f"  Total:     {len(site_keys) * len(platforms)} signups\n")

    asyncio.run(run_all(site_keys, platforms))


if __name__ == "__main__":
    main()
