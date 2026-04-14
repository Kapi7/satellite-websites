#!/usr/bin/env python3
"""
Queue health check for the daily publisher.

Runs BEFORE daily-publish.sh picks articles. For each satellite site:
  1. Counts how many `draft: true` articles remain (runway in days).
  2. For every draft, auto-fixes missing fields:
       - `author:` → assigned from per-category rotation (cycles authors).
       - hero image file → generated with Imagen 4.0 fast (text-to-image).
  3. Sends a single Telegram summary (runway + fixes made + warnings).

Never raises: missing API keys or network issues downgrade to warnings.
Exit 0 always so it never blocks the publisher.

Usage:
    python3 scripts/queue_health.py            # full run
    python3 scripts/queue_health.py --dry-run  # report only, no writes
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

# Make notify importable
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR / "social"))
try:
    from tg import notify as tg_notify  # shared helper
except Exception:  # pragma: no cover
    def tg_notify(msg, level="info", title=None):  # type: ignore
        return False

# Load .env so GEMINI_API_KEY / TELEGRAM_* are available when run standalone.
PROJECT_ROOT = SCRIPTS_DIR.parent
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except Exception:
    pass


SITES = {
    "cosmetics": {
        "blog": PROJECT_ROOT / "cosmetics/src/content/blog/en",
        "images": PROJECT_ROOT / "cosmetics/public/images",
        "label": "Glow Coded",
    },
    "wellness": {
        "blog": PROJECT_ROOT / "wellness/src/content/blog/en",
        "images": PROJECT_ROOT / "wellness/public/images",
        "label": "Rooted Glow",
    },
    "build-coded": {
        "blog": PROJECT_ROOT / "build-coded/src/content/blog/en",
        "images": PROJECT_ROOT / "build-coded/public/images",
        "label": "Build Coded",
    },
}

# Per-site author rotation by category. The publisher runs 1/day so
# rotation happens implicitly as drafts drain; this just fills blanks.
AUTHOR_ROTATION = {
    "cosmetics": {
        "skincare":    ["Sophie Laurent", "Mina Park", "Ava Chen"],
        "ingredients": ["Ava Chen", "Sophie Laurent"],
        "reviews":     ["Ava Chen", "Mina Park"],
        "how-tos":     ["Mina Park", "Sophie Laurent"],
    },
    "wellness": {
        "nutrition":      ["Nadia Okafor", "James Reeves"],
        "movement":       ["James Reeves", "Tara Benson"],
        "k-beauty":       ["Nadia Okafor", "Tara Benson"],
        "natural-health": ["Tara Benson", "James Reeves", "Nadia Okafor"],
    },
    "build-coded": {
        "woodworking":      ["Marcus Webb"],
        "home-improvement": ["Marcus Webb"],
        "electronics":      ["Danny Herrera"],
        "crafts":           ["Marcus Webb"],
    },
}

RUNWAY_WARN_DAYS = 10   # ping Telegram as warn if any site has < this many drafts
RUNWAY_CRIT_DAYS = 5    # ping Telegram as err below this

# Known brand domains — if an article links to these, it recommends real products
# and its hero image must show real product photos (not AI-generated fakes).
PRODUCT_DOMAINS = {
    "cosrx.com", "beautyofjoseon.com", "skin1004.com", "torriden.us",
    "anua.com", "medicube.us", "banilausa.com", "ksecretcosmetics.com",
    "axis-y.com", "innisfree.com", "us.innisfree.com", "pyunkangyul.us",
    "purito.com", "drjart.com", "etude.com",
    "nike.com", "brooksrunning.com", "asics.com", "saucony.com", "adidas.com",
    "dewalt.com", "milwaukeetool.com", "makitatools.com", "kleintools.com",
    "fluke.com", "hakko.com", "bambulab.com", "creality.com",
    "amazon.com",  # product reviews often link to Amazon
}

IMAGEN_MODEL = "imagen-4.0-fast-generate-001"
IMAGEN_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{IMAGEN_MODEL}:predict"
)
STYLE_SUFFIX = (
    "High quality editorial blog hero photography. Natural lighting. "
    "16:9 landscape composition. No text, no watermarks, no logos."
)


def parse_frontmatter(mdx_text: str) -> dict:
    m = re.match(r"^---\s*\n(.*?)\n---", mdx_text, re.DOTALL)
    if not m:
        return {}
    fm: dict = {}
    for line in m.group(1).splitlines():
        mm = re.match(r"^(\w[\w-]*):\s*(.*)$", line)
        if not mm:
            continue
        k, v = mm.group(1), mm.group(2).strip()
        v = v.strip('"').strip("'")
        fm[k] = v
    return fm


def list_drafts(site_key: str) -> list[Path]:
    blog = SITES[site_key]["blog"]
    if not blog.exists():
        return []
    out = []
    for mdx in sorted(blog.glob("*.mdx")):
        try:
            text = mdx.read_text(encoding="utf-8")
        except Exception:
            continue
        if re.search(r"^draft:\s*true\s*$", text, re.MULTILINE):
            out.append(mdx)
    return out


def ensure_author(mdx: Path, site_key: str, dry_run: bool) -> str | None:
    """If draft lacks `author:` field, assign next from rotation. Returns assigned name or None."""
    text = mdx.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    if fm.get("author"):
        return None  # already set
    category = fm.get("category", "").strip()
    rotation = AUTHOR_ROTATION.get(site_key, {}).get(category)
    if not rotation:
        return None  # unknown category, leave alone

    # Pick author by filename hash so same file always gets same author
    # but different files cycle through the list deterministically.
    idx = sum(ord(c) for c in mdx.stem) % len(rotation)
    author = rotation[idx]

    if dry_run:
        return author

    # Insert `author: "<name>"` right after the last frontmatter line
    m = re.match(r"^(---\s*\n)(.*?)(\n---)", text, re.DOTALL)
    if not m:
        return None
    new_fm = m.group(2).rstrip() + f'\nauthor: "{author}"'
    new_text = m.group(1) + new_fm + m.group(3) + text[m.end():]
    mdx.write_text(new_text, encoding="utf-8")
    return author


def is_product_article(mdx: Path) -> bool:
    """Check if an article recommends real products (links to brand/retailer sites)."""
    text = mdx.read_text(encoding="utf-8")
    # Count links to known product domains
    links = re.findall(r"https?://(?:www\.)?([a-z0-9.-]+)", text)
    product_links = sum(1 for domain in links if any(domain.endswith(pd) for pd in PRODUCT_DOMAINS))
    return product_links >= 2  # 2+ product links = product article


def build_image_prompt(fm: dict, site_key: str) -> str:
    base = fm.get("imageAlt") or fm.get("title") or "editorial lifestyle photograph"
    site_hint = {
        "cosmetics": "Clean, bright Korean beauty product photography aesthetic.",
        "wellness": "Warm, natural wellness lifestyle photography.",
        "build-coded": "Workshop / maker space photography with tools and materials.",
    }.get(site_key, "")
    return f"Realistic professional photograph: {base}. {site_hint} {STYLE_SUFFIX}"


def generate_hero_image(image_path: Path, prompt: str, api_key: str) -> bool:
    payload = json.dumps({
        "instances": [{"prompt": prompt}],
        "parameters": {
            "sampleCount": 1,
            "aspectRatio": "16:9",
            "outputOptions": {"mimeType": "image/jpeg"},
        },
    }).encode()
    req = urllib.request.Request(
        f"{IMAGEN_URL}?key={api_key}",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
        preds = result.get("predictions") or []
        if preds and "bytesBase64Encoded" in preds[0]:
            image_path.parent.mkdir(parents=True, exist_ok=True)
            image_path.write_bytes(base64.b64decode(preds[0]["bytesBase64Encoded"]))
            return True
    except Exception:
        return False
    return False


def ensure_hero(mdx: Path, site_key: str, api_key: str, dry_run: bool) -> str | None:
    """If draft references an image file that doesn't exist, generate it. Returns image_name or None."""
    text = mdx.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    image_raw = fm.get("image", "")
    if not image_raw:
        return None
    image_name = image_raw.removeprefix("/images/")
    if not image_name:
        return None
    image_path = SITES[site_key]["images"] / image_name
    if image_path.exists():
        return None
    if dry_run:
        return image_name
    if not api_key:
        return None
    prompt = build_image_prompt(fm, site_key)
    if generate_hero_image(image_path, prompt, api_key):
        return image_name
    return None


def main() -> int:
    p = argparse.ArgumentParser(description="Queue health check for satellite publishers")
    p.add_argument("--dry-run", action="store_true", help="Report only, no writes")
    args = p.parse_args()

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    dry = args.dry_run

    report_lines: list[str] = []
    highest_level = "ok"  # ok → warn → err

    for site_key, cfg in SITES.items():
        drafts = list_drafts(site_key)
        runway = len(drafts)

        authors_fixed = []
        images_fixed = []
        image_failed = []
        product_hero_warnings = []  # articles with products that need real-product heroes

        for mdx in drafts:
            # Author rotation
            assigned = ensure_author(mdx, site_key, dry)
            if assigned:
                authors_fixed.append(f"{mdx.stem} → {assigned}")

            # Hero image
            text = mdx.read_text(encoding="utf-8")
            fm = parse_frontmatter(text)
            image_raw = fm.get("image", "").removeprefix("/images/")
            if image_raw:
                image_path = cfg["images"] / image_raw
                if not image_path.exists():
                    if dry:
                        images_fixed.append(f"{mdx.stem} (dry-run)")
                    elif not api_key:
                        image_failed.append(f"{mdx.stem} (no GEMINI_API_KEY)")
                    else:
                        got = ensure_hero(mdx, site_key, api_key, dry)
                        if got:
                            images_fixed.append(mdx.stem)
                            time.sleep(2)  # rate-limit courtesy
                        else:
                            image_failed.append(mdx.stem)

            # Product-hero check: if article links to real products, warn that
            # the hero image should use real product photos (not text-to-image).
            if is_product_article(mdx):
                if image_raw and (cfg["images"] / image_raw).exists():
                    # Hero exists — check if file is small (< 50KB) which may
                    # indicate a text-only AI generation. Real-product heroes
                    # are typically 80-400KB.
                    hero_size = (cfg["images"] / image_raw).stat().st_size
                    if hero_size < 50_000:
                        product_hero_warnings.append(
                            f"{mdx.stem} (hero {hero_size // 1024}KB — may need real product photos)"
                        )
                elif not image_raw:
                    product_hero_warnings.append(
                        f"{mdx.stem} (no hero image set — product article needs one)"
                    )

        # Determine severity for this site
        if runway <= RUNWAY_CRIT_DAYS:
            level = "err"
        elif runway <= RUNWAY_WARN_DAYS:
            level = "warn"
        else:
            level = "ok"
        if ({"ok": 0, "warn": 1, "err": 2}[level]
                > {"ok": 0, "warn": 1, "err": 2}[highest_level]):
            highest_level = level

        line = f"• {cfg['label']}: {runway} draft(s) — runway ~{runway}d"
        if authors_fixed:
            line += f"\n    authors assigned: {len(authors_fixed)}"
        if images_fixed:
            line += f"\n    heroes generated: {len(images_fixed)}"
        if image_failed:
            line += f"\n    heroes FAILED: {len(image_failed)}"
        if product_hero_warnings:
            line += f"\n    ⚠ product-hero check: {len(product_hero_warnings)} need review"
        report_lines.append(line)

        print(line)
        for a in authors_fixed:
            print(f"    [author] {a}")
        for i in images_fixed:
            print(f"    [hero]   {i}")
        for i in image_failed:
            print(f"    [FAIL]   {i}")
        for w in product_hero_warnings:
            print(f"    [PRODUCT] {w}")

    summary = "\n".join(report_lines)
    if dry:
        summary = "[DRY-RUN] " + summary
    tg_notify(summary, level=highest_level, title="Queue health")
    return 0


if __name__ == "__main__":
    sys.exit(main())
