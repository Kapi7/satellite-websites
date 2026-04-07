"""
Newsletter Sender — Weekly digest for both satellite websites.

Reads subscribers from Cloudflare KV, finds articles published in the last 7 days,
generates branded HTML emails, and sends via SMTP.

Required env vars:
  CF_ACCOUNT_ID, CF_KV_API_TOKEN
  CF_KV_NAMESPACE_GLOWCODED, CF_KV_NAMESPACE_ROOTEDGLOW
  NEWSLETTER_SECRET
  SMTP_GLOWCODED_SERVER, SMTP_GLOWCODED_PORT, SMTP_GLOWCODED_PASSWORD
  SMTP_ROOTEDGLOW_SERVER, SMTP_ROOTEDGLOW_PORT, SMTP_ROOTEDGLOW_PASSWORD
  OUTREACH_GLOWCODED_EMAIL, OUTREACH_ROOTEDGLOW_EMAIL
"""

import hashlib
import hmac
import json
import os
import re
import smtplib
import sys
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import requests

# ── Config ────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SITES = {
    "glow-coded": {
        "domain": "glow-coded.com",
        "name": "Glow Coded",
        "tagline": "K-Beauty Ingredient Research & Reviews",
        "from_name": "Glow Coded",
        "content_dir": PROJECT_ROOT / "cosmetics" / "src" / "content" / "blog",
        "kv_namespace_env": "CF_KV_NAMESPACE_GLOWCODED",
        "smtp_server_env": "SMTP_GLOWCODED_SERVER",
        "smtp_port_env": "SMTP_GLOWCODED_PORT",
        "smtp_password_env": "SMTP_GLOWCODED_PASSWORD",
        "email_env": "OUTREACH_GLOWCODED_EMAIL",
        "primary_color": "#e11d48",
        "bg_color": "#fff5f5",
        "light_color": "#ffe4e6",
    },
    "rooted-glow": {
        "domain": "rooted-glow.com",
        "name": "Rooted Glow",
        "tagline": "Where Wellness Meets Skin Health",
        "from_name": "Rooted Glow",
        "content_dir": PROJECT_ROOT / "wellness" / "src" / "content" / "blog",
        "kv_namespace_env": "CF_KV_NAMESPACE_ROOTEDGLOW",
        "smtp_server_env": "SMTP_ROOTEDGLOW_SERVER",
        "smtp_port_env": "SMTP_ROOTEDGLOW_PORT",
        "smtp_password_env": "SMTP_ROOTEDGLOW_PASSWORD",
        "email_env": "OUTREACH_ROOTEDGLOW_EMAIL",
        "primary_color": "#15803d",
        "bg_color": "#f0fdf4",
        "light_color": "#dcfce7",
    },
}

NEWSLETTER_SECRET = os.getenv("NEWSLETTER_SECRET", "")
CF_ACCOUNT_ID = os.getenv("CF_ACCOUNT_ID", "")
CF_KV_API_TOKEN = os.getenv("CF_KV_API_TOKEN", "")

RATE_LIMIT_SECONDS = 30


# ── Helpers ───────────────────────────────────────────────────

def make_unsubscribe_token(email: str) -> str:
    return hmac.new(
        NEWSLETTER_SECRET.encode(), email.encode(), hashlib.sha256
    ).hexdigest()


def unsubscribe_url(domain: str, email: str) -> str:
    token = make_unsubscribe_token(email)
    return f"https://{domain}/api/unsubscribe?email={urllib.parse.quote(email)}&token={token}"


# ── KV subscriber fetching ────────────────────────────────────

def fetch_subscribers(namespace_id: str) -> list[dict]:
    """Fetch all subscriber emails + metadata from Cloudflare KV."""
    subscribers = []
    cursor = None
    base = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/storage/kv/namespaces/{namespace_id}/keys"
    headers = {"Authorization": f"Bearer {CF_KV_API_TOKEN}"}

    while True:
        params = {"limit": 1000}
        if cursor:
            params["cursor"] = cursor
        resp = requests.get(base, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()

        for key_info in data.get("result", []):
            email = key_info["name"]
            # Fetch value for locale info
            val_resp = requests.get(f"{base.replace('/keys', '')}/values/{urllib.parse.quote(email, safe='')}", headers=headers)
            if val_resp.ok:
                try:
                    meta = json.loads(val_resp.text)
                except json.JSONDecodeError:
                    meta = {}
                subscribers.append({"email": email, "locale": meta.get("locale", "en")})

        cursor = data.get("result_info", {}).get("cursor")
        if not cursor:
            break

    return subscribers


# ── Article scanning ──────────────────────────────────────────

def parse_frontmatter(filepath: Path) -> dict | None:
    """Extract YAML frontmatter from .mdx file."""
    text = filepath.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return None
    fm = {}
    for line in match.group(1).split("\n"):
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            fm[key] = val
    return fm


def find_recent_articles(content_dir: Path, days: int = 7) -> list[dict]:
    """Find articles published within the last N days (English only)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    articles = []

    if not content_dir.exists():
        return articles

    for mdx in content_dir.rglob("*.mdx"):
        fm = parse_frontmatter(mdx)
        if not fm:
            continue
        if fm.get("draft", "false").lower() == "true":
            continue
        if fm.get("locale", "en") != "en":
            continue

        date_str = fm.get("date", "")
        try:
            pub_date = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue

        if pub_date < cutoff:
            continue

        # Derive slug from filename
        slug = mdx.stem
        category = fm.get("category", "")
        articles.append({
            "title": fm.get("title", slug),
            "description": fm.get("description", ""),
            "date": pub_date,
            "image": fm.get("image", ""),
            "category": category,
            "slug": slug,
        })

    articles.sort(key=lambda a: a["date"], reverse=True)
    return articles[:4]


# ── Email HTML generation ─────────────────────────────────────

def generate_html_email(site_key: str, articles: list[dict], unsub_link: str) -> str:
    site = SITES[site_key]
    domain = site["domain"]
    primary = site["primary_color"]
    bg = site["bg_color"]
    light = site["light_color"]
    name = site["name"]
    tagline = site["tagline"]

    article_blocks = ""
    for a in articles:
        img_html = ""
        if a["image"]:
            img_html = f'<img src="https://{domain}{a["image"]}" alt="" style="width:100%;border-radius:12px;margin-bottom:16px;" />'
        article_blocks += f"""
        <tr><td style="padding:0 0 28px 0;">
          <table cellpadding="0" cellspacing="0" border="0" width="100%"><tr><td style="background:#fff;border-radius:12px;padding:20px;border:1px solid {light};">
            {img_html}
            <a href="https://{domain}/blog/{a['slug']}/" style="color:{primary};font-size:18px;font-weight:700;text-decoration:none;line-height:1.4;">{a['title']}</a>
            <p style="color:#64748b;font-size:14px;line-height:1.6;margin:8px 0 12px;">{a['description'][:160]}</p>
            <a href="https://{domain}/blog/{a['slug']}/" style="color:{primary};font-size:13px;font-weight:600;text-decoration:none;">Read more &rarr;</a>
          </td></tr></table>
        </td></tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>This Week on {name}</title></head>
<body style="margin:0;padding:0;background:{bg};font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<table cellpadding="0" cellspacing="0" border="0" width="100%" style="background:{bg};">
<tr><td align="center" style="padding:40px 16px;">
  <table cellpadding="0" cellspacing="0" border="0" width="560" style="max-width:560px;">

    <!-- Header -->
    <tr><td align="center" style="padding:0 0 32px;">
      <h1 style="margin:0;font-size:28px;color:{primary};font-weight:800;letter-spacing:-0.5px;">{name}</h1>
      <p style="margin:6px 0 0;font-size:13px;color:#94a3b8;">{tagline}</p>
    </td></tr>

    <!-- Intro -->
    <tr><td style="padding:0 0 24px;">
      <p style="margin:0;font-size:15px;color:#334155;line-height:1.6;">Here are this week's latest articles. Enjoy the read!</p>
    </td></tr>

    <!-- Articles -->
    {article_blocks}

    <!-- Footer -->
    <tr><td align="center" style="padding:24px 0 0;border-top:1px solid {light};">
      <p style="margin:0;font-size:12px;color:#94a3b8;line-height:1.6;">
        You received this because you subscribed at {domain}.<br>
        <a href="{unsub_link}" style="color:#94a3b8;text-decoration:underline;">Unsubscribe</a>
      </p>
    </td></tr>

  </table>
</td></tr>
</table>
</body></html>"""


def generate_plain_text(site_key: str, articles: list[dict], unsub_link: str) -> str:
    site = SITES[site_key]
    lines = [
        f"{site['name']} — This Week's Articles",
        f"{site['tagline']}",
        "",
        "Here are this week's latest articles:",
        "",
    ]
    for a in articles:
        lines.append(f"- {a['title']}")
        lines.append(f"  https://{site['domain']}/blog/{a['slug']}/")
        lines.append("")
    lines.append(f"Unsubscribe: {unsub_link}")
    return "\n".join(lines)


# ── Sending ───────────────────────────────────────────────────

def send_email(site_key: str, to_email: str, html: str, plain: str):
    site = SITES[site_key]
    from_email = os.getenv(site["email_env"], "")
    smtp_server = os.getenv(site["smtp_server_env"], "")
    smtp_port = int(os.getenv(site["smtp_port_env"], "587"))
    smtp_password = os.getenv(site["smtp_password_env"], "")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"This Week on {site['name']}"
    msg["From"] = f"{site['from_name']} <{from_email}>"
    msg["To"] = to_email
    msg["List-Unsubscribe"] = f"<{unsubscribe_url(site['domain'], to_email)}>"

    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(from_email, smtp_password)
        server.send_message(msg)


# ── Main ──────────────────────────────────────────────────────

def run_site(site_key: str) -> int:
    site = SITES[site_key]
    namespace_id = os.getenv(site["kv_namespace_env"], "")
    if not namespace_id:
        print(f"[{site_key}] No KV namespace configured, skipping.")
        return 0

    # 1. Find recent articles
    articles = find_recent_articles(site["content_dir"])
    if not articles:
        print(f"[{site_key}] No new articles in the last 7 days, skipping.")
        return 0
    print(f"[{site_key}] Found {len(articles)} recent article(s).")

    # 2. Fetch subscribers
    subscribers = fetch_subscribers(namespace_id)
    if not subscribers:
        print(f"[{site_key}] No subscribers, skipping.")
        return 0
    print(f"[{site_key}] Sending to {len(subscribers)} subscriber(s).")

    # 3. Send emails
    sent = 0
    for sub in subscribers:
        email = sub["email"]
        unsub = unsubscribe_url(site["domain"], email)
        html = generate_html_email(site_key, articles, unsub)
        plain = generate_plain_text(site_key, articles, unsub)
        try:
            send_email(site_key, email, html, plain)
            sent += 1
            print(f"  Sent to {email}")
        except Exception as e:
            print(f"  Failed to send to {email}: {e}")
        time.sleep(RATE_LIMIT_SECONDS)

    print(f"[{site_key}] Done. Sent {sent}/{len(subscribers)}.")
    return sent


def main():
    if not NEWSLETTER_SECRET:
        print("NEWSLETTER_SECRET not set, aborting.")
        sys.exit(1)
    if not CF_ACCOUNT_ID or not CF_KV_API_TOKEN:
        print("Cloudflare KV credentials not set, aborting.")
        sys.exit(1)

    total = 0
    for site_key in SITES:
        total += run_site(site_key)

    print(f"\nTotal emails sent: {total}")


if __name__ == "__main__":
    main()
