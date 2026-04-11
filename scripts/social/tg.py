"""
Thin Telegram notification helper for social posters.

Fire-and-forget: never raises, never blocks the poster run.
Reads TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from env (loaded by config.py).

Usage:
    from tg import notify
    notify("Reddit: posted #5 to r/running", level="ok")
    notify("Pinterest login failed for wellness", level="err")
"""

import os
import urllib.parse
import urllib.request

_ICONS = {
    "ok": "OK",
    "info": "i",
    "warn": "!",
    "err": "X",
    "ship": ">",
    "report": "=",
}


def notify(message: str, level: str = "info", title: str | None = None) -> bool:
    """Send a Telegram message. Returns True on success, False on failure.

    Never raises. Safe to call from inside a poster loop — if Telegram is
    down or env is missing, we silently swallow the error.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return False

    icon = _ICONS.get(level, "i")
    if title:
        text = f"<b>[{icon}] {title}</b>\n{message}"
    else:
        text = f"[{icon}] {message}"

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
        with urllib.request.urlopen(url, data=data, timeout=10) as resp:
            return resp.status == 200
    except Exception:
        return False
