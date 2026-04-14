#!/usr/bin/env python3
"""
Regenerate hero images using REAL product photos fed through Gemini.

Pipeline:
1. Fetch product page → extract main product image (og:image or first large img)
2. Download product photos to /tmp/hero-gen/products/
3. Feed real photos + styling prompt to Gemini 2.5 Flash Image
4. Save composed hero image (16:9, 1200x675)

Usage:
  python3 scripts/regen_hero_real_products.py                # all 28
  python3 scripts/regen_hero_real_products.py --start 0 --count 5  # first 5
  python3 scripts/regen_hero_real_products.py --dry-run      # preview only
"""
import os, sys, io, time, argparse, re, json
from urllib.parse import urljoin, urlparse
from html.parser import HTMLParser

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("ERROR: Set GEMINI_API_KEY environment variable")
    sys.exit(1)

import requests as req_lib
from google import genai
from google.genai import types
from PIL import Image

client = genai.Client(api_key=api_key)
MODEL = "gemini-2.5-flash-image"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRODUCTS_DIR = "/tmp/hero-gen/products"
os.makedirs(PRODUCTS_DIR, exist_ok=True)

SITE_IMAGE_DIRS = {
    "glow-coded.com": os.path.join(ROOT, "cosmetics/public/images"),
    "rooted-glow.com": os.path.join(ROOT, "wellness/public/images"),
    "build-coded.com": os.path.join(ROOT, "build-coded/public/images"),
}

# Browser-like session for reliable downloads
session = req_lib.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/*,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
})

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


# ── Image extraction from product pages ──────────────────────

class OGImageParser(HTMLParser):
    """Extract og:image or first large product image from HTML."""
    def __init__(self):
        super().__init__()
        self.og_image = None
        self.images = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "meta":
            prop = attrs_dict.get("property", "") or attrs_dict.get("name", "")
            if prop in ("og:image", "twitter:image") and not self.og_image:
                self.og_image = attrs_dict.get("content", "")
        elif tag == "img":
            src = attrs_dict.get("src", "") or attrs_dict.get("data-src", "")
            if src:
                self.images.append(src)


def is_direct_image_url(url):
    """Check if URL points directly to an image file or known image CDN."""
    parsed = urlparse(url)
    path_lower = parsed.path.lower()
    # Direct file extension
    if any(path_lower.endswith(ext) for ext in IMAGE_EXTS):
        return True
    # Known image CDN patterns (no file extension but serve images)
    known_image_hosts = ["images.asics.com", "media.ulta.com"]
    if parsed.hostname in known_image_hosts:
        return True
    return False


def fetch_product_image_url(page_url):
    """Fetch a product page and return the best product image URL.

    Strategy: direct image URL → JSON-LD Product.image → og:image → first large img
    """
    # If it's already a direct image URL, return as-is
    if is_direct_image_url(page_url):
        return page_url

    try:
        resp = session.get(page_url, timeout=15, allow_redirects=True)
        resp.raise_for_status()
        html = resp.text
        base_url = resp.url

        # 1. Try JSON-LD structured data (most reliable for product pages)
        ld_matches = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL)
        for ld_text in ld_matches:
            try:
                data = json.loads(ld_text)
                if isinstance(data, list):
                    data = data[0]
                if data.get("@type") == "Product" and data.get("image"):
                    imgs = data["image"]
                    img_url = imgs[0] if isinstance(imgs, list) else imgs
                    if img_url and not img_url.startswith("http"):
                        img_url = urljoin(base_url, img_url)
                    return img_url
            except (json.JSONDecodeError, KeyError, IndexError):
                pass

        # 2. Try og:image / twitter:image
        parser = OGImageParser()
        parser.feed(html)

        img_url = parser.og_image
        if img_url and not img_url.startswith("http"):
            img_url = urljoin(base_url, img_url)

        # 3. Fallback: first non-logo img tag
        if not img_url and parser.images:
            for img in parser.images:
                if any(skip in img.lower() for skip in ["logo", "icon", "favicon", "sprite", "badge", "pixel", "1x1", "svg"]):
                    continue
                img_url = img if img.startswith("http") else urljoin(base_url, img)
                break

        return img_url
    except Exception as e:
        print(f"    WARN: Could not fetch {page_url}: {e}")
        return None


def download_image(url, dest_path):
    """Download image from URL to local path."""
    try:
        resp = session.get(url, timeout=15, stream=True)
        resp.raise_for_status()
        data = resp.content
        if len(data) < 1000:
            print(f"    WARN: Suspiciously small download ({len(data)} bytes), skipping")
            return False
        with open(dest_path, "wb") as f:
            f.write(data)
        return True
    except Exception as e:
        print(f"    WARN: Download failed {url}: {e}")
        return False


def download_product_photos(products):
    """Download product photos, return list of local paths."""
    local_paths = []
    for p in products:
        name = p["name"]
        url = p["url"]
        safe_name = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60]
        local_path = os.path.join(PRODUCTS_DIR, f"{safe_name}.jpg")

        # Skip if already downloaded with good size
        if os.path.exists(local_path) and os.path.getsize(local_path) > 5000:
            print(f"    Cached: {name}")
            local_paths.append(local_path)
            continue

        print(f"    Fetching: {name}...")
        img_url = fetch_product_image_url(url)
        if img_url:
            if download_image(img_url, local_path):
                size_kb = os.path.getsize(local_path) / 1024
                print(f"    Downloaded: {size_kb:.0f} KB")
                local_paths.append(local_path)
            else:
                print(f"    SKIP: Download failed for {name}")
        else:
            print(f"    SKIP: No image found on page for {name}")

    return local_paths


def generate_hero(product_paths, prompt, output_path, dry_run=False):
    """Feed real product photos + prompt to Gemini, save hero image."""
    if dry_run:
        print(f"    Would generate: {output_path}")
        print(f"    Using {len(product_paths)} product photos")
        return True

    parts = [prompt]
    for img_path in product_paths:
        try:
            img = Image.open(img_path)
            parts.append(img)
        except Exception as e:
            print(f"    WARN: Could not open {img_path}: {e}")

    if len(parts) < 2:
        print(f"    ERROR: No valid product photos to compose")
        return False

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=parts,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )

        saved = False
        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                img = Image.open(io.BytesIO(part.inline_data.data))
                img = img.convert("RGB")

                # Crop to 16:9 and resize to 1200x675
                target_ratio = 16 / 9
                current_ratio = img.width / img.height
                if current_ratio > target_ratio:
                    new_w = int(img.height * target_ratio)
                    left = (img.width - new_w) // 2
                    img = img.crop((left, 0, left + new_w, img.height))
                elif current_ratio < target_ratio:
                    new_h = int(img.width / target_ratio)
                    top = (img.height - new_h) // 2
                    img = img.crop((0, top, img.width, top + new_h))
                img = img.resize((1200, 675), Image.LANCZOS)

                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                img.save(output_path, "JPEG", quality=90)
                size_kb = os.path.getsize(output_path) / 1024
                print(f"    Saved: {size_kb:.0f} KB")
                saved = True
                break

        if not saved:
            for part in response.candidates[0].content.parts:
                if hasattr(part, "text") and part.text:
                    print(f"    No image returned. Text: {part.text[:200]}")
            return False
        return True

    except Exception as e:
        print(f"    ERROR: {e}")
        return False


# ── The 28 images to regenerate ──────────────────────────────

BASE_PROMPT = (
    "Create a flat-lay product photograph in landscape 16:9 ratio. "
    "Place these Korean skincare products on a white marble surface with soft lighting and small botanical accents. "
    "The products should look exactly like these reference photos — same bottles, labels, and colors. "
    "Premium beauty blog photography. No text overlays. No watermarks."
)

TOOL_PROMPT = (
    "Create a product photograph in landscape 16:9 ratio. "
    "Place these tools on a clean workshop workbench with warm lighting. "
    "The tools should look exactly like these reference photos — same colors, brand logos, designs. "
    "Professional tool photography. No text overlays. No watermarks."
)

SHOE_PROMPT = (
    "Create a product photograph in landscape 16:9 ratio. "
    "Place these running shoes side by side on a clean surface with bright natural lighting. "
    "The shoes should look exactly like these reference photos — same colors, designs, brand logos. "
    "Premium athletic photography. No text overlays. No watermarks."
)

HEROES = [
    # ─── COSMETICS (glow-coded.com) ───
    {
        "site": "glow-coded.com",
        "image_file": "sunscreens-oily-skin.jpg",
        "products": [
            {"name": "Beauty of Joseon Relief Sun", "url": "https://beautyofjoseon.com/products/relief-sun-rice-probiotics-spf50-pa-uk"},
            {"name": "COSRX Ultra-Light Invisible Sunscreen", "url": "https://www.cosrx.com/products/ultra-light-invisible-sunscreen-spf50"},
            {"name": "Isntree Hyaluronic Acid Watery Sun Gel", "url": "https://www.iherb.com/pr/isntree-hyaluronic-acid-watery-sun-gel-50-spf-50-pa-1-69-fl-oz-50-ml/113671"},
        ],
        "prompt": BASE_PROMPT,
    },
    {
        "site": "glow-coded.com",
        "image_file": "moisturizers-sensitive-skin.jpg",
        "products": [
            {"name": "ETUDE SoonJung Hydro Barrier Cream", "url": "https://www.sephora.com/productimages/sku/s2624831-main-zoom.jpg"},
            {"name": "Dr.Jart+ Ceramidin Cream", "url": "https://www.sephora.com/productimages/sku/s2210557-main-zoom.jpg"},
        ],
        "prompt": BASE_PROMPT,
    },
    {
        "site": "glow-coded.com",
        "image_file": "dark-spots-hyperpigmentation.jpg",
        "products": [
            {"name": "K-SECRET SEOUL 1988 Glow Serum", "url": "https://ksecretcosmetics.com/products/seoul-1988-glow-serum-niacinamide-15-yuja"},
            {"name": "AXIS-Y Dark Spot Correcting Glow Toner", "url": "https://www.axis-y.com/products/dark-spot-correcting-glow-toner"},
        ],
        "prompt": BASE_PROMPT,
    },
    {
        "site": "glow-coded.com",
        "image_file": "korean-cleansing-oils.jpg",
        "products": [
            {"name": "Beauty of Joseon Ginseng Cleansing Oil", "url": "https://beautyofjoseon.com/products/ginseng-cleansing-oil"},
            {"name": "Banila Co Clean It Zero", "url": "https://banilausa.com/products/clean-it-zero-cleansing-balm-original"},
            {"name": "Anua Heartleaf Cleansing Oil", "url": "https://anua.com/products/heartleaf-pore-control-cleansing-oil-200ml"},
        ],
        "prompt": BASE_PROMPT,
    },
    {
        "site": "glow-coded.com",
        "image_file": "korean-toners-ranked.jpg",
        "products": [
            {"name": "Anua Heartleaf 77% Soothing Toner", "url": "https://anua.com/products/heartleaf-77-soothing-toner"},
            {"name": "COSRX Pure Fit Cica Toner", "url": "https://www.cosrx.com/products/pure-fit-cica-toner"},
        ],
        "prompt": BASE_PROMPT,
    },
    {
        "site": "glow-coded.com",
        "image_file": "korean-eye-cream-guide.jpg",
        "products": [
            {"name": "Beauty of Joseon Revive Eye Serum", "url": "https://beautyofjoseon.com/products/revive-eye-serum-ginseng-retinal"},
            {"name": "COSRX Advanced Snail Peptide Eye Cream", "url": "https://www.cosrx.com/products/advanced-snail-peptide-eye-cream"},
        ],
        "prompt": BASE_PROMPT,
    },
    {
        "site": "glow-coded.com",
        "image_file": "anti-aging-30s.jpg",
        "products": [
            {"name": "COSRX The Retinol 0.5 Oil", "url": "https://www.cosrx.com/products/the-retinol-0-5-oil"},
            {"name": "medicube Triple Collagen Serum", "url": "https://medicube.us/products/triple-collagen-serum"},
        ],
        "prompt": BASE_PROMPT,
    },
    {
        "site": "glow-coded.com",
        "image_file": "aha-bha-pha-guide.jpg",
        "products": [
            {"name": "COSRX AHA 7 Whitehead Power Liquid", "url": "https://www.cosrx.com/products/aha-7-whitehead-power-liquid"},
            {"name": "COSRX BHA Blackhead Power Liquid", "url": "https://www.cosrx.com/products/bha-blackhead-power-liquid"},
        ],
        "prompt": BASE_PROMPT,
    },
    {
        "site": "glow-coded.com",
        "image_file": "retinol-beginners-guide.jpg",
        "products": [
            {"name": "COSRX The Retinol 0.5 Oil", "url": "https://www.cosrx.com/products/the-retinol-0-5-oil"},
            {"name": "innisfree Retinol Cica Repair Ampoule", "url": "https://us.innisfree.com/"},
        ],
        "prompt": BASE_PROMPT,
    },
    {
        "site": "glow-coded.com",
        "image_file": "rosacea-routine.jpg",
        "products": [
            {"name": "SKIN1004 Centella Toning Toner", "url": "https://www.skin1004.com/products/skin1004-madagascar-centella-toning-toner"},
            {"name": "Torriden Balanceful Cica Serum", "url": "https://torriden.us/products/balanceful-serum"},
        ],
        "prompt": BASE_PROMPT,
    },
    {
        "site": "glow-coded.com",
        "image_file": "hydrating-winter-routine.jpg",
        "products": [
            {"name": "COSRX Snail 96 Mucin Essence", "url": "https://www.cosrx.com/products/advanced-snail-96-mucin-power-essence"},
            {"name": "COSRX Hyaluronic Acid Intensive Cream", "url": "https://www.cosrx.com/products/hyaluronic-acid-intensive-cream"},
        ],
        "prompt": BASE_PROMPT,
    },
    {
        "site": "glow-coded.com",
        "image_file": "korean-vs-western-spf.jpg",
        "products": [
            {"name": "Beauty of Joseon Relief Sun", "url": "https://beautyofjoseon.com/products/relief-sun-rice-probiotics-spf50-pa-uk"},
            {"name": "COSRX Aloe Soothing Sun Cream", "url": "https://www.cosrx.com/products/aloe-soothing-sun-cream-spf50-pa"},
        ],
        "prompt": BASE_PROMPT,
    },
    {
        "site": "glow-coded.com",
        "image_file": "korean-sunscreens-acne-prone.jpg",
        "products": [
            {"name": "Beauty of Joseon Relief Sun", "url": "https://beautyofjoseon.com/products/relief-sun-rice-probiotics-spf50-pa-uk"},
            {"name": "COSRX Aloe Soothing Sun Cream", "url": "https://www.cosrx.com/products/aloe-soothing-sun-cream-spf50-pa"},
        ],
        "prompt": BASE_PROMPT,
    },
    {
        "site": "glow-coded.com",
        "image_file": "k-beauty-under-15.jpg",
        "products": [
            {"name": "COSRX Snail 96 Mucin Essence", "url": "https://www.cosrx.com/products/advanced-snail-96-mucin-power-essence"},
            {"name": "Beauty of Joseon Relief Sun", "url": "https://beautyofjoseon.com/products/relief-sun-rice-probiotics-spf50-pa-uk"},
            {"name": "COSRX Low pH Good Morning Cleanser", "url": "https://www.cosrx.com/products/low-ph-good-morning-gel-cleanser"},
        ],
        "prompt": BASE_PROMPT,
    },
    {
        "site": "glow-coded.com",
        "image_file": "dry-skin-winter-guide.jpg",
        "products": [
            {"name": "Torriden Dive-In HA Serum", "url": "https://torriden.us/products/dive-in-serum"},
            {"name": "Illiyoon Ceramide Ato Cream", "url": "https://media.ulta.com/i/ulta/2610363?w=600"},
        ],
        "prompt": BASE_PROMPT,
    },

    # ─── WELLNESS (rooted-glow.com) ───
    {
        "site": "rooted-glow.com",
        "image_file": "best-running-shoes-beginners.jpg",
        "products": [
            {"name": "Nike Pegasus 42", "url": "https://www.nike.com/t/pegasus-42-mens-road-running-shoes-S1bYkOza"},
            {"name": "ASICS Gel-Nimbus 28", "url": "https://images.asics.com/is/image/asics/1011C127_100_SR_RT_GLB?wid=800"},
        ],
        "prompt": SHOE_PROMPT,
    },
    {
        "site": "rooted-glow.com",
        "image_file": "best-running-shoes-intermediate.jpg",
        "products": [
            {"name": "Nike Vomero 18", "url": "https://www.nike.com/t/vomero-18-mens-road-running-shoes-BWk4Dn"},
            {"name": "ASICS Novablast 5", "url": "https://images.asics.com/is/image/asics/1011B974_002_SR_RT_GLB?wid=800"},
        ],
        "prompt": SHOE_PROMPT,
    },
    {
        "site": "rooted-glow.com",
        "image_file": "best-running-shoes-advanced.jpg",
        "products": [
            {"name": "Nike Vaporfly 4", "url": "https://www.nike.com/t/vaporfly-4-mens-road-racing-shoes-HK05JWOf"},
            {"name": "Saucony Endorphin Elite 2", "url": "https://www.saucony.com/en/endorphin-elite-2/59824U.html"},
        ],
        "prompt": SHOE_PROMPT,
    },
    {
        "site": "rooted-glow.com",
        "image_file": "running-shoe-rotation-guide.jpg",
        "products": [
            {"name": "Saucony Kinvara 16", "url": "https://www.saucony.com/en/kinvara-16/60309M.html"},
            {"name": "Nike Pegasus 42", "url": "https://www.nike.com/t/pegasus-42-mens-road-running-shoes-S1bYkOza"},
        ],
        "prompt": SHOE_PROMPT,
    },
    {
        "site": "rooted-glow.com",
        "image_file": "stress-breakout-products.jpg",
        "products": [
            {"name": "SKIN1004 Centella Toning Toner", "url": "https://www.skin1004.com/products/skin1004-madagascar-centella-toning-toner"},
            {"name": "Torriden Balanceful Cica Serum", "url": "https://torriden.us/products/balanceful-serum"},
        ],
        "prompt": BASE_PROMPT,
    },
    {
        "site": "rooted-glow.com",
        "image_file": "skincare-for-runners.jpg",
        "products": [
            {"name": "Beauty of Joseon Relief Sun", "url": "https://beautyofjoseon.com/products/relief-sun-rice-probiotics-spf50-pa-uk"},
            {"name": "COSRX Low pH Good Morning Cleanser", "url": "https://www.cosrx.com/products/low-ph-good-morning-gel-cleanser"},
            {"name": "Torriden Balanceful Cica Serum", "url": "https://torriden.us/products/balanceful-serum"},
        ],
        "prompt": BASE_PROMPT,
    },
    {
        "site": "rooted-glow.com",
        "image_file": "post-workout-kbeauty.jpg",
        "products": [
            {"name": "COSRX Low pH Good Morning Cleanser", "url": "https://www.cosrx.com/products/low-ph-good-morning-gel-cleanser"},
            {"name": "Torriden Balanceful Cica Serum", "url": "https://torriden.us/products/balanceful-serum"},
            {"name": "COSRX Snail 96 Mucin Essence", "url": "https://www.cosrx.com/products/advanced-snail-96-mucin-power-essence"},
        ],
        "prompt": BASE_PROMPT,
    },

    # ─── BUILD-CODED (build-coded.com) ───
    {
        "site": "build-coded.com",
        "image_file": "best-cordless-drills.jpg",
        "products": [
            {"name": "Milwaukee M18 FUEL 2903-20", "url": "https://www.milwaukeetool.com/products/details/m18-fuel-1-2-drill-driver/2903-20"},
            {"name": "DeWalt DCD800", "url": "https://www.dewalt.com/product/dcd800b/20v-max-xr-12-brushless-cordless-drilldriver-tool-only"},
        ],
        "prompt": TOOL_PROMPT,
    },
    {
        "site": "build-coded.com",
        "image_file": "best-multimeters-home-use.jpg",
        "products": [
            {"name": "Klein Tools MM400", "url": "https://www.kleintools.com/catalog/multimeters/digital-multimeter-auto-ranging-600v"},
            {"name": "Fluke 117", "url": "https://www.fluke.com/en-us/product/electrical-testing/digital-multimeters/fluke-117"},
        ],
        "prompt": TOOL_PROMPT,
    },
    {
        "site": "build-coded.com",
        "image_file": "best-3d-printers-beginners.jpg",
        "products": [
            {"name": "Bambu Lab A1 Mini", "url": "https://bambulab.com/en/a1-mini"},
        ],
        "prompt": TOOL_PROMPT,
    },
    {
        "site": "build-coded.com",
        "image_file": "best-wood-finishes-beginners.jpg",
        "products": [
            {"name": "Minwax Fast-Drying Polyurethane", "url": "https://www.minwax.com/en/products/protective-finishes/fast-drying-polyurethane"},
        ],
        "prompt": TOOL_PROMPT,
    },
    {
        "site": "build-coded.com",
        "image_file": "best-soldering-irons-beginners.jpg",
        "products": [
            {"name": "Pine64 Pinecil V2", "url": "https://pine64.com/product/pinecil-smart-mini-portable-soldering-iron/"},
            {"name": "Hakko FX-888D", "url": "https://www.adafruit.com/product/1204"},
        ],
        "prompt": TOOL_PROMPT,
    },
    {
        "site": "build-coded.com",
        "image_file": "table-saw-vs-circular-saw.jpg",
        "products": [
            {"name": "DEWALT DWE575SB Circular Saw", "url": "https://www.dewalt.com/product/dwe575sb/7-14-lightweight-circular-saw-contractor-bag-tool-only"},
        ],
        "prompt": TOOL_PROMPT,
    },
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--count", type=int, default=len(HEROES))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    batch = HEROES[args.start:args.start + args.count]
    print(f"{'[DRY RUN] ' if args.dry_run else ''}Processing {len(batch)} hero images (starting at #{args.start + 1})...\n")

    ok = 0
    for i, hero in enumerate(batch):
        num = args.start + i + 1
        site = hero["site"]
        img_file = hero["image_file"]
        output_path = os.path.join(SITE_IMAGE_DIRS[site], img_file)

        print(f"\n[{num}/28] {site} — {img_file}")

        # Step 1: Download product photos
        print("  Downloading product photos...")
        product_paths = download_product_photos(hero["products"])

        if not product_paths:
            print("  SKIP: No product photos available")
            continue

        # Step 2: Generate hero via Gemini
        print(f"  Generating hero with {len(product_paths)} products...")
        if generate_hero(product_paths, hero["prompt"], output_path, dry_run=args.dry_run):
            ok += 1

        if not args.dry_run and i < len(batch) - 1:
            time.sleep(5)  # Rate limit between generations

    print(f"\n{'[DRY RUN] ' if args.dry_run else ''}Done: {ok}/{len(batch)}")


if __name__ == "__main__":
    main()
