#!/usr/bin/env python3
"""Compose Pinterest pin images for Mirai products.

Takes a JSON list (output of select_mirai_products.py) and renders one 1000x1500
pin image per product. Uses real Shopify product photo (NEVER alters product
appearance) on a brand-colored 2:3 canvas with text overlay (title + price + CTA).

Pinterest prefers vertical 2:3 ratio. We compose:
  Top 28%   →  brand-color band with kicker + headline
  Middle 56% →  product image, scaled to fit, centered, optional bg-removed
  Bottom 16% →  price + CTA chip

Usage:
  python3 build_mirai_pin_images.py picked.json [--out scripts/social/pin-images/mirai/]
  python3 build_mirai_pin_images.py /tmp/sample-3.json
"""
import argparse
import io
import json
import sys
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import MIRAI_PIN_IMAGES_DIR

# ── Brand palette per board ───────────────────────────────────────────────
BOARD_PALETTE = {
    "sunscreen":   {"band": "#cfe5ee", "ink": "#1f3a4a", "accent": "#f4a26b"},
    "moisturizer": {"band": "#f1e3cf", "ink": "#3a2418", "accent": "#c97e5b"},
    "cleanser":    {"band": "#d8e8d3", "ink": "#243a25", "accent": "#5b8a3e"},
    "serum":       {"band": "#dcc9d8", "ink": "#3b1f3a", "accent": "#7a3e6b"},
    "toner":       {"band": "#ecd0c8", "ink": "#3a1f1b", "accent": "#b85c4a"},
    "mask":        {"band": "#d6cae8", "ink": "#251a3b", "accent": "#5e3e8a"},
    "makeup":      {"band": "#e8c4b1", "ink": "#3a1d18", "accent": "#a64a3a"},
    "_default":    {"band": "#f0e7d8", "ink": "#2a1d18", "accent": "#a86a3a"},
}

# Headline kickers per board
KICKERS = {
    "sunscreen":   "KOREAN SUNSCREEN",
    "moisturizer": "BARRIER REPAIR",
    "cleanser":    "DOUBLE CLEANSE",
    "serum":       "SERUMS & ESSENCES",
    "toner":       "GLASS SKIN",
    "mask":        "MASKS & PATCHES",
    "makeup":      "K-BEAUTY MAKEUP",
    "_default":    "K-BEAUTY ESSENTIAL",
}

# ── Fonts (macOS system) ──────────────────────────────────────────────────
FONT_SERIF = "/System/Library/Fonts/Supplemental/Georgia Bold.ttf"
FONT_SERIF_REGULAR = "/System/Library/Fonts/Supplemental/Georgia.ttf"
FONT_SANS = "/System/Library/Fonts/Helvetica.ttc"
FONT_AVENIR = "/System/Library/Fonts/Avenir Next.ttc"

# ── Canvas constants ──────────────────────────────────────────────────────
W, H = 1000, 1500
BAND_H = int(H * 0.28)  # 420
PRODUCT_H_CAP = int(H * 0.56)  # 840 (allow tall bottles)
FOOTER_H = int(H * 0.16)  # 240
PADDING = 60


def load_image_from_url(url: str, timeout: int = 30) -> Image.Image:
    req = urllib.request.Request(url, headers={"User-Agent": "MiraiPinBuilder/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
    img = Image.open(io.BytesIO(data)).convert("RGBA")
    return img


def refresh_image_url(handle: str, timeout: int = 15) -> str | None:
    """Catalog images go stale (Shopify CDN URLs rotate). Hit the live
    storefront /products/{handle}.json for a fresh src."""
    if not handle:
        return None
    url = f"https://mirai-skin.com/products/{handle}.json"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MiraiPinBuilder/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read())
        product = data.get("product", {})
        for img in product.get("images") or []:
            src = img.get("src") if isinstance(img, dict) else None
            if src:
                return src
    except Exception as e:
        print(f"    ⤳ refresh failed for {handle}: {e}")
    return None


def fetch_product_image_with_fallback(product: dict) -> Image.Image | None:
    """Try catalog URL first; on 404, refresh via live Shopify endpoint."""
    src = product.get("image_src")
    if src:
        try:
            return load_image_from_url(src)
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
            print(f"    catalog URL 404, refreshing via storefront…")
        except Exception as e:
            print(f"    catalog URL failed: {e}, trying refresh…")
    # Fallback: live storefront
    fresh = refresh_image_url(product.get("handle", ""))
    if not fresh:
        return None
    try:
        return load_image_from_url(fresh)
    except Exception as e:
        print(f"    refresh URL also failed: {e}")
        return None


def paste_centered(canvas: Image.Image, sticker: Image.Image, cx: int, cy: int) -> None:
    sw, sh = sticker.size
    canvas.paste(sticker, (cx - sw // 2, cy - sh // 2), sticker)


def fit_into(image: Image.Image, max_w: int, max_h: int) -> Image.Image:
    iw, ih = image.size
    scale = min(max_w / iw, max_h / ih)
    return image.resize((int(iw * scale), int(ih * scale)), Image.LANCZOS)


def has_meaningful_alpha(im: Image.Image, threshold: float = 0.05) -> bool:
    """True if >= threshold fraction of pixels have alpha < 250 (i.e. real transparency)."""
    if im.mode != "RGBA":
        return False
    a = im.getchannel("A")
    hist = a.histogram()
    total = sum(hist)
    transparent = sum(hist[:250])
    return total > 0 and (transparent / total) >= threshold


def remove_white_bg_simple(im: Image.Image, white_threshold: int = 240) -> Image.Image:
    """Cheap white-background removal for product photos. Pixels brighter than
    threshold across all RGB → set alpha 0. Edge feathering via Gaussian blur on
    alpha to soften the cut."""
    rgba = im.convert("RGBA")
    pixels = rgba.load()
    w, h = rgba.size
    # Build alpha mask
    alpha_data: list[int] = []
    for y in range(h):
        for x in range(w):
            r, g, b, _ = pixels[x, y]
            alpha_data.append(0 if (r >= white_threshold and g >= white_threshold and b >= white_threshold) else 255)
    alpha_img = Image.new("L", (w, h))
    alpha_img.putdata(alpha_data)
    # Soften the mask
    alpha_img = alpha_img.filter(ImageFilter.GaussianBlur(radius=2))
    rgba.putalpha(alpha_img)
    return rgba


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for w in words:
        trial = (current + " " + w).strip()
        bbox = draw.textbbox((0, 0), trial, font=font)
        if bbox[2] - bbox[0] <= max_w:
            current = trial
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines


def shorten_title(title: str, vendor: str = "", max_chars: int = 36) -> str:
    """Punchy Pinterest headline. Strips:
    - leading vendor (we show vendor separately in footer)
    - trailing volume suffix (50ml, 100g, 1.69 oz, etc.)
    - PA+ ratings (too technical for Pinterest)
    - parenthetical sub-titles
    Then truncates at the last natural break before max_chars (no '…')."""
    import re
    t = title.strip()

    # Drop leading vendor (case-insensitive)
    if vendor and t.lower().startswith(vendor.lower()):
        t = t[len(vendor):].lstrip(" -")

    # Drop everything after the first volume token (50 mL, 100g, 1.69 oz, etc.)
    t = re.sub(r"\s+\d+(\.\d+)?\s*(ml|mL|ML|g|G|fl\.?\s*oz|FL\.?\s*OZ|oz|OZ).*$", "", t)

    # Drop PA ratings and parenthetical clauses
    t = re.sub(r"\s+PA\++", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s+\([^)]*\)", "", t)
    t = re.sub(r"\s+-\s.*$", "", t)  # Drop tail after ' - '

    # Collapse whitespace
    t = re.sub(r"\s+", " ", t).strip()

    if len(t) <= max_chars:
        return t

    # Cut at last word boundary that fits
    cut = t[:max_chars].rsplit(" ", 1)[0]
    return cut.rstrip(",.;:") if cut else t[:max_chars]


def compose_pin(product: dict, output_path: Path) -> bool:
    """Render a single pin image. Returns True on success."""
    board = product.get("board", "_default")
    palette = BOARD_PALETTE.get(board, BOARD_PALETTE["_default"])
    kicker = KICKERS.get(board, KICKERS["_default"])

    # Canvas
    canvas = Image.new("RGB", (W, H), palette["band"])
    draw = ImageDraw.Draw(canvas)

    # Bottom area is a different color (slightly lighter / warmer) for contrast
    canvas.paste(Image.new("RGB", (W, H - BAND_H), "#fbf6ee"), (0, BAND_H))
    draw = ImageDraw.Draw(canvas)  # refresh after paste

    # ── Top band: kicker + headline ────────────────────────────────────
    kicker_font = ImageFont.truetype(FONT_AVENIR, 26, index=0)
    title_font = ImageFont.truetype(FONT_SERIF, 64)
    sub_font = ImageFont.truetype(FONT_AVENIR, 22, index=0)

    # Kicker
    draw.text((PADDING, PADDING), kicker, fill=palette["ink"], font=kicker_font)

    # Headline (product title, cleaned + wrapped)
    headline = shorten_title(product.get("title", ""), product.get("vendor", "")).upper()
    title_y = PADDING + 50
    title_lines = wrap_text(draw, headline, title_font, W - PADDING * 2)[:3]
    line_h = 72
    for i, line in enumerate(title_lines):
        draw.text((PADDING, title_y + i * line_h), line, fill=palette["ink"], font=title_font)

    # ── Middle: product image ──────────────────────────────────────────
    product_img = fetch_product_image_with_fallback(product)
    if product_img is None:
        print(f"  ✗ image fetch failed for {product.get('handle')}")
        return False

    # If image has white bg AND no real alpha, remove it for cleaner composite
    if not has_meaningful_alpha(product_img):
        product_img = remove_white_bg_simple(product_img)

    # Fit into the middle region
    middle_y_start = BAND_H + 20
    middle_h = H - BAND_H - FOOTER_H - 40
    middle_w = W - PADDING * 2
    fit = fit_into(product_img, middle_w, middle_h)
    paste_centered(canvas, fit, W // 2, middle_y_start + middle_h // 2)

    # ── Footer: price + CTA ────────────────────────────────────────────
    footer_y = H - FOOTER_H + 30
    price = product.get("price")
    vendor = product.get("vendor") or ""

    # Vendor (left)
    vendor_font = ImageFont.truetype(FONT_AVENIR, 24, index=0)
    if vendor:
        draw.text((PADDING, footer_y + 28), vendor.upper(), fill=palette["ink"], font=vendor_font)

    # Price + CTA (right)
    if price:
        price_str = f"${price}"
        price_font = ImageFont.truetype(FONT_SERIF, 56)
        cta_font = ImageFont.truetype(FONT_AVENIR, 22, index=0)
        # Right-aligned price
        bbox = draw.textbbox((0, 0), price_str, font=price_font)
        pw = bbox[2] - bbox[0]
        draw.text((W - PADDING - pw, footer_y + 5), price_str, fill=palette["accent"], font=price_font)
        # CTA chip below price (use ASCII chevron — Helvetica.ttc lacks Unicode arrows)
        cta = "SHOP ON MIRAI »"
        bbox = draw.textbbox((0, 0), cta, font=cta_font)
        cw = bbox[2] - bbox[0]
        draw.text((W - PADDING - cw, footer_y + 70), cta, fill=palette["ink"], font=cta_font)

    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, "JPEG", quality=88, optimize=True)
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("picked", type=Path, help="JSON output of select_mirai_products.py")
    ap.add_argument("--out", type=Path, default=MIRAI_PIN_IMAGES_DIR)
    ap.add_argument("--prefix", default="pin")
    args = ap.parse_args()

    products = json.loads(args.picked.read_text())
    args.out.mkdir(parents=True, exist_ok=True)

    succeeded = 0
    for i, p in enumerate(products):
        slug = (p.get("handle") or f"item-{i}")[:40]
        outpath = args.out / f"{args.prefix}-{i:03d}-{slug}.jpg"
        ok = compose_pin(p, outpath)
        if ok:
            print(f"  ✓ [{i:03d}] {outpath.name}  ({outpath.stat().st_size // 1024}KB)")
            succeeded += 1
    print(f"\nrendered {succeeded}/{len(products)} pins → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
