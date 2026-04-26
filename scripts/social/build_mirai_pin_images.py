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
import base64
import hashlib
import io
import json
import os
import sys
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import MIRAI_PIN_IMAGES_DIR

# ── Mirai brand palette (extracted from mirai-skin.com homepage) ──────────
# Mirai's site uses a warm, neutral, editorial palette: cream/peach/blush
# backgrounds with a single warm-orange accent (#F4986C). All board
# subtypes share this palette — we keep brand consistency over per-category
# colors. Slight variations differentiate boards without breaking the vibe.
MIRAI_INK = "#1A1614"        # warm near-black for text
MIRAI_ACCENT = "#F4986C"     # the brand orange (rgb 244,152,108)
MIRAI_ACCENT_DARK = "#C76A3F"
MIRAI_CREAM = "#F3EEEA"      # rgb 243,238,234 — primary background
MIRAI_BLUSH = "#EFDED9"      # rgb 239,222,217
MIRAI_PEACH = "#FFE3C2"      # rgb 255,227,194
MIRAI_BEIGE = "#E8DCD0"      # rgb 232,220,208
MIRAI_PINK = "#F4E4E3"       # rgb 244,228,227

BOARD_PALETTE = {
    "sunscreen":   {"band": MIRAI_PEACH, "ink": MIRAI_INK, "accent": MIRAI_ACCENT},
    "moisturizer": {"band": MIRAI_CREAM, "ink": MIRAI_INK, "accent": MIRAI_ACCENT},
    "cleanser":    {"band": MIRAI_BEIGE, "ink": MIRAI_INK, "accent": MIRAI_ACCENT},
    "serum":       {"band": MIRAI_BLUSH, "ink": MIRAI_INK, "accent": MIRAI_ACCENT},
    "toner":       {"band": MIRAI_PINK,  "ink": MIRAI_INK, "accent": MIRAI_ACCENT},
    "mask":        {"band": MIRAI_BLUSH, "ink": MIRAI_INK, "accent": MIRAI_ACCENT},
    "makeup":      {"band": MIRAI_PINK,  "ink": MIRAI_INK, "accent": MIRAI_ACCENT_DARK},
    "_default":    {"band": MIRAI_CREAM, "ink": MIRAI_INK, "accent": MIRAI_ACCENT},
}

# OpenAI gpt-image-1 background-generation settings
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_BG_MODEL = os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1")
OPENAI_BG_SIZE = "1024x1536"  # closest to our 1000x1500 2:3 canvas
BG_CACHE_DIR = MIRAI_PIN_IMAGES_DIR.parent / "mirai-bg-cache"
USE_AI_BG = os.environ.get("USE_AI_BG", "1") not in ("0", "false", "False")

# Per-board background prompts. NEVER mention products — pure environmental
# editorial textures. The product photo is composited on top of this.
BG_PROMPTS = {
    "sunscreen":   "soft warm cream and peach editorial background, gentle morning sunlight casting subtle texture, luxe minimalist Korean beauty aesthetic, no products, no text, no people, blurred unfocused depth, 2:3 vertical composition, ample empty space",
    "moisturizer": "warm cream linen background with subtle natural texture and soft shadow, calm editorial Korean beauty aesthetic, no products, no text, no people, blurred unfocused depth, 2:3 vertical composition, ample empty space",
    "cleanser":    "gentle beige and cream editorial background with soft natural light, minimalist water-droplet bokeh effect in distance, Korean beauty aesthetic, no products, no text, no people, 2:3 vertical composition",
    "serum":       "soft blush pink and cream editorial backdrop with rose-petal texture, warm light, luxe minimalist Korean beauty aesthetic, no products, no text, no people, 2:3 vertical composition",
    "toner":       "soft pink and cream editorial backdrop, ethereal morning haze, dewy minimalist Korean beauty aesthetic, no products, no text, no people, 2:3 vertical composition",
    "mask":        "warm blush and cream editorial backdrop, soft natural shadow, calm Korean beauty aesthetic, no products, no text, no people, 2:3 vertical composition",
    "makeup":      "soft pink and cream editorial backdrop with sheer chiffon texture, glamorous minimalist Korean beauty aesthetic, no products, no text, no people, 2:3 vertical composition",
    "_default":    "warm cream editorial backdrop with subtle natural texture, calm minimalist Korean beauty aesthetic, no products, no text, no people, 2:3 vertical composition",
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

# ── Fonts (DM Sans matches mirai-skin.com headings; Helvetica for kicker/CTA) ──
_FONT_DIR = Path(__file__).resolve().parent / "fonts"
FONT_DM_SANS = str(_FONT_DIR / "DMSans-Regular.ttf")  # variable font, supports bold weights
FONT_SERIF = "/System/Library/Fonts/Supplemental/Georgia Bold.ttf"  # fallback
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


def generate_ai_background(board: str, force: bool = False) -> Image.Image | None:
    """Generate (or load cached) editorial background for this board via
    OpenAI gpt-image-1. Returns RGBA Image at 1024x1536, or None on failure.

    Cached on disk so repeated runs reuse the same backgrounds (saves $$).
    Per-board cache key — same prompt, same image."""
    if not OPENAI_API_KEY:
        return None
    BG_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    prompt = BG_PROMPTS.get(board, BG_PROMPTS["_default"])
    cache_key = hashlib.sha256(f"{OPENAI_BG_MODEL}|{OPENAI_BG_SIZE}|{prompt}".encode()).hexdigest()[:16]
    cache_path = BG_CACHE_DIR / f"{board}-{cache_key}.png"
    if cache_path.exists() and not force:
        try:
            return Image.open(cache_path).convert("RGBA")
        except Exception:
            cache_path.unlink(missing_ok=True)

    print(f"    🎨 generating AI background for board={board} via {OPENAI_BG_MODEL}…")
    body = json.dumps({
        "model": OPENAI_BG_MODEL,
        "prompt": prompt,
        "n": 1,
        "size": OPENAI_BG_SIZE,
    }).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/images/generations",
        data=body,
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            resp = json.loads(r.read())
    except Exception as e:
        print(f"    ✗ OpenAI image API failed: {e}")
        return None

    data_list = resp.get("data") or []
    if not data_list:
        print(f"    ✗ OpenAI returned no images: {resp}")
        return None
    item = data_list[0]
    if "b64_json" in item:
        img_bytes = base64.b64decode(item["b64_json"])
    elif "url" in item:
        with urllib.request.urlopen(item["url"], timeout=60) as r:
            img_bytes = r.read()
    else:
        print(f"    ✗ unexpected OpenAI response shape: {item.keys()}")
        return None

    cache_path.write_bytes(img_bytes)
    return Image.open(io.BytesIO(img_bytes)).convert("RGBA")


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


_REMBG_SESSION = None
def remove_bg_ml(im: Image.Image) -> Image.Image | None:
    """ML-based background removal via rembg (handles colored bgs, gradients,
    lifestyle shots — anything `remove_white_bg_simple` fails on). Returns None
    if rembg isn't installed."""
    global _REMBG_SESSION
    try:
        from rembg import remove, new_session
        if _REMBG_SESSION is None:
            # u2netp = lighter/faster; u2net = better quality. Default to u2net for product cutouts.
            _REMBG_SESSION = new_session("u2net")
    except ImportError:
        return None
    try:
        # rembg accepts PIL Image and returns PIL Image
        return remove(im, session=_REMBG_SESSION)
    except Exception as e:
        print(f"    rembg failed: {e}")
        return None


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
    """Render a single pin image. Returns True on success.

    Layout v2 (mirai vibe):
      • Background: AI-generated editorial scene (gpt-image-1) tinted into
        the mirai palette, with a top fade so headline reads cleanly.
      • Real product photo (bg-removed) centered in the middle 60%.
      • Top: small kicker (DM Sans uppercase) + headline (DM Sans display).
      • Bottom-left: vendor.
      • Bottom-right: price in mirai-orange + CTA chip.
    """
    board = product.get("board", "_default")
    palette = BOARD_PALETTE.get(board, BOARD_PALETTE["_default"])
    kicker = KICKERS.get(board, KICKERS["_default"])

    # ── Background ────────────────────────────────────────────────────
    bg = generate_ai_background(board) if USE_AI_BG else None
    if bg is not None:
        # Resize to canvas, then blend with mirai palette tint for brand consistency
        bg = bg.resize((W, H), Image.LANCZOS).convert("RGB")
        # Apply a soft palette overlay (50% blend with the board's band color)
        tint = Image.new("RGB", (W, H), palette["band"])
        canvas = Image.blend(bg, tint, 0.32)
        # Add a subtle white wash to lift contrast for text
        wash = Image.new("RGB", (W, H), "#FAF6F2")
        canvas = Image.blend(canvas, wash, 0.18)
    else:
        # No AI bg → flat brand background
        canvas = Image.new("RGB", (W, H), palette["band"])

    # Soft top-band gradient overlay for headline legibility (subtle)
    overlay = Image.new("RGBA", (W, BAND_H + 60), (255, 255, 255, 0))
    od = ImageDraw.Draw(overlay)
    for y in range(BAND_H + 60):
        # Fade from 60% white at top to 0% at bottom of overlay
        alpha = int(150 * max(0, 1 - y / (BAND_H + 60)))
        od.line([(0, y), (W, y)], fill=(250, 246, 242, alpha))
    canvas = canvas.convert("RGBA")
    canvas.alpha_composite(overlay)
    canvas = canvas.convert("RGB")

    draw = ImageDraw.Draw(canvas)

    # ── Top: kicker + headline ────────────────────────────────────────
    kicker_font = ImageFont.truetype(FONT_DM_SANS, 22)
    title_font = ImageFont.truetype(FONT_DM_SANS, 60)

    # Kicker
    draw.text((PADDING, PADDING), kicker, fill=palette["ink"], font=kicker_font,
              spacing=2)

    # Headline (product title — sentence case for mirai's editorial vibe)
    raw_headline = shorten_title(product.get("title", ""), product.get("vendor", ""))
    title_y = PADDING + 42
    title_lines = wrap_text(draw, raw_headline, title_font, W - PADDING * 2)[:3]
    line_h = 66
    for i, line in enumerate(title_lines):
        draw.text((PADDING, title_y + i * line_h), line, fill=palette["ink"], font=title_font)

    # ── Middle: product image (real, no AI) ───────────────────────────
    product_img = fetch_product_image_with_fallback(product)
    if product_img is None:
        print(f"  ✗ image fetch failed for {product.get('handle')}")
        return False

    if not has_meaningful_alpha(product_img):
        product_img = remove_white_bg_simple(product_img)

    middle_y_start = BAND_H + 20
    middle_h = H - BAND_H - FOOTER_H - 40
    middle_w = W - PADDING * 2
    fit = fit_into(product_img, middle_w, middle_h)
    # Add a soft drop shadow under the product for depth on the AI bg
    shadow = Image.new("RGBA", (fit.size[0] + 80, fit.size[1] + 80), (0, 0, 0, 0))
    sh_alpha = fit.getchannel("A").filter(ImageFilter.GaussianBlur(20)) if fit.mode == "RGBA" else None
    if sh_alpha is not None:
        shadow_layer = Image.new("RGBA", fit.size, (40, 28, 22, 70))
        shadow_layer.putalpha(sh_alpha)
        # Position shadow slightly below + to the right of the product
        canvas_rgba = canvas.convert("RGBA")
        sx = (W - fit.size[0]) // 2 + 12
        sy = middle_y_start + (middle_h - fit.size[1]) // 2 + 16
        canvas_rgba.alpha_composite(shadow_layer, (sx, sy))
        canvas = canvas_rgba.convert("RGB")
        draw = ImageDraw.Draw(canvas)
    paste_centered(canvas, fit, W // 2, middle_y_start + middle_h // 2)

    # ── Footer: vendor / price + CTA ──────────────────────────────────
    footer_y = H - FOOTER_H + 30
    price = product.get("price")
    vendor = (product.get("vendor") or "").strip()

    vendor_font = ImageFont.truetype(FONT_DM_SANS, 22)
    if vendor:
        draw.text((PADDING, footer_y + 28), vendor.upper(), fill=palette["ink"], font=vendor_font,
                  spacing=2)

    if price:
        price_str = f"${price}"
        price_font = ImageFont.truetype(FONT_DM_SANS, 52)
        cta_font = ImageFont.truetype(FONT_DM_SANS, 18)
        bbox = draw.textbbox((0, 0), price_str, font=price_font)
        pw = bbox[2] - bbox[0]
        draw.text((W - PADDING - pw, footer_y + 0), price_str, fill=palette["accent"], font=price_font)

        cta = "SHOP NOW  »"
        bbox = draw.textbbox((0, 0), cta, font=cta_font)
        cw = bbox[2] - bbox[0]
        draw.text((W - PADDING - cw, footer_y + 70), cta, fill=palette["ink"], font=cta_font,
                  spacing=2)

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
