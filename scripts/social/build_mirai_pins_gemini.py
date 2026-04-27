#!/usr/bin/env python3
"""Mirai Pinterest pins via Gemini 2.5 Flash Image multi-input compose.

This is the procedure already used in scripts/regen_hero_real_products.py:
  Real product images + styling prompt → Gemini → composed scene that
  PRESERVES the real products (labels, colors, bottle shapes intact).

Why Gemini over gpt-image-1: when given real input images, Gemini 2.5
Flash Image keeps the inputs photorealistically intact and stages them
in the requested scene. gpt-image-1 redraws labels and breaks brand
fidelity (Innisfree → 'Innisrree', Beauty of Joseon → 'Bosert of proton').

Usage:
  python3 build_mirai_pins_gemini.py /tmp/mirai-60.json --themes 3
"""
import argparse
import io
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from google import genai
from google.genai import types

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import MIRAI_PIN_IMAGES_DIR
from build_mirai_pin_images import (
    fetch_product_image_with_fallback,
    FONT_DM_SANS,
)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash-image"
W, H = 1024, 1536
MIRAI_INK = "#1A1614"
MIRAI_ACCENT = "#F4986C"
PIN_OUT_DIR = MIRAI_PIN_IMAGES_DIR / "gemini-composed"
PRODUCT_TMP_DIR = MIRAI_PIN_IMAGES_DIR.parent / "ai-input-products"


@dataclass
class Theme:
    slug: str
    headline: str
    subhead: str
    product_filter: callable
    count: int
    pin_url: str
    prompt: str
    cta: str


def _ptype(p): return (p.get("product_type") or "").lower()


def is_sunscreen(p):
    pt = _ptype(p)
    return any(k in pt for k in ["sun ", "sunscreen", "sun cream", "sun stick", "sun gel", "sun fluid", "sun essence", "spf"])


def is_moisturizer(p):
    pt = _ptype(p)
    if is_sunscreen(p): return False
    if any(k in pt for k in ["cleans", "serum", "ampoule", "toner", "mask", "patch", "cushion"]):
        return False
    return any(k in pt for k in ["moisturi", "lotion", "emulsion", "ceramide"]) or pt in ("cream", "face cream")


def is_cleanser(p):
    pt = _ptype(p)
    if is_sunscreen(p): return False
    return "cleans" in pt


# Pinterest is 2:3 portrait. Gemini follows aspect-ratio in prompt.
PINTEREST_PROMPT_TAIL = (
    "Create a single tall portrait 2:3 vertical Pinterest pin image (1024x1536). "
    "The products should look exactly like these reference photos — same bottles, "
    "labels, brand names, colors. Do not redraw labels or text on packaging. "
    "Premium magazine-quality flat-lay photography. Leave generous empty space at "
    "the very top 25% of the image for headline text to be added later. "
    "No text overlays, no watermarks, no other captions."
)


THEMES = [
    Theme(
        slug="korean-sunscreens",
        headline="Korean Sunscreens",
        subhead="that don't leave a white cast",
        product_filter=is_sunscreen,
        count=4,
        pin_url="https://mirai-skin.com/collections/sun-protection",
        prompt=(
            "Place these Korean sunscreens on a warm cream and peach marble surface "
            "with soft morning light from the upper-left and gentle natural shadows "
            "underneath each product. Add a small sprig of fresh green leaves in the "
            "upper-left corner and a soft folded white linen napkin in the upper-right. "
            "Arrange the products with editorial asymmetry — slightly tilted, "
            "slightly overlapping — like a high-end skincare magazine spread. "
            f"{PINTEREST_PROMPT_TAIL}"
        ),
        cta="Shop the edit at Mirai",
    ),
    Theme(
        slug="korean-moisturizers",
        headline="Korean Moisturizers",
        subhead="for sensitive, reactive skin",
        product_filter=is_moisturizer,
        count=4,
        pin_url="https://mirai-skin.com/collections/moisturizers",
        prompt=(
            "Place these Korean moisturizers on warm cream linen fabric with soft "
            "natural light from the upper-right and gentle wrinkle shadows in the "
            "fabric. Add a small white ceramic dish with a dollop of cream beside "
            "one product, and a soft cotton pad. Arrange the products with editorial "
            "asymmetry, slightly overlapping. "
            f"{PINTEREST_PROMPT_TAIL}"
        ),
        cta="Shop the edit at Mirai",
    ),
    Theme(
        slug="korean-cleansers",
        headline="The Double Cleanse",
        subhead="four Korean cleansers worth keeping",
        product_filter=is_cleanser,
        count=4,
        pin_url="https://mirai-skin.com/collections/cleansers",
        prompt=(
            "Place these Korean cleansers on a warm beige stone bathroom counter "
            "with subtle water-droplet reflections, soft morning light from above, "
            "and gentle organic shadows. Add a folded white washcloth and a small "
            "white ceramic spoon as decorative accents. Arrange the products with "
            "editorial asymmetry, slightly overlapping. "
            f"{PINTEREST_PROMPT_TAIL}"
        ),
        cta="Shop the edit at Mirai",
    ),
]


def fetch_real_product_image(product: dict) -> Image.Image | None:
    img = fetch_product_image_with_fallback(product)
    if img is None:
        return None
    return img.convert("RGBA")


def call_gemini_compose(images: list[Image.Image], prompt: str) -> Image.Image | None:
    """Send N real product images + styling prompt to Gemini 2.5 Flash Image.
    Returns the composed image, or None on failure."""
    if not GEMINI_API_KEY:
        print("    ✗ GEMINI_API_KEY not set")
        return None

    client = genai.Client(api_key=GEMINI_API_KEY)

    parts: list = [prompt]
    for im in images:
        parts.append(im)

    print(f"  🎨 calling {GEMINI_MODEL} with {len(images)} input products…")
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=parts,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )
    except Exception as e:
        print(f"    ✗ Gemini call failed: {e}")
        return None

    for part in response.candidates[0].content.parts:
        if part.inline_data and part.inline_data.mime_type.startswith("image/"):
            return Image.open(io.BytesIO(part.inline_data.data))
    # No image in response — log any text returned
    for part in response.candidates[0].content.parts:
        if hasattr(part, "text") and part.text:
            print(f"    ✗ Gemini returned no image. Text: {part.text[:200]}")
    return None


def crop_to_2_3(img: Image.Image) -> Image.Image:
    """Crop to 2:3 portrait + resize to 1024x1536."""
    img = img.convert("RGB")
    target_ratio = 2 / 3
    current_ratio = img.width / img.height
    if current_ratio > target_ratio:
        new_w = int(img.height * target_ratio)
        left = (img.width - new_w) // 2
        img = img.crop((left, 0, left + new_w, img.height))
    elif current_ratio < target_ratio:
        new_h = int(img.width / target_ratio)
        top = (img.height - new_h) // 2
        img = img.crop((0, top, img.width, top + new_h))
    return img.resize((W, H), Image.LANCZOS)


def _dm_sans(size: int, weight: int = 400, opsz: int | None = None) -> ImageFont.FreeTypeFont:
    """Load DM Sans variable font at the requested weight + optical size.

    mirai-skin.com loads DM Sans 400/500/600/700; we match those weights.
    Optical size axis: 9 (text) → 40 (display); auto-pick by font size."""
    f = ImageFont.truetype(FONT_DM_SANS, size)
    if opsz is None:
        opsz = 40 if size >= 36 else 14
    try:
        f.set_variation_by_axes([opsz, weight])
    except Exception:
        pass
    return f


def overlay_text(canvas: Image.Image, theme: Theme) -> Image.Image:
    """Add headline + CTA overlay matching mirai-skin.com typography.

    Mirai uses DM Sans across the site:
      - Heading: weight 700 (Bold)
      - Subhead/Body: weight 500 (Medium) or 400 (Regular)
      - Buttons / CTAs: weight 600 (Semibold)
      - Letter-spacing: ~0 for body, slightly tightened for big display
    """
    canvas = canvas.convert("RGB")
    # Soft cream wash on top 28% for legibility
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    fade_h = int(canvas.height * 0.28)
    for y in range(fade_h):
        alpha = int(220 * max(0, 1 - y / fade_h))
        od.line([(0, y), (canvas.width, y)], fill=(252, 246, 240, alpha))
    rgba = canvas.convert("RGBA")
    rgba.alpha_composite(overlay)
    canvas = rgba.convert("RGB")
    draw = ImageDraw.Draw(canvas)

    kicker = _dm_sans(22, weight=600)        # uppercase semibold (matches mirai nav)
    head = _dm_sans(82, weight=700)          # big bold display headline
    sub = _dm_sans(30, weight=500)           # medium subhead
    cta_font = _dm_sans(26, weight=600)      # semibold CTA (matches mirai buttons)
    PAD = 60

    draw.text((PAD, 50), "MIRAI · K-BEAUTY EDIT", fill=MIRAI_INK, font=kicker, spacing=2)
    draw.text((PAD, 100), theme.headline, fill=MIRAI_INK, font=head)
    draw.text((PAD, 200), theme.subhead, fill=MIRAI_INK, font=sub)

    cta_text = f"{theme.cta}  »"
    bbox = draw.textbbox((0, 0), cta_text, font=cta_font)
    cw = bbox[2] - bbox[0]
    bottom_y = canvas.height - 70
    draw.text((canvas.width - PAD - cw, bottom_y), cta_text, fill=MIRAI_ACCENT, font=cta_font)
    return canvas


def build_one(theme: Theme, products: list[dict], out_dir: Path) -> dict | None:
    print(f"\n=== building: {theme.slug}  ({len(products)} products) ===")
    PRODUCT_TMP_DIR.mkdir(parents=True, exist_ok=True)
    images = []
    chosen = []
    for p in products[:theme.count]:
        img = fetch_real_product_image(p)
        if img:
            print(f"  ✓ fetched {p['handle'][:50]}")
            images.append(img)
            chosen.append(p)
    if len(images) < 2:
        print(f"  ✗ not enough product images ({len(images)})")
        return None

    composed = call_gemini_compose(images, theme.prompt)
    if composed is None:
        return None

    composed = crop_to_2_3(composed)
    print(f"  ✓ Gemini composed: {composed.size}")

    final = overlay_text(composed, theme)

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"gemini-{theme.slug}.jpg"
    final.save(out_path, "JPEG", quality=90, optimize=True)
    print(f"  ✓ saved → {out_path.name} ({out_path.stat().st_size // 1024}KB)")

    return {
        "theme": theme.slug,
        "image_path": str(out_path.resolve()),
        "headline": theme.headline,
        "subhead": theme.subhead,
        "url": theme.pin_url,
        "cta": theme.cta,
        "products": [{"handle": p["handle"], "title": p["title"], "vendor": p.get("vendor", "")} for p in chosen],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pool", type=Path)
    ap.add_argument("--themes", type=int, default=3)
    ap.add_argument("--out", type=Path, default=PIN_OUT_DIR)
    args = ap.parse_args()

    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY not set in .env", file=sys.stderr)
        return 2

    pool = json.loads(args.pool.read_text())
    args.out.mkdir(parents=True, exist_ok=True)

    rendered = []
    for theme in THEMES[: args.themes]:
        candidates = [p for p in pool if theme.product_filter(p)]
        if len(candidates) < 2:
            print(f"\n  ✗ skipping {theme.slug} — only {len(candidates)} candidates")
            continue
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
    print(f"\nrendered {len(rendered)} Gemini-composed pins → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
