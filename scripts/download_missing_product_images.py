#!/usr/bin/env python3
"""
Find every /images/products/<handle>.jpg referenced in any MDX article that
doesn't exist on disk, then download the og:image from mirai-skin.com for
each missing handle and save it to {site}/public/images/products/{handle}.jpg.

Usage:
    python3 scripts/download_missing_product_images.py            # all 3 sites
    python3 scripts/download_missing_product_images.py --site cosmetics
    python3 scripts/download_missing_product_images.py --dry-run
"""
from __future__ import annotations
import argparse
import io
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SITES = {
    "cosmetics":   ROOT / "cosmetics",
    "wellness":    ROOT / "wellness",
    "build-coded": ROOT / "build-coded",
}

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/*,*/*;q=0.8",
})

PRODUCT_REF_RE = re.compile(r"/images/products/([a-z0-9][a-z0-9-]+)\.jpg", re.I)


def find_referenced_handles(site_dir: Path):
    handles = set()
    for f in (site_dir / "src" / "content" / "blog").rglob("*.mdx"):
        text = f.read_text(errors="ignore")
        for m in PRODUCT_REF_RE.finditer(text):
            handles.add(m.group(1))
    return handles


def find_existing_handles(site_dir: Path):
    images_dir = site_dir / "public" / "images" / "products"
    if not images_dir.exists():
        return set()
    return {p.stem for p in images_dir.glob("*.jpg")}


def fetch_product_og_image(handle: str) -> bytes | None:
    page = f"https://mirai-skin.com/products/{handle}"
    try:
        r = session.get(page, timeout=15, allow_redirects=True)
        if r.status_code != 200:
            return None
        m = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', r.text)
        if not m:
            return None
        img_url = m.group(1)
        if img_url.startswith("//"):
            img_url = "https:" + img_url
        elif not img_url.startswith("http"):
            img_url = urljoin(page, img_url)
        # Strip Shopify size suffix to get full-res
        img_url = re.sub(r"\?.*$", "", img_url)
        rr = session.get(img_url, timeout=20)
        if rr.status_code != 200:
            return None
        return rr.content
    except Exception as e:
        print(f"      [{handle}] error: {e}")
        return None


def save_jpeg(data: bytes, out_path: Path):
    """Convert any image format → JPEG and save with reasonable size cap."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.open(io.BytesIO(data))
    if img.mode != "RGB":
        img = img.convert("RGB")
    # Resize so longest side <= 1200 (saves space on mostly-thumbnail use)
    img.thumbnail((1200, 1200))
    img.save(out_path, "JPEG", quality=88, optimize=True)


def process_site(site_key: str, dry_run: bool = False):
    site_dir = SITES[site_key]
    referenced = find_referenced_handles(site_dir)
    existing = find_existing_handles(site_dir)
    missing = sorted(referenced - existing)

    print(f"\n=== {site_key} ===")
    print(f"  referenced: {len(referenced)}  on disk: {len(existing)}  MISSING: {len(missing)}")

    if not missing:
        return 0, 0

    if dry_run:
        for h in missing[:20]:
            print(f"  • {h}")
        if len(missing) > 20:
            print(f"  ... +{len(missing) - 20} more")
        return 0, len(missing)

    out_dir = site_dir / "public" / "images" / "products"
    success, failed = 0, 0
    for i, handle in enumerate(missing, 1):
        out = out_dir / f"{handle}.jpg"
        print(f"  [{i:>3}/{len(missing)}] {handle} ...", end=" ", flush=True)
        data = fetch_product_og_image(handle)
        if not data:
            print("FAIL")
            failed += 1
            continue
        try:
            save_jpeg(data, out)
            kb = out.stat().st_size // 1024
            print(f"OK ({kb}KB)")
            success += 1
        except Exception as e:
            print(f"SAVE-FAIL ({e})")
            failed += 1
        # Gentle rate limit
        if i % 10 == 0:
            time.sleep(1)

    return success, failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", choices=list(SITES.keys()))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    sites = [args.site] if args.site else list(SITES.keys())
    total_success, total_failed = 0, 0
    for s in sites:
        succ, fail = process_site(s, args.dry_run)
        total_success += succ
        total_failed += fail

    print(f"\n[done] {total_success} images downloaded, {total_failed} failed")


if __name__ == "__main__":
    main()
