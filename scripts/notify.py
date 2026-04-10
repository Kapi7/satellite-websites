#!/usr/bin/env python3
"""
Telegram notifier — sends messages to @SEO_mirai_bot for async visibility.

Usage:
  python3 scripts/notify.py "Build finished · glow-coded"
  python3 scripts/notify.py --level ok   "Deploy succeeded"
  python3 scripts/notify.py --level warn "GSC clicks dropped 20% on rooted-glow"
  python3 scripts/notify.py --level err  "Build failed in astro step"
  echo "message body" | python3 scripts/notify.py --stdin --title "Weekly digest"

Env:
  TELEGRAM_BOT_TOKEN  required
  TELEGRAM_CHAT_ID    required

Exits 0 on send success, 1 on config error, 2 on API error.
"""

import argparse
import os
import sys
import urllib.parse
import urllib.request

LEVEL_ICONS = {
    "ok": "✅",
    "info": "ℹ️",
    "warn": "⚠️",
    "err": "❌",
    "ship": "🚀",
    "report": "📊",
}


def send(token: str, chat_id: str, text: str) -> tuple[bool, str]:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }
    ).encode()
    try:
        with urllib.request.urlopen(url, data=data, timeout=15) as resp:
            body = resp.read().decode()
            return resp.status == 200, body
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read().decode()}"
    except Exception as e:
        return False, str(e)


def main() -> int:
    p = argparse.ArgumentParser(description="Send a Telegram notification.")
    p.add_argument("message", nargs="?", help="Message body (omit with --stdin).")
    p.add_argument(
        "--level",
        default="info",
        choices=list(LEVEL_ICONS.keys()),
        help="Severity icon.",
    )
    p.add_argument("--title", help="Optional bold title line.")
    p.add_argument("--stdin", action="store_true", help="Read message body from stdin.")
    args = p.parse_args()

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("notify: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set.", file=sys.stderr)
        return 1

    if args.stdin:
        body = sys.stdin.read().strip()
    else:
        body = (args.message or "").strip()

    if not body:
        print("notify: empty message.", file=sys.stderr)
        return 1

    icon = LEVEL_ICONS.get(args.level, "ℹ️")
    lines = []
    if args.title:
        lines.append(f"<b>{icon} {args.title}</b>")
        lines.append(body)
    else:
        lines.append(f"{icon} {body}")
    text = "\n".join(lines)

    ok, info = send(token, chat_id, text)
    if ok:
        return 0
    print(f"notify: failed — {info}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
