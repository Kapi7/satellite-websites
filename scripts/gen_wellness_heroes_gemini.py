#!/usr/bin/env python3
"""Generate wellness hero images using Gemini 2.5 Flash Image."""

import os, io, time
from PIL import Image
from google import genai
from google.genai import types

API_KEY = os.environ.get("GEMINI_API_KEY", "")
client = genai.Client(api_key=API_KEY)
MODEL = "gemini-2.5-flash-image"
OUT_DIR = "/Users/kapi7/satellite-websites/wellness/public/images"

BASE = (
    "Create a stunning photorealistic blog hero image in landscape orientation (16:9 ratio, wider than tall). "
    "No text, no watermarks, no logos. Professional editorial food/wellness photography. "
)

HEROES = [
    ("anti-inflammatory-meals.jpg",
     BASE + "Overhead shot of a beautiful spread of colorful anti-inflammatory foods: grilled salmon fillet, turmeric golden rice, roasted sweet potatoes, fresh berries, leafy greens, and avocado halves on a rustic wooden table. Warm natural light from a window. Earthy ceramic plates and linen napkin."),

    ("recovery-tools.jpg",
     BASE + "Flat lay of muscle recovery tools on a light wood floor: foam roller, massage gun, resistance bands, ice pack, and a yoga mat partially rolled. Athletic minimalist aesthetic. Bright clean studio lighting with subtle shadows."),

    ("foods-sharpen-focus.jpg",
     BASE + "Beautiful arrangement of brain-boosting foods on a clean marble surface: blueberries in a small bowl, dark chocolate pieces, walnuts, avocado half, green tea in a ceramic cup, and salmon sashimi. Bright natural daylight, editorial food photography style."),

    ("morning-meditation.jpg",
     BASE + "Serene woman sitting cross-legged on a cushion by a large window at sunrise, practicing meditation. Soft golden morning light streaming in. Minimalist room with a small plant and candle. Peaceful calm atmosphere. Side profile view."),

    ("cold-water-therapy.jpg",
     BASE + "Person stepping into a cold plunge tub or ice bath outdoors, misty morning setting with trees in background. Cool blue tones, visible breath in cold air. Fresh invigorating atmosphere. Clean modern wooden tub with ice floating on surface."),

    ("protein-smoothie-recipes.jpg",
     BASE + "Three colorful protein smoothies in tall glasses on a kitchen counter: one green (spinach), one pink-purple (berry), one golden (mango-turmeric). Fresh fruits and protein powder scoop arranged around them. Bright morning kitchen lighting."),

    ("weekly-meal-prep.jpg",
     BASE + "Overhead shot of a meal prep spread: glass containers filled with colorful portioned meals — grilled chicken, roasted vegetables, quinoa, leafy salads. Cutting board with fresh herbs. Clean organized modern kitchen counter. Bright natural light."),

    ("evening-wind-down-sleep.jpg",
     BASE + "Cozy bedroom nightstand scene: a warm cup of chamomile tea, a small lavender candle burning, a good book, soft eye mask, and a diffuser with warm light. Soft dim warm lighting. Relaxing sleep hygiene aesthetic. Muted earth tones."),

    ("warming-soups-gut-health.jpg",
     BASE + "Three beautiful bowls of healing soups on a rustic table: bone broth with vegetables, golden turmeric soup, and miso soup with tofu and seaweed. Steam rising. Crusty bread on the side. Warm cozy autumn lighting."),

    ("breathwork-techniques.jpg",
     BASE + "Close-up of a person with closed eyes practicing deep breathing exercises outdoors in a peaceful garden or park. Soft dappled sunlight through leaves. Calm serene expression. Shallow depth of field with bokeh greenery background."),

    ("brain-snacks-focus.jpg",
     BASE + "Aesthetically arranged brain-boosting snack board on marble: trail mix with nuts and dark chocolate, apple slices with almond butter, edamame, cheese cubes, and matcha energy bites. Clean modern snack platter styling. Bright overhead lighting."),

    ("intermittent-fasting-guide.jpg",
     BASE + "Split composition: one side shows an empty clean plate with just a glass of water and a clock showing morning time; the other side shows a beautiful colorful healthy meal. Clean minimalist aesthetic representing eating window vs fasting. Bright studio lighting."),

    ("body-scan-meditation.jpg",
     BASE + "Person lying in savasana pose on a yoga mat in a peaceful room with soft natural light. Plants nearby, candle burning. Overhead slightly angled view. Calm relaxing atmosphere with warm muted tones. Mindfulness and body awareness aesthetic."),

    ("anti-inflammatory-spice-blends.jpg",
     BASE + "Beautiful flat lay of anti-inflammatory spices in small ceramic bowls and wooden spoons: turmeric powder (bright yellow), cinnamon sticks, ginger root, black pepper, cardamom pods, and cloves. Dark moody background with warm directional light. Spice market editorial feel."),

    ("homemade-kimchi.jpg",
     BASE + "Traditional Korean kimchi making scene: fresh napa cabbage, red pepper flakes (gochugaru), garlic, ginger, glass fermentation jars with bright red kimchi visible inside. Rustic wooden cutting board. Warm kitchen lighting. Authentic homemade fermentation aesthetic."),
]

success = 0
for filename, prompt in HEROES:
    output = os.path.join(OUT_DIR, filename)
    print(f"\nGenerating: {filename}...")
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )
        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                img = Image.open(io.BytesIO(part.inline_data.data))
                img = img.convert("RGB")
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
                success += 1
                break
        else:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'text') and part.text:
                    print(f"  No image. Text: {part.text[:150]}")
    except Exception as e:
        print(f"  ERROR: {str(e)[:200]}")
    time.sleep(5)

print(f"\n=== Done: {success}/15 images generated ===")
