#!/usr/bin/env python3
"""Generate wellness hero images v2 — distinct from existing site images."""

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
    "No text, no watermarks, no logos, no words. Professional editorial photography. "
)

HEROES = [
    # 1. Anti-inflammatory meals — NOT overhead salmon. Show colorful Mediterranean-style plating.
    ("anti-inflammatory-meals.jpg",
     BASE + "Side-angle shot of a single beautiful ceramic bowl with a vibrant anti-inflammatory Buddha bowl: purple cabbage, golden turmeric-roasted cauliflower, bright pomegranate seeds, green edamame, orange carrot ribbons, and a drizzle of tahini. Dark moody background with dramatic side lighting. Fine dining restaurant editorial style. Shallow depth of field."),

    # 2. Recovery tools — NOT flat lay. Show them in action context.
    ("recovery-tools.jpg",
     BASE + "Athletic woman using a percussion massage gun on her quadricep while sitting on a gym bench after a workout. A foam roller and water bottle nearby on the floor. Industrial gym setting with warm afternoon light streaming through large windows. Sporty documentary photography style."),

    # 3. Foods sharpen focus — NOT marble flat lay. Show a creative desk setup.
    ("foods-sharpen-focus.jpg",
     BASE + "A modern minimalist desk workspace with a laptop partially visible, and in the foreground a wooden tray with brain-boosting snacks: a small cup of matcha latte, a bowl of fresh blueberries, a piece of dark chocolate, and a handful of almonds. Morning window light, clean and crisp. Productivity lifestyle photography."),

    # 4. Morning meditation — NOT woman by window. Show outdoor dawn scene.
    ("morning-meditation.jpg",
     BASE + "Wide shot of a person sitting in lotus position on a wooden deck overlooking misty mountains at golden sunrise. Shot from behind, silhouetted against a pink-orange dawn sky. Dew on the deck railing. Vast peaceful landscape. Cinematic travel photography feel with warm golden hour lighting."),

    # 5. Cold water therapy — the current one looks good actually, but let's make it more distinct
    ("cold-water-therapy.jpg",
     BASE + "Close-up of hands breaking the surface of crystal-clear ice water in a round cedar cold plunge tub. Ice chunks floating. Frost on the wooden rim. Crisp winter morning light. Shot from directly above looking down. The water is transparent with visible ice. Dramatic contrast between warm wood and cold water."),

    # 6. Protein smoothies — keep the 3 glass concept but different angle
    ("protein-smoothie-recipes.jpg",
     BASE + "Three protein smoothies in mason jars viewed from slightly above on a white concrete countertop: deep purple acai-berry, bright green spinach-banana, and orange mango-carrot. Each has a metal straw. Scattered frozen fruit pieces and a scoop of vanilla protein powder in the foreground. Harsh midday sunlight with strong shadows. Modern clean food blog style."),

    # 7. Weekly meal prep — NOT overhead glass containers. Show the process.
    ("weekly-meal-prep.jpg",
     BASE + "Kitchen scene showing the meal prep process: a person's hands chopping colorful vegetables on a large cutting board, with several already-filled meal prep containers stacked in the background. Fresh herbs, a knife, and a kitchen timer visible. Warm kitchen lighting. Action shot showing hands mid-chop. Documentary cooking photography."),

    # 8. Evening wind-down — keep nightstand but change the mood entirely
    ("evening-wind-down-sleep.jpg",
     BASE + "A cozy reading nook at dusk: a person's feet in thick wool socks resting on a velvet ottoman, with a cup of chamomile tea held in both hands. Soft fairy lights blurred in the background. A chunky knit blanket. Very warm amber tones, extremely cozy hygge atmosphere. Shot at eye level from the sofa perspective."),

    # 9. Warming soups — NOT 3 bowls on wood table. Single dramatic bowl.
    ("warming-soups-gut-health.jpg",
     BASE + "A single rustic clay bowl of bright orange butternut squash soup with a perfect swirl of coconut cream and fresh microgreens on top. Dark charcoal slate surface. Wisps of steam rising dramatically lit from behind. A torn piece of sourdough bread beside it. Moody dramatic food photography with a single spotlight effect."),

    # 10. Breathwork — NOT close-up woman face. Show the practice environment.
    ("breathwork-techniques.jpg",
     BASE + "Abstract close-up of a person's chest and hands in a cross-legged seated position, hands resting on knees in chin mudra. Wearing linen clothing. Soft bokeh light particles floating in the air like dust in sunbeams. Ethereal, almost dreamlike quality. Warm golden backlight creating a rim light effect. Artistic wellness photography."),

    # 11. Brain snacks — NOT snack board on marble. Show portable/office context.
    ("brain-snacks-focus.jpg",
     BASE + "A stylish bento box open on an office desk, packed with brain-boosting snacks: dark chocolate squares, mixed nuts, dried apricots, cheese cubes, and cherry tomatoes. A coffee cup and notebook beside it. Modern office with natural light from a large window. Clean minimal aesthetic. Lifestyle work photography."),

    # 12. Intermittent fasting — the split concept is great, keep but improve
    ("intermittent-fasting-guide.jpg",
     BASE + "A single place setting on a clean wooden table: an empty white plate with a beautiful analog clock placed in the center of the plate, showing 12 o'clock. A glass of sparkling water with lemon beside it. Fork and knife placed neatly. Bright airy Scandinavian kitchen in the background. Clean conceptual food photography."),

    # 13. Body scan meditation — NOT another person lying down. Show abstract body awareness concept.
    ("body-scan-meditation.jpg",
     BASE + "A tranquil bedroom scene at twilight: a neatly made bed with white linen sheets, a single meditation singing bowl on the nightstand, soft blue-purple evening light coming through sheer curtains. A yoga mat unrolled at the foot of the bed. Empty peaceful room. No people. Architectural interior photography with serene calming mood."),

    # 14. Spice blends — the current one is actually great, but make more distinct
    ("anti-inflammatory-spice-blends.jpg",
     BASE + "Five small glass spice jars in a row on a rustic wooden shelf, each filled with a different vibrant colored spice blend: golden turmeric, red cayenne-paprika, brown cinnamon-ginger, green herb blend, and orange curry. Dried whole spices scattered in front: star anise, cinnamon sticks, whole peppercorns. Warm sidelight from a kitchen window. Apothecary pantry aesthetic."),

    # 15. Kimchi — the current one is good but let's make it more dynamic
    ("homemade-kimchi.jpg",
     BASE + "Hands wearing food-safe gloves rubbing bright red gochugaru paste onto a quartered napa cabbage over a large traditional Korean onggi pot. Bowls of prepared ingredients around: sliced scallions, minced garlic, fish sauce, grated ginger. Authentic Korean kitchen setting. Action shot showing the kimjang process. Warm overhead kitchen lighting. Cultural food documentary photography."),
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
