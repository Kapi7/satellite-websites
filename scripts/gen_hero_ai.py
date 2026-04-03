#!/usr/bin/env python3
"""
Generate AI-enhanced blog hero images using Google Gemini 2.5 Flash Image.
Sends real Shopify product photos as input, gets styled hero compositions back.
Save this script for future hero image generation.
"""
import os, sys, io, time
from PIL import Image
from google import genai
from google.genai import types

API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL = "gemini-2.5-flash-image"
client = genai.Client(api_key=API_KEY)

PRODUCTS_DIR = "/tmp/hero-gen/products"

HEROES = [
    {
        "name": "skincare-ingredient-compatibility",
        "output": "/Users/kapi7/satellite-websites/cosmetics/public/images/skincare-ingredient-compatibility.jpg",
        "products": [
            f"{PRODUCTS_DIR}/torriden.jpg",
            f"{PRODUCTS_DIR}/cosrx-aha.jpg",
            f"{PRODUCTS_DIR}/cosrx-snail.png",
        ],
        "prompt": (
            "Create a beautiful flat-lay blog hero image in landscape orientation (wider than tall, 16:9 ratio). "
            "Take these three Korean skincare products and arrange them aesthetically on a clean white marble surface "
            "with soft natural morning light streaming from the left side. "
            "Add subtle botanical accents — a few small green eucalyptus leaves and dried baby's breath flowers scattered around. "
            "The products should look exactly like these reference photos — same bottles, labels, and colors. "
            "Soft diffused shadows, bright and airy mood, premium beauty blog photography style. "
            "No text overlays. No watermarks. Studio-quality product photography feel."
        ),
    },
    {
        "name": "double-cleansing-products",
        "output": "/Users/kapi7/satellite-websites/wellness/public/images/double-cleansing-products.jpg",
        "products": [
            f"{PRODUCTS_DIR}/anua-oil.jpg",
            f"{PRODUCTS_DIR}/banila-co.png",
            f"{PRODUCTS_DIR}/cosrx-gm.jpg",
        ],
        "prompt": (
            "Create a beautiful flat-lay blog hero image in landscape orientation (wider than tall, 16:9 ratio). "
            "Take these three Korean double cleansing products and arrange them on a clean light-toned bathroom vanity "
            "or shelf with soft morning light. "
            "Add a small folded white cotton towel nearby and a few tiny water droplets on the surface for freshness. "
            "The products should look exactly like these reference photos — same packaging, labels, and colors. "
            "Fresh, clean, dewy mood. Premium wellness blog photography style. "
            "No text overlays. No watermarks."
        ),
    },
    {
        "name": "double-cleansing-without-oil",
        "output": "/Users/kapi7/satellite-websites/wellness/public/images/double-cleansing-without-oil.jpg",
        "products": [
            f"{PRODUCTS_DIR}/banila-co.png",
            f"{PRODUCTS_DIR}/cosrx-gm.jpg",
        ],
        "prompt": (
            "Create a warm blog hero image in landscape orientation (wider than tall, 16:9 ratio). "
            "Take these two Korean cleansing products and place them on a soft neutral-toned bathroom counter "
            "with warm golden-hour natural light. "
            "Add a soft linen towel nearby and maybe a small ceramic dish. Cozy morning bathroom feel. "
            "The products should look exactly like these reference photos. "
            "Clean minimalist beauty blog photography. No text overlays."
        ),
    },
    {
        "name": "oil-cleansing-oily-skin",
        "output": "/Users/kapi7/satellite-websites/wellness/public/images/oil-cleansing-oily-skin.jpg",
        "products": [
            f"{PRODUCTS_DIR}/anua-oil.jpg",
            f"{PRODUCTS_DIR}/boj-balm.png",
        ],
        "prompt": (
            "Create a fresh blog hero image in landscape orientation (wider than tall, 16:9 ratio). "
            "Take these two Korean oil cleansing products and place them on a cool-toned minimalist surface "
            "(light grey or pale blue-white marble) with clean bright diffused light. "
            "Add a small fresh green leaf as an accent. Minimalist K-beauty editorial style. "
            "The products should look exactly like these reference photos. "
            "Clean, fresh, modern. No text overlays."
        ),
    },
]

for hero in HEROES:
    print(f"\nGenerating: {hero['name']}...")
    
    # Build content: prompt text + product images
    parts = [hero["prompt"]]
    for img_path in hero["products"]:
        img = Image.open(img_path)
        parts.append(img)
    
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
                
                # Resize to 1200x675 (16:9) if needed
                if img.size != (1200, 675):
                    # Crop to 16:9 first if aspect ratio differs
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
                
                img.save(hero["output"], "JPEG", quality=90)
                print(f"  Saved: {hero['output']} (1200x675)")
                saved = True
                break
        
        if not saved:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'text') and part.text:
                    print(f"  No image. Text: {part.text[:200]}")
        
        time.sleep(4)  # Rate limiting
        
    except Exception as e:
        print(f"  ERROR: {e}")

print("\nAll done!")
