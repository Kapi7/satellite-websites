#!/usr/bin/env python3
"""
Pinterest re-login that uses Telegram for the 2FA challenge — no human
needs to be at the machine running the script. Works the same whether
invoked locally, in CI, or via the Mac Mini.

Flow:
  1. Open Chromium (headless OK — most challenges don't need a screen).
  2. Navigate to pinterest.com/login, fill email + password from env.
  3. If a 2FA / OTP / code field appears, send a Telegram message asking
     for the code. Poll Telegram getUpdates for the user's reply.
     Extract digits, fill the field, submit.
  4. On confirmed login, save storage_state.json to the path the rest of
     the poster pipeline expects.

Usage:
    python3 scripts/social/pinterest_relogin_telegram.py --account mirai
    python3 scripts/social/pinterest_relogin_telegram.py --account all
    python3 scripts/social/pinterest_relogin_telegram.py --account mirai --headed

Required env: PINTEREST_*_EMAIL, PINTEREST_*_PASSWORD, TELEGRAM_BOT_TOKEN,
TELEGRAM_CHAT_ID.
"""
from __future__ import annotations
import argparse
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import PINTEREST_ACCOUNTS, BROWSER_STATE_DIR, BROWSER_ARGS

TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")


# ── Telegram helpers ────────────────────────────────────────────────────

def tg_send(text: str) -> int | None:
    """Send a message to the configured chat. Returns message_id or None."""
    if not TG_TOKEN or not TG_CHAT:
        print(f"[tg] no token/chat set — would send: {text}")
        return None
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    body = urllib.parse.urlencode({
        "chat_id": TG_CHAT,
        "text": text,
        "parse_mode": "Markdown",
    }).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=body), timeout=15) as r:
            import json
            data = json.loads(r.read())
            return data.get("result", {}).get("message_id")
    except Exception as e:
        print(f"[tg] send failed: {e}")
        return None


def tg_poll_for_code(prompt_message_id: int | None, timeout_sec: int = 300) -> str | None:
    """Long-poll Telegram getUpdates for a numeric message from the authorized
    chat. Returns the digits-only string, or None on timeout."""
    if not TG_TOKEN or not TG_CHAT:
        return None
    chat_id = int(TG_CHAT) if str(TG_CHAT).lstrip("-").isdigit() else TG_CHAT
    base = f"https://api.telegram.org/bot{TG_TOKEN}"

    # Drain existing updates first so old replies don't poison this poll
    try:
        with urllib.request.urlopen(f"{base}/getUpdates?offset=-1&limit=1", timeout=10) as r:
            import json
            data = json.loads(r.read())
            results = data.get("result", [])
            offset = results[-1]["update_id"] + 1 if results else 0
    except Exception as e:
        print(f"[tg] initial drain failed: {e}")
        offset = 0

    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        remaining = max(1, int(deadline - time.time()))
        wait = min(25, remaining)
        try:
            url = f"{base}/getUpdates?offset={offset}&timeout={wait}"
            with urllib.request.urlopen(url, timeout=wait + 10) as r:
                import json
                data = json.loads(r.read())
        except Exception as e:
            print(f"[tg] poll error: {e}")
            time.sleep(3)
            continue

        for upd in data.get("result", []):
            offset = upd["update_id"] + 1
            msg = upd.get("message", {})
            if str(msg.get("chat", {}).get("id")) != str(chat_id):
                continue
            text = (msg.get("text") or "").strip()
            digits = re.sub(r"\D", "", text)
            if 4 <= len(digits) <= 8:  # 2FA codes are typically 6 digits
                print(f"[tg] received code (length {len(digits)})")
                return digits
            else:
                print(f"[tg] message ignored (no 4-8 digit run): {text[:40]!r}")

    return None


# ── Pinterest login flow ────────────────────────────────────────────────

CODE_FIELD_SELECTORS = [
    'input[name="code"]',
    'input[id*="code" i]',
    'input[autocomplete="one-time-code"]',
    'input[inputmode="numeric"]',
    'input[type="tel"]',
]


def find_code_field(page):
    for sel in CODE_FIELD_SELECTORS:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=1500):
                return loc
        except Exception:
            continue
    return None


def is_logged_in(page) -> bool:
    """Multi-signal check — Pinterest UI changes a lot, so try several
    indicators and short-circuit on the first that says "yes"."""
    # 1. URL hints
    url = page.url or ""
    if "/business/hub" in url or "/pin-creation-tool" in url:
        return True
    if "/login" in url:
        return False

    # 2. Specific logged-in elements (multiple selectors, any match)
    indicators = [
        '[data-test-id="header-avatar"]',
        '[data-test-id="storyboard-create-header-heading"]',
        'div[aria-label="Your Profile menu"]',
        'div[data-test-id="header-profile"]',
        'a[href*="/pin-creation-tool"]',
        'a[href="/business/hub/"]',
        '[aria-label="Search"]',
        'svg[aria-label="Pinterest"][role="img"]',  # logo on logged-in home shell
    ]
    for sel in indicators:
        try:
            if page.locator(sel).first.is_visible(timeout=1000):
                return True
        except Exception:
            continue

    # 3. Negative check — login form absent means we're past it
    try:
        login_form_visible = page.locator('#email').first.is_visible(timeout=800) and \
                             page.locator('#password').first.is_visible(timeout=800)
        if not login_form_visible and "pinterest.com" in url:
            return True
    except Exception:
        # email/password locators throw when not on login page → likely logged in
        if "pinterest.com" in url and "/login" not in url:
            return True
    return False


def is_security_challenge(page) -> bool:
    """Detect Pinterest's 'verify it's you' / email-code / captcha screens
    that aren't the standard 2FA OTP."""
    indicators = [
        'text=/verify.*it.*you/i',
        'text=/security check/i',
        'text=/unusual activity/i',
        'text=/we sent.*code.*email/i',
        'text=/check your email/i',
        'iframe[src*="captcha"]',
        'iframe[title*="captcha" i]',
    ]
    for sel in indicators:
        try:
            if page.locator(sel).first.is_visible(timeout=500):
                return True
        except Exception:
            continue
    return False


def login_one(account_key: str, headed: bool) -> bool:
    creds = PINTEREST_ACCOUNTS.get(account_key) or {}
    email = creds.get("email", "")
    password = creds.get("password", "")
    if not email or not password:
        print(f"[{account_key}] missing creds — skipping")
        return False

    state_dir = BROWSER_STATE_DIR / f"pinterest-{account_key}"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / "state.json"

    print(f"\n=== Re-login: {account_key} ({email}) ===")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not headed, args=BROWSER_ARGS)
        ctx = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
        )
        ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
        page = ctx.new_page()

        try:
            page.goto("https://www.pinterest.com/login/", timeout=30000)
            time.sleep(2)
            try:
                accept = page.locator('button:has-text("Accept all")').first
                if accept.is_visible(timeout=2000):
                    accept.click()
            except Exception:
                pass

            # Fill email + password
            page.locator('#email').first.fill(email, timeout=10000)
            time.sleep(0.5)
            page.locator('#password').first.fill(password, timeout=10000)
            time.sleep(0.5)
            page.locator('button[type="submit"]').first.click()
            print(f"[{account_key}] credentials submitted")
            # Wait longer — Pinterest can take 10-15s to redirect after submit
            time.sleep(12)
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass

            # Always save a debug screenshot post-submit so we can see what
            # Pinterest is actually showing if anything goes wrong.
            screenshots_dir = Path("scripts/social/data") / "relogin-debug"
            screenshots_dir.mkdir(parents=True, exist_ok=True)
            try:
                page.screenshot(path=str(screenshots_dir / f"{account_key}-postsubmit.png"))
            except Exception:
                pass

            # Detect security-challenge screens BEFORE the OTP check —
            # these need email codes or Telegram-bridged input
            if is_security_challenge(page):
                print(f"[{account_key}] security challenge detected (not standard OTP)")
                tg_send(f"⚠️ Pinterest *{account_key}* served a security challenge "
                        f"(verify-it's-you / email code). Need manual login.")
                try:
                    page.screenshot(path=str(screenshots_dir / f"{account_key}-challenge.png"))
                except Exception:
                    pass

            # Check whether we hit a 2FA / code challenge
            code_field = find_code_field(page)
            if code_field:
                print(f"[{account_key}] 2FA challenge detected — asking via Telegram")
                msg_id = tg_send(
                    f"🔐 Pinterest *{account_key}* needs a 2FA code.\n\n"
                    f"Reply to this chat with the 6-digit code from email/SMS within 5 min."
                )
                code = tg_poll_for_code(msg_id, timeout_sec=300)
                if not code:
                    tg_send(f"❌ Pinterest *{account_key}* re-login: 2FA timeout.")
                    print(f"[{account_key}] 2FA timeout")
                    return False
                code_field.fill(code, timeout=5000)
                time.sleep(0.5)
                # Try common submit-button labels
                for btn_sel in ['button:has-text("Verify")', 'button:has-text("Next")',
                                'button:has-text("Submit")', 'button[type="submit"]']:
                    try:
                        b = page.locator(btn_sel).first
                        if b.is_visible(timeout=1500):
                            b.click()
                            break
                    except Exception:
                        continue
                time.sleep(6)

            # Verify success
            page.goto("https://www.pinterest.com/")
            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            time.sleep(4)
            try:
                page.screenshot(path=str(screenshots_dir / f"{account_key}-final.png"))
            except Exception:
                pass

            if not is_logged_in(page):
                cur = page.url or ""
                # Final fallback — try business hub URL directly; if it loads
                # without redirecting to /login, we're authenticated
                try:
                    page.goto("https://www.pinterest.com/business/hub/", timeout=15000)
                    time.sleep(3)
                    if "/login" not in (page.url or ""):
                        print(f"[{account_key}] verified via business hub")
                    else:
                        print(f"[{account_key}] login verification failed (url={cur} → {page.url})")
                        tg_send(f"❌ Pinterest *{account_key}* re-login failed — Pinterest didn't accept the login. "
                                f"Check screenshots in workflow artifacts.")
                        return False
                except Exception as e:
                    print(f"[{account_key}] hub probe error: {e}")
                    tg_send(f"❌ Pinterest *{account_key}* re-login failed (verification timeout).")
                    return False

            ctx.storage_state(path=str(state_file))
            kb = state_file.stat().st_size // 1024
            print(f"[{account_key}] saved state to {state_file} ({kb}KB)")
            tg_send(f"✅ Pinterest *{account_key}* re-login OK — state saved.")
            return True

        except Exception as e:
            print(f"[{account_key}] error: {e}")
            tg_send(f"❌ Pinterest *{account_key}* re-login error: `{type(e).__name__}: {str(e)[:120]}`")
            return False
        finally:
            browser.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", required=True,
                    help="cosmetics | wellness | mirai | all")
    ap.add_argument("--headed", action="store_true",
                    help="Show the browser (only if you're at the machine)")
    args = ap.parse_args()

    if args.account == "all":
        accounts = [a for a in PINTEREST_ACCOUNTS.keys()
                    if PINTEREST_ACCOUNTS[a].get("email") and PINTEREST_ACCOUNTS[a].get("password")]
    else:
        accounts = [args.account]

    results = {a: login_one(a, args.headed) for a in accounts}
    ok = [a for a, v in results.items() if v]
    fail = [a for a, v in results.items() if not v]
    print(f"\n[done] OK={ok}  FAIL={fail}")
    sys.exit(0 if not fail else 1)


if __name__ == "__main__":
    main()
