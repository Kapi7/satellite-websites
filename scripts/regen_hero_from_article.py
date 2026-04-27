#!/usr/bin/env python3
"""
Regenerate hero images by reading the products an article links to.

Reads each MDX, extracts mirai-skin.com/products/{handle} links, downloads
the real product photo from Mirai, then composes a hero with Gemini 2.5
Flash Image and saves to public/images/{slug}.jpg.

Usage:
    python3 scripts/regen_hero_from_article.py --site cosmetics
    python3 scripts/regen_hero_from_article.py --site cosmetics --slug <slug>
    python3 scripts/regen_hero_from_article.py --site cosmetics --drafts-only
    python3 scripts/regen_hero_from_article.py --site cosmetics --dry-run
"""
from __future__ import annotations
import argparse
import io
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse, urljoin

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

import requests as req_lib
from google import genai
from google.genai import types
from PIL import Image

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("ERROR: GEMINI_API_KEY not set"); sys.exit(1)

client = genai.Client(api_key=api_key)
MODEL = "gemini-2.5-flash-image"

ROOT = Path(__file__).resolve().parent.parent
PRODUCTS_CACHE = Path("/tmp/hero-gen-from-article/products")
PRODUCTS_CACHE.mkdir(parents=True, exist_ok=True)

SITES = {
    "cosmetics": ROOT / "cosmetics",
    "wellness": ROOT / "wellness",
    "build-coded": ROOT / "build-coded",
}

session = req_lib.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/*,*/*;q=0.8",
})

PRODUCT_LINK_RE = re.compile(r"mirai-skin\.com/products/([a-z0-9-]+)", re.I)

GLOW_PROMPT = (
    "Create a flat-lay product photograph in landscape 16:9 ratio. "
    "Place these Korean skincare products on a soft cream-colored marble surface "
    "with diffuse natural lighting and small green botanical accents. "
    "The products MUST look exactly like these reference photos — same bottles, "
    "same labels, same colors, same proportions. Do not invent products. "
    "Premium beauty editorial photography. No text overlays. No watermarks."
)


def parse_mdx(path: Path):
    text = path.read_text()
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.S)
    if not m:
        return None, None
    return m.group(1), m.group(2)


def download_product_image(handle: str) -> Path | None:
    """Hit mirai-skin product page, find og:image, download to cache."""
    cache = PRODUCTS_CACHE / f"{handle}.jpg"
    if cache.exists() and cache.stat().st_size > 8000:
        return cache

    page = f"https://mirai-skin.com/products/{handle}"
    try:
        r = session.get(page, timeout=15, allow_redirects=True)
        if r.status_code != 200:
            return None
        # og:image
        m = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', r.text)
        if not m:
            m = re.search(r'<meta\s+name="twitter:image"\s+content="([^"]+)"', r.text)
        if not m:
            return None
        img_url = m.group(1)
        if img_url.startswith("//"):
            img_url = "https:" + img_url
        elif not img_url.startswith("http"):
            img_url = urljoin(page, img_url)
        # Strip query suffix that downsizes Shopify image
        img_url = re.sub(r"\?.*$", "", img_url)

        rr = session.get(img_url, timeout=20)
        if rr.status_code != 200:
            return None
        cache.write_bytes(rr.content)
        return cache
    except Exception as e:
        print(f"      [{handle}] download error: {e}")
        return None


def compose_hero(product_paths: list[Path], output_path: Path, prompt: str):
    parts = [prompt]
    for p in product_paths:
        try:
            img = Image.open(p)
            if img.mode != "RGB":
                img = img.convert("RGB")
            # cap dimension to 1024 to control upload size
            img.thumbnail((1024, 1024))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=88)
            parts.append({"inline_data": {"mime_type": "image/jpeg", "data": buf.getvalue()}})
        except Exception as e:
            print(f"      WARN: skip {p.name}: {e}")

    if len(parts) < 2:
        return False

    # Convert dict-shape inline_data to types
    typed_parts = [parts[0]]
    for p in parts[1:]:
        typed_parts.append(types.Part.from_bytes(data=p["inline_data"]["data"], mime_type="image/jpeg"))

    try:
        resp = client.models.generate_content(
            model=MODEL,
            contents=typed_parts,
            config=types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
        )
        for part in resp.candidates[0].content.parts:
            if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                img = Image.open(io.BytesIO(part.inline_data.data)).convert("RGB")
                # crop to 16:9
                target = 16 / 9
                cur = img.width / img.height
                if cur > target:
                    new_w = int(img.height * target)
                    left = (img.width - new_w) // 2
                    img = img.crop((left, 0, left + new_w, img.height))
                elif cur < target:
                    new_h = int(img.width / target)
                    top = (img.height - new_h) // 2
                    img = img.crop((0, top, img.width, top + new_h))
                img = img.resize((1200, 675), Image.LANCZOS)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                img.save(output_path, "JPEG", quality=90)
                return True
    except Exception as e:
        print(f"      compose error: {e}")
    return False


def collect_drafts(site_dir: Path, drafts_only=True):
    en = site_dir / "src" / "content" / "blog" / "en"
    out = []
    for f in sorted(en.glob("*.mdx")):
        fm, body = parse_mdx(f)
        if not fm or body is None:
            continue
        is_draft = bool(re.search(r"^draft:\s*true\s*$", fm, re.M))
        if drafts_only and not is_draft:
            continue
        title_m = re.search(r'title:\s*"([^"]+)"', fm)
        image_m = re.search(r"^image:\s*([^\n]+)", fm, re.M)
        handles = list(dict.fromkeys(PRODUCT_LINK_RE.findall(body)))[:4]  # top 4 unique
        if not handles:
            continue
        out.append({
            "path": f,
            "slug": f.stem,
            "title": title_m.group(1) if title_m else f.stem,
            "image_rel": image_m.group(1).strip() if image_m else f"/images/{f.stem}.jpg",
            "handles": handles,
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True, choices=list(SITES.keys()))
    ap.add_argument("--slug", help="Only one slug")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--drafts-only", action="store_true", default=True)
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    site_dir = SITES[args.site]
    drafts = collect_drafts(site_dir, args.drafts_only)
    if args.slug:
        drafts = [d for d in drafts if d["slug"] == args.slug]
    if args.limit:
        drafts = drafts[: args.limit]

    print(f"[{args.site}] {len(drafts)} drafts with products to regen heroes for\n")

    success, fail = 0, 0
    for d in drafts:
        print(f"  → {d['slug']}")
        print(f"    products: {', '.join(d['handles'])}")
        if args.dry_run:
            print()
            continue

        # Download all product photos
        prod_paths = []
        for h in d["handles"]:
            p = download_product_image(h)
            if p:
                prod_paths.append(p)
                print(f"    [{h}] cached ({p.stat().st_size//1024}KB)")
            else:
                print(f"    [{h}] FAIL download")

        if len(prod_paths) < 2:
            print("    SKIP: need at least 2 product photos\n")
            fail += 1
            continue

        out_path = site_dir / "public" / d["image_rel"].lstrip("/")
        ok = compose_hero(prod_paths, out_path, GLOW_PROMPT)
        if ok:
            print(f"    SAVED → {out_path.relative_to(ROOT)}\n")
            success += 1
        else:
            print(f"    FAIL: compose failed\n")
            fail += 1
        time.sleep(2)  # rate-limit

    print(f"\n[done] {success} regenerated, {fail} failed")


if __name__ == "__main__":
    main()
