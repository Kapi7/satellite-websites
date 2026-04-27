#!/usr/bin/env python3
"""
Build hero images by COMPOSITING real Shopify product photos with PIL,
then optionally enhance the composite with Gemini 2.5 Flash Image.

Pipeline:
  1. PIL builds the layout (2-up for comparisons, 3-4 grid for listicles)
     from the actual Shopify og:image product photos.
  2. The composite is passed AS-IS to Gemini with an enhancement-only prompt.
     Gemini sees one image (the composite) and is told to keep the products
     pixel-perfect while enhancing background, lighting, and atmosphere.
  3. Output: 1200×675 16:9 JPEG.

If --no-enhance is passed, step 2 is skipped (raw PIL composite saved).

Usage:
    python3 scripts/compose_hero_pil.py --site cosmetics                # full
    python3 scripts/compose_hero_pil.py --site cosmetics --slug <slug>
    python3 scripts/compose_hero_pil.py --site cosmetics --no-enhance   # PIL only
    python3 scripts/compose_hero_pil.py --site cosmetics --dry-run
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
from PIL import Image, ImageFilter, ImageDraw

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

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
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/*,*/*;q=0.8",
})

PRODUCT_LINK_RE = re.compile(r"mirai-skin\.com/products/([a-z0-9-]+)", re.I)

# Hero canvas
W, H = 1200, 675

# Soft cream-marble background (procedural, no external file needed)
def make_background():
    bg = Image.new("RGB", (W, H), (250, 245, 238))
    # Add subtle veining via overlaid noise
    noise = Image.effect_noise((W, H), 8).convert("RGB")
    bg = Image.blend(bg, noise, 0.04)
    # Soft vignette
    vignette = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(vignette)
    d.ellipse((-200, -150, W + 200, H + 150), fill=255)
    vignette = vignette.filter(ImageFilter.GaussianBlur(120))
    bg.putalpha(vignette)
    final = Image.new("RGB", (W, H), (242, 235, 226))
    final.paste(bg, (0, 0), bg)
    return final


def parse_mdx(path: Path):
    text = path.read_text()
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.S)
    if not m:
        return None, None
    return m.group(1), m.group(2)


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


def trim_to_content(img: Image.Image, threshold=240) -> Image.Image:
    """Crop near-white borders (most Shopify shots are on pure white)."""
    rgb = img.convert("RGB")
    bbox = None
    # Get the bounding box of non-white pixels
    grayscale = rgb.point(lambda v: 0 if v >= threshold else 255).convert("L")
    bbox = grayscale.getbbox()
    if bbox:
        # add 6% margin
        x1, y1, x2, y2 = bbox
        mx = int((x2 - x1) * 0.06)
        my = int((y2 - y1) * 0.06)
        x1 = max(0, x1 - mx); y1 = max(0, y1 - my)
        x2 = min(rgb.width, x2 + mx); y2 = min(rgb.height, y2 + my)
        rgb = rgb.crop((x1, y1, x2, y2))
    return rgb


def make_alpha_from_white(img: Image.Image, white_threshold=245) -> Image.Image:
    """Make near-white pixels transparent so the product sits on the background.
    Simple heuristic — works for clean Shopify product shots on white BG."""
    img = img.convert("RGBA")
    pixels = img.getdata()
    new = []
    for r, g, b, a in pixels:
        if r >= white_threshold and g >= white_threshold and b >= white_threshold:
            new.append((r, g, b, 0))
        elif r >= 230 and g >= 230 and b >= 230:
            # Soft edge — partial transparency for anti-aliasing
            alpha = max(0, 255 - (min(r, g, b) - 230) * 25)
            new.append((r, g, b, alpha))
        else:
            new.append((r, g, b, a))
    img.putdata(new)
    return img


def add_shadow(img: Image.Image, offset=(8, 12), blur=14, opacity=70) -> Image.Image:
    """Add a soft drop shadow under a product (RGBA)."""
    shadow_layer = Image.new("RGBA", (img.width + offset[0]*2 + blur*2,
                                       img.height + offset[1]*2 + blur*2), (0, 0, 0, 0))
    # Shadow is a blurred copy of the product silhouette, dark
    silhouette = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sil_pixels = []
    for r, g, b, a in img.getdata():
        sil_pixels.append((40, 40, 40, int(a * opacity / 255)))
    silhouette.putdata(sil_pixels)
    shadow_layer.paste(silhouette, (offset[0] + blur, offset[1] + blur), silhouette)
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(blur))
    # Now paste original on top
    final = Image.new("RGBA", shadow_layer.size, (0, 0, 0, 0))
    final.paste(shadow_layer, (0, 0), shadow_layer)
    final.paste(img, (blur, blur), img)
    return final


def fit_product(img: Image.Image, max_h: int) -> Image.Image:
    """Resize so height is max_h, maintaining aspect."""
    if img.height == max_h:
        return img
    new_w = int(img.width * (max_h / img.height))
    return img.resize((new_w, max_h), Image.LANCZOS)


def compose_2_up(products: list[Path], out_path: Path, use_gemini_bg: bool = True, slug: str = "default"):
    """Side-by-side comparison layout."""
    bg = make_background_from_gemini_or_fallback(slug) if use_gemini_bg else make_background()
    bg = bg.copy()
    target_h = int(H * 0.72)
    items = []
    for p in products[:2]:
        img = Image.open(p)
        img = trim_to_content(img)
        img = make_alpha_from_white(img)
        img = fit_product(img, target_h)
        img = add_shadow(img)
        items.append(img)
    if len(items) < 2:
        return False
    # Center two products with gap
    gap = 80
    total_w = items[0].width + items[1].width + gap
    x = (W - total_w) // 2
    y = (H - max(items[0].height, items[1].height)) // 2
    for img in items:
        bg.paste(img, (x, y + (H - img.height) // 2 - y), img)
        x += img.width + gap
    bg.save(out_path, "JPEG", quality=92)
    return True


def compose_grid(products: list[Path], out_path: Path, use_gemini_bg: bool = True, slug: str = "default", _slug=None):
    """3-4 product flat-lay grid."""
    bg = make_background_from_gemini_or_fallback(slug) if use_gemini_bg else make_background()
    bg = bg.copy()
    n = len(products[:4])
    target_h = int(H * 0.55) if n <= 3 else int(H * 0.45)
    items = []
    for p in products[:4]:
        img = Image.open(p)
        img = trim_to_content(img)
        img = make_alpha_from_white(img)
        img = fit_product(img, target_h)
        img = add_shadow(img)
        items.append(img)
    if len(items) < 2:
        return False

    if n == 2:
        return compose_2_up(products, out_path, use_gemini_bg=use_gemini_bg, slug=slug)
    if n == 3:
        # Triangle: 2 on top, 1 centered below
        gap_x = 60
        top_total = items[0].width + items[1].width + gap_x
        x = (W - top_total) // 2
        y = int(H * 0.05)
        bg.paste(items[0], (x, y), items[0])
        bg.paste(items[1], (x + items[0].width + gap_x, y), items[1])
        x3 = (W - items[2].width) // 2
        y3 = H - items[2].height - int(H * 0.05)
        bg.paste(items[2], (x3, y3), items[2])
    else:
        # 4 = single row spread across width with slight stagger for editorial feel
        gap = 30
        total_w = sum(it.width for it in items[:4]) + gap * 3
        if total_w > W - 60:
            scale = (W - 60) / total_w
            items = [fit_product(it, int(it.height * scale)) for it in items[:4]]
            total_w = sum(it.width for it in items[:4]) + gap * 3
        x = (W - total_w) // 2
        y_center = H // 2
        for i, img in enumerate(items[:4]):
            stagger = -10 if i % 2 == 0 else 10
            bg.paste(img, (x, y_center - img.height // 2 + stagger), img)
            x += img.width + gap

    bg.save(out_path, "JPEG", quality=92)
    return True


def slug_from_handle_pair(slug: str) -> tuple[str, str] | None:
    """For X-vs-Y articles, extract the two key terms."""
    m = re.match(r"^(.+?)-vs-(.+)$", slug)
    if m:
        return m.group(1), m.group(2)
    return None


def collect_drafts(site_dir: Path):
    en = site_dir / "src" / "content" / "blog" / "en"
    out = []
    for f in sorted(en.glob("*.mdx")):
        fm, body = parse_mdx(f)
        if not fm or body is None:
            continue
        is_draft = bool(re.search(r"^draft:\s*true\s*$", fm, re.M))
        if not is_draft:
            continue
        title_m = re.search(r'title:\s*"([^"]+)"', fm)
        image_m = re.search(r"^image:\s*([^\n]+)", fm, re.M)
        handles = list(dict.fromkeys(PRODUCT_LINK_RE.findall(body)))
        if not handles:
            continue

        # For "X vs Y" articles, pick one handle from each side of the comparison.
        # Match by brand keywords in the handle, NOT by accidental token overlap.
        title = title_m.group(1) if title_m else f.stem
        is_comparison = " vs " in title.lower()
        if is_comparison:
            pair = slug_from_handle_pair(f.stem)
            if pair:
                left, right = pair
                # Use first 2 tokens as brand keywords (e.g. "abib-heartleaf" → ["abib", "heartleaf"])
                left_kws = left.split("-")[:2]
                right_kws = right.split("-")[:2]

                def matches_side(handle: str, side_kws: list, other_kws: list) -> bool:
                    # Must include at least one side keyword AND not be dominated by other-side keyword
                    h_lower = handle.lower()
                    has_side = any(kw in h_lower for kw in side_kws)
                    # Exclude if it leads with the OTHER side's primary brand
                    starts_other = any(h_lower.startswith(kw + "-") for kw in other_kws[:1])
                    return has_side and not starts_other

                left_match = next((h for h in handles if matches_side(h, left_kws, right_kws)), None)
                right_match = next((h for h in handles if matches_side(h, right_kws, left_kws) and h != left_match), None)

                if left_match and right_match:
                    handles = [left_match, right_match]
                else:
                    # Couldn't balance — keep the original ordering but cap to 2
                    handles = handles[:2]

        out.append({
            "path": f,
            "slug": f.stem,
            "title": title,
            "image_rel": image_m.group(1).strip() if image_m else f"/images/{f.stem}.jpg",
            "handles": handles[:4],
            "is_comparison": " vs " in title.lower(),
        })
    return out


BACKGROUND_VARIANTS = [
    "cream marble with subtle veining + green heartleaf sprigs + water droplets",
    "warm sandstone slab + dried lavender stems + small camellia leaves",
    "soft beige linen fabric texture + eucalyptus sprigs + small white flowers",
    "pale pink terrazzo + green ivy sprig + scattered rose petals",
    "ivory ceramic surface with sun-dappled light + fresh mint leaves + glass droplets",
    "weathered birch wood grain + green tea leaves + a single white camellia",
    "sage-tinted marble + dried wheat stems + small jade-toned pebbles",
    "beige washed concrete + green succulent sprigs + scattered seashells",
    "blush peach plaster wall light + fresh peach leaves + soft morning shadows",
    "pale champagne silk fabric + small fresh peony petals + glass beads",
]


def background_prompt_for(slug: str) -> str:
    # Pick deterministic variant per slug so heroes are diverse but reproducible
    idx = hash(slug) % len(BACKGROUND_VARIANTS)
    variant = BACKGROUND_VARIANTS[idx]
    return (
        "Generate a 16:9 landscape editorial photograph of an EMPTY K-beauty flat-lay scene. "
        "NO products, NO bottles, NO jars. Composition: " + variant + ". "
        "Diffuse natural sunlight from upper-left, soft shadows, premium beauty magazine aesthetic. "
        "All decorative elements must be at the EDGES. The center 70% of the frame must be a "
        "CLEAR open background where products can be placed afterwards. No text, no watermarks."
    )


_BG_CACHE: dict[str, Image.Image] = {}


def gemini_generate_background(prompt: str) -> Image.Image | None:
    """Ask Gemini for an EMPTY scene to use as background. Cached per prompt."""
    if prompt in _BG_CACHE:
        return _BG_CACHE[prompt]
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return None

    client = genai.Client(api_key=api_key)
    try:
        resp = client.models.generate_content(
            model="gemini-2.5-flash-image",
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
                img = img.resize((W, H), Image.LANCZOS)
                _BG_CACHE[prompt] = img
                return img
    except Exception as e:
        print(f"    [bg-gen] gemini error: {e}")
    return None


def make_background_from_gemini_or_fallback(slug: str = "default") -> Image.Image:
    """Try to get a Gemini-generated background; fall back to procedural if it fails."""
    img = gemini_generate_background(background_prompt_for(slug))
    return img if img is not None else make_background()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True, choices=list(SITES.keys()))
    ap.add_argument("--slug")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-enhance", action="store_true", help="Skip Gemini enhancement, save PIL composite directly")
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    site_dir = SITES[args.site]
    drafts = collect_drafts(site_dir)
    if args.slug:
        drafts = [d for d in drafts if d["slug"] == args.slug]
    if args.limit:
        drafts = drafts[: args.limit]

    print(f"[{args.site}] {len(drafts)} drafts to compose heroes for\n")

    success, fail = 0, 0
    for d in drafts:
        layout = "2-up (vs)" if d["is_comparison"] else f"{len(d['handles'])}-grid"
        print(f"  → {d['slug']}  [{layout}]")
        for h in d["handles"][:4]:
            print(f"    - {h}")
        if args.dry_run:
            print()
            continue

        prod_paths = []
        for h in d["handles"][:4]:
            p = download_product_image(h)
            if p:
                prod_paths.append(p)
            else:
                print(f"    [{h}] FAIL download")

        if len(prod_paths) < 2:
            print("    SKIP: <2 product photos available\n")
            fail += 1
            continue

        out_path = site_dir / "public" / d["image_rel"].lstrip("/")
        use_gemini = not args.no_enhance
        ok = (compose_2_up(prod_paths, out_path, use_gemini_bg=use_gemini, slug=d["slug"]) if d["is_comparison"]
              else compose_grid(prod_paths, out_path, use_gemini_bg=use_gemini, slug=d["slug"]))
        if ok:
            tag = "Gemini-bg + real products" if use_gemini else "procedural-bg + real products"
            print(f"    SAVED ({tag}) → {out_path.relative_to(ROOT)}\n")
            success += 1
        else:
            print(f"    FAIL: composite error\n")
            fail += 1
        time.sleep(1)

    print(f"\n[done] {success} composed, {fail} failed")


if __name__ == "__main__":
    main()
