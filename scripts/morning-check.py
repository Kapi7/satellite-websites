#!/usr/bin/env python3
"""Morning Check — GSC + Ahrefs + GA4 daily report for all sites."""

import json
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timedelta

# ── Config ──────────────────────────────────────────────────────────────────
GSC_TOKEN_FILE = "/Users/kapi7/.config/gsc-token.json"
GA4_PROPERTIES_FILE = "/Users/kapi7/.config/ga4-properties.json"
AHREFS_API_KEY = "bldAb-4QInmVjjFRldH6r-32VeDrIDnJQVReJhpw"

SITES = {
    "glow-coded.com": {"gsc": "sc-domain:glow-coded.com"},
    "rooted-glow.com": {"gsc": "sc-domain:rooted-glow.com"},
    "build-coded.com": {"gsc": "sc-domain:build-coded.com"},
    "mirai-skin.com": {"gsc": "sc-domain:mirai-skin.com"},
}

TODAY = datetime.now()
TODAY_STR = TODAY.strftime("%Y-%m-%d")

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
        err = e.read().decode()[:200]
        print(f"  GSC error {e.code}: {err}")
        return None

def ahrefs_get(endpoint, params):
    qs = urllib.parse.urlencode(params)
    url = f"https://api.ahrefs.com/v3/{endpoint}?{qs}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {AHREFS_API_KEY}"})
    try:
        resp = urllib.request.urlopen(req)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        print(f"  Ahrefs error {e.code}: {body}")
        return None

def ga4_request(access_token, property_id, body):
    url = f"https://analyticsdata.googleapis.com/v1beta/properties/{property_id}:runReport"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        resp = urllib.request.urlopen(req)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err = e.read().decode()[:200]
        print(f"  GA4 error {e.code}: {err}")
        return None

def fmt_num(n):
    """Format number with comma separators."""
    if isinstance(n, float):
        return f"{n:,.1f}"
    return f"{int(n):,}"

def pct_change(current, previous):
    """Return formatted percentage change string."""
    if not previous or previous == 0:
        return "  new"
    change = ((current - previous) / previous) * 100
    if change > 0:
        return f" +{change:.0f}%"
    elif change < 0:
        return f" {change:.0f}%"
    return "   0%"

# ── GSC Section ─────────────────────────────────────────────────────────────
def print_gsc(access_token, site_id, domain):
    print(f"\n  --- GSC Search Performance ---")

    base = f"https://www.googleapis.com/webmasters/v3/sites/{urllib.parse.quote(site_id, safe='')}"
    analytics_url = f"{base}/searchAnalytics/query"

    # This week (last 7 days, offset by 3 days for GSC data delay)
    end = (TODAY - timedelta(days=3)).strftime("%Y-%m-%d")
    start = (TODAY - timedelta(days=9)).strftime("%Y-%m-%d")
    # Previous week for comparison
    prev_end = (TODAY - timedelta(days=10)).strftime("%Y-%m-%d")
    prev_start = (TODAY - timedelta(days=16)).strftime("%Y-%m-%d")

    this_week = gsc_request(access_token, analytics_url, "POST", {"startDate": start, "endDate": end, "dimensions": []})
    prev_week = gsc_request(access_token, analytics_url, "POST", {"startDate": prev_start, "endDate": prev_end, "dimensions": []})

    if this_week and "rows" in this_week:
        r = this_week["rows"][0]
        clicks = r["clicks"]
        impr = r["impressions"]
        ctr = r["ctr"] * 100
        pos = r["position"]

        line = f"  Clicks: {fmt_num(clicks)}"
        if prev_week and "rows" in prev_week:
            pr = prev_week["rows"][0]
            line += f" ({pct_change(clicks, pr['clicks'])})"
        line += f"  |  Impressions: {fmt_num(impr)}"
        if prev_week and "rows" in prev_week:
            line += f" ({pct_change(impr, pr['impressions'])})"
        print(line)
        print(f"  CTR: {ctr:.1f}%  |  Avg Position: {pos:.1f}")
    else:
        print("  No search data yet")

    # Top 5 queries
    queries = gsc_request(access_token, analytics_url, "POST", {
        "startDate": start, "endDate": end,
        "dimensions": ["query"], "rowLimit": 5,
    })
    if queries and "rows" in queries:
        print(f"\n  Top queries:")
        print(f"  {'Query':<40} {'Clicks':>6} {'Impr':>7} {'CTR':>6} {'Pos':>5}")
        for r in queries["rows"]:
            q = r["keys"][0][:38]
            print(f"  {q:<40} {r['clicks']:>6.0f} {r['impressions']:>7.0f} {r['ctr']*100:>5.1f}% {r['position']:>5.1f}")

    # Top 5 pages
    pages = gsc_request(access_token, analytics_url, "POST", {
        "startDate": start, "endDate": end,
        "dimensions": ["page"], "rowLimit": 5,
    })
    if pages and "rows" in pages:
        print(f"\n  Top pages:")
        for r in pages["rows"]:
            path = r["keys"][0].replace(f"https://{domain}", "").replace(f"http://{domain}", "")
            if len(path) > 50:
                path = path[:47] + "..."
            print(f"  {path:<52} {r['clicks']:.0f}c  {r['impressions']:.0f}i")

    # Index coverage — sitemaps
    sitemaps_url = f"{base}/sitemaps"
    sitemaps = gsc_request(access_token, sitemaps_url)
    if sitemaps and "sitemap" in sitemaps:
        total_submitted = 0
        total_indexed = 0
        for sm in sitemaps["sitemap"]:
            for c in sm.get("contents", []):
                total_submitted += int(c.get("submitted", 0) or 0)
                total_indexed += int(c.get("indexed", 0) or 0)
        if total_submitted:
            print(f"\n  Index: {total_indexed}/{total_submitted} pages ({total_indexed/total_submitted*100:.0f}%)")

# ── Ahrefs Section ──────────────────────────────────────────────────────────
def print_ahrefs(domain):
    print(f"\n  --- Ahrefs ---")

    # Domain Rating
    dr = ahrefs_get("site-explorer/domain-rating", {"target": domain, "date": TODAY_STR})
    if dr:
        inner = dr.get("domain_rating", dr)
        if isinstance(inner, dict):
            print(f"  DR: {inner.get('domain_rating', '?')}  |  Ahrefs Rank: {fmt_num(inner.get('ahrefs_rank', 0))}")
        else:
            print(f"  DR: {inner}")

    # Backlinks
    bl = ahrefs_get("site-explorer/backlinks-stats", {"target": domain, "date": TODAY_STR})
    if bl:
        stats = bl.get("metrics") or bl
        if isinstance(stats, dict):
            live = stats.get("live", "?")
            ref = stats.get("live_refdomains", stats.get("refdomains", "?"))
            print(f"  Backlinks: {fmt_num(live) if isinstance(live, (int,float)) else live} live  |  Ref domains: {fmt_num(ref) if isinstance(ref, (int,float)) else ref}")

    # Top organic keywords
    ok = ahrefs_get("site-explorer/organic-keywords", {
        "target": domain, "country": "us",
        "select": "keyword,volume,best_position",
        "limit": 5, "order_by": "volume:desc",
        "date": TODAY_STR,
    })
    if ok and "keywords" in ok:
        print(f"\n  Top organic keywords:")
        print(f"  {'Keyword':<40} {'Vol':>6} {'Pos':>5}")
        for kw in ok["keywords"]:
            print(f"  {kw['keyword'][:38]:<40} {kw.get('volume',0):>6} {kw.get('best_position','?'):>5}")

# ── GA4 Section ─────────────────────────────────────────────────────────────
def print_ga4(access_token, property_id, domain):
    print(f"\n  --- GA4 Traffic ---")

    end = (TODAY - timedelta(days=1)).strftime("%Y-%m-%d")
    start = (TODAY - timedelta(days=7)).strftime("%Y-%m-%d")
    prev_end = (TODAY - timedelta(days=8)).strftime("%Y-%m-%d")
    prev_start = (TODAY - timedelta(days=14)).strftime("%Y-%m-%d")

    body = {
        "dateRanges": [
            {"startDate": start, "endDate": end},
            {"startDate": prev_start, "endDate": prev_end},
        ],
        "metrics": [
            {"name": "sessions"},
            {"name": "activeUsers"},
            {"name": "screenPageViews"},
            {"name": "averageSessionDuration"},
            {"name": "bounceRate"},
        ],
    }

    result = ga4_request(access_token, property_id, body)
    if not result or "rows" not in result:
        print("  No GA4 data yet")
        return

    # First row = current period, with comparison
    row = result["rows"][0]
    metrics = row.get("metricValues", [])
    if len(metrics) >= 10:  # 5 metrics * 2 date ranges
        sessions = float(metrics[0]["value"])
        users = float(metrics[1]["value"])
        pageviews = float(metrics[2]["value"])
        avg_dur = float(metrics[3]["value"])
        bounce = float(metrics[4]["value"]) * 100

        prev_sessions = float(metrics[5]["value"])
        prev_users = float(metrics[6]["value"])
        prev_pageviews = float(metrics[7]["value"])

        print(f"  Sessions: {fmt_num(sessions)} ({pct_change(sessions, prev_sessions)})")
        print(f"  Users: {fmt_num(users)} ({pct_change(users, prev_users)})")
        print(f"  Pageviews: {fmt_num(pageviews)} ({pct_change(pageviews, prev_pageviews)})")
        print(f"  Avg Duration: {avg_dur:.0f}s  |  Bounce: {bounce:.1f}%")
    elif len(metrics) >= 5:
        sessions = float(metrics[0]["value"])
        users = float(metrics[1]["value"])
        pageviews = float(metrics[2]["value"])
        avg_dur = float(metrics[3]["value"])
        bounce = float(metrics[4]["value"]) * 100
        print(f"  Sessions: {fmt_num(sessions)}  |  Users: {fmt_num(users)}  |  Pageviews: {fmt_num(pageviews)}")
        print(f"  Avg Duration: {avg_dur:.0f}s  |  Bounce: {bounce:.1f}%")

    # Traffic by channel — reconciles GA4 vs GSC (Organic Search slice = GSC comparable)
    channel_body = {
        "dateRanges": [{"startDate": start, "endDate": end}],
        "dimensions": [{"name": "sessionDefaultChannelGroup"}],
        "metrics": [{"name": "sessions"}, {"name": "activeUsers"}, {"name": "engagedSessions"}],
        "limit": 10,
        "orderBys": [{"metric": {"metricName": "sessions"}, "desc": True}],
    }
    channel_result = ga4_request(access_token, property_id, channel_body)
    if channel_result and "rows" in channel_result:
        print(f"\n  By channel (7d):")
        print(f"  {'Channel':<22} {'Sessions':>9} {'Users':>7} {'Engaged':>8}")
        for r in channel_result["rows"]:
            ch = r["dimensionValues"][0]["value"] or "(not set)"
            sess = int(r["metricValues"][0]["value"])
            usrs = int(r["metricValues"][1]["value"])
            eng = int(r["metricValues"][2]["value"])
            print(f"  {ch[:20]:<22} {sess:>9} {usrs:>7} {eng:>8}")

    # Top pages by pageviews
    pages_body = {
        "dateRanges": [{"startDate": start, "endDate": end}],
        "dimensions": [{"name": "pagePath"}],
        "metrics": [{"name": "screenPageViews"}, {"name": "activeUsers"}],
        "limit": 5,
        "orderBys": [{"metric": {"metricName": "screenPageViews"}, "desc": True}],
    }
    pages_result = ga4_request(access_token, property_id, pages_body)
    if pages_result and "rows" in pages_result:
        print(f"\n  Top pages (GA4):")
        for r in pages_result["rows"]:
            path = r["dimensionValues"][0]["value"]
            if len(path) > 45:
                path = path[:42] + "..."
            pvs = int(r["metricValues"][0]["value"])
            users = int(r["metricValues"][1]["value"])
            print(f"  {path:<47} {pvs:>5} views  {users:>4} users")

# ── Main ────────────────────────────────────────────────────────────────────
def main():
    print("=" * 62)
    print(f"  MORNING CHECK — {TODAY.strftime('%A %B %d, %Y %H:%M')}")
    print("=" * 62)

    token_data = load_gsc_token()
    access_token = refresh_gsc_token(token_data)

    # Load GA4 properties
    try:
        with open(GA4_PROPERTIES_FILE) as f:
            ga4_props = json.load(f)
    except FileNotFoundError:
        ga4_props = {}

    for domain, cfg in SITES.items():
        print(f"\n{'='*62}")
        print(f"  {domain.upper()}")
        print(f"{'='*62}")

        print_gsc(access_token, cfg["gsc"], domain)
        print_ahrefs(domain)

        ga4_id = ga4_props.get(domain)
        if ga4_id:
            print_ga4(access_token, ga4_id, domain)

    print(f"\n{'='*62}")
    print(f"  Done — {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*62}")

if __name__ == "__main__":
    main()
