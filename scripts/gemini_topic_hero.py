#!/usr/bin/env python3
"""
Generate topic-based editorial heroes via Gemini text-to-image.

For sites/articles that don't have product photos to feed into multi-product
compose (build-coded DIY content, pure-wellness rooted-glow articles), this
script generates a clean editorial scene from the article's title + category
using a per-category prompt template.

Usage:
    python3 scripts/gemini_topic_hero.py --site build-coded
    python3 scripts/gemini_topic_hero.py --site wellness --no-products-only
    python3 scripts/gemini_topic_hero.py --site build-coded --slug <slug>
"""
from __future__ import annotations
import argparse
import io
import os
import re
import sys
import time
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

from google import genai
from google.genai import types
from PIL import Image

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("ERROR: GEMINI_API_KEY not set"); sys.exit(1)

client = genai.Client(api_key=api_key)
MODEL = "gemini-2.5-flash-image"

ROOT = Path(__file__).resolve().parent.parent
SITES = {
    "cosmetics":   ROOT / "cosmetics",
    "wellness":    ROOT / "wellness",
    "build-coded": ROOT / "build-coded",
}

PRODUCT_LINK_RE = re.compile(r"mirai-skin\.com/products/([a-z0-9-]+)", re.I)


# Per-category mood prompts. Each is appended to a base "make a 16:9 editorial photo of..."
CATEGORY_PROMPTS = {
    # build-coded
    "woodworking": "a beautifully styled woodworking workshop scene — freshly planed wood, sharp tools, sawdust haze in golden afternoon light, warm and skilled-craftsman aesthetic. No people, no text, no logos. Editorial overhead or 3/4 view.",
    "home-improvement": "a styled home renovation scene — modern tools laid neatly, natural materials, bright daylight from a window, hopeful and capable mood. No people, no text, no logos.",
    "electronics": "a clean modern maker's electronics bench — circuit boards, tools, soldering iron at edge, warm desk lamp glow, focused-precision aesthetic. No people, no text, no logos.",
    "crafts": "a styled craft workspace — natural materials, beautiful textures, soft daylight, calming and creative mood. No people, no text, no logos.",
    # wellness — pure wellness (no K-beauty products)
    "nutrition": "a beautifully styled wellness food scene — fresh ingredients laid on a stone or wood surface, soft morning light, healthy and inviting magazine aesthetic. No people, no text, no logos.",
    "movement": "a serene movement/fitness scene — clean workout floor or trail in early morning light, gentle athletic mood, magazine quality. No people unless from behind in soft focus, no text, no logos.",
    "natural-health": "a calming natural-health flat-lay — herbs, dried flowers, glass jars, soft window light, holistic-wellness magazine aesthetic. No people, no text, no logos.",
    "k-beauty": "a luxurious K-beauty editorial scene — soft cream marble, fresh botanicals, water droplets, magazine-quality natural light. No products visible (those will be added later). No text, no logos.",
}


def parse_mdx(path: Path):
    text = path.read_text()
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.S)
    return (m.group(1), m.group(2)) if m else (None, None)


def gemini_generate(prompt: str, output_path: Path) -> bool:
    try:
        resp = client.models.generate_content(
            model=MODEL,
            contents=[prompt],
            config=types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
        )
        for part in resp.candidates[0].content.parts:
            if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                img = Image.open(io.BytesIO(part.inline_data.data)).convert("RGB")
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
    except Exception as e:
        print(f"      gemini error: {e}")
    return False


def collect_drafts(site_dir: Path, no_products_only: bool):
    en = site_dir / "src" / "content" / "blog" / "en"
    out = []
    for f in sorted(en.glob("*.mdx")):
        fm, body = parse_mdx(f)
        if not fm or body is None:
            continue
        if not re.search(r"^draft:\s*true\s*$", fm, re.M):
            continue
        if no_products_only and PRODUCT_LINK_RE.search(body):
            continue
        title_m = re.search(r'title:\s*"([^"]+)"', fm)
        cat_m = re.search(r"^category:\s*([^\s\n]+)", fm, re.M)
        image_m = re.search(r"^image:\s*([^\n]+)", fm, re.M)
        out.append({
            "path": f,
            "slug": f.stem,
            "title": title_m.group(1) if title_m else f.stem,
            "category": (cat_m.group(1) if cat_m else "").strip().strip('"'),
            "image_rel": image_m.group(1).strip() if image_m else f"/images/{f.stem}.jpg",
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True, choices=list(SITES.keys()))
    ap.add_argument("--slug")
    ap.add_argument("--no-products-only", action="store_true",
                    help="Only process drafts that have NO mirai-skin product links (default: false, all drafts)")
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    site_dir = SITES[args.site]
    drafts = collect_drafts(site_dir, args.no_products_only)
    if args.slug:
        drafts = [d for d in drafts if d["slug"] == args.slug]
    if args.limit:
        drafts = drafts[: args.limit]

    print(f"[{args.site}] {len(drafts)} drafts to generate topic heroes for\n")

    success, fail = 0, 0
    for d in drafts:
        cat = d["category"]
        cat_prompt = CATEGORY_PROMPTS.get(cat)
        if not cat_prompt:
            print(f"  → {d['slug']}  category={cat!r} — no prompt template, using k-beauty fallback")
            cat_prompt = CATEGORY_PROMPTS["k-beauty"]

        prompt = (
            f"Create a premium editorial 16:9 landscape photograph for the article: "
            f"\"{d['title']}\". The scene should depict {cat_prompt} "
            "Realistic photography, premium magazine aesthetic, soft natural light, "
            "shallow depth of field, no text or watermarks anywhere in the image."
        )
        out_path = site_dir / "public" / d["image_rel"].lstrip("/")
        print(f"  → {d['slug']}  [{cat}]")
        ok = gemini_generate(prompt, out_path)
        if ok:
            print(f"    SAVED → {out_path.relative_to(ROOT)}\n")
            success += 1
        else:
            print(f"    FAIL\n")
            fail += 1
        time.sleep(2)

    print(f"\n[done] {success} generated, {fail} failed")


if __name__ == "__main__":
    main()
