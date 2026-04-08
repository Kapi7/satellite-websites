#!/usr/bin/env python3
"""Generate missing hero images for build-coded using Gemini image generation."""
import os, io, time
from PIL import Image
from google import genai
from google.genai import types

API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyC06AlrcQOrsnbWGzP63Tm7VVzZtgWgBBY")
MODEL = "gemini-2.5-flash-image"
client = genai.Client(api_key=API_KEY)

OUT_DIR = "/Users/kapi7/satellite-websites/build-coded/public/images"

HEROES = [
    {
        "file": "change-a-tire.jpg",
        "prompt": "Professional DIY blog hero photo, landscape 16:9 ratio. A car jack lifting a vehicle with a spare tire leaning against the car on a suburban driveway. Lug wrench and jack handle visible. Daytime, slightly overcast natural light. Clean, instructional photography style. No text, no watermarks."
    },
    {
        "file": "chicken-coop-plans.jpg",
        "prompt": "Professional DIY blog hero photo, landscape 16:9 ratio. A beautifully built wooden backyard chicken coop with a small fenced run, painted in classic barn red with white trim. A few chickens visible in the run. Green grass, warm afternoon sunlight. Farmhouse aesthetic. No text, no watermarks."
    },
    {
        "file": "fix-running-toilet.jpg",
        "prompt": "Professional DIY blog hero photo, landscape 16:9 ratio. Close-up of a toilet tank interior showing the flapper valve, fill valve, and flush mechanism. Clean white bathroom, bright overhead lighting. Tools (adjustable wrench, replacement flapper) neatly placed beside the tank. Instructional plumbing photography style. No text, no watermarks."
    },
    {
        "file": "french-drain-installation.jpg",
        "prompt": "Professional DIY blog hero photo, landscape 16:9 ratio. A trench dug alongside a house foundation with gravel and perforated drain pipe visible. Landscape fabric lining the trench. Shovel leaning against the trench wall. Backyard setting, natural daylight. Clean home improvement photography. No text, no watermarks."
    },
    {
        "file": "get-rid-ants-naturally.jpg",
        "prompt": "Professional DIY blog hero photo, landscape 16:9 ratio. A clean kitchen counter with natural ant deterrent items arranged neatly: a small bowl of diatomaceous earth, white vinegar spray bottle, cinnamon sticks, peppermint essential oil bottle, and lemon slices. Bright natural kitchen light from a window. Clean, editorial home photography. No text, no watermarks."
    },
    {
        "file": "install-gutter-guards.jpg",
        "prompt": "Professional DIY blog hero photo, landscape 16:9 ratio. Close-up view of a person's gloved hands installing mesh gutter guards on a roof gutter. Aluminum ladder visible. Suburban home exterior with shingles and fascia board. Blue sky, natural daylight. Home improvement photography style. No text, no watermarks."
    },
    {
        "file": "patio-ideas-budget.jpg",
        "prompt": "Professional DIY blog hero photo, landscape 16:9 ratio. A beautiful budget-friendly backyard patio with concrete pavers, string lights overhead, a small fire pit area, and simple outdoor furniture with cushions. Potted plants and flowers around the edges. Warm golden hour evening light. Aspirational but achievable home design photography. No text, no watermarks."
    },
    {
        "file": "raised-garden-bed-diy.jpg",
        "prompt": "Professional DIY blog hero photo, landscape 16:9 ratio. A freshly built cedar raised garden bed in a sunny backyard, filled with rich dark soil. A few seedlings just planted. Hand tools (trowel, gloves) resting on the edge. Natural afternoon sunlight, green lawn background. Garden and woodworking photography style. No text, no watermarks."
    },
    {
        "file": "replace-circuit-breaker.jpg",
        "prompt": "Professional DIY blog hero photo, landscape 16:9 ratio. An open residential electrical panel (breaker box) with circuit breakers clearly visible. A multimeter and insulated screwdriver placed nearby on a workbench. Well-lit garage or utility room setting. Clean, safety-focused home electrical photography. No text, no watermarks."
    },
    {
        "file": "water-heater-maintenance.jpg",
        "prompt": "Professional DIY blog hero photo, landscape 16:9 ratio. A standard residential tank water heater in a utility room or garage. Nearby: a garden hose attached to the drain valve, adjustable wrench, and a bucket. Clean well-organized utility space with good lighting. Home maintenance photography style. No text, no watermarks."
    },
    {
        "file": "og-default.jpg",
        "prompt": "Professional blog hero photo, landscape 16:9 ratio. A well-organized workshop workbench with neatly arranged hand tools (hammer, tape measure, screwdrivers, pliers) on a pegboard wall. Warm wood tones, clean workshop aesthetic. Natural window light with warm workshop ambiance. Generic DIY and maker lifestyle photography. No text, no watermarks."
    },
]

def generate_hero(hero):
    out_path = os.path.join(OUT_DIR, hero["file"])
    if os.path.exists(out_path):
        print(f"  SKIP (exists): {hero['file']}")
        return True

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=hero["prompt"],
            config=types.GenerateContentConfig(
                response_modalities=["image", "text"],
            ),
        )

        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                img = Image.open(io.BytesIO(part.inline_data.data))
                img = img.convert("RGB")
                # Resize to 1200x675 (16:9)
                img = img.resize((1200, 675), Image.LANCZOS)
                img.save(out_path, "JPEG", quality=85, optimize=True)
                print(f"  OK: {hero['file']}")
                return True

        print(f"  FAIL (no image in response): {hero['file']}")
        return False
    except Exception as e:
        print(f"  ERROR: {hero['file']} - {e}")
        return False

if __name__ == "__main__":
    total = len(HEROES)
    for i, hero in enumerate(HEROES, 1):
        print(f"[{i}/{total}] Generating {hero['file']}...")
        success = generate_hero(hero)
        if not success:
            time.sleep(5)
            print(f"  Retrying...")
            generate_hero(hero)
        if i < total:
            time.sleep(2)
    print("\nDone!")
