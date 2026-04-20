#!/usr/bin/env python3
"""Weekly SEO Report — GSC + Ahrefs + Bing with week-over-week deltas.

Runs every Monday at 8 AM via cron:
  0 8 * * 1 /opt/homebrew/bin/python3 /Users/kapi7/satellite-websites/scripts/weekly-report.py

Saves to scripts/reports/YYYY-MM-DD.txt and prints to stdout.
"""

import json
import os
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timedelta

# ── Config ──────────────────────────────────────────────────────────────────
GSC_TOKEN_FILE = os.environ.get("GSC_TOKEN_FILE", os.path.expanduser("~/.config/gsc-token.json"))
AHREFS_API_KEY = os.environ.get("AHREFS_API_KEY", "bldAb-4QInmVjjFRldH6r-32VeDrIDnJQVReJhpw")
BING_API_KEY = os.environ.get("BING_API_KEY", "282fd9e402f641b9a21fe8c171b6925e")
GA4_SERVICE_ACCOUNT_FILE = os.environ.get(
    "GA4_SERVICE_ACCOUNT_FILE",
    os.path.expanduser("~/.config/ga4-service-account.json"),
)
REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")

# Set GA4 property IDs via env or edit here (numeric string like "123456789").
SITES = {
    "glow-coded.com": {
        "gsc": "sc-domain:glow-coded.com",
        "url": "https://glow-coded.com",
        "ga4": os.environ.get("GA4_PROPERTY_GLOW_CODED", ""),
    },
    "rooted-glow.com": {
        "gsc": "sc-domain:rooted-glow.com",
        "url": "https://rooted-glow.com",
        "ga4": os.environ.get("GA4_PROPERTY_ROOTED_GLOW", ""),
    },
    "build-coded.com": {
        "gsc": "sc-domain:build-coded.com",
        "url": "https://build-coded.com",
        "ga4": os.environ.get("GA4_PROPERTY_BUILD_CODED", ""),
    },
}

# Referral hosts known to be AI assistants / chatbots.
AI_REFERRER_HOSTS = {
    "chatgpt.com": "ChatGPT",
    "chat.openai.com": "ChatGPT (legacy)",
    "openai.com": "OpenAI",
    "perplexity.ai": "Perplexity",
    "www.perplexity.ai": "Perplexity",
    "gemini.google.com": "Gemini",
    "bard.google.com": "Gemini (legacy Bard)",
    "claude.ai": "Claude",
    "copilot.microsoft.com": "Copilot",
    "bing.com": "Bing (incl. Copilot chat)",
    "www.bing.com": "Bing (incl. Copilot chat)",
    "you.com": "You.com",
    "phind.com": "Phind",
    "poe.com": "Poe",
    "duckduckgo.com": "DuckDuckGo (incl. DuckAssist)",
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

def api_get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        resp = urllib.request.urlopen(req)
        return json.loads(resp.read())
    except urllib.error.HTTPError:
        return None

def gsc_query(access_token, site_id, start, end, dimensions=None, row_limit=10):
    url = f"https://www.googleapis.com/webmasters/v3/sites/{urllib.parse.quote(site_id, safe='')}/searchAnalytics/query"
    body = {"startDate": start, "endDate": end, "dimensions": dimensions or [], "rowLimit": row_limit}
    data = json.dumps(body).encode()
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        resp = urllib.request.urlopen(req)
        return json.loads(resp.read())
    except urllib.error.HTTPError:
        return None

def ahrefs_get(endpoint, params):
    params["date"] = TODAY
    url = f"https://api.ahrefs.com/v3/{endpoint}?" + urllib.parse.urlencode(params)
    return api_get(url, {"Authorization": f"Bearer {AHREFS_API_KEY}"})

def bing_get(endpoint, site_url):
    url = f"https://ssl.bing.com/webmaster/api.svc/json/{endpoint}?apikey={BING_API_KEY}&siteUrl={urllib.parse.quote(site_url, safe='')}"
    return api_get(url)

def delta_str(current, previous):
    if previous is None or current is None:
        return ""
    diff = current - previous
    if diff > 0:
        return f" ▲ +{diff:.1f}" if isinstance(diff, float) else f" ▲ +{diff}"
    elif diff < 0:
        return f" ▼ {diff:.1f}" if isinstance(diff, float) else f" ▼ {diff}"
    return " ─ 0"

def load_previous_report():
    if not os.path.exists(REPORTS_DIR):
        return None
    files = sorted(f for f in os.listdir(REPORTS_DIR) if f.endswith(".json"))
    if not files:
        return None
    with open(os.path.join(REPORTS_DIR, files[-1])) as f:
        return json.load(f)

# ── Report Sections ─────────────────────────────────────────────────────────
def gsc_section(access_token, site_id, domain, prev_data):
    lines = []
    lines.append(f"\n  GSC — {domain}")
    lines.append(f"  {'─'*50}")

    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    prev_end = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    prev_start = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")

    this_week = gsc_query(access_token, site_id, start, end)
    last_week = gsc_query(access_token, site_id, prev_start, prev_end)

    data = {}
    if this_week and "rows" in this_week:
        r = this_week["rows"][0]
        clicks, impr = r["clicks"], r["impressions"]
        ctr, pos = r["ctr"] * 100, r["position"]
        data = {"clicks": clicks, "impressions": impr, "ctr": ctr, "position": pos}

        prev = {}
        if last_week and "rows" in last_week:
            p = last_week["rows"][0]
            prev = {"clicks": p["clicks"], "impressions": p["impressions"],
                     "ctr": p["ctr"] * 100, "position": p["position"]}

        lines.append(f"  Clicks:      {clicks:.0f}{delta_str(clicks, prev.get('clicks'))}")
        lines.append(f"  Impressions: {impr:.0f}{delta_str(impr, prev.get('impressions'))}")
        lines.append(f"  CTR:         {ctr:.1f}%{delta_str(ctr, prev.get('ctr'))}")
        lines.append(f"  Position:    {pos:.1f}{delta_str(pos, prev.get('position'))}")
    else:
        lines.append("  No data yet")

    queries = gsc_query(access_token, site_id, start, end, ["query"], 10)
    if queries and "rows" in queries:
        lines.append(f"\n  Top Queries:")
        lines.append(f"  {'Query':<40} {'Clicks':>6} {'Impr':>6} {'CTR':>6} {'Pos':>5}")
        for r in queries["rows"]:
            lines.append(f"  {r['keys'][0][:38]:<40} {r['clicks']:>6.0f} "
                         f"{r['impressions']:>6.0f} {r['ctr']*100:>5.1f}% {r['position']:>5.1f}")

    return "\n".join(lines), data

def ahrefs_section(domain, prev_data):
    lines = []
    lines.append(f"\n  Ahrefs — {domain}")
    lines.append(f"  {'─'*50}")

    data = {}

    dr = ahrefs_get("site-explorer/domain-rating", {"target": domain})
    if dr:
        inner = dr.get("domain_rating", dr)
        if isinstance(inner, dict):
            dr_val = inner.get("domain_rating", 0)
            rank = inner.get("ahrefs_rank", "?")
            data["dr"] = dr_val
            prev_dr = prev_data.get("dr") if prev_data else None
            lines.append(f"  DR:          {dr_val}{delta_str(dr_val, prev_dr)}")
            lines.append(f"  Ahrefs Rank: {rank}")

    bl = ahrefs_get("site-explorer/backlinks-stats", {"target": domain})
    if bl:
        stats = bl.get("metrics") or bl
        if not isinstance(stats, dict):
            stats = {}
        live = stats.get("live", 0)
        refdoms = stats.get("live_refdomains", stats.get("refdomains", 0))
        data["backlinks"] = live
        data["refdomains"] = refdoms
        prev_bl = prev_data.get("backlinks") if prev_data else None
        prev_rd = prev_data.get("refdomains") if prev_data else None
        lines.append(f"  Backlinks:   {live}{delta_str(live, prev_bl)}")
        lines.append(f"  Ref Domains: {refdoms}{delta_str(refdoms, prev_rd)}")

    ok = ahrefs_get("site-explorer/organic-keywords", {
        "target": domain, "country": "us",
        "select": "keyword,volume",
        "limit": 5, "order_by": "volume:desc",
    })
    if ok and "keywords" in ok:
        data["organic_kw_count"] = len(ok["keywords"])
        lines.append(f"\n  Top Organic Keywords:")
        for kw in ok["keywords"]:
            lines.append(f"    {kw['keyword'][:45]:<47} vol: {kw.get('volume', 0)}")

    return "\n".join(lines), data

def ga4_access_token():
    """Return a token for the GA4 Data API.

    Prefers the existing GSC OAuth token (~/.config/gsc-token.json) because
    it already has the analytics.readonly scope. Falls back to a service
    account JSON if GSC_TOKEN_FILE is missing scope or not present.
    """
    try:
        td = json.load(open(GSC_TOKEN_FILE))
    except (FileNotFoundError, json.JSONDecodeError):
        td = None
    if td and "analytics.readonly" in " ".join(td.get("scopes", [])):
        return refresh_gsc_token(td)

    if not os.path.exists(GA4_SERVICE_ACCOUNT_FILE):
        return None
    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
    except ImportError:
        return None
    scopes = ["https://www.googleapis.com/auth/analytics.readonly"]
    creds = service_account.Credentials.from_service_account_file(
        GA4_SERVICE_ACCOUNT_FILE, scopes=scopes
    )
    creds.refresh(Request())
    return creds.token

def ga4_run_report(access_token, property_id, body):
    url = f"https://analyticsdata.googleapis.com/v1beta/properties/{property_id}:runReport"
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"_error": f"{e.code} {e.reason}: {e.read()[:200].decode('utf-8', 'replace')}"}

def ga4_section(access_token, domain, property_id):
    lines = []
    lines.append(f"\n  GA4 — {domain}")
    lines.append(f"  {'─'*50}")

    if not access_token:
        lines.append("  (GA4 not configured: drop service-account JSON at")
        lines.append(f"   {GA4_SERVICE_ACCOUNT_FILE} and set GA4_PROPERTY_* env vars)")
        return "\n".join(lines), {}
    if not property_id:
        lines.append("  (no GA4_PROPERTY_* env var set for this site)")
        return "\n".join(lines), {}

    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    totals = ga4_run_report(access_token, property_id, {
        "dateRanges": [{"startDate": start, "endDate": end}],
        "metrics": [
            {"name": "sessions"},
            {"name": "totalUsers"},
            {"name": "engagedSessions"},
        ],
    })
    data = {}
    if totals and "rows" in totals and totals["rows"]:
        row = totals["rows"][0]["metricValues"]
        sessions = int(row[0]["value"])
        users = int(row[1]["value"])
        engaged = int(row[2]["value"])
        data.update(sessions=sessions, users=users, engaged=engaged)
        lines.append(f"  Sessions:   {sessions}   Users: {users}   Engaged: {engaged}")
    elif totals and "_error" in totals:
        lines.append(f"  API error: {totals['_error']}")
        return "\n".join(lines), data

    channels = ga4_run_report(access_token, property_id, {
        "dateRanges": [{"startDate": start, "endDate": end}],
        "dimensions": [{"name": "sessionDefaultChannelGroup"}],
        "metrics": [{"name": "sessions"}],
        "orderBys": [{"metric": {"metricName": "sessions"}, "desc": True}],
    })
    if channels and "rows" in channels:
        lines.append("  Channels:")
        for r in channels["rows"][:6]:
            ch = r["dimensionValues"][0]["value"]
            s = int(r["metricValues"][0]["value"])
            lines.append(f"    {ch[:30]:<32} {s:>6}")

    ai = ga4_run_report(access_token, property_id, {
        "dateRanges": [{"startDate": start, "endDate": end}],
        "dimensions": [{"name": "sessionSource"}],
        "metrics": [{"name": "sessions"}, {"name": "engagedSessions"}],
        "orderBys": [{"metric": {"metricName": "sessions"}, "desc": True}],
        "limit": 200,
    })
    ai_total = 0
    ai_rows = []
    if ai and "rows" in ai:
        for r in ai["rows"]:
            src = r["dimensionValues"][0]["value"].lower().strip()
            matched = next((label for host, label in AI_REFERRER_HOSTS.items() if host in src), None)
            if matched:
                s = int(r["metricValues"][0]["value"])
                eg = int(r["metricValues"][1]["value"])
                ai_rows.append((matched, src, s, eg))
                ai_total += s
    data["ai_sessions"] = ai_total
    data["ai_sources"] = [{"label": lbl, "source": src, "sessions": s, "engaged": eg}
                          for lbl, src, s, eg in ai_rows]
    lines.append(f"  AI referrals: {ai_total} sessions")
    if ai_rows:
        for label, src, s, eg in ai_rows[:8]:
            lines.append(f"    {label} ({src})  sessions: {s}  engaged: {eg}")
    else:
        lines.append("    (no AI-referral sessions this week)")

    return "\n".join(lines), data

def bing_section(domain):
    lines = []
    lines.append(f"\n  Bing — {domain}")
    lines.append(f"  {'─'*50}")

    url = f"https://{domain}/"

    stats = bing_get("GetCrawlStats", url)
    if stats and "d" in stats:
        d = stats["d"]
        if isinstance(d, list) and d:
            latest = d[0]
            lines.append(f"  Crawled: {latest.get('CrawledPages', '?')}  |  "
                         f"Indexed: {latest.get('InIndex', '?')}")
        elif isinstance(d, dict):
            lines.append(f"  Crawl data: {json.dumps(d)[:100]}")
    else:
        lines.append("  No crawl data")

    quota = bing_get("GetUrlSubmissionQuota", url)
    if quota and "d" in quota:
        d = quota["d"]
        lines.append(f"  Daily quota left: {d.get('DailyQuota', '?')}  |  "
                     f"Monthly: {d.get('MonthlyQuota', '?')}")

    return "\n".join(lines)

# ── Main ────────────────────────────────────────────────────────────────────
def main():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    prev = load_previous_report()

    output = []
    output.append("=" * 60)
    output.append("  WEEKLY SEO REPORT")
    output.append(f"  Week of {TODAY}")
    output.append("=" * 60)

    token_data = load_gsc_token()
    access_token = refresh_gsc_token(token_data)
    ga4_token = ga4_access_token()

    report_data = {}

    for domain, cfg in SITES.items():
        output.append(f"\n{'='*60}")
        output.append(f"  {domain.upper()}")
        output.append(f"{'='*60}")

        prev_site = prev.get(domain, {}) if prev else {}

        gsc_text, gsc_data = gsc_section(access_token, cfg["gsc"], domain,
                                          prev_site.get("gsc"))
        output.append(gsc_text)

        ahrefs_text, ahrefs_data = ahrefs_section(domain, prev_site.get("ahrefs"))
        output.append(ahrefs_text)

        ga4_text, ga4_data = ga4_section(ga4_token, domain, cfg.get("ga4", ""))
        output.append(ga4_text)

        bing_text = bing_section(domain)
        output.append(bing_text)

        report_data[domain] = {"gsc": gsc_data, "ahrefs": ahrefs_data, "ga4": ga4_data}

    output.append(f"\n{'='*60}")
    output.append(f"  Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    output.append(f"{'='*60}")

    report_text = "\n".join(output)

    report_file = os.path.join(REPORTS_DIR, f"{TODAY}.txt")
    with open(report_file, "w") as f:
        f.write(report_text)

    json_file = os.path.join(REPORTS_DIR, f"{TODAY}.json")
    with open(json_file, "w") as f:
        json.dump(report_data, f, indent=2)

    print(report_text)
    print(f"\n  Saved to: {report_file}")

if __name__ == "__main__":
    main()
