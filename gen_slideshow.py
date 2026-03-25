#!/usr/bin/env python3
import os
from google import genai
from google.genai import types

client = genai.Client(api_key="AIzaSyAHpRI0T1KO5D9CvAUwOFYnVzWhHfvcX-Q")

IMAGES = [
    # Wellness slideshow
    {
        "path": "wellness/public/images/hero-slide-1.jpg",
        "prompt": "A serene outdoor morning scene: a woman doing yoga stretches on a wooden deck overlooking misty green hills at sunrise. Warm golden light, soft focus background, wellness lifestyle photography. Shot from behind at a distance, editorial style. No face visible."
    },
    {
        "path": "wellness/public/images/hero-slide-2.jpg",
        "prompt": "Beautiful overhead shot of a farmers market haul spread on a butcher block: colorful seasonal vegetables, fresh herbs, wild berries in a basket, eggs in a carton, and artisanal sourdough bread. Morning light, editorial food photography, rich warm tones."
    },
    {
        "path": "wellness/public/images/hero-slide-3.jpg",
        "prompt": "Aesthetic bathroom shelf arrangement showing Korean skincare products: glass bottles, a jade roller, cotton pads, and a small vase with dried eucalyptus. Clean minimalist styling, soft natural light from a window, earth tones and sage green accents. No text on products."
    },
    # Cosmetics slideshow
    {
        "path": "cosmetics/public/images/hero-slide-1.jpg",
        "prompt": "Luxurious close-up beauty photography: golden serum drops falling from a glass dropper into a small pool on a reflective rose-gold surface. Soft pink and gold lighting, macro detail showing the viscosity of the serum, beauty editorial style. No people."
    },
    {
        "path": "cosmetics/public/images/hero-slide-2.jpg",
        "prompt": "Elegant vanity table scene from above: an organized collection of premium skincare products in frosted glass, a round mirror, fresh peonies in a small vase, and a silk scrunchie. Soft diffused window light, cream and blush pink color palette, editorial beauty photography. No text on products."
    },
    {
        "path": "cosmetics/public/images/hero-slide-3.jpg",
        "prompt": "Abstract beauty texture: close-up of rich moisturizer cream swirled artfully on a smooth marble surface, showing the silky whipped texture. Soft pink and cream tones, macro photography, clean luxurious feel. No people, no products, just the cream texture."
    },
]

def generate_image(img_info):
    path = os.path.join("/Users/kapi7/satellite-websites", img_info["path"])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        print(f"  SKIP: {img_info['path']}")
        return True
    print(f"  Generating: {img_info['path']}...")
    try:
        response = client.models.generate_images(
            model="imagen-4.0-generate-001",
            prompt=img_info["prompt"],
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="16:9",
                output_mime_type="image/jpeg",
            ),
        )
        if response.generated_images:
            with open(path, "wb") as f:
                f.write(response.generated_images[0].image.image_bytes)
            size_kb = os.path.getsize(path) / 1024
            print(f"  OK: {img_info['path']} ({size_kb:.0f} KB)")
            return True
        else:
            print(f"  FAIL: {img_info['path']}")
            return False
    except Exception as e:
        print(f"  ERROR: {img_info['path']} - {e}")
        return False

if __name__ == "__main__":
    print(f"Generating {len(IMAGES)} slideshow images...")
    ok = sum(1 for img in IMAGES if generate_image(img))
    print(f"\nDone: {ok}/{len(IMAGES)}")
