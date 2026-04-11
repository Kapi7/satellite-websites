#!/usr/bin/env python3
"""
Manual SEO morning brief — no Claude Agent SDK required.

Produces the same digest as morning_brief.py by directly running GSC
queries and the MDX content crawl in one Python process. Use this when
the Agent SDK orchestrator isn't working (e.g., on Mac Mini without the
Claude CLI logged in), or when you want to run the brief from a laptop.

Usage:
  python3 scripts/seo/manual_brief.py                    # all 3 sites, save + telegram
  python3 scripts/seo/manual_brief.py --skip-telegram    # dry run
  python3 scripts/seo/manual_brief.py --stdout           # print instead of writing file
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
import urllib.error
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = REPO_ROOT / "scripts" / "seo" / "reports"
NOTIFY_SCRIPT = REPO_ROOT / "scripts" / "notify.py"
GSC_TOKEN_FILE = Path(os.path.expanduser("~/.config/gsc-token.json"))

SITES = [
    ("glow-coded.com", "cosmetics", "sc-domain:glow-coded.com"),
    ("rooted-glow.com", "wellness", "sc-domain:rooted-glow.com"),
    ("mirai-skin.com", None, "sc-domain:mirai-skin.com"),  # no local repo
    ("build-coded.com", "build-coded", None),  # no GSC (not verified yet)
]


# ── GSC helpers (copied pattern from scripts/seo-dashboard.py) ───────────────

def load_gsc_token() -> dict:
    return json.loads(GSC_TOKEN_FILE.read_text())


def refresh_gsc_token(token_data: dict) -> str:
    expiry = datetime.fromisoformat(token_data["expiry"])
    if datetime.now() < expiry - timedelta(minutes=5):
        return token_data["token"]

    body = urllib.parse.urlencode({
        "client_id": token_data["client_id"],
        "client_secret": token_data["client_secret"],
        "refresh_token": token_data["refresh_token"],
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=body)
    resp = urllib.request.urlopen(req, timeout=15)
    result = json.loads(resp.read())
    token_data["token"] = result["access_token"]
    token_data["expiry"] = (datetime.now() + timedelta(seconds=result["expires_in"])).isoformat()
    GSC_TOKEN_FILE.write_text(json.dumps(token_data, indent=2))
    return result["access_token"]


def gsc_query(access_token: str, site_id: str, body: dict) -> dict | None:
    url = (
        "https://www.googleapis.com/webmasters/v3/sites/"
        f"{urllib.parse.quote(site_id, safe='')}/searchAnalytics/query"
    )
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"  GSC {site_id} error {e.code}: {e.read().decode()[:200]}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  GSC {site_id} error: {e}", file=sys.stderr)
        return None


def gsc_brief_for_site(access_token: str, site_id: str, domain: str) -> str:
    """Produce the structured GSC markdown block for one site."""
    today = datetime.now()
    end7 = today.strftime("%Y-%m-%d")
    start7 = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    end_prev = (today - timedelta(days=8)).strftime("%Y-%m-%d")
    start_prev = (today - timedelta(days=14)).strftime("%Y-%m-%d")
    end28 = end7
    start28 = (today - timedelta(days=28)).strftime("%Y-%m-%d")

    def tot(start: str, end: str) -> dict | None:
        rows = gsc_query(access_token, site_id, {
            "startDate": start, "endDate": end, "dimensions": []
        })
        if rows and rows.get("rows"):
            return rows["rows"][0]
        return None

    cur = tot(start7, end7) or {}
    prev = tot(start_prev, end_prev) or {}

    def fmt_delta(a: float, b: float, unit: str = "") -> str:
        if b == 0:
            return f"+{a:.0f}{unit}" if a else "0"
        pct = (a - b) / b * 100
        sign = "+" if pct >= 0 else ""
        return f"{sign}{pct:.1f}%"

    lines = [f"## {domain} · 7d vs prev 7d"]
    lines.append(
        f"Clicks: {int(prev.get('clicks', 0))} → {int(cur.get('clicks', 0))} "
        f"({fmt_delta(cur.get('clicks', 0), prev.get('clicks', 0))})"
    )
    lines.append(
        f"Impressions: {int(prev.get('impressions', 0))} → {int(cur.get('impressions', 0))} "
        f"({fmt_delta(cur.get('impressions', 0), prev.get('impressions', 0))})"
    )
    cur_ctr = cur.get("ctr", 0) * 100
    prev_ctr = prev.get("ctr", 0) * 100
    lines.append(f"CTR: {prev_ctr:.2f}% → {cur_ctr:.2f}% ({cur_ctr - prev_ctr:+.2f}pp)")
    cur_pos = cur.get("position", 0)
    prev_pos = prev.get("position", 0)
    lines.append(f"Avg pos: {prev_pos:.1f} → {cur_pos:.1f} ({prev_pos - cur_pos:+.1f})")

    # Top queries (28d)
    q28 = gsc_query(access_token, site_id, {
        "startDate": start28, "endDate": end28,
        "dimensions": ["query"], "rowLimit": 20
    })
    top_queries = (q28 or {}).get("rows", [])
    top_queries = sorted(top_queries, key=lambda r: r.get("clicks", 0), reverse=True)[:10]
    if top_queries:
        lines.append("")
        lines.append("### Top 10 queries (28d)")
        for r in top_queries:
            kw = r["keys"][0][:50]
            lines.append(
                f"- {kw} — {int(r['clicks'])} clicks / "
                f"{int(r['impressions'])} imp / pos {r['position']:.1f}"
            )

    # Striking distance (pos 8-20, >=100 imp, 28d)
    if q28 and q28.get("rows"):
        strikers = [
            r for r in q28["rows"]
            if 8 <= r.get("position", 0) <= 20 and r.get("impressions", 0) >= 100
        ]
        strikers.sort(key=lambda r: r["impressions"], reverse=True)
        if strikers:
            lines.append("")
            lines.append("### Striking distance (pos 8-20, ≥100 imp)")
            for r in strikers[:10]:
                lines.append(
                    f"- \"{r['keys'][0][:60]}\" — pos {r['position']:.1f} / "
                    f"{int(r['impressions'])} imp / {int(r['clicks'])} clicks"
                )

    # Top landing pages (28d)
    p28 = gsc_query(access_token, site_id, {
        "startDate": start28, "endDate": end28,
        "dimensions": ["page"], "rowLimit": 10
    })
    if p28 and p28.get("rows"):
        lines.append("")
        lines.append("### Top 10 landing pages (28d)")
        for r in p28["rows"]:
            path = r["keys"][0].replace(f"https://{domain}", "") or "/"
            lines.append(
                f"- {path[:70]} — {int(r['clicks'])} clicks / "
                f"{int(r['impressions'])} imp"
            )

    # Declining pages (7d vs prev 7d, >20% drop)
    cur_pages = gsc_query(access_token, site_id, {
        "startDate": start7, "endDate": end7,
        "dimensions": ["page"], "rowLimit": 200
    })
    prev_pages = gsc_query(access_token, site_id, {
        "startDate": start_prev, "endDate": end_prev,
        "dimensions": ["page"], "rowLimit": 200
    })
    if cur_pages and prev_pages:
        cur_map = {r["keys"][0]: r.get("clicks", 0) for r in cur_pages.get("rows", [])}
        prev_map = {r["keys"][0]: r.get("clicks", 0) for r in prev_pages.get("rows", [])}
        decliners = []
        for page, cur_clicks in cur_map.items():
            pc = prev_map.get(page, 0)
            if pc >= 5 and cur_clicks < pc * 0.8:
                decliners.append((page, pc, cur_clicks))
        decliners.sort(key=lambda t: t[1] - t[2], reverse=True)
        if decliners:
            lines.append("")
            lines.append("### Declining pages (>20% WoW, prev ≥5 clicks)")
            for page, pc, cc in decliners[:10]:
                path = page.replace(f"https://{domain}", "") or "/"
                lines.append(f"- {path[:70]} — {int(pc)} → {int(cc)} clicks")

    # New queries: last 7d impressions > 0, prev 28d impressions == 0
    q7 = gsc_query(access_token, site_id, {
        "startDate": start7, "endDate": end7,
        "dimensions": ["query"], "rowLimit": 500
    })
    q_prev28 = gsc_query(access_token, site_id, {
        "startDate": (today - timedelta(days=35)).strftime("%Y-%m-%d"),
        "endDate": (today - timedelta(days=8)).strftime("%Y-%m-%d"),
        "dimensions": ["query"], "rowLimit": 1000
    })
    if q7 and q_prev28:
        prev_set = {r["keys"][0] for r in q_prev28.get("rows", [])}
        new_queries = [
            r for r in q7.get("rows", [])
            if r["keys"][0] not in prev_set and r.get("impressions", 0) >= 5
        ]
        new_queries.sort(key=lambda r: r.get("impressions", 0), reverse=True)
        if new_queries:
            lines.append("")
            lines.append("### New queries (7d, not seen in prior 28d, ≥5 imp)")
            for r in new_queries[:10]:
                lines.append(
                    f"- \"{r['keys'][0][:60]}\" — "
                    f"{int(r['impressions'])} imp / {int(r['clicks'])} clicks"
                )

    return "\n".join(lines)


# ── Content crawler ──────────────────────────────────────────────────────────

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_frontmatter(text: str) -> tuple[dict, str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm_text = m.group(1)
    fm: dict = {}
    for line in fm_text.splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        fm[k] = v
    return fm, text[m.end():]


def word_count(body: str) -> int:
    # Strip import lines, code blocks, HTML tags, MDX components
    body = re.sub(r"```.*?```", "", body, flags=re.DOTALL)
    body = re.sub(r"<[^>]+>", " ", body)
    body = re.sub(r"\{[^}]*\}", " ", body)
    body = re.sub(r"[#*_\[\]()`]", " ", body)
    return len(body.split())


def crawl_site(site_dir: str, domain: str) -> str:
    blog_en = REPO_ROOT / site_dir / "src" / "content" / "blog" / "en"
    if not blog_en.is_dir():
        return f"## {site_dir} / {domain} audit\n(no en/ content dir)"

    files = sorted(blog_en.glob("*.mdx"))
    if not files:
        return f"## {site_dir} / {domain} audit\nTotal MDX (en): 0"

    articles = []
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        fm, body = parse_frontmatter(text)
        articles.append({
            "slug": f.stem,
            "path": f,
            "fm": fm,
            "body": body,
            "words": word_count(body),
        })

    # Inventory
    total = len(articles)
    type_ct = Counter(a["fm"].get("type", "unknown") for a in articles)
    cat_ct = Counter(a["fm"].get("category", "unknown") for a in articles)
    dates = [a["fm"].get("date", "") for a in articles if a["fm"].get("date")]
    dates = [d for d in dates if re.match(r"\d{4}-\d{2}-\d{2}", d)]
    oldest = min(dates) if dates else "?"
    newest = max(dates) if dates else "?"

    # Orphans: slugs never referenced (/slug/) by any other file in the collection
    all_body = "\n".join(a["body"] for a in articles)
    orphans = []
    for a in articles:
        pattern = f"/{a['slug']}/"
        # Count occurrences in OTHER articles (exclude self-mentions)
        other_bodies = "\n".join(x["body"] for x in articles if x["slug"] != a["slug"])
        if pattern not in other_bodies:
            orphans.append(a)
    # Sort by date desc (newest first), show 10
    orphans.sort(key=lambda a: a["fm"].get("date", ""), reverse=True)
    orphans = [a for a in orphans if a["fm"].get("draft") != "true"]

    # Thin content (<800 words), exclude drafts
    thin = [a for a in articles if a["words"] < 800 and a["fm"].get("draft") != "true"]
    thin.sort(key=lambda a: a["words"])

    # Missing frontmatter
    required = ["description", "image", "imageAlt", "author", "tags"]
    missing = []
    for a in articles:
        gaps = [k for k in required if not a["fm"].get(k)]
        if gaps:
            missing.append((a["slug"], gaps))

    # Missing FAQ blocks
    no_faq = []
    for a in articles:
        if "## Frequently Asked Questions" not in a["body"] and "## FAQ" not in a["body"]:
            no_faq.append(a)

    # Hub coverage
    hubs = [a for a in articles if a["fm"].get("type") == "hub"]
    hub_coverage = []
    for h in hubs:
        inbound = sum(1 for x in articles if x["slug"] != h["slug"] and f"/{h['slug']}/" in x["body"])
        outbound = len(re.findall(r"/([a-z0-9-]+)/", h["body"]))
        health = "HEALTHY" if inbound >= 5 and outbound >= 5 else "WEAK"
        hub_coverage.append((h["slug"], inbound, outbound, health))

    # Drafts
    drafts = [a for a in articles if a["fm"].get("draft") == "true"]

    # Build markdown
    lines = [f"## {site_dir} / {domain} audit"]
    lines.append(f"Total MDX (en): {total}  (drafts: {len(drafts)})")
    type_s = " · ".join(f"{k} {v}" for k, v in type_ct.most_common())
    cat_s = " · ".join(f"{k} {v}" for k, v in cat_ct.most_common())
    lines.append(f"By type: {type_s}")
    lines.append(f"By category: {cat_s}")
    lines.append(f"Date range: {oldest} → {newest}")

    if orphans:
        lines.append("")
        lines.append(f"### Orphans ({len(orphans)} total, 10 newest)")
        for a in orphans[:10]:
            title = a["fm"].get("title", "")[:60]
            date = a["fm"].get("date", "")
            lines.append(f"- {a['slug']} · \"{title}\" ({date})")

    if thin:
        lines.append("")
        lines.append(f"### Thin content <800 words ({len(thin)} total)")
        for a in thin[:10]:
            lines.append(f"- {a['slug']} · {a['words']} words")

    if missing:
        lines.append("")
        lines.append(f"### Missing frontmatter ({len(missing)} total)")
        for slug, gaps in missing[:10]:
            lines.append(f"- {slug} · missing: {', '.join(gaps)}")

    if no_faq:
        lines.append("")
        lines.append(f"### Missing FAQ blocks ({len(no_faq)} total, 10 shown)")
        for a in no_faq[:10]:
            title = a["fm"].get("title", "")[:60]
            lines.append(f"- {a['slug']} · \"{title}\"")

    if hub_coverage:
        lines.append("")
        lines.append("### Hub coverage")
        for slug, inb, outb, health in hub_coverage:
            lines.append(f"- {slug} · in: {inb} · out: {outb} · {health}")

    if drafts:
        lines.append("")
        lines.append(f"### Drafts pending ({len(drafts)} total)")
        for a in drafts[:10]:
            lines.append(f"- {a['slug']}")

    return "\n".join(lines)


# ── Telegram notification ────────────────────────────────────────────────────

def load_dotenv() -> None:
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def notify_telegram(title: str, body: str) -> None:
    if not NOTIFY_SCRIPT.exists():
        print(f"notify: {NOTIFY_SCRIPT} not found, skipping", file=sys.stderr)
        return
    if not os.getenv("TELEGRAM_BOT_TOKEN") or not os.getenv("TELEGRAM_CHAT_ID"):
        print("notify: TELEGRAM_BOT_TOKEN/CHAT_ID not set, skipping", file=sys.stderr)
        return
    try:
        subprocess.run(
            [sys.executable, str(NOTIFY_SCRIPT), "--stdin",
             "--level", "report", "--title", title],
            input=body, text=True, check=True, timeout=20,
        )
    except Exception as e:
        print(f"notify: send failed ({e})", file=sys.stderr)


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Manual SEO morning brief (no Agent SDK).")
    parser.add_argument("--skip-telegram", action="store_true")
    parser.add_argument("--stdout", action="store_true", help="Print to stdout instead of saving")
    parser.add_argument("--skip-gsc", action="store_true")
    parser.add_argument("--skip-crawler", action="store_true")
    args = parser.parse_args()

    load_dotenv()
    today = datetime.now().strftime("%Y-%m-%d")

    gsc_blocks: list[str] = []
    if not args.skip_gsc:
        try:
            token_data = load_gsc_token()
            access_token = refresh_gsc_token(token_data)
        except Exception as e:
            gsc_blocks.append(f"(GSC auth failed: {e})")
            access_token = None
        if access_token:
            for domain, _site_dir, gsc_id in SITES:
                if not gsc_id:
                    continue
                print(f"[gsc] {domain} …")
                try:
                    gsc_blocks.append(gsc_brief_for_site(access_token, gsc_id, domain))
                except Exception as e:
                    gsc_blocks.append(f"## {domain}\n(error: {e})")

    crawler_blocks: list[str] = []
    if not args.skip_crawler:
        for domain, site_dir, _gsc_id in SITES:
            if not site_dir:
                continue
            print(f"[crawl] {site_dir} …")
            try:
                crawler_blocks.append(crawl_site(site_dir, domain))
            except Exception as e:
                crawler_blocks.append(f"## {site_dir}\n(error: {e})")

    digest = (
        f"# SEO morning brief · {today}\n\n"
        f"## GSC findings\n\n"
        + "\n\n".join(gsc_blocks) + "\n\n"
        f"---\n\n"
        f"## Content inventory\n\n"
        + "\n\n".join(crawler_blocks) + "\n"
    )

    if args.stdout:
        print(digest)
    else:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        out = REPORTS_DIR / f"{today}-morning.md"
        out.write_text(digest)
        print(f"[ok] wrote {out.relative_to(REPO_ROOT)}")

    if not args.skip_telegram:
        summary = (
            f"Morning brief ready for {len(gsc_blocks)} GSC sites + "
            f"{len(crawler_blocks)} repos.\n"
            f"scripts/seo/reports/{today}-morning.md"
        )
        notify_telegram(f"SEO morning brief · {today}", summary)

    return 0


if __name__ == "__main__":
    sys.exit(main())
