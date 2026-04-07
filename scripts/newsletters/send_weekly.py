"""
Pre-Written Newsletter Sender — Sends curated Friday afternoon newsletters.

Cycles through 10 pre-written editions. Reads subscribers from Cloudflare KV,
renders branded HTML, and sends via SMTP.

Usage:
  python3 scripts/newsletters/send_weekly.py              # auto-pick edition by week
  python3 scripts/newsletters/send_weekly.py --edition 3   # force specific edition
  python3 scripts/newsletters/send_weekly.py --preview      # print HTML, don't send

Required env vars:
  CF_ACCOUNT_ID, CF_KV_API_TOKEN
  CF_KV_NAMESPACE_GLOWCODED, CF_KV_NAMESPACE_ROOTEDGLOW
  NEWSLETTER_SECRET
  SMTP_GLOWCODED_SERVER, SMTP_GLOWCODED_PORT, SMTP_GLOWCODED_PASSWORD
  SMTP_ROOTEDGLOW_SERVER, SMTP_ROOTEDGLOW_PORT, SMTP_ROOTEDGLOW_PASSWORD
  OUTREACH_GLOWCODED_EMAIL, OUTREACH_ROOTEDGLOW_EMAIL
"""

import argparse
import hashlib
import hmac
import json
import os
import smtplib
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import requests

# ── Config ────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
EDITIONS_FILE = SCRIPT_DIR / "editions.json"

SITES = {
    "glow-coded": {
        "domain": "glow-coded.com",
        "name": "Glow Coded",
        "tagline": "K-Beauty Ingredient Research & Reviews",
        "from_name": "Glow Coded",
        "kv_namespace_env": "CF_KV_NAMESPACE_GLOWCODED",
        "smtp_server_env": "SMTP_GLOWCODED_SERVER",
        "smtp_port_env": "SMTP_GLOWCODED_PORT",
        "smtp_password_env": "SMTP_GLOWCODED_PASSWORD",
        "email_env": "OUTREACH_GLOWCODED_EMAIL",
        "primary_color": "#e11d48",
        "bg_color": "#fff5f5",
        "light_color": "#ffe4e6",
        "accent_color": "#fb7185",
    },
    "rooted-glow": {
        "domain": "rooted-glow.com",
        "name": "Rooted Glow",
        "tagline": "Where Wellness Meets Skin Health",
        "from_name": "Rooted Glow",
        "kv_namespace_env": "CF_KV_NAMESPACE_ROOTEDGLOW",
        "smtp_server_env": "SMTP_ROOTEDGLOW_SERVER",
        "smtp_port_env": "SMTP_ROOTEDGLOW_PORT",
        "smtp_password_env": "SMTP_ROOTEDGLOW_PASSWORD",
        "email_env": "OUTREACH_ROOTEDGLOW_EMAIL",
        "primary_color": "#15803d",
        "bg_color": "#f0fdf4",
        "light_color": "#dcfce7",
        "accent_color": "#4ade80",
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


def load_editions() -> list[dict]:
    with open(EDITIONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def pick_edition(editions: list[dict], force: int | None = None) -> dict:
    if force is not None:
        for ed in editions:
            if ed["edition"] == force:
                return ed
        print(f"Edition {force} not found. Available: {[e['edition'] for e in editions]}")
        sys.exit(1)

    # Auto-pick based on ISO week number, cycling through 1-10
    week = datetime.now(timezone.utc).isocalendar()[1]
    idx = ((week - 1) % len(editions))
    return editions[idx]


# ── KV subscriber fetching ────────────────────────────────────

def fetch_subscribers(namespace_id: str) -> list[dict]:
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
            val_resp = requests.get(
                f"{base.replace('/keys', '')}/values/{urllib.parse.quote(email, safe='')}",
                headers=headers,
            )
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


# ── Email HTML generation ─────────────────────────────────────

def generate_html(site_key: str, edition: dict, unsub_link: str) -> str:
    site = SITES[site_key]
    ed = edition[site_key]
    domain = site["domain"]
    primary = site["primary_color"]
    bg = site["bg_color"]
    light = site["light_color"]
    accent = site["accent_color"]
    name = site["name"]
    tagline = site["tagline"]

    article_blocks = ""
    for i, a in enumerate(ed["articles"]):
        url = f"https://{domain}/blog/{a['slug']}/"
        article_blocks += f"""
        <tr><td style="padding:0 0 24px 0;">
          <table cellpadding="0" cellspacing="0" border="0" width="100%"><tr><td style="background:#ffffff;border-radius:12px;padding:24px;border:1px solid {light};">
            <a href="{url}" style="color:{primary};font-size:18px;font-weight:700;text-decoration:none;line-height:1.4;display:block;margin-bottom:8px;">{a['title']}</a>
            <p style="color:#64748b;font-size:14px;line-height:1.6;margin:0 0 14px;">{a['blurb']}</p>
            <a href="{url}" style="display:inline-block;background:{primary};color:#ffffff;font-size:13px;font-weight:600;text-decoration:none;padding:8px 20px;border-radius:6px;">Read Article &rarr;</a>
          </td></tr></table>
        </td></tr>"""

    edition_num = edition["edition"]
    theme = edition["theme"]

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{ed['subject']}</title></head>
<body style="margin:0;padding:0;background:{bg};font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',sans-serif;">
<table cellpadding="0" cellspacing="0" border="0" width="100%" style="background:{bg};">
<tr><td align="center" style="padding:40px 16px;">
  <table cellpadding="0" cellspacing="0" border="0" width="560" style="max-width:560px;">

    <!-- Header -->
    <tr><td align="center" style="padding:0 0 12px;">
      <h1 style="margin:0;font-size:28px;color:{primary};font-weight:800;letter-spacing:-0.5px;">{name}</h1>
      <p style="margin:4px 0 0;font-size:12px;color:#94a3b8;letter-spacing:1px;text-transform:uppercase;">{tagline}</p>
    </td></tr>

    <!-- Divider -->
    <tr><td style="padding:0 0 28px;">
      <table cellpadding="0" cellspacing="0" border="0" width="100%"><tr>
        <td style="width:40%;height:1px;background:{light};"></td>
        <td align="center" style="padding:0 12px;"><span style="font-size:11px;color:{accent};font-weight:600;text-transform:uppercase;letter-spacing:2px;white-space:nowrap;">Edition {edition_num}</span></td>
        <td style="width:40%;height:1px;background:{light};"></td>
      </tr></table>
    </td></tr>

    <!-- Theme -->
    <tr><td style="padding:0 0 8px;">
      <h2 style="margin:0;font-size:22px;color:#1e293b;font-weight:700;text-align:center;">{theme}</h2>
    </td></tr>

    <!-- Intro -->
    <tr><td style="padding:0 0 28px;">
      <p style="margin:0;font-size:15px;color:#475569;line-height:1.7;text-align:center;">{ed['intro']}</p>
    </td></tr>

    <!-- Articles -->
    {article_blocks}

    <!-- CTA -->
    <tr><td align="center" style="padding:8px 0 32px;">
      <p style="margin:0;font-size:14px;color:#64748b;line-height:1.6;">
        Explore more on <a href="https://{domain}" style="color:{primary};text-decoration:none;font-weight:600;">{domain}</a>
      </p>
    </td></tr>

    <!-- Footer -->
    <tr><td align="center" style="padding:24px 0 0;border-top:1px solid {light};">
      <p style="margin:0;font-size:12px;color:#94a3b8;line-height:1.8;">
        You received this because you subscribed at {domain}.<br>
        <a href="{unsub_link}" style="color:#94a3b8;text-decoration:underline;">Unsubscribe</a>
      </p>
    </td></tr>

  </table>
</td></tr>
</table>
</body></html>"""


def generate_plain_text(site_key: str, edition: dict, unsub_link: str) -> str:
    site = SITES[site_key]
    ed = edition[site_key]
    domain = site["domain"]
    lines = [
        f"{site['name']} — {ed['subject']}",
        f"Edition {edition['edition']}: {edition['theme']}",
        "",
        ed["intro"],
        "",
    ]
    for a in ed["articles"]:
        lines.append(f"* {a['title']}")
        lines.append(f"  {a['blurb']}")
        lines.append(f"  https://{domain}/blog/{a['slug']}/")
        lines.append("")
    lines.append(f"Visit: https://{domain}")
    lines.append(f"Unsubscribe: {unsub_link}")
    return "\n".join(lines)


# ── Sending ───────────────────────────────────────────────────

def send_email(site_key: str, to_email: str, subject: str, html: str, plain: str):
    site = SITES[site_key]
    from_email = os.getenv(site["email_env"], "")
    smtp_server = os.getenv(site["smtp_server_env"], "")
    smtp_port = int(os.getenv(site["smtp_port_env"], "587"))
    smtp_password = os.getenv(site["smtp_password_env"], "")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
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

def run_site(site_key: str, edition: dict, preview: bool = False) -> int:
    site = SITES[site_key]
    ed = edition[site_key]
    subject = ed["subject"]

    print(f"\n[{site_key}] Edition {edition['edition']}: \"{subject}\"")
    print(f"  Articles: {len(ed['articles'])}")

    if preview:
        html = generate_html(site_key, edition, "https://example.com/unsubscribe")
        print(html)
        return 0

    namespace_id = os.getenv(site["kv_namespace_env"], "")
    if not namespace_id:
        print(f"  No KV namespace configured, skipping.")
        return 0

    subscribers = fetch_subscribers(namespace_id)
    if not subscribers:
        print(f"  No subscribers, skipping.")
        return 0
    print(f"  Sending to {len(subscribers)} subscriber(s).")

    sent = 0
    for sub in subscribers:
        email = sub["email"]
        unsub = unsubscribe_url(site["domain"], email)
        html = generate_html(site_key, edition, unsub)
        plain = generate_plain_text(site_key, edition, unsub)
        try:
            send_email(site_key, email, subject, html, plain)
            sent += 1
            print(f"    Sent to {email}")
        except Exception as e:
            print(f"    Failed: {email} — {e}")
        time.sleep(RATE_LIMIT_SECONDS)

    print(f"  Done. Sent {sent}/{len(subscribers)}.")
    return sent


def main():
    parser = argparse.ArgumentParser(description="Send pre-written newsletter edition")
    parser.add_argument("--edition", type=int, help="Force specific edition number (1-10)")
    parser.add_argument("--preview", action="store_true", help="Print HTML without sending")
    args = parser.parse_args()

    if not args.preview:
        if not NEWSLETTER_SECRET:
            print("NEWSLETTER_SECRET not set, aborting.")
            sys.exit(1)
        if not CF_ACCOUNT_ID or not CF_KV_API_TOKEN:
            print("Cloudflare KV credentials not set, aborting.")
            sys.exit(1)

    editions = load_editions()
    edition = pick_edition(editions, args.edition)
    print(f"Selected edition {edition['edition']}: {edition['theme']}")

    total = 0
    for site_key in SITES:
        total += run_site(site_key, edition, preview=args.preview)

    if not args.preview:
        print(f"\nTotal emails sent: {total}")


if __name__ == "__main__":
    main()
