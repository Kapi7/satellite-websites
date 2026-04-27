#!/usr/bin/env python3
"""
Take MULTIPLE real product photos → upload to Gemini → get back a styled
editorial K-beauty flat-lay hero with all of them in it.

Same idea as gemini_enhance_hero.py but with 3-4 product photos per article
so the hero feels like a real K-beauty website hero (multiple bottles, good
vibe) instead of a single isolated product.

Usage:
    python3 scripts/gemini_compose_hero.py --site cosmetics
    python3 scripts/gemini_compose_hero.py --site cosmetics --slug <slug>
    python3 scripts/gemini_compose_hero.py --site cosmetics --max-products 4
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

# Editorial K-beauty mood variants for variety across articles
SCENE_VARIANTS = [
    "soft cream marble surface with diffuse window light, fresh green heartleaf and small white camellia petals scattered around the edges",
    "warm sandstone slab with golden-hour sunlight, fresh eucalyptus sprigs and small water droplets dotted across the surface",
    "pale beige linen fabric with soft morning shadows, dried lavender stems and a small ceramic bowl of rose petals at one corner",
    "white travertine surface with bright natural daylight, fresh mint leaves and clear glass beads scattered subtly",
    "blush-toned terrazzo with sun-dappled shadows from leaves overhead, a few rose petals and small pebbles at the edges",
    "smooth pale-pink ceramic tile with soft daylight, fresh peony petals and a single dried wheat stem in one corner",
    "ivory plaster surface with delicate side lighting, fresh green tea leaves and a tiny porcelain dish of seaweed at one corner",
    "champagne silk fabric draped naturally with soft warm light, fresh white camellia flowers and small glass beads",
    "weathered oak wood grain with morning sun streaks, fresh basil leaves and a small bamboo bowl in the corner",
    "sage-tinted marble with cool overhead light, fresh ivy sprigs and small smooth river pebbles at the edges",
]


def scene_for(slug: str) -> str:
    return SCENE_VARIANTS[hash(slug) % len(SCENE_VARIANTS)]


PROMPT_TEMPLATE = """Create a 16:9 landscape editorial hero photograph for a premium K-beauty magazine using ALL of the attached product photos.

ABSOLUTE PRESERVATION RULES (read carefully):
- The attached photos are REAL products. Treat them as photographs to arrange in a scene, not as references to redraw.
- Preserve every product's exact bottle shape, exact label, exact brand name, exact Korean characters, exact ingredient list, exact volume/SPF rating, exact text — pixel-for-pixel as it appears in the input.
- Do NOT invent products. Do NOT alter labels. Do NOT change colors. Do NOT redraw anything on the bottles.
- Every attached product must appear in the final image. None may be missing.

SCENE COMPOSITION:
- Arrange ALL the products in an editorial K-beauty flat-lay (overhead view).
- Vary placement: some standing, some tilted, some lying down. Stagger heights and angles.
- Surface and atmosphere: {scene}.
- Soft natural sunlight, gentle drop shadows under each product, magazine-quality depth of field.
- 16:9 landscape composition, products grouped roughly in the center-third with breathing room around them.
- No text overlays. No watermarks. No additional invented products.

Style reference: think Glossier, Beauty of Joseon, COSRX official campaign photography — clean, warm, naturally lit, uncluttered."""


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


def normalize_for_gemini(path: Path) -> bytes:
    """Open the product image, resize to a consistent max dimension so Gemini
    sees them at similar scale, return JPEG bytes."""
    img = Image.open(path).convert("RGB")
    img.thumbnail((900, 900), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def gemini_compose(product_paths: list[Path], output_path: Path, slug: str) -> bool:
    if len(product_paths) < 2:
        print("      need at least 2 product photos")
        return False
    parts: list = [PROMPT_TEMPLATE.format(scene=scene_for(slug))]
    for p in product_paths:
        parts.append(types.Part.from_bytes(data=normalize_for_gemini(p), mime_type="image/jpeg"))

    try:
        resp = client.models.generate_content(
            model=MODEL,
            contents=parts,
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
        for part in resp.candidates[0].content.parts:
            if hasattr(part, "text") and part.text:
                print(f"      gemini text-only response: {part.text[:200]}")
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
    ap.add_argument("--max-products", type=int, default=4, help="Max product photos per hero (default 4)")
    args = ap.parse_args()

    site_dir = SITES[args.site]
    drafts = collect_drafts(site_dir)
    if args.slug:
        drafts = [d for d in drafts if d["slug"] == args.slug]
    if args.limit:
        drafts = drafts[: args.limit]

    print(f"[{args.site}] {len(drafts)} drafts to compose multi-product heroes for\n")

    success, fail = 0, 0
    for d in drafts:
        print(f"  → {d['slug']}")
        prods = []
        for h in d["handles"][: args.max_products + 2]:  # try a few extra in case some 404
            p = download_product_image(h)
            if p:
                prods.append(p)
                print(f"    + {h} ({p.stat().st_size//1024}KB)")
            if len(prods) >= args.max_products:
                break
        if len(prods) < 2:
            print("    SKIP: <2 product photos available\n")
            fail += 1
            continue

        out_path = site_dir / "public" / d["image_rel"].lstrip("/")
        ok = gemini_compose(prods, out_path, d["slug"])
        if ok:
            print(f"    SAVED → {out_path.relative_to(ROOT)}\n")
            success += 1
        else:
            print(f"    FAIL: gemini didn't return image\n")
            fail += 1
        time.sleep(2)

    print(f"\n[done] {success} composed, {fail} failed")


if __name__ == "__main__":
    main()
