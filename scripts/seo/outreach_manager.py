#!/usr/bin/env python3
"""
Outreach Manager — Review drafts, send emails, track responses.

Usage:
    python3 outreach_manager.py --review            # Interactive review queue
    python3 outreach_manager.py --send              # Send approved emails
    python3 outreach_manager.py --send-followups    # Send 7-day follow-ups
    python3 outreach_manager.py --status            # Dashboard
    python3 outreach_manager.py --auto              # Auto-send approved (cron)
    python3 outreach_manager.py --response ID --got-link URL
    python3 outreach_manager.py --response ID --rejected
    python3 outreach_manager.py --response ID --pending
"""

import argparse
import json
import os
import smtplib
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from pathlib import Path

# ── Imports from config ──────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (
    SMTP_CONFIG,
    OUTREACH_QUEUE,
    OUTREACH_LOG,
    ACCOUNTS,
    SITES,
)

# ── Constants ────────────────────────────────────────────────

MAX_EMAILS_PER_DAY = 20
SEND_DELAY_SECONDS = 30
FOLLOWUP_DAYS = 7

FOLLOWUP_TEMPLATE = """Hi {first_name},

Just wanted to follow up on my previous email — I hope it didn't get lost in the shuffle!

I'd still love to contribute if you're open to it. Happy to adjust the angle or provide
additional information if that would help.

Best,
{sender_name}"""


# ── Helpers ──────────────────────────────────────────────────

def load_json(path: Path) -> list:
    """Load a JSON file, returning empty list if missing or invalid."""
    if not path.exists():
        return []
    try:
        with open(path, "r") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, IOError):
        return []


def save_json(path: Path, data: list) -> None:
    """Save data to JSON file with pretty formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def extract_first_name(email_body: str, target_email: str) -> str:
    """Try to extract a first name from the email body greeting line."""
    for line in email_body.strip().split("\n"):
        line = line.strip()
        if line.lower().startswith("hi ") or line.lower().startswith("hey "):
            parts = line.split()
            if len(parts) >= 2:
                name = parts[1].rstrip(",").rstrip("!")
                if name and name[0].isupper():
                    return name
    # Fallback: use part before @ from target email
    return target_email.split("@")[0].split(".")[0].title()


def count_sent_today(queue: list, log: list) -> int:
    """Count how many emails were sent today across queue and log."""
    today = today_str()
    count = 0
    for item in queue + log:
        if item.get("sent_date", "").startswith(today):
            count += 1
    return count


def get_smtp(site: str) -> dict | None:
    """Get SMTP config for a site, return None if not configured."""
    cfg = SMTP_CONFIG.get(site, {})
    if not cfg.get("server") or not cfg.get("password"):
        return None
    return cfg


def send_email(smtp_cfg: dict, to_email: str, subject: str,
               body: str, from_name: str = "") -> bool:
    """Send a plain-text email via SMTP. Returns True on success."""
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    if from_name:
        msg["From"] = f"{from_name} <{smtp_cfg['email']}>"
    else:
        msg["From"] = smtp_cfg["email"]
    msg["To"] = to_email

    try:
        with smtplib.SMTP(smtp_cfg["server"], smtp_cfg["port"], timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_cfg["email"], smtp_cfg["password"])
            server.send_message(msg)
        return True
    except smtplib.SMTPAuthenticationError as e:
        print(f"  [ERROR] SMTP auth failed: {e}")
        return False
    except smtplib.SMTPException as e:
        print(f"  [ERROR] SMTP error: {e}")
        return False
    except ConnectionError as e:
        print(f"  [ERROR] Connection failed: {e}")
        return False
    except OSError as e:
        print(f"  [ERROR] Network error: {e}")
        return False


def open_in_editor(text: str) -> str:
    """Open text in $EDITOR (or nano) and return edited text."""
    editor = os.environ.get("EDITOR", "nano")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
        tmp.write(text)
        tmp_path = tmp.name

    try:
        subprocess.call([editor, tmp_path])
        with open(tmp_path, "r") as f:
            return f.read()
    finally:
        os.unlink(tmp_path)


# ── Review Command ───────────────────────────────────────────

def cmd_review():
    """Interactive review of pending_review items in the queue."""
    queue = load_json(OUTREACH_QUEUE)
    pending = [i for i, item in enumerate(queue) if item.get("status") == "pending_review"]

    if not pending:
        print("No items pending review.")
        return

    reviewed = 0
    for pos, idx in enumerate(pending):
        item = queue[idx]
        site_key = item.get("site", "unknown")
        site_name = SITES.get(site_key, {}).get("name", site_key)
        outreach_type = item.get("type", "outreach")
        target = item.get("target_email", "unknown")
        found_via = item.get("found_via", "")
        subject = item.get("subject", "(no subject)")
        body = item.get("body", "(no body)")

        print()
        print("\u2501" * 50)
        print(f"[{pos + 1}/{len(pending)}] {outreach_type.upper().replace('_', ' ')} \u2014 {site_name}")
        print(f"Target: {target}")
        if found_via:
            print(f"Found via: {found_via}")
        if item.get("target_url"):
            print(f"URL: {item['target_url']}")
        print("\u2501" * 50)
        print()
        print(f"Subject: {subject}")
        print()
        print("Body:")
        print(body)
        print()
        print("\u2501" * 50)

        while True:
            choice = input("[A]pprove  [E]dit  [S]kip  [D]elete  [Q]uit: ").strip().lower()

            if choice == "a":
                queue[idx]["status"] = "approved"
                queue[idx]["approved_date"] = now_str()
                print("  -> Approved")
                reviewed += 1
                break
            elif choice == "e":
                edited_body = open_in_editor(body)
                queue[idx]["body"] = edited_body.strip()
                queue[idx]["status"] = "approved"
                queue[idx]["approved_date"] = now_str()
                print("  -> Edited & Approved")
                reviewed += 1
                break
            elif choice == "s":
                print("  -> Skipped (stays pending)")
                break
            elif choice == "d":
                queue[idx]["status"] = "deleted"
                queue[idx]["deleted_date"] = now_str()
                print("  -> Deleted")
                reviewed += 1
                break
            elif choice == "q":
                print(f"\nReviewed {reviewed} items. Saving and exiting.")
                # Remove deleted items
                queue = [item for item in queue if item.get("status") != "deleted"]
                save_json(OUTREACH_QUEUE, queue)
                return
            else:
                print("  Invalid choice. Use A/E/S/D/Q.")

    # Remove deleted items
    queue = [item for item in queue if item.get("status") != "deleted"]
    save_json(OUTREACH_QUEUE, queue)
    print(f"\nDone. Reviewed {reviewed} items.")


# ── Send Command ─────────────────────────────────────────────

def cmd_send(auto: bool = False):
    """Send all approved emails via SMTP."""
    queue = load_json(OUTREACH_QUEUE)
    log = load_json(OUTREACH_LOG)

    approved = [i for i, item in enumerate(queue) if item.get("status") == "approved"]
    if not approved:
        if not auto:
            print("No approved emails to send.")
        return

    sent_today = count_sent_today(queue, log)
    remaining = MAX_EMAILS_PER_DAY - sent_today
    if remaining <= 0:
        print(f"Daily limit reached ({MAX_EMAILS_PER_DAY} emails/day). Try again tomorrow.")
        return

    to_send = approved[:remaining]
    print(f"Sending {len(to_send)} emails ({sent_today} already sent today, "
          f"limit {MAX_EMAILS_PER_DAY})...\n")

    sent_count = 0
    for pos, idx in enumerate(to_send):
        item = queue[idx]
        site_key = item.get("site", "unknown")
        target = item.get("target_email", "unknown")
        subject = item.get("subject", "")
        body = item.get("body", "")

        smtp_cfg = get_smtp(site_key)
        if not smtp_cfg:
            print(f"  [{pos + 1}] SKIP {target} — SMTP not configured for {site_key}. "
                  f"Add SMTP_* vars to .env")
            continue

        from_name = ACCOUNTS.get(site_key, {}).get("display_name", "")
        print(f"  [{pos + 1}] Sending to {target}...", end=" ", flush=True)

        success = send_email(smtp_cfg, target, subject, body, from_name)
        if success:
            queue[idx]["status"] = "sent"
            queue[idx]["sent_date"] = now_str()
            queue[idx]["follow_up_sent"] = False

            # Copy to permanent log
            log_entry = dict(queue[idx])
            log.append(log_entry)

            print("OK")
            sent_count += 1
        else:
            print("FAILED")

        # Rate limiting delay between sends
        if pos < len(to_send) - 1:
            if not auto:
                print(f"    Waiting {SEND_DELAY_SECONDS}s (rate limit)...")
            time.sleep(SEND_DELAY_SECONDS)

    save_json(OUTREACH_QUEUE, queue)
    save_json(OUTREACH_LOG, log)
    print(f"\nDone. Sent {sent_count}/{len(to_send)} emails.")


# ── Send Follow-ups Command ──────────────────────────────────

def cmd_send_followups():
    """Send follow-ups for items sent > 7 days ago without a follow-up."""
    queue = load_json(OUTREACH_QUEUE)
    log = load_json(OUTREACH_LOG)

    cutoff = datetime.now() - timedelta(days=FOLLOWUP_DAYS)
    due = []

    for i, item in enumerate(queue):
        if item.get("status") != "sent":
            continue
        if item.get("follow_up_sent", False):
            continue
        if item.get("response_status"):
            continue  # Already got a response, skip follow-up
        sent_date_str = item.get("sent_date", "")
        if not sent_date_str:
            continue
        try:
            sent_date = datetime.strptime(sent_date_str[:10], "%Y-%m-%d")
        except ValueError:
            continue
        if sent_date <= cutoff:
            due.append(i)

    if not due:
        print("No follow-ups due.")
        return

    sent_today = count_sent_today(queue, log)
    remaining = MAX_EMAILS_PER_DAY - sent_today
    if remaining <= 0:
        print(f"Daily limit reached ({MAX_EMAILS_PER_DAY}/day). Try again tomorrow.")
        return

    to_send = due[:remaining]
    print(f"Sending {len(to_send)} follow-ups...\n")

    sent_count = 0
    for pos, idx in enumerate(to_send):
        item = queue[idx]
        site_key = item.get("site", "unknown")
        target = item.get("target_email", "unknown")
        original_subject = item.get("subject", "")
        original_body = item.get("body", "")

        smtp_cfg = get_smtp(site_key)
        if not smtp_cfg:
            print(f"  [{pos + 1}] SKIP {target} — SMTP not configured for {site_key}.")
            continue

        # Build follow-up
        first_name = extract_first_name(original_body, target)
        sender_name = ACCOUNTS.get(site_key, {}).get("display_name", site_key)
        followup_body = FOLLOWUP_TEMPLATE.format(
            first_name=first_name,
            sender_name=sender_name,
        )
        followup_subject = f"Re: {original_subject}"

        from_name = ACCOUNTS.get(site_key, {}).get("display_name", "")
        print(f"  [{pos + 1}] Follow-up to {target}...", end=" ", flush=True)

        success = send_email(smtp_cfg, target, followup_subject, followup_body, from_name)
        if success:
            queue[idx]["follow_up_sent"] = True
            queue[idx]["follow_up_date"] = now_str()

            # Update log entry too
            item_id = item.get("id", "")
            for log_item in log:
                if log_item.get("id") == item_id:
                    log_item["follow_up_sent"] = True
                    log_item["follow_up_date"] = now_str()
                    break

            print("OK")
            sent_count += 1
        else:
            print("FAILED")

        if pos < len(to_send) - 1:
            time.sleep(SEND_DELAY_SECONDS)

    save_json(OUTREACH_QUEUE, queue)
    save_json(OUTREACH_LOG, log)
    print(f"\nDone. Sent {sent_count}/{len(to_send)} follow-ups.")


# ── Status Dashboard ─────────────────────────────────────────

def cmd_status():
    """Show the outreach dashboard."""
    queue = load_json(OUTREACH_QUEUE)
    log = load_json(OUTREACH_LOG)

    # Combine for full picture
    all_items = queue + log
    # Deduplicate by id (queue items may also be in log)
    seen_ids = set()
    unique = []
    for item in all_items:
        item_id = item.get("id", id(item))
        if item_id not in seen_ids:
            seen_ids.add(item_id)
            unique.append(item)

    # Count by status
    pending = sum(1 for i in queue if i.get("status") == "pending_review")
    approved = sum(1 for i in queue if i.get("status") == "approved")
    sent = sum(1 for i in unique if i.get("status") == "sent")

    # Follow-ups due
    cutoff = datetime.now() - timedelta(days=FOLLOWUP_DAYS)
    followups_due = 0
    for item in queue:
        if item.get("status") != "sent":
            continue
        if item.get("follow_up_sent", False):
            continue
        if item.get("response_status"):
            continue
        sent_str = item.get("sent_date", "")
        if not sent_str:
            continue
        try:
            sd = datetime.strptime(sent_str[:10], "%Y-%m-%d")
            if sd <= cutoff:
                followups_due += 1
        except ValueError:
            pass

    responses = sum(1 for i in unique if i.get("response_status"))

    # By type
    type_stats = {}
    for item in unique:
        t = item.get("type", "unknown")
        if t not in type_stats:
            type_stats[t] = {"sent": 0, "responses": 0}
        if item.get("status") == "sent":
            type_stats[t]["sent"] += 1
        if item.get("response_status"):
            type_stats[t]["responses"] += 1

    # By site
    site_stats = {}
    for item in unique:
        s = item.get("site", "unknown")
        if s not in site_stats:
            site_stats[s] = {"sent": 0}
        if item.get("status") == "sent":
            site_stats[s]["sent"] += 1

    # This week / this month
    now = datetime.now()
    week_start = now - timedelta(days=now.weekday())
    month_start = now.replace(day=1)

    week_sent = 0
    week_responses = 0
    month_sent = 0
    month_responses = 0

    for item in unique:
        sent_str = item.get("sent_date", "")
        if not sent_str:
            continue
        try:
            sd = datetime.strptime(sent_str[:10], "%Y-%m-%d")
        except ValueError:
            continue

        if sd >= week_start:
            if item.get("status") == "sent":
                week_sent += 1
            if item.get("response_status"):
                week_responses += 1

        if sd >= month_start:
            if item.get("status") == "sent":
                month_sent += 1
            if item.get("response_status"):
                month_responses += 1

    # Print dashboard
    today = datetime.now().strftime("%B %-d, %Y")
    print(f"\nOutreach Dashboard \u2014 {today}")
    print("\u2501" * 50)
    print(f"Pending review:     {pending}")
    print(f"Approved (unsent):  {approved}")
    print(f"Sent:              {sent:>2}")
    print(f"Follow-ups due:     {followups_due}")
    print(f"Responses:          {responses}")
    print()

    print("By type:")
    all_types = ["haro_response", "broken_link", "resource_page", "brand_mention",
                 "guest_post", "unlinked_mention"]
    for t in all_types:
        label = t.replace("_", " ").title() + "s"
        stats = type_stats.get(t, {"sent": 0, "responses": 0})
        if stats["sent"] > 0 or t in type_stats:
            print(f"  {label:<20} {stats['sent']} sent, {stats['responses']} response(s)")
        elif t in ("haro_response", "broken_link", "resource_page", "brand_mention"):
            print(f"  {label:<20} 0 sent")
    # Any other types
    for t, stats in type_stats.items():
        if t not in all_types:
            label = t.replace("_", " ").title() + "s"
            print(f"  {label:<20} {stats['sent']} sent, {stats['responses']} response(s)")
    print()

    print("By site:")
    for s in sorted(site_stats.keys()):
        print(f"  {s:<20} {site_stats[s]['sent']} sent")
    if not site_stats:
        for s in SITES:
            print(f"  {s:<20} 0 sent")
    print()

    print(f"This week: {week_sent} sent, {week_responses} response(s)")
    print(f"This month: {month_sent} sent, {month_responses} response(s)")
    print("\u2501" * 50)


# ── Response Tracking ────────────────────────────────────────

def cmd_response(item_id: str, got_link: str = None,
                 rejected: bool = False, pending: bool = False):
    """Mark an outreach item with a response status."""
    queue = load_json(OUTREACH_QUEUE)
    log = load_json(OUTREACH_LOG)

    # Find item in queue or log
    found = False
    for collection in (queue, log):
        for item in collection:
            if item.get("id") == item_id:
                if got_link:
                    item["response_status"] = "got_link"
                    item["response_link"] = got_link
                    item["response_date"] = now_str()
                    print(f"Marked {item_id} as GOT LINK: {got_link}")
                elif rejected:
                    item["response_status"] = "rejected"
                    item["response_date"] = now_str()
                    print(f"Marked {item_id} as REJECTED")
                elif pending:
                    item["response_status"] = "pending_response"
                    item["response_date"] = now_str()
                    print(f"Marked {item_id} as PENDING (interested)")
                else:
                    print("Specify --got-link URL, --rejected, or --pending")
                    return
                found = True

    if not found:
        print(f"Item {item_id} not found in queue or log.")
        # Show available IDs
        all_ids = []
        for item in queue + log:
            if item.get("id") and item.get("status") == "sent":
                all_ids.append(
                    f"  {item['id'][:12]}... -> {item.get('target_email', '?')} "
                    f"({item.get('type', '?')})"
                )
        if all_ids:
            print("\nSent items:")
            for line in all_ids[:20]:
                print(line)
        return

    save_json(OUTREACH_QUEUE, queue)
    save_json(OUTREACH_LOG, log)


# ── Main ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Outreach Manager — Review, send, and track outreach emails."
    )
    parser.add_argument("--review", action="store_true",
                        help="Interactive review of pending drafts")
    parser.add_argument("--send", action="store_true",
                        help="Send all approved emails")
    parser.add_argument("--send-followups", action="store_true",
                        help="Send follow-ups for emails sent >7 days ago")
    parser.add_argument("--status", action="store_true",
                        help="Show outreach dashboard")
    parser.add_argument("--auto", action="store_true",
                        help="Auto-send approved emails (for cron)")
    parser.add_argument("--response", metavar="ID",
                        help="Mark response for an outreach item by ID")
    parser.add_argument("--got-link", metavar="URL",
                        help="URL of the link received (use with --response)")
    parser.add_argument("--rejected", action="store_true",
                        help="Mark as rejected (use with --response)")
    parser.add_argument("--pending", action="store_true",
                        help="Mark as pending/interested (use with --response)")

    args = parser.parse_args()

    if args.review:
        cmd_review()
    elif args.send:
        cmd_send(auto=False)
    elif args.send_followups:
        cmd_send_followups()
    elif args.status:
        cmd_status()
    elif args.auto:
        cmd_send(auto=True)
    elif args.response:
        cmd_response(
            item_id=args.response,
            got_link=args.got_link,
            rejected=args.rejected,
            pending=args.pending,
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
