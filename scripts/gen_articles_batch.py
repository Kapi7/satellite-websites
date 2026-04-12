#!/usr/bin/env python3
"""Generate a batch of articles from a JSON spec using Gemini 2.5 Flash + Imagen 4.0."""
import os, sys, json, time, base64, urllib.request, urllib.error
from pathlib import Path
from datetime import date, timedelta

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

API_KEY = os.environ.get("GEMINI_API_KEY", "")
if not API_KEY:
    print("ERROR: GEMINI_API_KEY not set"); sys.exit(1)

BASE = Path(__file__).resolve().parent.parent
TEXT_MODEL = "gemini-2.5-flash"
IMAGEN_MODEL = "imagen-4.0-fast-generate-001"


def gemini_generate(prompt: str, max_tokens: int = 10000) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{TEXT_MODEL}:generateContent?key={API_KEY}"
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.7},
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except urllib.error.HTTPError as e:
            wait = min(15 * (2 ** attempt), 300)
            if e.code in (429, 403):
                print(f"    Rate limited, waiting {wait}s...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("Gemini API failed after retries")


def imagen_generate(prompt: str, output_path: Path) -> bool:
    if output_path.exists() and output_path.stat().st_size > 10_000:
        print(f"    Image exists: {output_path.name}")
        return True
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{IMAGEN_MODEL}:predict?key={API_KEY}"
    body = json.dumps({
        "instances": [{"prompt": prompt}],
        "parameters": {"sampleCount": 1, "aspectRatio": "16:9"},
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.loads(resp.read())
            img_b64 = data["predictions"][0]["bytesBase64Encoded"]
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(base64.b64decode(img_b64))
            print(f"    Image: {output_path.name} ({output_path.stat().st_size // 1024}KB)")
            return True
        except urllib.error.HTTPError as e:
            if e.code in (429, 403):
                wait = 15 * (2 ** attempt)
                print(f"    Image rate limited, waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"    Image failed: {e}")
                return False
        except Exception as e:
            print(f"    Image failed: {e}")
            return False
    return False


def generate_one(spec: dict, pub_date: str):
    site = spec["site"]
    slug = spec["slug"]
    content_dir = BASE / site / "src" / "content" / "blog" / "en"
    image_dir = BASE / site / "public" / "images"
    mdx_path = content_dir / f"{slug}.mdx"

    if mdx_path.exists():
        print(f"  SKIP: {slug}.mdx already exists")
        return False

    print(f"\n  [{spec['slug']}] ({site})")

    # Hero image
    imagen_generate(spec["image_prompt"], image_dir / f"{slug}.jpg")
    time.sleep(2)

    # Article content
    print(f"    Generating content...")
    body = gemini_generate(spec["prompt"])

    # Strip accidental frontmatter/fences
    body = body.strip()
    if body.startswith("---"):
        parts = body.split("---", 2)
        if len(parts) >= 3:
            body = parts[2].strip()
    if body.startswith("```"):
        body = "\n".join(body.split("\n")[1:])
    if body.endswith("```"):
        body = body[:-3].rstrip()

    # Build frontmatter
    fm = ["---"]
    fm.append(f'title: "{spec["title"]}"')
    fm.append(f'description: "{spec["description"]}"')
    fm.append(f"date: {pub_date}")
    fm.append(f"category: {spec['category']}")
    fm.append(f"type: {spec.get('type', 'guide')}")
    fm.append(f"tags: {json.dumps(spec['tags'])}")
    fm.append(f"image: /images/{slug}.jpg")
    fm.append(f'imageAlt: "{spec.get("imageAlt", spec["title"])}"')
    fm.append("draft: false")
    fm.append("locale: en")
    fm.append(f'author: "{spec["author"]}"')
    if "difficulty" in spec:
        fm.append(f"difficulty: {spec['difficulty']}")
    fm.append("---")

    content = "\n".join(fm) + "\n\n" + body + "\n"
    mdx_path.write_text(content)
    print(f"    Saved: {slug}.mdx ({len(content)} chars)")
    return True


def main():
    spec_file = sys.argv[1] if len(sys.argv) > 1 else None
    if not spec_file:
        print("Usage: python3 gen_articles_batch.py <spec.json>")
        sys.exit(1)

    specs = json.loads(Path(spec_file).read_text())
    today = date.today()
    generated = 0

    for i, spec in enumerate(specs):
        pub_date = (today + timedelta(days=i + 1)).isoformat()
        if generate_one(spec, pub_date):
            generated += 1
        time.sleep(3)

    print(f"\nDone! Generated {generated} articles.")


if __name__ == "__main__":
    main()
