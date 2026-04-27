#!/usr/bin/env python3
"""
Take ONE real product photo → upload to Gemini → save enhanced photo.

Per article, picks the first valid product handle linked in the article body,
downloads its og:image from mirai-skin.com, sends that single image to Gemini
2.5 Flash Image with an enhancement prompt, saves the response as the hero.

That's it. No PIL composition, no compositing. Just photo → Gemini → photo.

Usage:
    python3 scripts/gemini_enhance_hero.py --site cosmetics
    python3 scripts/gemini_enhance_hero.py --site cosmetics --slug <slug>
"""
from __future__ import annotations
import argparse
import io
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from PIL import Image

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

from google import genai
from google.genai import types

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

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36",
})

PRODUCT_LINK_RE = re.compile(r"mirai-skin\.com/products/([a-z0-9-]+)", re.I)

PROMPT = (
    "Take this attached product photo and use it as the centerpiece of a 16:9 landscape "
    "editorial hero image for a premium K-beauty blog. Keep the product EXACTLY as it appears "
    "in the photo — same bottle shape, same label text, same brand name, same Korean characters, "
    "same ingredient list, same SPF rating. DO NOT redraw or alter the product in any way. "
    "Around the product, build a luxurious editorial scene: a soft cream marble or warm "
    "sandstone surface, diffuse natural sunlight from the upper left casting soft shadows, "
    "a few sprigs of green heartleaf or eucalyptus and small water droplets at the corners "
    "of the frame — never overlapping the product. Premium beauty magazine aesthetic. "
    "No text overlays. No watermarks. The product must remain instantly recognizable with "
    "every label detail intact."
)


def parse_mdx(path: Path):
    text = path.read_text()
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.S)
    return (m.group(1), m.group(2)) if m else (None, None)


def download_product_image(handle: str) -> Path | None:
    cache = PRODUCTS_CACHE / f"{handle}.jpg"
    if cache.exists() and cache.stat().st_size > 8000:
        return cache
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
        img_url = re.sub(r"\?.*$", "", img_url)
        rr = session.get(img_url, timeout=20)
        if rr.status_code != 200:
            return None
        cache.write_bytes(rr.content)
        return cache
    except Exception as e:
        print(f"      [{handle}] download error: {e}")
        return None


def gemini_enhance(input_path: Path, output_path: Path) -> bool:
    img_bytes = input_path.read_bytes()
    try:
        resp = client.models.generate_content(
            model=MODEL,
            contents=[
                PROMPT,
                types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"),
            ],
            config=types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
        )
        for part in resp.candidates[0].content.parts:
            if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                img = Image.open(io.BytesIO(part.inline_data.data)).convert("RGB")
                # crop to 16:9 if needed
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
                img.save(output_path, "JPEG", quality=92)
                return True
        # if no image in response, log the text
        for part in resp.candidates[0].content.parts:
            if hasattr(part, "text") and part.text:
                print(f"      gemini returned text instead: {part.text[:160]}")
    except Exception as e:
        print(f"      gemini error: {e}")
    return False


def collect_drafts(site_dir: Path):
    en = site_dir / "src" / "content" / "blog" / "en"
    out = []
    for f in sorted(en.glob("*.mdx")):
        fm, body = parse_mdx(f)
        if not fm or body is None:
            continue
        if not re.search(r"^draft:\s*true\s*$", fm, re.M):
            continue
        title_m = re.search(r'title:\s*"([^"]+)"', fm)
        image_m = re.search(r"^image:\s*([^\n]+)", fm, re.M)
        handles = list(dict.fromkeys(PRODUCT_LINK_RE.findall(body)))
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
    ap.add_argument("--slug")
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    site_dir = SITES[args.site]
    drafts = collect_drafts(site_dir)
    if args.slug:
        drafts = [d for d in drafts if d["slug"] == args.slug]
    if args.limit:
        drafts = drafts[: args.limit]

    print(f"[{args.site}] {len(drafts)} drafts to enhance heroes for\n")

    success, fail = 0, 0
    for d in drafts:
        print(f"  → {d['slug']}")
        # Pick first product whose photo we can download
        product_path = None
        chosen_handle = None
        for h in d["handles"]:
            p = download_product_image(h)
            if p:
                product_path = p
                chosen_handle = h
                break
        if not product_path:
            print("    SKIP: no product photo could be downloaded\n")
            fail += 1
            continue

        print(f"    using: {chosen_handle}  ({product_path.stat().st_size//1024}KB)")
        out_path = site_dir / "public" / d["image_rel"].lstrip("/")
        ok = gemini_enhance(product_path, out_path)
        if ok:
            print(f"    SAVED → {out_path.relative_to(ROOT)}\n")
            success += 1
        else:
            print(f"    FAIL: gemini didn't return an image\n")
            fail += 1
        time.sleep(2)

    print(f"\n[done] {success} enhanced, {fail} failed")


if __name__ == "__main__":
    main()
