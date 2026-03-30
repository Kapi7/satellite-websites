#!/usr/bin/env python3
"""SEO Dashboard — GSC + Ahrefs + Bing Webmaster combined view."""

import json
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timedelta

# ── Config ──────────────────────────────────────────────────────────────────
GSC_TOKEN_FILE = "/Users/kapi7/.config/gsc-token.json"
AHREFS_API_KEY = "bldAb-4QInmVjjFRldH6r-32VeDrIDnJQVReJhpw"
BING_API_KEY = "282fd9e402f641b9a21fe8c171b6925e"

SITES = {
    "glow-coded.com": {
        "gsc": "sc-domain:glow-coded.com",
        "url": "https://glow-coded.com",
    },
    "rooted-glow.com": {
        "gsc": "sc-domain:rooted-glow.com",
        "url": "https://rooted-glow.com",
    },
}

TODAY = datetime.now().strftime("%Y-%m-%d")

# ── Helpers ─────────────────────────────────────────────────────────────────
def load_gsc_token():
    with open(GSC_TOKEN_FILE) as f:
        return json.load(f)

def refresh_gsc_token(token_data):
    expiry = datetime.fromisoformat(token_data["expiry"])
    if datetime.now() < expiry:
        return token_data["token"]

    print("  [GSC] Token expired, refreshing...")
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

def gsc_request(access_token, url, method="GET", body=None):
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"  GSC error {e.code}: {e.read().decode()[:200]}")
        return None

def ahrefs_get(endpoint, params):
    params["date"] = TODAY
    url = f"https://api.ahrefs.com/v3/{endpoint}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {AHREFS_API_KEY}"})
    try:
        resp = urllib.request.urlopen(req)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        print(f"  Ahrefs error {e.code}: {body}")
        return None

def bing_request(endpoint, site_url):
    url = f"https://ssl.bing.com/webmaster/api.svc/json/{endpoint}?apikey={BING_API_KEY}&siteUrl={urllib.parse.quote(site_url, safe='')}"
    req = urllib.request.Request(url)
    try:
        resp = urllib.request.urlopen(req)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"  Bing error {e.code}: {e.read().decode()[:200]}")
        return None

# ── GSC Section ─────────────────────────────────────────────────────────────
def print_gsc(access_token, site_id, domain):
    print(f"\n{'─'*60}")
    print(f"  GSC — {domain}")
    print(f"{'─'*60}")

    sitemaps_url = f"https://www.googleapis.com/webmasters/v3/sites/{urllib.parse.quote(site_id, safe='')}/sitemaps"
    sitemaps = gsc_request(access_token, sitemaps_url)
    if sitemaps and "sitemap" in sitemaps:
        for sm in sitemaps["sitemap"]:
            submitted = sm.get("contents", [{}])[0].get("submitted", "?")
            indexed = sm.get("contents", [{}])[0].get("indexed", "?")
            print(f"  Sitemap: {sm['path']}  submitted={submitted}  indexed={indexed}")

    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    analytics_url = f"https://www.googleapis.com/webmasters/v3/sites/{urllib.parse.quote(site_id, safe='')}/searchAnalytics/query"

    totals = gsc_request(access_token, analytics_url, "POST", {"startDate": start, "endDate": end, "dimensions": []})
    if totals and "rows" in totals:
        r = totals["rows"][0]
        print(f"  7-day: {r['clicks']:.0f} clicks | {r['impressions']:.0f} impressions | CTR {r['ctr']*100:.1f}% | Pos {r['position']:.1f}")
    else:
        print("  7-day: no data yet")

    queries = gsc_request(access_token, analytics_url, "POST", {"startDate": start, "endDate": end, "dimensions": ["query"], "rowLimit": 10})
    if queries and "rows" in queries:
        print(f"\n  Top queries (7d):")
        print(f"  {'Query':<40} {'Clicks':>6} {'Impr':>6} {'CTR':>6} {'Pos':>5}")
        for r in queries["rows"]:
            print(f"  {r['keys'][0][:38]:<40} {r['clicks']:>6.0f} {r['impressions']:>6.0f} {r['ctr']*100:>5.1f}% {r['position']:>5.1f}")

    pages = gsc_request(access_token, analytics_url, "POST", {"startDate": start, "endDate": end, "dimensions": ["page"], "rowLimit": 10})
    if pages and "rows" in pages:
        print(f"\n  Top pages (7d):")
        for r in pages["rows"]:
            path = r["keys"][0].replace(f"https://{domain}", "")
            print(f"  {path:<50} {r['clicks']:.0f}c {r['impressions']:.0f}i")

# ── Ahrefs Section ──────────────────────────────────────────────────────────
def print_ahrefs(domain):
    print(f"\n{'─'*60}")
    print(f"  Ahrefs — {domain}")
    print(f"{'─'*60}")

    dr = ahrefs_get("site-explorer/domain-rating", {"target": domain})
    if dr:
        # Response: {"domain_rating": {"domain_rating": X, "ahrefs_rank": Y}}
        inner = dr.get("domain_rating", dr)
        if isinstance(inner, dict):
            print(f"  DR: {inner.get('domain_rating', '?')}  |  Ahrefs Rank: {inner.get('ahrefs_rank', '?')}")
        else:
            print(f"  DR: {inner}")

    bl = ahrefs_get("site-explorer/backlinks-stats", {"target": domain})
    if bl:
        # Response may nest under "stats" or be flat
        stats = bl.get("metrics", bl)
        print(f"  Backlinks: {stats.get('live', '?')} live / {stats.get('all_time', '?')} all-time  |  Ref domains: {stats.get('live_refdomains', stats.get('refdomains', '?'))}")

    ok = ahrefs_get("site-explorer/organic-keywords", {
        "target": domain, "country": "us",
        "select": "keyword,volume,cpc,keyword_difficulty",
        "limit": 10, "order_by": "volume:desc",
    })
    if ok and "keywords" in ok:
        print(f"\n  Top organic keywords:")
        print(f"  {'Keyword':<40} {'Vol':>6} {'CPC':>6} {'KD':>4}")
        for kw in ok["keywords"]:
            print(f"  {kw['keyword'][:38]:<40} {kw.get('volume',0):>6} ${kw.get('cpc',0):>.2f} {kw.get('keyword_difficulty',0):>4}")
    elif ok:
        print(f"  Raw response: {json.dumps(ok)[:200]}")

# ── Bing Section ────────────────────────────────────────────────────────────
def print_bing(domain):
    print(f"\n{'─'*60}")
    print(f"  Bing Webmaster — {domain}")
    print(f"{'─'*60}")

    url = f"https://{domain}/"

    stats = bing_request("GetCrawlStats", url)
    if stats and "d" in stats:
        d = stats["d"]
        if isinstance(d, list) and d:
            latest = d[0]
            print(f"  Crawled: {latest.get('CrawledPages', '?')}  |  In index: {latest.get('InIndex', '?')}")
        elif isinstance(d, dict):
            print(f"  Crawl data: {json.dumps(d)[:120]}")

    quota = bing_request("GetUrlSubmissionQuota", url)
    if quota and "d" in quota:
        d = quota["d"]
        print(f"  Daily quota remaining: {d.get('DailyQuota', '?')}  |  Monthly: {d.get('MonthlyQuota', '?')}")

# ── Main ────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  SEO DASHBOARD")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    token_data = load_gsc_token()
    access_token = refresh_gsc_token(token_data)

    for domain, cfg in SITES.items():
        print(f"\n{'='*60}")
        print(f"  {domain.upper()}")
        print(f"{'='*60}")
        print_gsc(access_token, cfg["gsc"], domain)
        print_ahrefs(domain)
        print_bing(domain)

    print(f"\n{'='*60}")
    print("  Done.")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
