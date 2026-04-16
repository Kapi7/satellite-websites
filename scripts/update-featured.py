#!/usr/bin/env python3
"""Update Featured Articles — queries GSC for top-performing pages and writes
featured.json files that each site's homepage reads at build time.

Usage:
  python3 scripts/update-featured.py              # all sites
  python3 scripts/update-featured.py cosmetics    # single site

Integrates into daily-publish.sh to run before each build.
"""

import json
import os
import sys
import urllib.request
import urllib.parse
import re
from datetime import datetime, timedelta

# ── Config ──────────────────────────────────────────────────────────────────
GSC_TOKEN_FILE = os.environ.get("GSC_TOKEN_FILE", os.path.expanduser("~/.config/gsc-token.json"))
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)

SITES = {
    "cosmetics": {
        "gsc_site": "sc-domain:glow-coded.com",
        "domain": "glow-coded.com",
        "data_dir": os.path.join(ROOT_DIR, "cosmetics", "src", "data"),
        "blog_dir": os.path.join(ROOT_DIR, "cosmetics", "src", "content", "blog", "en"),
    },
    "wellness": {
        "gsc_site": "sc-domain:rooted-glow.com",
        "domain": "rooted-glow.com",
        "data_dir": os.path.join(ROOT_DIR, "wellness", "src", "data"),
        "blog_dir": os.path.join(ROOT_DIR, "wellness", "src", "content", "blog", "en"),
    },
    "build-coded": {
        "gsc_site": "sc-domain:build-coded.com",
        "domain": "build-coded.com",
        "data_dir": os.path.join(ROOT_DIR, "build-coded", "src", "data"),
        "blog_dir": os.path.join(ROOT_DIR, "build-coded", "src", "content", "blog", "en"),
    },
}

# How many featured articles to select
TRENDING_COUNT = 6
# How many days of GSC data to look at
LOOKBACK_DAYS = 28
# Minimum impressions to qualify
MIN_IMPRESSIONS = 10


# ── GSC Auth ────────────────────────────────────────────────────────────────
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


# ── GSC Query ───────────────────────────────────────────────────────────────
def query_gsc_top_pages(access_token, site_url, start_date, end_date):
    """Query GSC Search Analytics for top pages by clicks+impressions."""
    api_url = f"https://www.googleapis.com/webmasters/v3/sites/{urllib.parse.quote(site_url, safe='')}/searchAnalytics/query"

    payload = {
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": ["page"],
        "rowLimit": 100,
        "startRow": 0,
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    req = urllib.request.Request(api_url, data=json.dumps(payload).encode(), headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"  GSC API error {e.code}: {e.read().decode()[:300]}")
        return {"rows": []}


def extract_slug_from_url(url, domain):
    """Extract the article slug from a full URL, ignoring locale prefixes."""
    # https://glow-coded.com/best-sunscreens/ -> best-sunscreens
    # https://glow-coded.com/es/best-sunscreens/ -> best-sunscreens
    pattern = rf"https?://{re.escape(domain)}/(?:[a-z]{{2}}/)?([^/]+)/"
    match = re.match(pattern, url)
    if match:
        return match.group(1)
    return None


def get_existing_slugs(blog_dir):
    """Get set of slugs that exist as published articles."""
    slugs = set()
    if not os.path.isdir(blog_dir):
        return slugs
    for fname in os.listdir(blog_dir):
        if fname.endswith(".mdx") or fname.endswith(".md"):
            slug = fname.rsplit(".", 1)[0]
            # Check it's not a draft
            fpath = os.path.join(blog_dir, fname)
            try:
                with open(fpath) as f:
                    content = f.read(500)
                    if "draft: true" not in content:
                        slugs.add(slug)
            except Exception:
                slugs.add(slug)
    return slugs


def score_page(row):
    """Score a page for featuring. Weighs clicks heavily, impressions as tiebreak."""
    clicks = row.get("clicks", 0)
    impressions = row.get("impressions", 0)
    ctr = row.get("ctr", 0)
    position = row.get("position", 100)

    # Primary: clicks (direct traffic value)
    # Secondary: impressions * CTR potential (pages ranking well but not yet clicked)
    # Bonus: good position (under 20) signals authority
    score = (clicks * 10) + (impressions * 0.5)
    if position < 10:
        score *= 1.5  # Top-10 boost
    elif position < 20:
        score *= 1.2

    return score


# ── Main ────────────────────────────────────────────────────────────────────
def update_site(site_key, access_token):
    """Update featured.json for a single site."""
    config = SITES[site_key]
    print(f"\n{'='*60}")
    print(f"  {site_key} ({config['domain']})")
    print(f"{'='*60}")

    # Date range
    end_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")  # GSC has 48h delay
    start_date = (datetime.now() - timedelta(days=LOOKBACK_DAYS + 2)).strftime("%Y-%m-%d")
    print(f"  GSC range: {start_date} to {end_date}")

    # Query GSC
    data = query_gsc_top_pages(access_token, config["gsc_site"], start_date, end_date)
    rows = data.get("rows", [])
    print(f"  GSC returned {len(rows)} pages")

    if not rows:
        print("  No data — skipping")
        return False

    # Get existing article slugs
    existing = get_existing_slugs(config["blog_dir"])
    print(f"  {len(existing)} published articles on disk")

    # Process and rank pages
    candidates = []
    seen_slugs = set()

    for row in rows:
        url = row["keys"][0]
        slug = extract_slug_from_url(url, config["domain"])

        if not slug:
            continue
        if slug in seen_slugs:
            continue  # Dedupe (same slug, different locale URLs)
        if slug not in existing:
            continue  # Skip pages that aren't articles (about, quiz, etc.)
        if row.get("impressions", 0) < MIN_IMPRESSIONS:
            continue

        seen_slugs.add(slug)
        candidates.append({
            "slug": slug,
            "clicks": int(row.get("clicks", 0)),
            "impressions": int(row.get("impressions", 0)),
            "ctr": round(row.get("ctr", 0), 4),
            "position": round(row.get("position", 0), 1),
            "score": score_page(row),
        })

    # Sort by score
    candidates.sort(key=lambda x: x["score"], reverse=True)

    # Pick top N
    trending = candidates[:TRENDING_COUNT]

    print(f"\n  Top {len(trending)} trending articles:")
    for i, item in enumerate(trending):
        print(f"    {i+1}. {item['slug']}")
        print(f"       clicks={item['clicks']} impr={item['impressions']} pos={item['position']} score={item['score']:.0f}")

    # Also identify "rising" articles: recent articles with good early traction
    # (Published in last 14 days with any impressions)
    rising = []
    for c in candidates[TRENDING_COUNT:]:
        # Check if article was published recently
        fpath = os.path.join(config["blog_dir"], f"{c['slug']}.mdx")
        if not os.path.exists(fpath):
            fpath = os.path.join(config["blog_dir"], f"{c['slug']}.md")
        if os.path.exists(fpath):
            try:
                with open(fpath) as f:
                    content = f.read(300)
                date_match = re.search(r"date:\s*(\d{4}-\d{2}-\d{2})", content)
                if date_match:
                    pub_date = datetime.strptime(date_match.group(1), "%Y-%m-%d")
                    days_old = (datetime.now() - pub_date).days
                    if days_old <= 14 and c["impressions"] >= 5:
                        rising.append({**c, "days_old": days_old})
            except Exception:
                pass

    rising.sort(key=lambda x: x["score"], reverse=True)
    rising = rising[:3]

    if rising:
        print(f"\n  Rising articles (published <14 days, getting traction):")
        for item in rising:
            print(f"    - {item['slug']} ({item['days_old']}d old, {item['impressions']} impr)")

    # Write featured.json
    os.makedirs(config["data_dir"], exist_ok=True)
    output = {
        "updated": datetime.now().strftime("%Y-%m-%d"),
        "period": f"{start_date} to {end_date}",
        "trending": [{"slug": t["slug"], "clicks": t["clicks"], "impressions": t["impressions"], "position": t["position"]} for t in trending],
        "rising": [{"slug": r["slug"], "clicks": r["clicks"], "impressions": r["impressions"], "days_old": r.get("days_old", 0)} for r in rising],
    }

    output_path = os.path.join(config["data_dir"], "featured.json")
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n  Wrote {output_path}")
    return True


def main():
    # Which sites to update
    target = sys.argv[1] if len(sys.argv) > 1 else None
    sites_to_update = [target] if target and target in SITES else list(SITES.keys())

    # Auth
    token_data = load_gsc_token()
    access_token = refresh_gsc_token(token_data)

    updated = 0
    for site_key in sites_to_update:
        if update_site(site_key, access_token):
            updated += 1

    print(f"\nDone — updated {updated}/{len(sites_to_update)} sites")


if __name__ == "__main__":
    main()
