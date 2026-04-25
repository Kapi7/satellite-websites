#!/usr/bin/env python3
"""Generate Mirai Pinterest pin batch — appends entries to pinterest_schedule.json.

Pipeline:
  1. select_mirai_products.py picks N products
  2. build_mirai_pin_images.py renders each into a 1000x1500 jpg
  3. (this script) generates Pinterest title/description/board mapping
     and appends scheduled entries to pinterest_schedule.json

Pinterest copy is template-driven (no LLM call needed for v1) — keeps the
pipeline cheap and deterministic. Future iteration can swap for Gemini if
descriptions feel generic.

Usage:
  python3 generate_mirai_pin_batch.py picked.json [--start-date 2026-04-26] [--per-day 3]
  python3 generate_mirai_pin_batch.py /tmp/sample-3.json --per-day 1 --start-date 2026-04-26
"""
import argparse
import json
import sys
import urllib.parse
import uuid
from datetime import datetime, timedelta, time as dtime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (
    PINTEREST_BOARD_MAP,
    PINTEREST_MIRAI_UTM,
    PINTEREST_SCHEDULE,
    MIRAI_PIN_IMAGES_DIR,
)
from build_mirai_pin_images import shorten_title

# Time slots through the day. Pinterest's algorithm prefers consistent posting.
DAILY_SLOTS = [dtime(12, 0), dtime(15, 0), dtime(18, 0)]

# Pinterest title templates by board (≤100 chars; rich punctuation OK)
TITLE_TEMPLATES = {
    "sunscreen":   "{vendor} {short}: Korean SPF you'll actually want to wear",
    "moisturizer": "{vendor} {short} — Korean barrier-repair moisturizer",
    "cleanser":    "{vendor} {short}: a gentle K-beauty cleanser worth keeping",
    "serum":       "{vendor} {short}: Korean serum that earns its place in the routine",
    "toner":       "{vendor} {short} — the K-beauty toner step nobody talks about",
    "mask":        "{vendor} {short}: Korean treatment mask, tested and recommended",
    "makeup":      "{vendor} {short} — Korean beauty pick worth shelf space",
    "_default":    "{vendor} {short}: K-beauty essential",
}

# Pinterest descriptions (≤500 chars). Use 4-7 hashtags at the end.
DESC_TEMPLATES = {
    "sunscreen": (
        "Looking for a Korean sunscreen that actually feels good on the skin? "
        "{vendor} {long} delivers SPF protection without the white cast or greasy finish "
        "Western sunscreens are known for. Tested + recommended at Mirai. "
        "Tap to shop.\n\n"
        "#kbeauty #koreanskincare #koreansunscreen #spf #skincareroutine #koreanbeauty"
    ),
    "moisturizer": (
        "Real Korean barrier-repair moisturizer, not hype. {vendor} {long} works "
        "for sensitive, dehydrated, and reactive skin types. Ceramides, panthenol, "
        "and madecassoside that calm the skin instead of irritating it. "
        "Shop at Mirai.\n\n"
        "#kbeauty #koreanskincare #moisturizer #skincare #barrierrepair #sensitiveskin"
    ),
    "cleanser": (
        "{vendor} {long} — a Korean cleanser worth keeping in the routine. "
        "Gentle enough for daily use, effective enough that your skin feels clean "
        "without that tight post-wash feeling. The first step in a real Korean routine.\n\n"
        "#kbeauty #koreanskincare #cleanser #doublecleansing #skincareroutine"
    ),
    "serum": (
        "Korean serums earn their place. {vendor} {long} delivers actives in a vehicle "
        "that absorbs cleanly without pilling under sunscreen. Layer-friendly. "
        "Honest review and shop at Mirai.\n\n"
        "#kbeauty #koreanskincare #serum #skincare #koreanbeauty"
    ),
    "toner": (
        "{vendor} {long} — the Korean toner step that actually changes how skin "
        "feels. Hydration, pH balance, prep for actives. Glass-skin starts here.\n\n"
        "#kbeauty #koreanskincare #toner #glassskin #skincareroutine"
    ),
    "mask": (
        "{vendor} {long} — Korean treatment mask we'd recommend without the influencer "
        "act. Real ingredients, real result. Shop at Mirai.\n\n"
        "#kbeauty #koreanskincare #sheetmask #masks #skincare"
    ),
    "makeup": (
        "{vendor} {long} — K-beauty makeup pick that earns shelf space. "
        "Skin-first formulas that flatter without sitting heavy. Shop at Mirai.\n\n"
        "#kbeauty #koreanmakeup #cushion #bbcream #koreanbeauty"
    ),
    "_default": (
        "{vendor} {long} — a K-beauty pick we'd recommend to a friend. "
        "Honest review and shop at Mirai.\n\n"
        "#kbeauty #koreanskincare #koreanbeauty #skincare"
    ),
}


def pin_url(handle: str, slug: str) -> str:
    base = f"https://mirai-skin.com/products/{handle}/"
    params = dict(PINTEREST_MIRAI_UTM)
    params["utm_content"] = slug
    return base + "?" + urllib.parse.urlencode(params)


def build_pin_entry(product: dict, image_path: Path, scheduled_at: datetime, slug: str) -> dict:
    board = product.get("board", "_default")
    vendor = (product.get("vendor") or "").strip()
    short = shorten_title(product.get("title", ""), vendor, max_chars=40)
    long_title = product.get("title", "").strip()
    # Strip leading vendor from long title too (avoids "Innisfree Innisfree ..." in copy)
    if vendor and long_title.lower().startswith(vendor.lower()):
        long_title = long_title[len(vendor):].lstrip(" -").strip()

    title_tmpl = TITLE_TEMPLATES.get(board, TITLE_TEMPLATES["_default"])
    desc_tmpl = DESC_TEMPLATES.get(board, DESC_TEMPLATES["_default"])
    title = title_tmpl.format(vendor=vendor, short=short)[:100]
    desc = desc_tmpl.format(vendor=vendor, long=long_title)[:500]

    board_name = PINTEREST_BOARD_MAP["mirai"].get(board, PINTEREST_BOARD_MAP["mirai"]["_default"])

    return {
        "id": str(uuid.uuid4())[:8],
        "title": title,
        "description": desc,
        "url": pin_url(product["handle"], slug),
        "image_path": str(image_path.resolve()),
        "board": board_name,
        "site": "mirai",
        "domain": "mirai-skin.com",
        "category": board,
        "tags": product.get("tags", [])[:8],
        "scheduled_date": scheduled_at.strftime("%Y-%m-%dT%H:%M:%S"),
        "status": "pending",
        "posted_at": None,
        "_meta": {
            "vendor": vendor,
            "product_handle": product["handle"],
            "price": product.get("price"),
        },
    }


def slot_iterator(start_date: datetime, per_day: int):
    slots = DAILY_SLOTS[:per_day]
    day = start_date
    while True:
        for s in slots:
            yield datetime.combine(day.date(), s)
        day += timedelta(days=1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("picked", type=Path, help="JSON output of select_mirai_products.py")
    ap.add_argument("--start-date", default=None,
                    help="ISO date for first pin (default: tomorrow). e.g. 2026-04-26")
    ap.add_argument("--per-day", type=int, default=3, help="Pins per day (max 3 for safety)")
    ap.add_argument("--images-dir", type=Path, default=MIRAI_PIN_IMAGES_DIR)
    ap.add_argument("--prefix", default="pin")
    ap.add_argument("--schedule", type=Path, default=PINTEREST_SCHEDULE)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    products = json.loads(args.picked.read_text())

    if args.start_date:
        start = datetime.fromisoformat(args.start_date)
    else:
        start = datetime.now() + timedelta(days=1)
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)

    slots = slot_iterator(start, max(1, min(args.per_day, 3)))

    new_entries = []
    for i, p in enumerate(products):
        slug_suffix = (p.get("handle") or f"item-{i}")[:40]
        pin_slug = f"{args.prefix}-{i:03d}"
        image_path = args.images_dir / f"{pin_slug}-{slug_suffix}.jpg"
        if not image_path.exists():
            print(f"  ⚠ missing image, skipping: {image_path}")
            continue
        scheduled_at = next(slots)
        entry = build_pin_entry(p, image_path, scheduled_at, pin_slug)
        new_entries.append(entry)

    print(f"\nbuilt {len(new_entries)} schedule entries")
    print(f"first scheduled: {new_entries[0]['scheduled_date'] if new_entries else 'n/a'}")
    print(f"last scheduled:  {new_entries[-1]['scheduled_date'] if new_entries else 'n/a'}")

    if args.dry_run:
        print("\n=== DRY RUN sample (first entry) ===")
        print(json.dumps(new_entries[0], indent=2))
        return 0

    # Append to existing schedule
    existing = []
    if args.schedule.exists():
        try:
            existing = json.loads(args.schedule.read_text())
            if not isinstance(existing, list):
                existing = []
        except Exception:
            existing = []
    args.schedule.write_text(json.dumps(existing + new_entries, indent=2))
    print(f"appended → {args.schedule}  (total entries now: {len(existing) + len(new_entries)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
