#!/usr/bin/env python3
"""Build the 30-day Mirai Pinterest pipeline.

Generates 90 unique pins from 30 themes × 3 product variants each.
Renders all images via Gemini 2.5 Flash Image and writes pinterest_schedule.json
entries staggered at 3 pins/day starting tomorrow.

Usage:
  python3 build_mirai_30day_pipeline.py
  python3 build_mirai_30day_pipeline.py --start 2026-04-28 --variants 3
  python3 build_mirai_30day_pipeline.py --themes-only sunscreens-no-white-cast,centella-moisturizers
"""
import argparse
import json
import os
import random
import sys
import time
import urllib.request
import uuid
from datetime import datetime, timedelta, time as dtime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import MIRAI_PIN_IMAGES_DIR, MIRAI_PRODUCT_CATALOG, PINTEREST_MIRAI_UTM, PINTEREST_SCHEDULE
from mirai_themes import THEMES, Theme
from build_mirai_pins_gemini import (
    fetch_real_product_image,
    call_gemini_compose,
    crop_to_2_3,
    overlay_text,
)

PIN_OUT_DIR = MIRAI_PIN_IMAGES_DIR / "pipeline-30day"
DAILY_SLOTS = [dtime(11, 30), dtime(15, 0), dtime(18, 30)]


def vendor_balanced_pick(candidates: list[dict], n: int, exclude_handles: set[str] = None) -> list[dict]:
    """Pick n products from candidates with vendor diversity, skipping any
    handles in exclude_handles (used to ensure 3 variants of one theme have
    no duplicate products)."""
    exclude_handles = exclude_handles or set()
    avail = [p for p in candidates if p.get("handle") not in exclude_handles]
    if len(avail) < n:
        # Fall back to allowing reuse if not enough fresh products
        avail = candidates
    seen, chosen = set(), []
    for p in avail:
        v = (p.get("vendor") or "").lower().strip()
        if v in seen: continue
        chosen.append(p); seen.add(v)
        if len(chosen) >= n: break
    if len(chosen) < n:
        for p in avail:
            if p not in chosen:
                chosen.append(p)
                if len(chosen) >= n: break
    return chosen[:n]


def render_pin_image(theme: Theme, products: list[dict], variant_idx: int, out_dir: Path) -> Path | None:
    print(f"  → rendering {theme.slug} variant {variant_idx} ({len(products)} products)")
    images = []
    chosen = []
    for p in products:
        img = fetch_real_product_image(p)
        if img:
            images.append(img)
            chosen.append(p)
            print(f"    ✓ {p['handle'][:55]}")
    if len(images) < 2:
        print(f"    ✗ not enough product images ({len(images)})")
        return None

    composed = call_gemini_compose(images, theme.prompt)
    if composed is None:
        return None
    composed = crop_to_2_3(composed)
    final = overlay_text(composed, theme)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{theme.slug}-v{variant_idx}.jpg"
    final.save(out_path, "JPEG", quality=90, optimize=True)
    print(f"    ✓ saved → {out_path.name}")
    return out_path


THEME_TO_BOARD = {t.slug: t.board for t in THEMES}


# Pinterest description templates per theme cluster
DESC_GENERIC = (
    "{headline} — {subhead}. Curated picks tested at Mirai Skin. "
    "Tap to shop the full edit.\n\n"
    "#kbeauty #koreanskincare #koreanbeauty #skincareroutine"
)


def build_description(theme: Theme) -> str:
    return DESC_GENERIC.format(headline=theme.headline, subhead=theme.subhead)[:500]


def build_url(theme: Theme, variant_idx: int) -> str:
    base = theme.pin_url
    sep = "&" if "?" in base else "?"
    params = dict(PINTEREST_MIRAI_UTM)
    params["utm_campaign"] = "30day_pipeline"
    params["utm_content"] = f"{theme.slug}-v{variant_idx}"
    return base + sep + "&".join(f"{k}={v}" for k, v in params.items())


def slot_iter(start_date: datetime):
    day = start_date
    while True:
        for s in DAILY_SLOTS:
            yield datetime.combine(day.date(), s)
        day += timedelta(days=1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=None,
                    help="ISO start date (default: tomorrow). e.g. 2026-04-28")
    ap.add_argument("--variants", type=int, default=3,
                    help="Pins per theme (default 3 → 90 pins / 30 days)")
    ap.add_argument("--themes-only", default=None,
                    help="Comma-separated theme slugs to build (default: all)")
    ap.add_argument("--no-render", action="store_true",
                    help="Skip Gemini rendering, only schedule from existing images")
    ap.add_argument("--no-schedule", action="store_true",
                    help="Skip schedule writes, only render images")
    ap.add_argument("--out", type=Path, default=PIN_OUT_DIR)
    args = ap.parse_args()

    if not os.environ.get("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY not set", file=sys.stderr)
        return 2

    catalog = json.loads(MIRAI_PRODUCT_CATALOG.read_text())
    print(f"Catalog: {len(catalog)} products")
    # Trim catalog products that have no images
    catalog = [p for p in catalog if (p.get("images") and any(i.get("src") for i in p["images"] if isinstance(i, dict)))]
    print(f"With images: {len(catalog)} products")
    # Add normalized fields for the filters
    for p in catalog:
        p.setdefault("price", None)
        if p.get("variants"):
            for v in p["variants"]:
                if isinstance(v, dict) and v.get("price"):
                    p["price"] = v["price"]
                    break

    selected = THEMES
    if args.themes_only:
        wanted = {s.strip() for s in args.themes_only.split(",")}
        selected = [t for t in THEMES if t.slug in wanted]
        print(f"Filtered to {len(selected)} theme(s)")

    if args.start:
        start = datetime.fromisoformat(args.start)
    else:
        start = (datetime.now() + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    slots = slot_iter(start)

    new_entries = []
    args.out.mkdir(parents=True, exist_ok=True)
    skipped = []

    for theme in selected:
        candidates = [p for p in catalog if theme.product_filter(p)]
        print(f"\n=== {theme.slug}  candidates: {len(candidates)} ===")
        if len(candidates) < theme.product_count:
            print(f"  ⚠ skipping — only {len(candidates)} candidates, need {theme.product_count}")
            skipped.append((theme.slug, len(candidates)))
            continue

        # Shuffle for variety across variants
        random.seed(theme.slug)
        random.shuffle(candidates)

        used_handles = set()
        for variant in range(args.variants):
            picks = vendor_balanced_pick(candidates, theme.product_count, used_handles)
            if len(picks) < min(2, theme.product_count):
                print(f"  variant {variant}: not enough fresh products, stopping")
                break
            used_handles.update(p["handle"] for p in picks)

            # Render image
            image_path = args.out / f"{theme.slug}-v{variant}.jpg"
            if args.no_render and image_path.exists():
                print(f"  variant {variant}: reusing {image_path.name}")
            else:
                rendered = render_pin_image(theme, picks, variant, args.out)
                if rendered is None:
                    print(f"  variant {variant}: render failed, skipping")
                    continue
                image_path = rendered

            # Build schedule entry
            scheduled_at = next(slots).strftime("%Y-%m-%d")
            entry = {
                "id": str(uuid.uuid4())[:8],
                "title": f"{theme.headline} — {theme.subhead}"[:100],
                "description": build_description(theme),
                "url": build_url(theme, variant),
                "image_path": str(image_path.resolve()),
                "board": theme.board,
                "site": "mirai",
                "domain": "mirai-skin.com",
                "category": theme.slug,
                "tags": ["kbeauty", "koreanbeauty", "skincare", theme.slug.split("-")[0]],
                "scheduled_date": scheduled_at,
                "status": "pending",
                "posted_at": None,
                "_meta": {
                    "theme": theme.slug,
                    "variant": variant,
                    "kind": "30day-pipeline",
                    "products": [{"handle": p["handle"], "title": p["title"], "vendor": p.get("vendor", "")} for p in picks],
                },
            }
            new_entries.append(entry)
            print(f"  ✓ scheduled for {scheduled_at}")

    # Write to schedule
    if not args.no_schedule and new_entries:
        existing = json.loads(PINTEREST_SCHEDULE.read_text())
        PINTEREST_SCHEDULE.write_text(json.dumps(existing + new_entries, indent=2))
        print(f"\n📌 appended {len(new_entries)} entries → {PINTEREST_SCHEDULE.name}")

    print(f"\n=== summary ===")
    print(f"  rendered + scheduled: {len(new_entries)} pins")
    print(f"  themes skipped (insufficient products): {len(skipped)}")
    for slug, count in skipped:
        print(f"    - {slug}: only {count} products in catalog")
    if new_entries:
        first = new_entries[0]["scheduled_date"]
        last = new_entries[-1]["scheduled_date"]
        print(f"  schedule range: {first} → {last}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
