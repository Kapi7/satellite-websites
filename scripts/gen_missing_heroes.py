#!/usr/bin/env python3
"""Regenerate low-quality hero images for build-coded using Imagen 4.0."""
import os, sys, io, time, json, base64, urllib.request, urllib.error
from pathlib import Path

API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL = "imagen-4.0-fast-generate-001"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "build-coded" / "public" / "images"

HEROES = [
    {
        "slug": "change-a-tire",
        "prompt": "Realistic photograph of a car being lifted by a jack on a suburban driveway, with a spare tire leaning against the bumper and a lug wrench on the ground. Daytime overcast light. Clean DIY instructional photography. Blog hero image style, 16:9 landscape, no text.",
    },
    {
        "slug": "chicken-coop-plans",
        "prompt": "Beautiful photograph of a well-built wooden backyard chicken coop with a fenced run, painted classic barn red with white trim. A few chickens pecking inside the run. Green grass, warm afternoon sunlight. Farmhouse aesthetic. Blog hero image style, 16:9 landscape, no text.",
    },
    {
        "slug": "fix-running-toilet",
        "prompt": "Close-up photograph inside a toilet tank showing the flapper valve, fill valve, and overflow tube. Clean white bathroom. An adjustable wrench and a replacement flapper kit placed on the tank lid. Bright bathroom lighting. Instructional plumbing photography. Blog hero image style, 16:9 landscape, no text.",
    },
    {
        "slug": "french-drain-installation",
        "prompt": "Photograph of a trench dug alongside a house foundation, showing gravel bed and perforated PVC drain pipe inside the trench. Landscape fabric lining visible. A shovel leaning against the trench wall. Backyard setting with natural daylight. Home improvement photography. Blog hero image style, 16:9 landscape, no text.",
    },
    {
        "slug": "get-rid-ants-naturally",
        "prompt": "Styled flat-lay photograph on a bright kitchen counter showing natural ant repellent items: a small glass bowl of diatomaceous earth, white vinegar spray bottle, cinnamon sticks, peppermint essential oil bottle, and sliced lemons. Bright natural kitchen light from a window. Clean editorial home photography. Blog hero image style, 16:9 landscape, no text.",
    },
    {
        "slug": "install-gutter-guards",
        "prompt": "Photograph of gloved hands installing aluminum mesh gutter guards onto a roof gutter. View from a ladder showing the roofline, fascia board, and shingles. Blue sky background. Suburban home exterior. Home improvement photography. Blog hero image style, 16:9 landscape, no text.",
    },
    {
        "slug": "patio-ideas-budget",
        "prompt": "Beautiful photograph of an inviting budget-friendly backyard patio with concrete pavers, warm string lights overhead, a small fire pit in the center, and simple outdoor furniture with cushions. Potted plants and flowers around the edges. Warm golden hour evening light. Aspirational outdoor living photography. Blog hero image style, 16:9 landscape, no text.",
    },
    {
        "slug": "raised-garden-bed-diy",
        "prompt": "Photograph of a freshly built cedar raised garden bed in a sunny backyard, filled with rich dark soil and a few seedlings just planted. Hand trowel and gardening gloves resting on the wooden edge. Natural afternoon sunlight, green lawn background. Garden photography. Blog hero image style, 16:9 landscape, no text.",
    },
    {
        "slug": "replace-circuit-breaker",
        "prompt": "Photograph of an open residential electrical breaker panel with rows of circuit breakers visible. A multimeter and insulated screwdriver placed on a small shelf nearby. Well-lit garage or utility room. Safety-focused home electrical photography. Blog hero image style, 16:9 landscape, no text.",
    },
    {
        "slug": "water-heater-maintenance",
        "prompt": "Photograph of a standard residential tank water heater in a clean utility room. A garden hose connected to the drain valve at the bottom. An adjustable wrench and a small bucket placed nearby. Clean well-organized utility space with good lighting. Home maintenance photography. Blog hero image style, 16:9 landscape, no text.",
    },
    {
        "slug": "og-default",
        "prompt": "Professional photograph of a well-organized workshop pegboard wall with neatly arranged hand tools: hammers, tape measures, screwdrivers, pliers, wrenches, and levels. Warm wood workbench visible below. Natural window light with warm workshop ambiance. Maker lifestyle photography. Blog hero image style, 16:9 landscape, no text.",
    },
]


def generate_image(hero):
    output_path = OUTPUT_DIR / f"{hero['slug']}.jpg"

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:predict?key={API_KEY}"
    payload = json.dumps({
        "instances": [{"prompt": hero["prompt"]}],
        "parameters": {
            "sampleCount": 1,
            "aspectRatio": "16:9",
            "outputOptions": {"mimeType": "image/jpeg"},
        }
    })

    try:
        req = urllib.request.Request(
            url,
            data=payload.encode(),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())

        if "predictions" in result and len(result["predictions"]) > 0:
            img_b64 = result["predictions"][0]["bytesBase64Encoded"]
            img_bytes = base64.b64decode(img_b64)
            output_path.write_bytes(img_bytes)
            print(f"  OK: {hero['slug']}.jpg ({len(img_bytes) // 1024}KB)")
            return True
        else:
            print(f"  No image returned for {hero['slug']}: {json.dumps(result)[:200]}")
            return False
    except Exception as e:
        print(f"  FAIL {hero['slug']}: {e}")
        return False


def main():
    if not API_KEY:
        print("Set GEMINI_API_KEY env var first")
        sys.exit(1)

    print(f"Regenerating {len(HEROES)} hero images with Imagen 4.0")
    print(f"Output: {OUTPUT_DIR}\n")

    success = 0
    for i, hero in enumerate(HEROES, 1):
        print(f"[{i}/{len(HEROES)}] {hero['slug']}")
        if generate_image(hero):
            success += 1
        time.sleep(3)
    print(f"\nDone. {success}/{len(HEROES)} generated.")


if __name__ == "__main__":
    main()
