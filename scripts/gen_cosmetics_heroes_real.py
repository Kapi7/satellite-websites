#!/usr/bin/env python3
"""Generate cosmetics hero images using real Shopify product photos + Gemini."""

import os, sys, io, time, json, urllib.request
from PIL import Image
from google import genai
from google.genai import types

API_KEY = os.environ.get("GEMINI_API_KEY", "")
client = genai.Client(api_key=API_KEY)
MODEL = "gemini-2.5-flash-image"
OUT_DIR = "/Users/kapi7/satellite-websites/cosmetics/public/images"
PRODUCTS_DIR = "/tmp/hero-gen/products"
os.makedirs(PRODUCTS_DIR, exist_ok=True)

# Get full product catalog with images
print("Fetching Shopify catalog...")
url = "https://mirai-skin.com/products.json?limit=250"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
resp = urllib.request.urlopen(req)
catalog = {p["handle"]: p for p in json.loads(resp.read())["products"]}

def get_product_image(handle):
    """Download product image and return PIL Image."""
    p = catalog.get(handle)
    if not p or not p.get("images"):
        print(f"  WARNING: No image for {handle}")
        return None
    img_url = p["images"][0]["src"]
    cache = os.path.join(PRODUCTS_DIR, f"{handle}.jpg")
    if not os.path.exists(cache):
        urllib.request.urlretrieve(img_url, cache)
    return Image.open(cache)

def generate_hero(filename, product_handles, prompt):
    """Generate hero image from real product photos."""
    output = os.path.join(OUT_DIR, filename)
    print(f"\nGenerating: {filename}...")
    
    # Build content: prompt + product images
    parts = [prompt]
    for handle in product_handles:
        img = get_product_image(handle)
        if img:
            parts.append(img)
            print(f"  Added product: {handle}")
    
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=parts,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )
        
        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                img = Image.open(io.BytesIO(part.inline_data.data))
                img = img.convert("RGB")
                # Crop to 16:9 and resize
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
                img.save(output, "JPEG", quality=90)
                print(f"  OK: {filename}")
                return True
        
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'text') and part.text:
                print(f"  No image. Text: {part.text[:150]}")
        return False
    except Exception as e:
        print(f"  ERROR: {str(e)[:200]}")
        return False

BASE_PROMPT = (
    "Create a beautiful flat-lay blog hero image in landscape orientation (wider than tall, 16:9 ratio). "
    "Take these Korean skincare products and arrange them aesthetically. "
    "The products should look exactly like these reference photos — same bottles, labels, and colors. "
    "No text overlays. No watermarks. Studio-quality product photography feel. "
)

HEROES = [
    ("ceramide-creams-barrier.jpg",
     ["illiyoon-ceramide-ato-concentrate-cream-200ml", "torriden-solid-in-ceramide-cream-70ml-1", "tocobo-multi-ceramide-cream-50ml"],
     BASE_PROMPT + "Place on soft pink marble surface with dewy water droplets and small eucalyptus leaves. Soft morning light from left. Premium beauty blog photography."),

    ("korean-lip-products.jpg",
     ["torriden-cellmazing-low-molecular-collagen-lip-ess", "tocobo-vitamin-nourishing-lip-balm-3-5g", "anua-pdrn-lip-serum-10ml"],
     BASE_PROMPT + "Place on pastel pink surface with fresh rose petals scattered around. Glossy, hydrated lip care aesthetic. Soft studio lighting."),

    ("pdrn-skincare-products.jpg",
     ["cosrx-5pdrn-collagen-intense-vitalizing-serum-100m", "tonymoly-snail-pdrn-recovery-cream-50ml", "cosrx-5-pdrn-b5-vital-soothing-toner-280ml"],
     BASE_PROMPT + "Place on white marble with a few salmon roe capsules as accents. Clinical yet luxurious PDRN skincare aesthetic. Soft diffused lighting."),

    ("sheet-masks-by-concern.jpg",
     ["innisfree-madecassoside-active-mask-25ml-x-5ea", "torriden-dive-in-low-molecule-hyaluronic-acid-mask", "parnell-cicamanu-serum-mask-sheet-25ml-x-10ea"],
     BASE_PROMPT + "Fan out these sheet mask packets on a clean white surface with cucumber slices and small white flowers. Spa day aesthetic. Bright natural lighting."),

    ("dark-spots-hyperpigmentation.jpg",
     ["k-secret-seoul-1988-glow-serum-niacinamide-15-yuja", "axis-y-dark-spot-correcting-glow-toner-125ml", "parnell-niacinamide-20-35-rice-brightening-serum-3"],
     BASE_PROMPT + "Place on light surface with lemon slices and vitamin C capsules. Radiant brightening glow aesthetic. Warm soft lighting."),

    ("korean-skincare-men.jpg",
     ["torriden-balanceful-for-men-cica-fresh-all-in-one-", "belif-man-101-aqua-refresher-125ml", "torriden-dive-in-for-men-low-molecular-hyaluronic-"],
     BASE_PROMPT + "Place on dark slate surface with a eucalyptus sprig. Masculine minimalist grooming aesthetic. Moody studio lighting."),

    ("cushion-foundations-guide.jpg",
     ["tirtir-mask-fit-red-cushion-spf40-pa-4-5g-mini-45s", "tocobo-apple-dewy-fit-cushion-spf50-pa-15g", "parnell-cicamanu-serum-cushion-spf45-pa-15g-refill"],
     BASE_PROMPT + "Show compacts open revealing cushion pads on vanity surface with a soft makeup brush. Dewy glass skin finish. Soft warm lighting."),

    ("cica-products-sensitive-skin.jpg",
     ["tocobo-cica-calming-gel-cream-75ml", "parnell-panthenol-5-78-heartleaf-calming-serum-30m", "tocobo-cica-calming-serum-50ml"],
     BASE_PROMPT + "Place on mint green surface with fresh centella asiatica leaves. Calming soothing natural aesthetic. Soft diffused lighting."),

    ("cleansing-balms-oils.jpg",
     ["tirtir-hydro-boost-enzyme-cleansing-balm-120ml", "tocobo-calamine-pore-control-cleansing-oil-200ml", "parnell-aha-omija-ceramic-cleansing-oil-200ml"],
     BASE_PROMPT + "Place with cotton pads and water splashes on clean white surface. Fresh double cleanse aesthetic. Soft natural lighting."),

    ("korean-toners-glass-skin.jpg",
     ["torriden-dive-in-toner-300ml-1", "tocobo-vita-berry-pore-toner-150ml", "tirtir-match-skin-toner-150ml"],
     BASE_PROMPT + "Place with water droplets and a glass prism on reflective surface. Glass skin dewy aesthetic with light refractions. Bright studio lighting."),

    ("moisturizers-under-25.jpg",
     ["torriden-dive-in-hyaluronic-acid-soothing-cream-10", "tocobo-multi-ceramide-cream-50ml", "innisfree-green-tea-ceramide-cream-50ml"],
     BASE_PROMPT + "Place on colorful pastel split background. Budget-friendly cute K-beauty aesthetic. Bright natural lighting."),

    ("medicube-age-r-devices.jpg",
     ["medicube-age-r-booster-pro-pink-it-can-only-be-shi", "medicube-age-r-high-focus-shot-plus-2colors-it-can", "medicube-age-r-booster-v-roller-2colors-it-can-onl"],
     BASE_PROMPT + "Place on futuristic white surface with soft blue LED glow. High-tech beauty device aesthetic. Studio lighting with ambient glow."),

    ("korean-body-care.jpg",
     ["illiyoon-ceramide-ato-lotion-350ml", "illiyoon-fresh-moisture-body-wash-500ml", "parnell-cicamanu-ph-balanced-body-wash-400ml"],
     BASE_PROMPT + "Place with fluffy white towels on spa-like marble surface. Body care pampering aesthetic with warm tones."),

    ("korean-hair-care-repair.jpg",
     ["cosrx-peptide-132-ultra-perfect-hair-bonding-oil-s", "cosrx-peptide-132-ultra-perfect-hair-bonding-treat", "tonymoly-black-tea-intense-repair-serum-50ml"],
     BASE_PROMPT + "Place alongside flowing silky brown hair strands on neutral surface. Healthy shiny hair aesthetic. Soft studio lighting."),

    ("anti-aging-serums.jpg",
     ["dalba-vita-toning-capsule-serum-100ml", "parnell-bakuchiol-retinol-wild-yam-2-12-firming-se", "torriden-cellmazing-small-molecule-collagen-firmin"],
     BASE_PROMPT + "Place with golden serum droplets on luxurious surface with gold accents. Premium anti-aging skincare aesthetic. Soft warm lighting."),
]

success = 0
for filename, handles, prompt in HEROES:
    if generate_hero(filename, handles, prompt):
        success += 1
    time.sleep(5)

print(f"\n=== Done: {success}/15 images generated ===")
