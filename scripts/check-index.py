#!/usr/bin/env python3
"""GSC Index Checker + Bing Auto-Submit.

Checks indexing status via GSC URL Inspection API and auto-submits all URLs to Bing.
Run via cron: 15 6 * * * /opt/homebrew/bin/python3 /Users/kapi7/satellite-websites/scripts/check-index.py
"""

import json
import os
import sys
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

# ── Config ──────────────────────────────────────────────────────────────────
GSC_TOKEN_FILE = os.environ.get("GSC_TOKEN_FILE", os.path.expanduser("~/.config/gsc-token.json"))
BING_API_KEY = os.environ.get("BING_API_KEY", "282fd9e402f641b9a21fe8c171b6925e")

SITES = {
    "glow-coded.com": {
        "gsc": "sc-domain:glow-coded.com",
        "sitemap": "https://glow-coded.com/sitemap-0.xml",
        "bing_url": "https://glow-coded.com/",
    },
    "rooted-glow.com": {
        "gsc": "sc-domain:rooted-glow.com",
        "sitemap": "https://rooted-glow.com/sitemap-0.xml",
        "bing_url": "https://rooted-glow.com/",
    },
    "build-coded.com": {
        "gsc": "sc-domain:build-coded.com",
        "sitemap": "https://build-coded.com/sitemap-0.xml",
        "bing_url": "https://build-coded.com/",
    },
}

# Keyword value for prioritizing unindexed URLs (slug -> approximate monthly volume)
KEYWORD_VALUES = {
    # Glow Coded
    "what-is-glass-skin-how-to-get-it": 20000,
    "best-korean-sunscreens-oily-skin-no-white-cast": 7800,
    "tirtir-cushion-foundation-shade-guide": 6100,
    "best-korean-moisturizers-sensitive-skin": 4700,
    "korean-eye-cream-guide": 2300,
    "korean-toners-ranked-best-every-skin-type": 2200,
    "sheet-masks-how-often-best-picks": 1200,
    "best-korean-cleansing-oils": 1200,
    "aha-vs-bha-vs-pha-which-exfoliant": 500,
    "vitamin-c-korean-skincare": 450,
    "korean-skincare-routine-rosacea": 80,
    "best-anti-aging-korean-skincare-30s": 50,
    # Rooted Glow
    "8-adaptogens-that-actually-work": 36000,
    "couch-to-5k-8-week-running-plan": 31000,
    "bone-broth-benefits": 24000,
    "how-to-make-sauerkraut-at-home": 10000,
    "why-we-quit-seed-oils": 4700,
    "meditation-for-beginners-start-5-minutes": 2800,
    "how-to-start-running-beginners-guide": 1800,
    "fermented-beetroot-kvass-probiotic-drink": 600,
    "heart-rate-zones-explained-train-smarter": 400,
}

# ── Helpers ─────────────────────────────────────────────────────────────────
def load_gsc_token():
    with open(GSC_TOKEN_FILE) as f:
        return json.load(f)

def refresh_gsc_token(token_data):
    expiry = datetime.fromisoformat(token_data["expiry"])
    if datetime.now() < expiry:
        return token_data["token"]

    print("[GSC] Refreshing expired token...")
    body = urllib.parse.urlencode({
        "client_id": token_data["client_id"],
        "client_secret": token_data["client_secret"],
        "refresh_token": token_data["refresh_token"],
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=body)
    resp = urllib.request.urlopen(req)
    result = json.loads(resp.read())

    token_data["token"] = result["access_token"]
    token_data["expiry"] = (datetime.now() + timedelta(seconds=result["expires_in"])).isoformat()
    with open(GSC_TOKEN_FILE, "w") as f:
        json.dump(token_data, f, indent=2)
    return result["access_token"]

def fetch_sitemap_urls(sitemap_url):
    """Fetch all URLs from a sitemap XML."""
    try:
        req = urllib.request.Request(sitemap_url, headers={"User-Agent": "SEO-Checker/1.0"})
        resp = urllib.request.urlopen(req, timeout=15)
        content = resp.read()
        root = ET.fromstring(content)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = [loc.text for loc in root.findall(".//sm:loc", ns)]
        return urls
    except Exception as e:
        print(f"  Error fetching sitemap {sitemap_url}: {e}")
        return []

def inspect_url(access_token, site_id, url):
    """Use GSC URL Inspection API to check index status."""
    api_url = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"
    body = {"inspectionUrl": url, "siteUrl": site_id}
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    req = urllib.request.Request(api_url, data=json.dumps(body).encode(), headers=headers, method="POST")
    try:
        resp = urllib.request.urlopen(req)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()[:200]
        if e.code == 429:
            print(f"  Rate limited on {url}")
            return None
        print(f"  Inspection error {e.code} for {url}: {error_body}")
        return None

def submit_to_bing(site_url, urls):
    """Submit URLs to Bing Webmaster API."""
    if not urls:
        print("  No URLs to submit to Bing")
        return

    api_url = f"https://ssl.bing.com/webmaster/api.svc/json/SubmitUrlBatch?apikey={BING_API_KEY}"
    body = json.dumps({"siteUrl": site_url, "urlList": urls}).encode()
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(api_url, data=body, headers=headers, method="POST")
    try:
        resp = urllib.request.urlopen(req)
        result = resp.read().decode()
        print(f"  Bing: submitted {len(urls)} URLs — response: {result[:100]}")
    except urllib.error.HTTPError as e:
        print(f"  Bing submit error {e.code}: {e.read().decode()[:200]}")

def get_slug(url):
    """Extract slug from URL for keyword value lookup."""
    path = urllib.parse.urlparse(url).path.strip("/").rstrip("/")
    parts = path.split("/")
    return parts[-1] if parts else ""

# ── Main ────────────────────────────────────────────────────────────────────
def main():
    print(f"=== Index Check — {datetime.now().strftime('%Y-%m-%d %H:%M')} ===\n")

    token_data = load_gsc_token()
    access_token = refresh_gsc_token(token_data)

    for domain, cfg in SITES.items():
        print(f"\n{'='*50}")
        print(f"  {domain}")
        print(f"{'='*50}")

        # Fetch sitemap URLs
        urls = fetch_sitemap_urls(cfg["sitemap"])
        print(f"  Sitemap URLs: {len(urls)}")

        if not urls:
            print("  Skipping — no sitemap URLs found")
            continue

        # Check each URL via GSC URL Inspection
        indexed = []
        unindexed = []

        for url in urls:
            result = inspect_url(access_token, cfg["gsc"], url)
            if result is None:
                continue

            inspection = result.get("inspectionResult", {}).get("indexStatusResult", {})
            verdict = inspection.get("verdict", "UNKNOWN")
            coverage = inspection.get("coverageState", "Unknown")

            slug = get_slug(url)
            vol = KEYWORD_VALUES.get(slug, 0)

            if verdict == "PASS":
                indexed.append((url, vol))
            else:
                unindexed.append((url, vol, coverage))

        # Print results
        print(f"\n  Indexed: {len(indexed)} / {len(indexed) + len(unindexed)}")

        if unindexed:
            # Sort by keyword value (highest first)
            unindexed.sort(key=lambda x: x[1], reverse=True)
            print(f"\n  UNINDEXED (sorted by keyword value — submit to GSC in this order):")
            for i, (url, vol, status) in enumerate(unindexed, 1):
                slug = get_slug(url)
                vol_str = f"{vol:,}" if vol > 0 else "—"
                print(f"  {i:>2}. {slug:<55} vol={vol_str:<8} [{status}]")

        if indexed:
            print(f"\n  INDEXED:")
            for url, vol in sorted(indexed, key=lambda x: x[1], reverse=True):
                slug = get_slug(url)
                vol_str = f"{vol:,}" if vol > 0 else "—"
                print(f"      {slug:<55} vol={vol_str}")

        # Auto-submit ALL URLs to Bing
        print(f"\n  Submitting {len(urls)} URLs to Bing...")
        submit_to_bing(cfg["bing_url"], urls)

    print(f"\n{'='*50}")
    print("  Done.")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()
