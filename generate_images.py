#!/usr/bin/env python3
"""Generate hero images for satellite websites using Gemini Imagen 4."""

import os
import base64
from google import genai
from google.genai import types

client = genai.Client(api_key="AIzaSyAHpRI0T1KO5D9CvAUwOFYnVzWhHfvcX-Q")

IMAGES = [
    # Wellness site
    {
        "path": "wellness/public/images/ancestral-eating-hero.jpg",
        "prompt": "Overhead flat-lay food photography of a rustic wooden table spread with whole foods: a perfectly grilled ribeye steak, soft-boiled eggs, fresh seasonal vegetables, a small bowl of bone broth, wild berries, and a sprig of rosemary. Warm natural lighting from a window, soft shadows, earth tones, editorial food magazine style. No text, no people, no hands."
    },
    {
        "path": "wellness/public/images/cooking-oils.jpg",
        "prompt": "Elegant still life photography of artisanal cooking oils and fats arranged on a marble countertop: a dark glass bottle of extra virgin olive oil, a small jar of golden ghee, a ceramic dish of white beef tallow, and a stick of grass-fed butter on parchment. Soft diffused natural light, warm tones, clean minimalist composition, editorial kitchen photography. No text, no people."
    },
    {
        "path": "wellness/public/images/protein-breakfast.jpg",
        "prompt": "Overhead food photography of a cast iron skillet containing a hearty breakfast: two sunny-side-up eggs with runny yolks, crispy bacon strips, and sauteed cherry tomatoes with fresh herbs. Rustic wooden table background, morning sunlight streaming in, steam visible, warm earthy color palette. Editorial food styling. No text, no people, no hands."
    },
    {
        "path": "wellness/public/images/double-cleansing.jpg",
        "prompt": "Minimalist beauty product photography on a clean marble bathroom shelf: a frosted glass jar of cleansing balm next to a soft pink tube of gentle foam cleanser, with a small white ceramic dish and a cotton pad. Soft diffused bathroom lighting, clean aesthetic, Korean beauty inspired styling, pastel and neutral tones. No text, no people."
    },
    {
        "path": "wellness/public/images/og-default.jpg",
        "prompt": "Abstract nature-inspired flat lay: fresh green eucalyptus branches, a smooth river stone, dried lavender sprigs, and a small glass bottle of oil arranged on a cream linen background. Overhead shot, soft natural light, earthy sage and cream color palette, wellness magazine aesthetic. No text, no people."
    },
    # Cosmetics site
    {
        "path": "cosmetics/public/images/korean-routine-hero.jpg",
        "prompt": "Luxurious flat-lay beauty photography of an organized Korean skincare routine: elegant glass bottles and jars of serums, essences, and creams arranged in a deliberate sequence on a white marble vanity. Soft rose gold accents, morning light, dewdrops on the bottles, editorial beauty magazine composition. No text, no people, no hands."
    },
    {
        "path": "cosmetics/public/images/niacinamide-vitamin-c.jpg",
        "prompt": "Clean minimalist beauty product photography: two amber glass dropper bottles of serum placed side by side on a neutral beige surface, with a few drops of golden and clear liquid between them. Soft directional light creating gentle shadows, beauty editorial aesthetic, warm neutral tones. No text, no people, no hands, no labels on bottles."
    },
    {
        "path": "cosmetics/public/images/snail-mucin-products.jpg",
        "prompt": "Editorial beauty flat-lay of several Korean skincare products arranged artfully on a clean white surface with soft shadows: clear essence bottles, a white cream jar, and product tubes in minimalist packaging with subtle Korean design elements. Soft even lighting, clean luxurious feel, dewy moisture droplets scattered. No text, no people, no hands."
    },
    {
        "path": "cosmetics/public/images/og-default.jpg",
        "prompt": "Abstract beauty-inspired composition: soft pink rose petals, a smooth ceramic dish with golden serum drops, a jade roller, and a sprig of cherry blossom on a cream silk fabric background. Overhead shot, soft diffused light, rose and cream color palette, luxury beauty magazine aesthetic. No text, no people."
    },
]

def generate_image(img_info):
    path = os.path.join("/Users/kapi7/satellite-websites", img_info["path"])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        print(f"  SKIP (exists): {img_info['path']}")
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
            img = response.generated_images[0]
            with open(path, "wb") as f:
                f.write(img.image.image_bytes)
            size_kb = os.path.getsize(path) / 1024
            print(f"  OK: {img_info['path']} ({size_kb:.0f} KB)")
            return True
        else:
            print(f"  FAIL (no images returned): {img_info['path']}")
            return False
    except Exception as e:
        print(f"  ERROR: {img_info['path']} — {e}")
        return False

if __name__ == "__main__":
    print(f"Generating {len(IMAGES)} images with Imagen 4.0...")
    success = 0
    for img in IMAGES:
        if generate_image(img):
            success += 1
    print(f"\nDone: {success}/{len(IMAGES)} images generated.")
