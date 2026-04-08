#!/usr/bin/env python3
"""Generate professional headshot photos for team members using Gemini."""

import io, os, time
from PIL import Image
from google import genai
from google.genai import types

API_KEY = "AIzaSyC06AlrcQOrsnbWGzP63Tm7VVzZtgWgBBY"
client = genai.Client(api_key=API_KEY)
MODEL = "gemini-2.5-flash-image"

TEAM = [
    # Cosmetics (glow-coded)
    {
        "name": "mina-park",
        "prompt": "Professional headshot portrait of a Korean-American woman in her early 30s. She has shoulder-length black hair, warm brown eyes, and a confident smile. She wears a cream blouse. Clean white studio background. Soft natural lighting. Editorial magazine style. High quality portrait photography. No text.",
        "out": "/Users/kapi7/satellite-websites/cosmetics/public/images/team/mina-park.jpg",
    },
    {
        "name": "sophie-laurent",
        "prompt": "Professional headshot portrait of a French woman in her late 20s with light brown wavy hair past her shoulders, blue-green eyes, light skin, and a natural smile. She wears a simple navy top. Clean white studio background. Soft natural lighting. Editorial magazine style. High quality portrait photography. No text.",
        "out": "/Users/kapi7/satellite-websites/cosmetics/public/images/team/sophie-laurent.jpg",
    },
    {
        "name": "ava-chen",
        "prompt": "Professional headshot portrait of a Chinese-American woman in her mid-20s with long straight dark hair, brown eyes, and a friendly open smile. She wears a soft pink blouse. Clean white studio background. Soft natural lighting. Editorial magazine style. High quality portrait photography. No text.",
        "out": "/Users/kapi7/satellite-websites/cosmetics/public/images/team/ava-chen.jpg",
    },
    {
        "name": "priya-kapoor",
        "prompt": "Professional headshot portrait of an Indian woman in her early 30s with dark brown wavy hair, dark eyes, warm olive skin, and a warm genuine smile. She wears an emerald green top. Clean white studio background. Soft natural lighting. Editorial magazine style. High quality portrait photography. No text.",
        "out": "/Users/kapi7/satellite-websites/cosmetics/public/images/team/priya-kapoor.jpg",
    },
    # Wellness (rooted-glow)
    {
        "name": "elena-voss",
        "prompt": "Professional headshot portrait of a European woman in her mid-30s with honey blonde hair in a loose bun, green eyes, and a calm confident smile. She wears a sage green linen shirt. Clean white studio background. Soft natural lighting. Editorial magazine style. High quality portrait photography. No text.",
        "out": "/Users/kapi7/satellite-websites/wellness/public/images/team/elena-voss.jpg",
    },
    {
        "name": "nadia-okafor",
        "prompt": "Professional headshot portrait of a Nigerian-American woman in her early 30s with short natural coily hair, dark brown eyes, rich brown skin, and a bright warm smile. She wears a white linen blouse. Clean white studio background. Soft natural lighting. Editorial magazine style. High quality portrait photography. No text.",
        "out": "/Users/kapi7/satellite-websites/wellness/public/images/team/nadia-okafor.jpg",
    },
    {
        "name": "james-reeves",
        "prompt": "Professional headshot portrait of a fit Caucasian man in his early 30s with short brown hair, blue eyes, light stubble, and a friendly approachable smile. He wears a dark navy henley shirt. Clean white studio background. Soft natural lighting. Editorial magazine style. High quality portrait photography. No text.",
        "out": "/Users/kapi7/satellite-websites/wellness/public/images/team/james-reeves.jpg",
    },
    {
        "name": "yuna-kim",
        "prompt": "Professional headshot portrait of a Korean woman in her late 20s with long straight black hair, brown eyes, clear glowing skin, and a gentle smile. She wears a soft lavender blouse. Clean white studio background. Soft natural lighting. Editorial magazine style. High quality portrait photography. No text.",
        "out": "/Users/kapi7/satellite-websites/wellness/public/images/team/yuna-kim.jpg",
    },
    {
        "name": "tara-benson",
        "prompt": "Professional headshot portrait of a Caucasian woman in her late 30s with auburn red hair past her shoulders, hazel eyes, light freckles, and a thoughtful warm smile. She wears an earth-tone linen top. Clean white studio background. Soft natural lighting. Editorial magazine style. High quality portrait photography. No text.",
        "out": "/Users/kapi7/satellite-websites/wellness/public/images/team/tara-benson.jpg",
    },
    # Build-coded
    {
        "name": "marcus-webb",
        "prompt": "Professional headshot portrait of a Caucasian man in his late 30s with short dark brown hair, brown eyes, a short trimmed beard, and a confident friendly smile. He wears a dark charcoal flannel shirt. Clean white studio background. Soft natural lighting. Editorial magazine style. High quality portrait photography. No text.",
        "out": "/Users/kapi7/satellite-websites/build-coded/public/images/team/marcus-webb.jpg",
    },
    {
        "name": "danny-herrera",
        "prompt": "Professional headshot portrait of a Latino man in his late 20s with short black hair, brown eyes, clean-shaven, and an enthusiastic genuine smile. He wears a steel blue button-up shirt. Clean white studio background. Soft natural lighting. Editorial magazine style. High quality portrait photography. No text.",
        "out": "/Users/kapi7/satellite-websites/build-coded/public/images/team/danny-herrera.jpg",
    },
]

for i, person in enumerate(TEAM):
    if os.path.exists(person["out"]):
        print(f"[{i+1}/{len(TEAM)}] {person['name']} — already exists, skipping")
        continue

    print(f"[{i+1}/{len(TEAM)}] Generating {person['name']}...")
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=[person["prompt"]],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )

        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                result = Image.open(io.BytesIO(part.inline_data.data))
                result = result.convert("RGB")
                # Crop to square from center
                size = min(result.width, result.height)
                left = (result.width - size) // 2
                top = (result.height - size) // 2
                result = result.crop((left, top, left + size, top + size))
                result = result.resize((400, 400), Image.LANCZOS)
                result.save(person["out"], "JPEG", quality=92)
                print(f"  OK: {person['out'].split('/')[-1]}")
                break
        else:
            print(f"  WARN: No image returned for {person['name']}")

    except Exception as e:
        print(f"  ERROR: {str(e)[:100]}")

    if i < len(TEAM) - 1:
        time.sleep(5)

print("\nDone!")
