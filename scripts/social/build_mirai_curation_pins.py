#!/usr/bin/env python3
"""Mirai Pinterest CURATION pins — value-driven shopping guides.

A curation pin shows 4–5 real products from one category, composed onto an
AI-generated editorial backdrop, with a benefit-led headline. Pin URL goes
to a Mirai collection page (not a single product), so users land on the
full curated set.

Why curation > single-product:
- Pinterest users save shopping guides, not ads
- More products = more saves = more reach in Pinterest's algorithm
- Real products stay real (we never AI-alter products), only the SCENE is AI

Usage:
  python3 build_mirai_curation_pins.py /tmp/mirai-60.json --themes 3
"""
import argparse
import base64
import hashlib
import io
import json
import os
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import MIRAI_PIN_IMAGES_DIR
from build_mirai_pin_images import (
    fetch_product_image_with_fallback,
    has_meaningful_alpha,
    remove_white_bg_simple,
    remove_bg_ml,
    fit_into,
    wrap_text,
    FONT_DM_SANS,
)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_BG_MODEL = os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1")
BG_CACHE_DIR = MIRAI_PIN_IMAGES_DIR.parent / "mirai-bg-cache"
W, H = 1024, 1536
MIRAI_INK = "#1A1614"
MIRAI_ACCENT = "#F4986C"


@dataclass
class Theme:
    slug: str
    headline: str
    subhead: str
    product_filter: callable
    count: int
    pin_url: str
    bg_prompt: str
    cta: str


def _ptype(p): return (p.get("product_type") or "").lower()


def is_sunscreen(p):
    pt = _ptype(p)
    return any(k in pt for k in ["sun ", "sunscreen", "sun cream", "sun stick", "sun gel", "sun fluid", "sun essence", "spf"]) or pt in ("sun", "sun protect")


def is_moisturizer(p):
    pt = _ptype(p)
    if is_sunscreen(p):
        return False
    if any(k in pt for k in ["cleans", "serum", "ampoule", "toner", "mask", "patch", "cushion", "bb cream", "cc cream"]):
        return False
    return any(k in pt for k in ["moisturi", "lotion", "emulsion", "barrier cream", "ceramide cream", "anti-aging cream", "night cream", "day cream"]) or pt == "cream" or pt == "face cream"


def is_cleanser(p):
    pt = _ptype(p)
    if is_sunscreen(p):
        return False
    return "cleans" in pt


THEMES = [
    Theme(
        slug="korean-sunscreens-oily-skin",
        headline="Korean Sunscreens",
        subhead="that don't leave a white cast",
        product_filter=is_sunscreen,
        count=5,
        pin_url="https://mirai-skin.com/collections/sun-protection",
        bg_prompt=(
            "warm cream and peach editorial flat-lay backdrop with soft natural morning light, "
            "subtle marble texture, completely empty surface with no objects or products, "
            "minimalist Korean beauty aesthetic, 2:3 vertical, ample empty space at bottom 70 percent"
        ),
        cta="Shop the edit at Mirai",
    ),
    Theme(
        slug="moisturizers-sensitive-skin",
        headline="Korean Moisturizers",
        subhead="for sensitive, reactive skin",
        product_filter=is_moisturizer,
        count=5,
        pin_url="https://mirai-skin.com/collections/moisturizers",
        bg_prompt=(
            "warm cream linen editorial backdrop with soft natural light and gentle shadow, "
            "completely empty surface, no objects, calm minimalist Korean beauty aesthetic, "
            "2:3 vertical, ample empty space at bottom 70 percent"
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
        bg_prompt=(
            "warm beige editorial backdrop with subtle water-droplet bokeh in the distance, "
            "soft natural light, completely empty foreground, no objects, "
            "minimalist Korean beauty aesthetic, 2:3 vertical, ample empty space"
        ),
        cta="Shop the edit at Mirai",
    ),
]


def gen_bg(theme: Theme, force: bool = False) -> Image.Image:
    BG_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(f"{OPENAI_BG_MODEL}|{theme.slug}|{theme.bg_prompt}".encode()).hexdigest()[:16]
    cache_path = BG_CACHE_DIR / f"curation-{theme.slug}-{key}.png"
    if cache_path.exists() and not force:
        try:
            return Image.open(cache_path).convert("RGB").resize((W, H), Image.LANCZOS)
        except Exception:
            cache_path.unlink(missing_ok=True)

    print(f"  🎨 generating scene for theme={theme.slug} via {OPENAI_BG_MODEL}…")
    body = json.dumps({
        "model": OPENAI_BG_MODEL,
        "prompt": theme.bg_prompt,
        "n": 1,
        "size": "1024x1536",
    }).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/images/generations",
        data=body,
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        resp = json.loads(r.read())
    item = resp["data"][0]
    if "b64_json" in item:
        img_bytes = base64.b64decode(item["b64_json"])
    else:
        with urllib.request.urlopen(item["url"], timeout=60) as r:
            img_bytes = r.read()
    cache_path.write_bytes(img_bytes)
    return Image.open(io.BytesIO(img_bytes)).convert("RGB").resize((W, H), Image.LANCZOS)


def get_cutout(product: dict) -> Image.Image | None:
    img = fetch_product_image_with_fallback(product)
    if img is None:
        return None
    if has_meaningful_alpha(img):
        return img
    # Try ML-based bg removal first (handles colored bgs, lifestyle shots)
    ml = remove_bg_ml(img)
    if ml is not None and has_meaningful_alpha(ml):
        return ml
    # Fall back to simple white-threshold (won't help on colored bgs but better than nothing)
    return remove_white_bg_simple(img, white_threshold=235)


def shadow_paste(canvas: Image.Image, sticker: Image.Image, x: int, y: int) -> Image.Image:
    """Paste sticker on canvas with a soft drop shadow. Returns updated canvas."""
    if sticker.mode != "RGBA":
        sticker = sticker.convert("RGBA")
    alpha = sticker.getchannel("A").filter(ImageFilter.GaussianBlur(18))
    # Reduce alpha intensity for a softer shadow (replaces Image.eval to satisfy hook)
    soft_alpha = alpha.point(lambda v: int(v * 0.40))
    shadow = Image.new("RGBA", sticker.size, (40, 28, 22, 0))
    shadow.putalpha(soft_alpha)

    canvas_rgba = canvas.convert("RGBA") if canvas.mode != "RGBA" else canvas.copy()
    canvas_rgba.alpha_composite(shadow, (x + 14, y + 18))
    canvas_rgba.alpha_composite(sticker, (x, y))
    return canvas_rgba.convert("RGB")


def layout_products(canvas: Image.Image, products: list[Image.Image], region: tuple) -> Image.Image:
    """Place 4-5 products in a flat-lay arrangement within `region`.
    Returns updated canvas (RGB)."""
    x0, y0, x1, y1 = region
    rw, rh = x1 - x0, y1 - y0
    n = len(products)
    if n == 0:
        return canvas

    if n >= 5:
        # Editorial layout: 2 top + 1 hero + 2 bottom — symmetric, tight, no gap
        # Vertical bands: row1 (28% rh) → hero (44% rh) → row2 (28% rh)
        row1_h = int(rh * 0.28)
        hero_h = int(rh * 0.44)
        row2_h = rh - row1_h - hero_h

        # Top row — 2 small products
        for i, p in enumerate(products[:2]):
            cell_w = (rw - 80) // 2 - 20
            cell_h = int(row1_h * 0.92)
            fit = fit_into(p, cell_w, cell_h)
            cell_cx = x0 + (rw // 4) + (rw // 2) * i
            ix = cell_cx - fit.size[0] // 2
            iy = y0 + (row1_h - fit.size[1]) // 2
            canvas = shadow_paste(canvas, fit, ix, iy)

        # Hero — center, slightly larger than row items
        hero = products[2]
        hero_max_w = int(rw * 0.42)
        hero_max_h = int(hero_h * 0.94)
        hero_fit = fit_into(hero, hero_max_w, hero_max_h)
        hx = x0 + rw // 2 - hero_fit.size[0] // 2
        hy = y0 + row1_h + (hero_h - hero_fit.size[1]) // 2
        canvas = shadow_paste(canvas, hero_fit, hx, hy)

        # Bottom row — 2 small products
        for i, p in enumerate(products[3:5]):
            cell_w = (rw - 80) // 2 - 20
            cell_h = int(row2_h * 0.92)
            fit = fit_into(p, cell_w, cell_h)
            cell_cx = x0 + (rw // 4) + (rw // 2) * i
            ix = cell_cx - fit.size[0] // 2
            iy = y0 + row1_h + hero_h + (row2_h - fit.size[1]) // 2
            canvas = shadow_paste(canvas, fit, ix, iy)
    elif n == 4:
        # 2x2 grid
        cell_w = (rw - 80) // 2 - 10
        cell_h = (rh - 80) // 2 - 10
        for i, p in enumerate(products):
            row, col = divmod(i, 2)
            fit = fit_into(p, cell_w, cell_h)
            cx = x0 + (rw // 2) * col + (rw // 4)
            cy = y0 + (rh // 2) * row + (rh // 4) + 30
            ix = cx - fit.size[0] // 2
            iy = cy - fit.size[1] // 2
            canvas = shadow_paste(canvas, fit, ix, iy)
    elif n == 3:
        # Single row
        item_max_w = (rw - 100) // 3
        item_max_h = int(rh * 0.7)
        for i, p in enumerate(products):
            fit = fit_into(p, item_max_w, item_max_h)
            cell_cx = x0 + (rw // 3) * i + (rw // 6)
            ix = cell_cx - fit.size[0] // 2
            iy = y0 + (rh - fit.size[1]) // 2
            canvas = shadow_paste(canvas, fit, ix, iy)

    return canvas


def compose_curation_pin(theme: Theme, products: list[dict], output_path: Path) -> bool:
    print(f"\n  building pin: {theme.slug}  ({len(products)} products)")

    canvas = gen_bg(theme).convert("RGB")

    # Soft cream wash on top 36% for headline legibility
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    fade_h = int(H * 0.36)
    for y in range(fade_h):
        alpha = int(220 * max(0, 1 - y / fade_h))
        od.line([(0, y), (W, y)], fill=(250, 245, 240, alpha))
    rgba = canvas.convert("RGBA")
    rgba.alpha_composite(overlay)
    canvas = rgba.convert("RGB")

    # Cutouts
    cutouts = []
    for p in products[:theme.count]:
        c = get_cutout(p)
        if c is not None:
            cutouts.append(c)
    if len(cutouts) < min(3, theme.count):
        print(f"  ✗ not enough product cutouts ({len(cutouts)} < {theme.count})")
        return False

    # Place products in bottom 65%
    canvas = layout_products(
        canvas,
        cutouts,
        region=(60, int(H * 0.34), W - 60, H - 220),
    )

    # Headline + subhead
    draw = ImageDraw.Draw(canvas)
    kicker_font = ImageFont.truetype(FONT_DM_SANS, 22)
    headline_font = ImageFont.truetype(FONT_DM_SANS, 78)
    subhead_font = ImageFont.truetype(FONT_DM_SANS, 30)

    draw.text((60, 50), "MIRAI · K-BEAUTY EDIT", fill=MIRAI_INK, font=kicker_font, spacing=2)

    head_lines = wrap_text(draw, theme.headline, headline_font, W - 120)[:2]
    y = 100
    for line in head_lines:
        draw.text((60, y), line, fill=MIRAI_INK, font=headline_font)
        y += 84
    if theme.subhead:
        draw.text((60, y + 8), theme.subhead, fill=MIRAI_INK, font=subhead_font)

    # Bottom: chip + CTA
    cta_font = ImageFont.truetype(FONT_DM_SANS, 26)
    count_font = ImageFont.truetype(FONT_DM_SANS, 20)
    bottom_y = H - 130

    chip_text = f"{len(cutouts)} PICKS"
    bbox = draw.textbbox((0, 0), chip_text, font=count_font)
    cw = bbox[2] - bbox[0]
    chip_pad_x, chip_pad_y = 18, 10
    chip_x = 60
    draw.rounded_rectangle(
        (chip_x, bottom_y, chip_x + cw + chip_pad_x * 2, bottom_y + 50),
        radius=24, fill=MIRAI_INK,
    )
    draw.text((chip_x + chip_pad_x, bottom_y + chip_pad_y + 2),
              chip_text, fill="#F3EEEA", font=count_font, spacing=2)

    cta_text = f"{theme.cta}  »"
    bbox = draw.textbbox((0, 0), cta_text, font=cta_font)
    cw = bbox[2] - bbox[0]
    draw.text((W - 60 - cw, bottom_y + 12), cta_text, fill=MIRAI_ACCENT, font=cta_font)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, "JPEG", quality=88, optimize=True)
    print(f"  ✓ {output_path.name}  ({output_path.stat().st_size // 1024}KB)")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pool", type=Path, help="JSON list from select_mirai_products.py")
    ap.add_argument("--themes", type=int, default=3)
    ap.add_argument("--out", type=Path, default=MIRAI_PIN_IMAGES_DIR / "curation")
    args = ap.parse_args()

    pool = json.loads(args.pool.read_text())
    args.out.mkdir(parents=True, exist_ok=True)

    rendered = []
    for theme in THEMES[: args.themes]:
        candidates = [p for p in pool if theme.product_filter(p)]
        if len(candidates) < 3:
            print(f"  ✗ skipping {theme.slug} — only {len(candidates)} candidates")
            continue

        # Vendor-balanced selection
        seen_vendors = set()
        chosen = []
        for p in candidates:
            v = (p.get("vendor") or "").lower().strip()
            if v in seen_vendors:
                continue
            chosen.append(p)
            seen_vendors.add(v)
            if len(chosen) >= theme.count:
                break
        if len(chosen) < theme.count:
            for p in candidates:
                if p not in chosen:
                    chosen.append(p)
                    if len(chosen) >= theme.count:
                        break

        out_path = args.out / f"curation-{theme.slug}.jpg"
        ok = compose_curation_pin(theme, chosen, out_path)
        if ok:
            rendered.append({
                "theme": theme.slug,
                "image_path": str(out_path.resolve()),
                "headline": theme.headline,
                "subhead": theme.subhead,
                "url": theme.pin_url,
                "cta": theme.cta,
                "products": [{"handle": p["handle"], "title": p["title"], "vendor": p.get("vendor", "")} for p in chosen],
            })

    manifest = args.out / "manifest.json"
    manifest.write_text(json.dumps(rendered, indent=2))
    print(f"\nrendered {len(rendered)} curation pins → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
