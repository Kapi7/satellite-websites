#!/usr/bin/env python3
"""Mirai Pinterest pins via OpenAI gpt-image-1 multi-image edit.

Procedure (per user spec 2026-04-27):
  1. Take 1+ real product images from the Mirai Shopify catalog.
  2. Send them to gpt-image-1 /v1/images/edits with a scene prompt.
  3. OpenAI composes them into an editorial Pinterest pin in 1024x1536.
  4. Optionally overlay a headline + CTA chip via Pillow on top.

Why this is different from previous versions:
  v1 = single product on flat color block (Pillow only)
  v2 = single product on AI-generated background (Pillow composite)
  v3 = multiple Pillow-cutouts on AI background (still flat compositing)
  v4 = real products HANDED TO gpt-image-1 to compose naturally with
       proper light/shadow/depth — single image generation, not paste

Usage:
  python3 build_mirai_pins_ai.py /tmp/mirai-60.json --themes 3
"""
import argparse
import base64
import io
import json
import os
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import MIRAI_PIN_IMAGES_DIR
from build_mirai_pin_images import (
    fetch_product_image_with_fallback,
    FONT_DM_SANS,
)

W, H = 1024, 1536
MIRAI_INK = "#1A1614"
MIRAI_ACCENT = "#F4986C"
PIN_OUT_DIR = MIRAI_PIN_IMAGES_DIR / "ai-composed"
PRODUCT_TMP_DIR = MIRAI_PIN_IMAGES_DIR.parent / "ai-input-products"


@dataclass
class Theme:
    slug: str
    headline: str
    subhead: str
    product_filter: callable
    count: int
    pin_url: str
    edit_prompt: str  # passed to gpt-image-1 with the products as input
    cta: str


def _ptype(p): return (p.get("product_type") or "").lower()


def is_sunscreen(p):
    pt = _ptype(p)
    return any(k in pt for k in ["sun ", "sunscreen", "sun cream", "sun stick", "sun gel", "sun fluid", "sun essence", "spf"])


def is_moisturizer(p):
    pt = _ptype(p)
    if is_sunscreen(p): return False
    if any(k in pt for k in ["cleans", "serum", "ampoule", "toner", "mask", "patch", "cushion", "bb cream", "cc cream"]):
        return False
    return any(k in pt for k in ["moisturi", "lotion", "emulsion", "barrier cream", "ceramide"]) or pt in ("cream", "face cream", "day cream", "night cream")


def is_cleanser(p):
    pt = _ptype(p)
    if is_sunscreen(p): return False
    return "cleans" in pt


# Edit prompts per theme — these instruct gpt-image-1 how to compose
# the input products into a magazine-quality scene.
THEMES = [
    Theme(
        slug="korean-sunscreens-oily-skin",
        headline="Korean Sunscreens",
        subhead="that don't leave a white cast",
        product_filter=is_sunscreen,
        count=4,
        pin_url="https://mirai-skin.com/collections/sun-protection",
        edit_prompt=(
            "Compose all of the supplied Korean sunscreen products into a single "
            "editorial Pinterest flat-lay pin. Place the products on a warm cream "
            "and peach marble surface with soft morning light coming from the "
            "upper-left. Add subtle natural shadows beneath each product. "
            "Arrange products with editorial asymmetry — slightly overlapping, "
            "varied angles, like a high-end magazine spread. Add small natural "
            "decorative elements: a sprig of green leaves and a soft white linen "
            "napkin. Include generous empty space at the very top of the image "
            "for headline text to be added later. Use a 2:3 vertical composition. "
            "Do NOT alter, redesign, or change any product label, color, or shape — "
            "preserve them exactly as supplied. Photo-realistic magazine quality."
        ),
        cta="Shop the edit at Mirai",
    ),
    Theme(
        slug="moisturizers-sensitive-skin",
        headline="Korean Moisturizers",
        subhead="for sensitive, reactive skin",
        product_filter=is_moisturizer,
        count=4,
        pin_url="https://mirai-skin.com/collections/moisturizers",
        edit_prompt=(
            "Compose all of the supplied Korean moisturizer products into a single "
            "editorial Pinterest flat-lay pin. Place them on a warm cream linen "
            "fabric with soft natural light from the upper-right and gentle wrinkle "
            "shadows in the fabric. Arrange the products with editorial asymmetry, "
            "slightly overlapping, like a high-end skincare magazine. Add a small "
            "white ceramic dish with cream beside one product, and a soft cotton "
            "round. Include generous empty space at the very top of the image for "
            "headline text to be added later. 2:3 vertical composition. "
            "Do NOT alter, redesign, or change any product label, color, or shape — "
            "preserve them exactly as supplied. Photo-realistic magazine quality."
        ),
        cta="Shop the edit at Mirai",
    ),
    Theme(
        slug="korean-cleansers-double-cleanse",
        headline="The Double Cleanse",
        subhead="four Korean cleansers worth keeping",
        product_filter=is_cleanser,
        count=4,
        pin_url="https://mirai-skin.com/collections/cleansers",
        edit_prompt=(
            "Compose all of the supplied Korean cleanser products into a single "
            "editorial Pinterest flat-lay pin. Place them on a warm beige stone "
            "bathroom counter with subtle water-droplet reflections, soft morning "
            "light from above, and gentle organic shadows. Arrange the products "
            "with editorial asymmetry, slightly overlapping, like a high-end skincare "
            "magazine. Add small details: a folded white washcloth, a white ceramic "
            "spoon. Include generous empty space at the very top for headline text "
            "to be added later. 2:3 vertical composition. "
            "Do NOT alter, redesign, or change any product label, color, or shape — "
            "preserve them exactly as supplied. Photo-realistic magazine quality."
        ),
        cta="Shop the edit at Mirai",
    ),
]


def fetch_to_disk(product: dict, out_dir: Path) -> Path | None:
    """Download a real product image to disk in PNG. Returns local path."""
    img = fetch_product_image_with_fallback(product)
    if img is None:
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{product['handle'][:50]}.png"
    img.save(path, "PNG")
    return path


def call_openai_edit(image_paths: list[Path], prompt: str, *, quality: str = "high") -> bytes:
    """Send N input images + prompt to gpt-image-1 /v1/images/edits.
    Returns the raw bytes of the composed image."""
    client = OpenAI()
    files = [open(p, "rb") for p in image_paths]
    try:
        resp = client.images.edit(
            model="gpt-image-1",
            image=files,
            prompt=prompt,
            size="1024x1536",
            quality=quality,
            input_fidelity="high",  # try to preserve input product details
            n=1,
        )
    finally:
        for f in files:
            f.close()
    item = resp.data[0]
    if getattr(item, "b64_json", None):
        return base64.b64decode(item.b64_json)
    if getattr(item, "url", None):
        with urllib.request.urlopen(item.url, timeout=60) as r:
            return r.read()
    raise RuntimeError(f"unexpected response shape: {item}")


def overlay_text(canvas: Image.Image, theme: Theme) -> Image.Image:
    """Add a clean headline + CTA to the AI-composed image. Headline goes
    in the top empty area we asked the prompt to leave."""
    canvas = canvas.convert("RGB")
    draw = ImageDraw.Draw(canvas)

    # Soft cream wash on top 28% for legibility
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    fade_h = int(canvas.height * 0.30)
    for y in range(fade_h):
        alpha = int(220 * max(0, 1 - y / fade_h))
        od.line([(0, y), (canvas.width, y)], fill=(252, 246, 240, alpha))
    rgba = canvas.convert("RGBA")
    rgba.alpha_composite(overlay)
    canvas = rgba.convert("RGB")
    draw = ImageDraw.Draw(canvas)

    kicker = ImageFont.truetype(FONT_DM_SANS, 22)
    head = ImageFont.truetype(FONT_DM_SANS, 78)
    sub = ImageFont.truetype(FONT_DM_SANS, 30)
    cta_font = ImageFont.truetype(FONT_DM_SANS, 26)

    PAD = 60
    draw.text((PAD, 50), "MIRAI · K-BEAUTY EDIT", fill=MIRAI_INK, font=kicker, spacing=2)
    draw.text((PAD, 100), theme.headline, fill=MIRAI_INK, font=head)
    draw.text((PAD, 192), theme.subhead, fill=MIRAI_INK, font=sub)

    # Bottom CTA
    cta_text = f"{theme.cta}  »"
    bbox = draw.textbbox((0, 0), cta_text, font=cta_font)
    cw = bbox[2] - bbox[0]
    bottom_y = canvas.height - 70
    draw.text((canvas.width - PAD - cw, bottom_y), cta_text, fill=MIRAI_ACCENT, font=cta_font)
    return canvas


def build_one(theme: Theme, products: list[dict], out_dir: Path) -> dict | None:
    print(f"\n=== building: {theme.slug}  ({len(products)} products) ===")
    # Download real product images
    paths = []
    for p in products[:theme.count]:
        path = fetch_to_disk(p, PRODUCT_TMP_DIR)
        if path:
            print(f"  ✓ fetched {p['handle'][:50]}")
            paths.append(path)
    if len(paths) < 2:
        print(f"  ✗ not enough product images ({len(paths)})")
        return None

    # Call OpenAI to compose
    print(f"  🎨 calling gpt-image-1 images.edit with {len(paths)} input products…")
    try:
        composed_bytes = call_openai_edit(paths, theme.edit_prompt, quality="high")
    except Exception as e:
        print(f"  ✗ OpenAI failed: {e}")
        return None
    composed = Image.open(io.BytesIO(composed_bytes))
    print(f"  ✓ AI composed: {composed.size}, {len(composed_bytes) // 1024}KB raw")

    # Add headline + CTA overlay
    final = overlay_text(composed, theme)

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"ai-{theme.slug}.jpg"
    final.save(out_path, "JPEG", quality=90, optimize=True)
    print(f"  ✓ saved → {out_path.name} ({out_path.stat().st_size // 1024}KB)")

    return {
        "theme": theme.slug,
        "image_path": str(out_path.resolve()),
        "headline": theme.headline,
        "subhead": theme.subhead,
        "url": theme.pin_url,
        "cta": theme.cta,
        "products": [{"handle": p["handle"], "title": p["title"], "vendor": p.get("vendor", "")} for p in products[:theme.count]],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pool", type=Path)
    ap.add_argument("--themes", type=int, default=3)
    ap.add_argument("--out", type=Path, default=PIN_OUT_DIR)
    args = ap.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY not set", file=sys.stderr)
        return 2

    pool = json.loads(args.pool.read_text())
    args.out.mkdir(parents=True, exist_ok=True)

    rendered = []
    for theme in THEMES[: args.themes]:
        candidates = [p for p in pool if theme.product_filter(p)]
        if len(candidates) < 2:
            print(f"\n  ✗ skipping {theme.slug} — only {len(candidates)} candidates")
            continue
        # Vendor-balanced
        seen, chosen = set(), []
        for p in candidates:
            v = (p.get("vendor") or "").lower().strip()
            if v in seen: continue
            chosen.append(p); seen.add(v)
            if len(chosen) >= theme.count: break
        for p in candidates:
            if len(chosen) >= theme.count: break
            if p not in chosen:
                chosen.append(p)

        result = build_one(theme, chosen, args.out)
        if result:
            rendered.append(result)

    manifest = args.out / "manifest.json"
    manifest.write_text(json.dumps(rendered, indent=2))
    print(f"\nrendered {len(rendered)} AI-composed pins → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
