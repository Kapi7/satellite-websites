#!/usr/bin/env python3
"""Generate product thumbnail images from Shopify catalog for cosmetics articles."""

import os, sys, json, urllib.request, io, re, time
from PIL import Image
from google import genai
from google.genai import types

API_KEY = os.environ.get("GEMINI_API_KEY", "")
client = genai.Client(api_key=API_KEY)
MODEL = "gemini-2.5-flash-image"

OUT_DIR = "/Users/kapi7/satellite-websites/cosmetics/public/images/products"
CACHE_DIR = "/tmp/product-thumbs-cache"
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

# Fetch Shopify catalog
print("Fetching Shopify catalog...")
url = "https://mirai-skin.com/products.json?limit=250"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
resp = urllib.request.urlopen(req)
products = json.loads(resp.read())["products"]
catalog = {}
for p in products:
    catalog[p["handle"]] = p
    # Also index by simplified name for fuzzy matching
    simple = re.sub(r'-\d+ml.*|-\d+g.*|-\d+ea.*|-\d+colors.*|-spf\d+.*', '', p["handle"])
    catalog[simple] = p

print(f"  Found {len(products)} products in catalog")

def find_product(image_name):
    """Try to match an image filename to a Shopify product handle."""
    # Direct handle match
    if image_name in catalog:
        return catalog[image_name]

    # Try common patterns: image_name might be simplified
    # e.g., "cosrx-barrier-cream" -> look for handles containing these words
    parts = image_name.split('-')
    brand = parts[0] if parts else ""

    best_match = None
    best_score = 0

    for handle, product in catalog.items():
        if handle == product.get("handle", ""):  # only check actual handles
            # Score based on word overlap
            handle_parts = set(handle.lower().split('-'))
            name_parts = set(image_name.lower().split('-'))
            overlap = len(handle_parts & name_parts)
            # Brand must match
            if parts[0] in handle.split('-')[0] or handle.split('-')[0] in parts[0]:
                if overlap > best_score:
                    best_score = overlap
                    best_match = product

    if best_score >= 2:
        return best_match
    return None

def download_product_image(product):
    """Download the first product image and return as PIL Image."""
    if not product.get("images"):
        return None
    img_url = product["images"][0]["src"]
    cache_file = os.path.join(CACHE_DIR, f"{product['handle']}.jpg")
    if not os.path.exists(cache_file):
        urllib.request.urlretrieve(img_url, cache_file)
    return Image.open(cache_file)

def generate_thumbnail(image_name, product):
    """Generate a clean product thumbnail using Gemini."""
    output = os.path.join(OUT_DIR, f"{image_name}.jpg")
    if os.path.exists(output):
        return True

    img = download_product_image(product)
    if not img:
        print(f"  No image available for {product['handle']}")
        return False

    product_name = product.get("title", image_name)

    prompt = (
        f"Create a clean product photo of this Korean skincare product ({product_name}). "
        "Place the product on a clean white or very light background. "
        "The product should be centered and fill most of the frame. "
        "Professional product photography style. No text overlays. No watermarks. "
        "Square format. Studio lighting."
    )

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=[prompt, img],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )

        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                result = Image.open(io.BytesIO(part.inline_data.data))
                result = result.convert("RGB")
                # Resize to square thumbnail
                size = min(result.width, result.height)
                left = (result.width - size) // 2
                top = (result.height - size) // 2
                result = result.crop((left, top, left + size, top + size))
                result = result.resize((600, 600), Image.LANCZOS)
                result.save(output, "JPEG", quality=90)
                print(f"  OK: {image_name}.jpg")
                return True

        # If Gemini didn't return an image, just use the original resized
        print(f"  Gemini no image, using original for {image_name}")
        img = img.convert("RGB")
        size = min(img.width, img.height)
        left = (img.width - size) // 2
        top = (img.height - size) // 2
        img = img.crop((left, top, left + size, top + size))
        img = img.resize((600, 600), Image.LANCZOS)
        img.save(output, "JPEG", quality=90)
        return True

    except Exception as e:
        print(f"  Gemini error for {image_name}: {str(e)[:100]}")
        # Fallback: just resize the original
        try:
            img = img.convert("RGB")
            size = min(img.width, img.height)
            left = (img.width - size) // 2
            top = (img.height - size) // 2
            img = img.crop((left, top, left + size, top + size))
            img = img.resize((600, 600), Image.LANCZOS)
            img.save(output, "JPEG", quality=90)
            print(f"  FALLBACK OK: {image_name}.jpg (original resized)")
            return True
        except:
            return False

# Get list of missing images
missing = []
blog_dir = "/Users/kapi7/satellite-websites/cosmetics/src/content/blog/en"
for f in os.listdir(blog_dir):
    if not f.endswith('.mdx'):
        continue
    with open(os.path.join(blog_dir, f)) as fh:
        content = fh.read()
    for match in re.findall(r'/images/products/([^")\s]+)\.jpg', content):
        output = os.path.join(OUT_DIR, f"{match}.jpg")
        if not os.path.exists(output) and match not in missing:
            missing.append(match)

print(f"\n{len(missing)} missing product images to generate")

success = 0
failed = []
for i, image_name in enumerate(missing):
    print(f"\n[{i+1}/{len(missing)}] {image_name}")
    product = find_product(image_name)
    if product:
        print(f"  Matched: {product['handle']} ({product['title'][:50]})")
        if generate_thumbnail(image_name, product):
            success += 1
        else:
            failed.append(image_name)
    else:
        print(f"  NO MATCH in Shopify catalog")
        failed.append(image_name)

    if i < len(missing) - 1:
        time.sleep(3)  # Rate limit

print(f"\n=== Done: {success}/{len(missing)} generated ===")
if failed:
    print(f"Failed ({len(failed)}):")
    for f in failed:
        print(f"  - {f}")
