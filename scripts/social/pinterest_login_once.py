#!/usr/bin/env python3
"""One-shot interactive Pinterest login for any account in PINTEREST_ACCOUNTS.

Opens a visible Chromium, navigates to pinterest.com, auto-fills creds, and
waits for the user to clear CAPTCHA / 2FA / onboarding. Saves the storage
state to scripts/social/browser-state/pinterest-{account}/state.json so all
future automation runs headless against that account.

Usage:
    python3 pinterest_login_once.py --account mirai
    python3 pinterest_login_once.py --account cosmetics
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import PINTEREST_ACCOUNTS, BROWSER_STATE_DIR, BROWSER_ARGS

from playwright.sync_api import sync_playwright


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", required=True, choices=list(PINTEREST_ACCOUNTS.keys()))
    ap.add_argument("--timeout", type=int, default=600,
                    help="Seconds to wait for you to complete login (default 600 = 10 min)")
    args = ap.parse_args()

    creds = PINTEREST_ACCOUNTS[args.account]
    if not creds.get("email") or not creds.get("password"):
        print(f"ERROR: missing creds for account '{args.account}' in .env", file=sys.stderr)
        return 2

    state_dir = BROWSER_STATE_DIR / f"pinterest-{args.account}"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / "state.json"

    print(f"\n=== Pinterest login for account: {args.account} ===")
    print(f"Email: {creds['email']}")
    print(f"State will save to: {state_file}")
    print()
    print("1. A visible Chromium will open and navigate to pinterest.com/login.")
    print("2. The script will auto-fill the email + password fields.")
    print("3. You complete any CAPTCHA, email verification, 2FA, or onboarding.")
    print("4. Once you reach the Pinterest home feed, return here and press ENTER.")
    print("5. Cookies + localStorage will be saved for headless automation.")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=BROWSER_ARGS)
        context = browser.new_context(
            storage_state=str(state_file) if state_file.exists() else None,
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        page = context.new_page()

        # Force the Chromium window to front via AppleScript so the user
        # can't miss it. Playwright launches "Chromium" not "Google Chrome".
        try:
            import subprocess
            subprocess.run(
                ["osascript", "-e", 'tell application "Chromium" to activate'],
                check=False, timeout=3,
            )
        except Exception:
            pass

        # Try home first — if cookies are valid, we're done
        page.goto("https://www.pinterest.com/", wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)

        # Quick check: are we already logged in?
        already = False
        try:
            content = page.content().lower()
            if 'data-test-id="header-profile"' in content or '"unauthid"' not in content[:5000]:
                # Heuristic: the profile button shows when logged in
                already = page.locator('[data-test-id="header-profile"]').count() > 0
        except Exception:
            pass

        if already:
            print("\n✓ Already logged in via existing session cookies — no work needed.")
        else:
            print("\nNot logged in yet. Going to /login and auto-filling credentials...")
            page.goto("https://www.pinterest.com/login/", wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)

            # Dismiss cookie banner if present
            try:
                page.locator('button:has-text("Accept all")').first.click(timeout=2000)
                time.sleep(1)
            except Exception:
                pass

            try:
                page.locator('#email').first.fill(creds["email"])
                time.sleep(0.5)
                page.locator('#password').first.fill(creds["password"])
                time.sleep(0.5)
                # Inject a HUGE banner so the user knows which window to use
                page.evaluate("""() => {
                    const b = document.createElement('div');
                    b.id = '__claude_marker__';
                    b.textContent = '👇 LOG IN IN THIS WINDOW (controlled by Claude)';
                    Object.assign(b.style, {
                        position: 'fixed', top: '0', left: '0', right: '0',
                        background: '#ff4d6d', color: 'white', padding: '14px',
                        textAlign: 'center', fontSize: '20px', fontWeight: '700',
                        fontFamily: 'system-ui, sans-serif',
                        zIndex: '999999', boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
                    });
                    document.body.prepend(b);
                }""")
                print("Credentials filled. Click 'Log in' in the browser, solve CAPTCHA / 2FA")
                print("/ onboarding as Pinterest prompts. Script will detect login automatically.")
            except Exception as e:
                print(f"Auto-fill failed: {e}")
                print("Type the credentials manually in the browser.")

            # Bring window to front a second time after fill (Pinterest's form
            # might steal focus during render)
            try:
                import subprocess as _sp
                _sp.run(["osascript", "-e", 'tell application "Chromium" to activate'],
                        check=False, timeout=3)
            except Exception:
                pass

            print()
            print(f"Polling for successful login (timeout: {args.timeout}s)...")
            print("Detection: waiting for the Pinterest auth cookie to be set.")
            print("=" * 60)

            # Cookie-based detection — works regardless of which Pinterest URL
            # the user lands on (home, onboarding, business hub, profile, etc).
            # Pinterest sets `_pinterest_sess` and `_auth` cookies after a
            # successful login. Either is a reliable signal.
            start = time.time()
            logged_in = False
            sentinel = Path("/tmp/pinterest-login-mirai-done")
            sentinel.unlink(missing_ok=True)
            while time.time() - start < args.timeout:
                try:
                    cookies = context.cookies("https://www.pinterest.com/")
                    cookie_names = {c.get("name") for c in cookies}
                    has_session = "_pinterest_sess" in cookie_names
                    has_auth = any(c.get("name") == "_auth" and str(c.get("value", "")).strip("0 ").strip() for c in cookies)
                    url = page.url
                    if has_session and "/login" not in url and "pinterest.com" in url:
                        logged_in = True
                        break
                    # Also accept a manual "I'm done" sentinel file in case Pinterest
                    # blocks the session cookie (rare).
                    if sentinel.exists():
                        logged_in = True
                        sentinel.unlink(missing_ok=True)
                        break
                except Exception:
                    pass
                time.sleep(4)
                elapsed = int(time.time() - start)
                try:
                    cookies = context.cookies("https://www.pinterest.com/")
                    has = "_pinterest_sess" in {c.get("name") for c in cookies}
                except Exception:
                    has = False
                print(f"  …polling ({elapsed}s) url={page.url[:60]}  pinterest_sess={'YES' if has else 'no'}", flush=True)

            if not logged_in:
                print(f"\n✗ Login not detected within {args.timeout}s — saving anyway.")
            else:
                print("\n✓ Login detected (auth cookie set).")

        # Save storage state
        try:
            context.storage_state(path=str(state_file))
            print(f"\n✓ Saved Pinterest session → {state_file}")
            print(f"  ({state_file.stat().st_size} bytes)")
        except Exception as e:
            print(f"\n✗ Failed to save state: {e}")
            return 1

        browser.close()

    print("\nNext: create the 8 boards on Pinterest, then post the 3 sample pins:")
    print("  python3 scripts/social/pinterest_poster.py --site mirai --run-due")
    return 0


if __name__ == "__main__":
    sys.exit(main())
