#!/usr/bin/env python3
"""Delete rooted-glow Pinterest pins linking to build-coded.com.

Strategy:
1. Open Pinterest profile → Created tab. Scroll to load all pins.
2. For each pin, fetch outbound URL via HTTP request using session cookies (no browser nav).
3. Filter pins whose outbound URL matches --target-domain.
4. Delete via Playwright UI flow with 12s human-like delays.

Why HTTP for URL extraction: Pinterest throttles repeated browser navigations to
individual pin pages. A plain GET with session cookies is one round-trip and
indistinguishable from normal page loads.
"""
import argparse
import json
import random
import re
import sys
import time
import urllib.request
import urllib.error
from http.cookiejar import CookieJar
from pathlib import Path
from playwright.sync_api import sync_playwright

REPO = Path("/Users/agentdavid/mirai-seo/satellite-websites")
STATE_DIR = REPO / "scripts/social/browser-state"
DATA_DIR = REPO / "scripts/social/data"
DATA_DIR.mkdir(exist_ok=True)


def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def cookies_from_state(state_file: Path):
    """Convert Playwright state.json cookies → header string."""
    with open(state_file) as f:
        s = json.load(f)
    pairs = []
    for c in s.get("cookies", []):
        if "pinterest.com" in c.get("domain", ""):
            pairs.append(f'{c["name"]}={c["value"]}')
    return "; ".join(pairs)


def collect_created_pins(page, profile_url):
    if "/_created/" not in profile_url:
        if "/_saved/" in profile_url:
            profile_url = profile_url.rsplit("/_saved/")[0] + "/_created/"
        else:
            profile_url = profile_url.rstrip("/") + "/_created/"
    log(f"Navigating to {profile_url}")
    page.goto(profile_url, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(5000)
    seen = {}
    no_change_iters = 0
    last_count = 0
    for i in range(50):
        items = page.evaluate("""
            () => {
              const out = [];
              const seen = new Set();
              document.querySelectorAll('a[href*="/pin/"]').forEach(a => {
                const m = a.href.match(/\\/pin\\/(\\d+)\\//);
                if (!m) return;
                const pin_id = m[1];
                if (seen.has(pin_id)) return;
                seen.add(pin_id);
                let card = a;
                let title = '';
                for (let i=0; i<10 && card; i++) {
                  const img = card.querySelector('img[alt]');
                  if (img && img.alt && img.alt.trim().length > 5) { title = img.alt.trim(); break; }
                  card = card.parentElement;
                }
                out.push({pin_id, pin_url: `https://www.pinterest.com/pin/${pin_id}/`, title: title.split('\\n')[0]});
              });
              return out;
            }
        """)
        for it in items:
            if it["pin_id"] not in seen:
                seen[it["pin_id"]] = it
        if len(seen) == last_count:
            no_change_iters += 1
            if no_change_iters >= 4: break
        else:
            no_change_iters = 0
            last_count = len(seen)
        page.evaluate("window.scrollBy(0, 1200)")
        page.wait_for_timeout(2000)
    log(f"Collected {len(seen)} unique pins from Created tab")
    return list(seen.values())


def fetch_outbound_via_http(pin_id, cookie_header):
    """Fetch /pin/{id}/ via plain HTTP, parse out destination URL from HTML."""
    url = f"https://www.pinterest.com/pin/{pin_id}/"
    req = urllib.request.Request(url, headers={
        "Cookie": cookie_header,
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        return ""
    # Pinterest embeds the pin's link in JSON: "link":"https://...","..."
    # Look for "link":"<url>" in the page. Pinterest may double-escape — handle both.
    m = re.search(r'"link"\s*:\s*"([^"]+?)"', html)
    if m:
        link = m.group(1).encode().decode("unicode_escape")
        if link.startswith("http"): return link
    # Fallback: og:url or canonical
    m = re.search(r'<meta\s+property="og:see_also"\s+content="([^"]+)"', html)
    if m: return m.group(1)
    return ""


def delete_pin(page, pin_url, dry_run=False):
    if dry_run:
        log(f"  [DRY-RUN] would delete {pin_url}")
        return True
    log(f"  → opening {pin_url}")
    try:
        page.goto(pin_url, wait_until="domcontentloaded", timeout=45000)
    except Exception as e:
        log(f"  [ERROR] navigate: {e}")
        return False
    page.wait_for_timeout(3500)
    try:
        opened = False
        for sel in [
            'button[aria-label="Pin actions"]',
            'button[aria-label="More options"]',
            '[data-test-id="more-pin-actions"]',
            '[aria-label="More"]',
        ]:
            try: page.click(sel, timeout=4000); opened = True; break
            except Exception: continue
        if not opened: log("  [SKIP] no menu button"); return False
        page.wait_for_timeout(1500)
        clicked = False
        for sel in ['div[role="menuitem"]:has-text("Edit Pin")','div[role="menuitem"]:has-text("Edit")','button:has-text("Edit Pin")','a:has-text("Edit Pin")']:
            try: page.click(sel, timeout=4000); clicked = True; break
            except Exception: continue
        if not clicked: log("  [SKIP] no Edit"); return False
        page.wait_for_timeout(3000)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1500)
        try: page.click('button:has-text("Delete")', timeout=5000)
        except Exception:
            try: page.click('text="Delete"', timeout=5000)
            except Exception: log("  [SKIP] no Delete"); return False
        page.wait_for_timeout(2000)
        for sel in ['div[role="dialog"] button:has-text("Delete")','button:has-text("Delete")']:
            try: page.click(sel, timeout=4000); break
            except Exception: continue
        page.wait_for_timeout(3500)
        log("  [OK] deleted")
        return True
    except Exception as e:
        log(f"  [ERROR] {e}")
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", default="wellness")
    ap.add_argument("--target-domain", default="build-coded.com")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max", type=int, default=200)
    ap.add_argument("--delay", type=float, default=12.0)
    args = ap.parse_args()

    state = STATE_DIR / f"pinterest-{args.account}" / "state.json"
    if not state.exists():
        log(f"NO SESSION at {state}"); sys.exit(2)

    cookie_header = cookies_from_state(state)
    if not cookie_header:
        log("WARN: no pinterest.com cookies in state file"); sys.exit(2)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(
            storage_state=str(state),
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
        )
        page = ctx.new_page()
        try:
            page.goto("https://www.pinterest.com/", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3500)
            try: page.click('[data-test-id="header-profile"]', timeout=8000)
            except Exception: page.click('a[data-test-id="profile-button"]', timeout=8000)
            page.wait_for_timeout(4000)
            profile_url = page.url
            log(f"Profile: {profile_url}")

            pins = collect_created_pins(page, profile_url)
            log(f"\\nFetching outbound URLs via HTTP for {len(pins)} pins...")
            for i, pin in enumerate(pins):
                pin["outbound_url"] = fetch_outbound_via_http(pin["pin_id"], cookie_header)
                if i and i % 15 == 0:
                    log(f"  {i}/{len(pins)} resolved")
                time.sleep(random.uniform(0.4, 0.9))

            targets = [p for p in pins if args.target_domain in p["outbound_url"]]
            unresolved = [p for p in pins if not p["outbound_url"]]
            log(f"\\n=== TARGETS: {len(targets)} pins → {args.target_domain} ===")
            for t in targets[:50]:
                log(f"  {t['pin_url']}  →  {t['outbound_url']}")
            if unresolved:
                log(f"\\n[WARN] {len(unresolved)} pins had no resolvable URL — not in target list:")
                for p in unresolved[:10]:
                    log(f"  {p['pin_url']} | {p['title'][:60]}")

            audit = DATA_DIR / f"delete-targets-{args.account}-{int(time.time())}.json"
            with open(audit, "w") as f:
                json.dump({"all_pins": pins, "targets": targets}, f, indent=2)
            log(f"\\nAudit: {audit}")

            if args.dry_run:
                log(f"\\n[DRY-RUN] would delete {len(targets)} pins.")
                return
            if not targets:
                log("Nothing to delete.")
                return

            log(f"\\nDeleting {len(targets)} pins, ~{args.delay}s between each...")
            ok = 0
            for i, p in enumerate(targets[:args.max]):
                log(f"\\n[{i+1}/{len(targets)}] {p['title'][:60] or p['pin_url']}")
                log(f"  -> {p['outbound_url']}")
                if delete_pin(page, p["pin_url"], dry_run=False):
                    ok += 1
                d = args.delay + random.uniform(-2.0, 4.0)
                log(f"  sleep {d:.1f}s")
                time.sleep(d)
            log(f"\\nDone: {ok}/{len(targets)} deleted")
        finally:
            ctx.close()
            browser.close()


if __name__ == "__main__":
    main()
