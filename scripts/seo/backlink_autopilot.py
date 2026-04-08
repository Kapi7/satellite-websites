#!/usr/bin/env python3
"""
Backlink Autopilot — Daily SEO automation for finding backlink opportunities
and drafting outreach emails.

Runs 5 modules sequentially:
  1. HARO/Connectively Monitor (IMAP)
  2. Broken Link Finder (Ahrefs API)
  3. Resource Page Finder (Google Search)
  4. Unlinked Brand Mention Checker
  5. Follow-up Generator

Usage:
  python3 backlink_autopilot.py                  # run all modules
  python3 backlink_autopilot.py --module haro     # just HARO
  python3 backlink_autopilot.py --module broken   # just broken links
  python3 backlink_autopilot.py --module resources # just resource pages
  python3 backlink_autopilot.py --module mentions  # just brand mentions
  python3 backlink_autopilot.py --module followups # just follow-ups
  python3 backlink_autopilot.py --site glow-coded  # just one site
"""

import argparse
import imaplib
import email
import json
import re
import sys
import time
import uuid
from datetime import datetime, timedelta
from email.header import decode_header
from pathlib import Path

# ── Local config ────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config

# ── Optional dependency: google.generativeai ────────────────
try:
    from google import genai
    client = genai.Client(api_key=config.GEMINI_API_KEY)
    GEMINI_MODEL = "gemini-2.5-flash"
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False
    print("[WARN] google-genai not installed. AI drafting disabled.")
    print("       pip install google-genai")
except Exception as exc:
    HAS_GEMINI = False
    print(f"[WARN] Gemini init failed: {exc}. AI drafting disabled.")

# ── Optional dependency: googlesearch ───────────────────────
try:
    from googlesearch import search as gsearch
    HAS_GOOGLESEARCH = True
except ImportError:
    HAS_GOOGLESEARCH = False
    print("[WARN] googlesearch-python not installed. Resource/mention modules disabled.")
    print("       pip install googlesearch-python")

# ── Optional dependency: requests ───────────────────────────
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    print("[WARN] requests not installed. Ahrefs / web modules disabled.")
    print("       pip install requests")


# ═══════════════════════════════════════════════════════════════
#  Shared helpers
# ═══════════════════════════════════════════════════════════════

def load_queue() -> list:
    """Load the outreach queue from disk."""
    if config.OUTREACH_QUEUE.exists():
        with open(config.OUTREACH_QUEUE, "r") as f:
            return json.load(f)
    return []


def save_queue(queue: list):
    """Persist the outreach queue to disk."""
    with open(config.OUTREACH_QUEUE, "w") as f:
        json.dump(queue, f, indent=2, default=str)


def load_log() -> list:
    """Load the outreach log (contacted URLs) from disk."""
    if config.OUTREACH_LOG.exists():
        with open(config.OUTREACH_LOG, "r") as f:
            return json.load(f)
    return []


def save_log(log: list):
    """Persist the outreach log to disk."""
    with open(config.OUTREACH_LOG, "w") as f:
        json.dump(log, f, indent=2, default=str)


def contacted_urls(log: list) -> set:
    """Return set of URLs already contacted."""
    return {entry.get("target_url", "") for entry in log}


def today_str() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def make_entry(
    opp_type: str,
    site_key: str,
    target_url: str,
    subject: str,
    body: str,
    target_email: str = None,
    target_name: str = None,
    notes: str = "",
) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "type": opp_type,
        "site": site_key,
        "target_url": target_url,
        "target_email": target_email,
        "target_name": target_name,
        "subject": subject,
        "body": body,
        "status": "pending_review",
        "created_date": today_str(),
        "sent_date": None,
        "follow_up_sent": False,
        "notes": notes,
    }


def ai_draft(prompt: str) -> str:
    """Use Gemini to draft an outreach email. Falls back to placeholder."""
    if not HAS_GEMINI:
        return "[AI drafting unavailable — install google-genai]"
    try:
        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        result = response.text.strip()
        time.sleep(15)  # Rate limit: free tier allows 5/min
        return result
    except Exception as exc:
        print(f"  [WARN] Gemini draft failed: {exc}")
        return f"[AI drafting error: {exc}]"


def site_context(site_key: str) -> str:
    """Build a context string about one of our sites for AI prompts."""
    s = config.SITES[site_key]
    return (
        f"Our website: {s['name']} ({s['domain']})\n"
        f"Tagline: {s['tagline']}\n"
        f"Niche: {s['niche']}\n"
        f"Contact email: {s['email']}"
    )


# ═══════════════════════════════════════════════════════════════
#  MODULE 1 — HARO / Connectively Monitor (IMAP)
# ═══════════════════════════════════════════════════════════════

HARO_SENDERS = [
    "helpareporter.com",
    "connectively.us",
    "qwoted.com",
    "featured.com",
    "terkel.io",
    "sourcebottle.com",
    "thesourcebottle.com",
]


def _decode_mime_header(raw: str) -> str:
    """Decode a MIME-encoded email header."""
    parts = decode_header(raw or "")
    decoded = []
    for data, charset in parts:
        if isinstance(data, bytes):
            decoded.append(data.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(data)
    return " ".join(decoded)


def _extract_email_body(msg) -> str:
    """Extract plain-text body from an email.Message."""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode("utf-8", errors="replace")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            return payload.decode("utf-8", errors="replace")
    return ""


def _matches_topics(text: str, topics: list[str]) -> list[str]:
    """Return list of matching topic keywords found in text."""
    text_lower = text.lower()
    return [t for t in topics if t.lower() in text_lower]


def _parse_queries_from_body(body: str) -> list[dict]:
    """
    Attempt to split a HARO-style digest email into individual queries.
    Returns a list of dicts with 'query' text and optional 'journalist'.
    """
    # Simple heuristic: split on numbered patterns or horizontal rules
    queries = []
    # Try splitting on patterns like "1.", "2.", etc. or "---"
    sections = re.split(r'\n(?=\d+[\.\)]\s)|(?:\n-{3,}\n)', body)
    for section in sections:
        section = section.strip()
        if len(section) > 50:  # skip tiny fragments
            journalist = None
            # Try to find journalist name
            name_match = re.search(
                r'(?:Name|Journalist|From|By)[:\s]+([A-Z][a-z]+ [A-Z][a-z]+)',
                section,
            )
            if name_match:
                journalist = name_match.group(1)
            queries.append({"query": section[:2000], "journalist": journalist})
    # If no splits worked, treat whole body as one query
    if not queries and len(body.strip()) > 50:
        queries.append({"query": body.strip()[:2000], "journalist": None})
    return queries


def run_haro(site_keys: list[str]) -> list[dict]:
    """Module 1: Check IMAP for HARO/journalist queries and draft responses."""
    print("\n=== Module 1: HARO/Connectively Monitor ===")
    entries = []

    for site_key in site_keys:
        imap_cfg = config.IMAP_CONFIG.get(site_key, {})
        server = imap_cfg.get("server", "")
        imap_email = imap_cfg.get("email", "")
        imap_pass = imap_cfg.get("password", "")

        if not server or not imap_pass:
            print(f"  [{site_key}] IMAP not configured — skipping.")
            continue

        print(f"  [{site_key}] Connecting to {server}...")
        try:
            mail = imaplib.IMAP4_SSL(server)
            mail.login(imap_email, imap_pass)
            mail.select("INBOX")
        except Exception as exc:
            print(f"  [{site_key}] IMAP connection failed: {exc}")
            continue

        topics = config.SITES[site_key]["topics"]

        for sender_domain in HARO_SENDERS:
            # Search for recent emails from this sender (last 7 days)
            since_date = (datetime.utcnow() - timedelta(days=7)).strftime("%d-%b-%Y")
            search_criteria = f'(FROM "@{sender_domain}" SINCE {since_date})'

            try:
                status, msg_ids = mail.search(None, search_criteria)
            except Exception as exc:
                print(f"  [{site_key}] Search failed for {sender_domain}: {exc}")
                continue

            if status != "OK" or not msg_ids[0]:
                continue

            ids = msg_ids[0].split()
            print(f"  [{site_key}] Found {len(ids)} emails from {sender_domain}")

            for mid in ids[-10:]:  # cap at 10 most recent
                try:
                    _, msg_data = mail.fetch(mid, "(RFC822)")
                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)
                except Exception:
                    continue

                subject = _decode_mime_header(msg.get("Subject", ""))
                body = _extract_email_body(msg)

                # Parse individual queries from the email
                queries = _parse_queries_from_body(body)

                for q in queries:
                    matched = _matches_topics(q["query"], topics)
                    if not matched:
                        continue

                    print(f"    -> Match! Topics: {matched[:3]}")

                    prompt = (
                        f"You are a PR writer for a website. Draft a concise, professional "
                        f"but friendly response to this journalist query.\n\n"
                        f"Journalist query:\n{q['query'][:1500]}\n\n"
                        f"{site_context(site_key)}\n\n"
                        f"Matching topics: {', '.join(matched)}\n\n"
                        f"Requirements:\n"
                        f"- Keep it under 200 words\n"
                        f"- Be helpful and specific, offer a unique angle\n"
                        f"- Include a short bio line at the end\n"
                        f"- Professional but casual tone, not salesy\n"
                        f"- Do NOT include a subject line — just the body"
                    )
                    draft = ai_draft(prompt)

                    entry = make_entry(
                        opp_type="haro",
                        site_key=site_key,
                        target_url=f"email:{sender_domain}",
                        subject=f"RE: {subject[:100]}",
                        body=draft,
                        target_name=q.get("journalist"),
                        notes=f"HARO via {sender_domain}. Matched topics: {', '.join(matched[:5])}",
                    )
                    entries.append(entry)

        try:
            mail.logout()
        except Exception:
            pass

    print(f"  HARO module done: {len(entries)} opportunities found.")
    return entries


# ═══════════════════════════════════════════════════════════════
#  MODULE 2 — Broken Link Finder (Ahrefs API)
# ═══════════════════════════════════════════════════════════════

def run_broken_links(site_keys: list[str]) -> list[dict]:
    """Module 2: Find broken backlinks from competitor domains via Ahrefs."""
    print("\n=== Module 2: Broken Link Finder (Ahrefs) ===")

    if not HAS_REQUESTS:
        print("  [SKIP] requests not installed.")
        return []
    if not config.AHREFS_API_KEY:
        print("  [SKIP] AHREFS_API_KEY not set.")
        return []

    headers = {"Authorization": f"Bearer {config.AHREFS_API_KEY}"}
    entries = []

    for site_key in site_keys:
        competitors = config.COMPETITORS.get(site_key, [])
        site_info = config.SITES[site_key]

        for comp_domain in competitors:
            print(f"  [{site_key}] Checking broken backlinks for {comp_domain}...")

            url = (
                f"{config.AHREFS_BASE}/site-explorer/broken-backlinks"
                f"?target={comp_domain}&mode=domain&limit=10&select=url_from,url_to,anchor,http_code,first_seen,last_visited"
            )

            try:
                resp = requests.get(url, headers=headers, timeout=30)
            except requests.RequestException as exc:
                print(f"    Request failed: {exc}")
                time.sleep(5)
                continue

            if resp.status_code == 429:
                print(f"    Rate limited. Sleeping 60s...")
                time.sleep(60)
                continue
            elif resp.status_code != 200:
                print(f"    API error {resp.status_code}: {resp.text[:200]}")
                time.sleep(5)
                continue

            data = resp.json()
            backlinks = data.get("backlinks", data.get("pages", []))

            if not backlinks:
                print(f"    No broken backlinks found.")
                time.sleep(5)
                continue

            print(f"    Found {len(backlinks)} broken backlinks.")

            for bl in backlinks:
                referring_page = bl.get("url_from", bl.get("referring_page_url", ""))
                broken_url = bl.get("url_to", bl.get("target_url", ""))
                anchor = bl.get("anchor", "")

                if not referring_page:
                    continue

                prompt = (
                    f"Draft a short, polite 'broken link replacement' outreach email.\n\n"
                    f"Context:\n"
                    f"- We found that {referring_page} links to a broken page: {broken_url}\n"
                    f"- The anchor text was: '{anchor}'\n"
                    f"- The broken link was on a competitor site: {comp_domain}\n\n"
                    f"{site_context(site_key)}\n\n"
                    f"Requirements:\n"
                    f"- Politely let them know about the broken link\n"
                    f"- Suggest our site as a replacement resource\n"
                    f"- Keep under 150 words\n"
                    f"- Professional but casual, not salesy, concise\n"
                    f"- Include both a subject line (first line, prefixed 'Subject: ') "
                    f"and body (rest)"
                )
                draft = ai_draft(prompt)

                # Split subject from body if the AI included it
                subject = f"Broken link on your page — quick fix"
                body = draft
                if draft.startswith("Subject:"):
                    lines = draft.split("\n", 1)
                    subject = lines[0].replace("Subject:", "").strip()
                    body = lines[1].strip() if len(lines) > 1 else draft

                entry = make_entry(
                    opp_type="broken_link",
                    site_key=site_key,
                    target_url=referring_page,
                    subject=subject,
                    body=body,
                    notes=(
                        f"Broken link on {referring_page} -> {broken_url} "
                        f"(anchor: '{anchor}'). Competitor: {comp_domain}"
                    ),
                )
                entries.append(entry)

            # Rate limit: 1 request per 5 seconds
            time.sleep(5)

    print(f"  Broken link module done: {len(entries)} opportunities found.")
    return entries


# ═══════════════════════════════════════════════════════════════
#  MODULE 3 — Resource Page Finder
# ═══════════════════════════════════════════════════════════════

def run_resource_pages(site_keys: list[str]) -> list[dict]:
    """Module 3: Find resource pages via Google Search and draft outreach."""
    print("\n=== Module 3: Resource Page Finder ===")

    if not HAS_GOOGLESEARCH:
        print("  [SKIP] googlesearch-python not installed.")
        return []

    log = load_log()
    already = contacted_urls(log)
    entries = []

    for site_key in site_keys:
        queries = config.RESOURCE_SEARCHES.get(site_key, [])
        site_info = config.SITES[site_key]
        our_domain = site_info["domain"]

        for query in queries:
            print(f"  [{site_key}] Searching: {query[:60]}...")

            try:
                results = list(gsearch(query, num_results=10, sleep_interval=5))
            except Exception as exc:
                print(f"    Search failed: {exc}")
                continue

            for result_url in results:
                # Skip our own sites and already-contacted pages
                if our_domain in result_url:
                    continue
                if result_url in already:
                    continue
                # Skip social media / non-actionable
                skip_domains = [
                    "reddit.com", "pinterest.com", "facebook.com",
                    "twitter.com", "x.com", "youtube.com", "instagram.com",
                    "amazon.com", "tiktok.com",
                ]
                if any(d in result_url for d in skip_domains):
                    continue

                print(f"    -> New resource page: {result_url[:80]}")
                already.add(result_url)

                # Try to extract contact info from page
                contact_email = None
                if HAS_REQUESTS:
                    try:
                        page_resp = requests.get(
                            result_url, timeout=10,
                            headers={"User-Agent": "Mozilla/5.0"},
                        )
                        if page_resp.status_code == 200:
                            emails_found = re.findall(
                                r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
                                page_resp.text,
                            )
                            # Filter out common non-person emails
                            ignore = {"example.com", "sentry.io", "wixpress.com", "w3.org"}
                            emails_found = [
                                e for e in emails_found
                                if not any(ig in e for ig in ignore)
                            ]
                            if emails_found:
                                contact_email = emails_found[0]
                    except Exception:
                        pass

                prompt = (
                    f"Draft a short outreach email asking a website owner to add our "
                    f"site to their resource page.\n\n"
                    f"Target resource page: {result_url}\n"
                    f"Found via search query: {query}\n\n"
                    f"{site_context(site_key)}\n\n"
                    f"Requirements:\n"
                    f"- Compliment their resource page\n"
                    f"- Briefly explain why our site would be a good addition\n"
                    f"- Keep under 150 words\n"
                    f"- Professional but casual, not salesy, concise\n"
                    f"- Include both a subject line (first line, prefixed 'Subject: ') "
                    f"and body"
                )
                draft = ai_draft(prompt)

                subject = f"Resource page addition suggestion"
                body = draft
                if draft.startswith("Subject:"):
                    lines = draft.split("\n", 1)
                    subject = lines[0].replace("Subject:", "").strip()
                    body = lines[1].strip() if len(lines) > 1 else draft

                entry = make_entry(
                    opp_type="resource_page",
                    site_key=site_key,
                    target_url=result_url,
                    subject=subject,
                    body=body,
                    target_email=contact_email,
                    notes=f"Found via search: {query}",
                )
                entries.append(entry)

            # Be polite to Google
            time.sleep(10)

    # Update log with newly found URLs
    for e in entries:
        log.append({
            "target_url": e["target_url"],
            "site": e["site"],
            "type": "resource_page",
            "found_date": today_str(),
        })
    save_log(log)

    print(f"  Resource page module done: {len(entries)} opportunities found.")
    return entries


# ═══════════════════════════════════════════════════════════════
#  MODULE 4 — Unlinked Brand Mention Checker
# ═══════════════════════════════════════════════════════════════

BRAND_SEARCHES = {
    "glow-coded": {
        "query": '"glow coded" -site:glow-coded.com -site:reddit.com -site:pinterest.com',
        "domain": "glow-coded.com",
        "brand": "Glow Coded",
    },
    "rooted-glow": {
        "query": '"rooted glow" -site:rooted-glow.com -site:reddit.com -site:pinterest.com',
        "domain": "rooted-glow.com",
        "brand": "Rooted Glow",
    },
}


def run_brand_mentions(site_keys: list[str]) -> list[dict]:
    """Module 4: Find pages that mention our brand but don't link to us."""
    print("\n=== Module 4: Unlinked Brand Mention Checker ===")

    if not HAS_GOOGLESEARCH:
        print("  [SKIP] googlesearch-python not installed.")
        return []
    if not HAS_REQUESTS:
        print("  [SKIP] requests not installed.")
        return []

    log = load_log()
    already = contacted_urls(log)
    entries = []

    for site_key in site_keys:
        info = BRAND_SEARCHES.get(site_key)
        if not info:
            continue

        print(f"  [{site_key}] Searching for unlinked mentions...")

        try:
            results = list(gsearch(info["query"], num_results=10, sleep_interval=5))
        except Exception as exc:
            print(f"    Search failed: {exc}")
            continue

        for result_url in results:
            if info["domain"] in result_url:
                continue
            if result_url in already:
                continue

            # Check if the page actually links to us already
            has_link = False
            contact_email = None
            try:
                page_resp = requests.get(
                    result_url, timeout=10,
                    headers={"User-Agent": "Mozilla/5.0"},
                )
                if page_resp.status_code == 200:
                    page_text = page_resp.text
                    # Check if they already link to our domain
                    if f'href="https://{info["domain"]}' in page_text or \
                       f'href="http://{info["domain"]}' in page_text or \
                       f'href="//{info["domain"]}' in page_text:
                        has_link = True
                    # Extract contact email
                    emails_found = re.findall(
                        r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
                        page_text,
                    )
                    ignore = {"example.com", "sentry.io", "wixpress.com", "w3.org"}
                    emails_found = [
                        e for e in emails_found
                        if not any(ig in e for ig in ignore)
                    ]
                    if emails_found:
                        contact_email = emails_found[0]
            except Exception:
                pass

            if has_link:
                print(f"    {result_url[:60]} — already links to us, skipping.")
                continue

            print(f"    -> Unlinked mention: {result_url[:80]}")
            already.add(result_url)

            prompt = (
                f"Draft a short outreach email to a website that mentions our brand "
                f"'{info['brand']}' but doesn't link to us.\n\n"
                f"Their page: {result_url}\n\n"
                f"{site_context(site_key)}\n\n"
                f"Requirements:\n"
                f"- Thank them for mentioning our brand\n"
                f"- Politely ask if they'd be willing to add a link to {info['domain']}\n"
                f"- Keep under 120 words\n"
                f"- Professional but casual, not salesy, concise\n"
                f"- Include both a subject line (first line, prefixed 'Subject: ') and body"
            )
            draft = ai_draft(prompt)

            subject = f"Thanks for mentioning {info['brand']}!"
            body = draft
            if draft.startswith("Subject:"):
                lines = draft.split("\n", 1)
                subject = lines[0].replace("Subject:", "").strip()
                body = lines[1].strip() if len(lines) > 1 else draft

            entry = make_entry(
                opp_type="brand_mention",
                site_key=site_key,
                target_url=result_url,
                subject=subject,
                body=body,
                target_email=contact_email,
                notes=f"Unlinked brand mention of '{info['brand']}'",
            )
            entries.append(entry)

        time.sleep(10)

    # Update log
    for e in entries:
        log.append({
            "target_url": e["target_url"],
            "site": e["site"],
            "type": "brand_mention",
            "found_date": today_str(),
        })
    save_log(log)

    print(f"  Brand mention module done: {len(entries)} opportunities found.")
    return entries


# ═══════════════════════════════════════════════════════════════
#  MODULE 5 — Follow-up Generator
# ═══════════════════════════════════════════════════════════════

def run_followups(site_keys: list[str]) -> list[dict]:
    """Module 5: Generate follow-up emails for sent outreach older than 7 days."""
    print("\n=== Module 5: Follow-up Generator ===")

    queue = load_queue()
    entries = []
    cutoff = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")

    for item in queue:
        # Only follow up on sent items
        if item.get("status") != "sent":
            continue
        if item.get("follow_up_sent", False):
            continue
        if item.get("site") not in site_keys:
            continue

        sent_date = item.get("sent_date", "")
        if not sent_date or sent_date > cutoff:
            continue

        site_key = item["site"]
        print(f"  [{site_key}] Follow-up due for {item['target_url'][:60]} "
              f"(sent {sent_date})")

        prompt = (
            f"Draft a polite, brief follow-up email.\n\n"
            f"Original outreach type: {item['type']}\n"
            f"Original subject: {item['subject']}\n"
            f"Target page: {item['target_url']}\n"
            f"Days since sent: {(datetime.utcnow() - datetime.strptime(sent_date, '%Y-%m-%d')).days}\n\n"
            f"{site_context(site_key)}\n\n"
            f"Requirements:\n"
            f"- Reference the original email without re-stating everything\n"
            f"- Keep under 80 words\n"
            f"- Friendly, not pushy\n"
            f"- Do NOT include a subject line — just the body"
        )
        draft = ai_draft(prompt)

        entry = make_entry(
            opp_type="follow_up",
            site_key=site_key,
            target_url=item["target_url"],
            subject=f"Re: {item['subject']}",
            body=draft,
            target_email=item.get("target_email"),
            target_name=item.get("target_name"),
            notes=f"Follow-up for item {item['id']} (originally sent {sent_date})",
        )
        entries.append(entry)

    print(f"  Follow-up module done: {len(entries)} follow-ups due.")
    return entries


# ═══════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════

MODULE_MAP = {
    "haro": run_haro,
    "broken": run_broken_links,
    "resources": run_resource_pages,
    "mentions": run_brand_mentions,
    "followups": run_followups,
}


def main():
    parser = argparse.ArgumentParser(
        description="Backlink Autopilot — daily SEO outreach automation"
    )
    parser.add_argument(
        "--module",
        choices=list(MODULE_MAP.keys()),
        help="Run only a specific module",
    )
    parser.add_argument(
        "--site",
        choices=list(config.SITES.keys()),
        help="Run only for a specific site",
    )
    args = parser.parse_args()

    # Determine which sites to process
    if args.site:
        site_keys = [args.site]
    else:
        site_keys = list(config.SITES.keys())

    # Determine which modules to run
    if args.module:
        modules_to_run = {args.module: MODULE_MAP[args.module]}
    else:
        modules_to_run = MODULE_MAP

    print(f"Backlink Autopilot — {today_str()}")
    print(f"Sites: {', '.join(site_keys)}")
    print(f"Modules: {', '.join(modules_to_run.keys())}")

    all_new = []
    counts = {
        "haro": 0,
        "broken": 0,
        "resources": 0,
        "mentions": 0,
        "followups": 0,
    }

    for mod_name, mod_func in modules_to_run.items():
        try:
            results = mod_func(site_keys)
            count_key = mod_name
            counts[count_key] = len(results)
            all_new.extend(results)
        except Exception as exc:
            print(f"\n  [ERROR] Module '{mod_name}' failed: {exc}")
            import traceback
            traceback.print_exc()

    # Append to existing queue
    if all_new:
        queue = load_queue()
        queue.extend(all_new)
        save_queue(queue)

    # Print summary
    total = sum(counts.values())
    print("\n" + "=" * 60)
    print(f"SUMMARY: Found {total} opportunities:")
    if "haro" in modules_to_run:
        print(f"  - {counts['haro']} HARO matches")
    if "broken" in modules_to_run:
        print(f"  - {counts['broken']} broken links")
    if "resources" in modules_to_run:
        print(f"  - {counts['resources']} resource pages")
    if "mentions" in modules_to_run:
        print(f"  - {counts['mentions']} brand mentions")
    if "followups" in modules_to_run:
        print(f"  - {counts['followups']} follow-ups due")
    print(f"\nAll entries saved to: {config.OUTREACH_QUEUE}")
    print("=" * 60)


if __name__ == "__main__":
    main()
