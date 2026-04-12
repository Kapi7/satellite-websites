#!/usr/bin/env python3
"""Generate comparison (vs) articles for all 3 satellite sites using Gemini 2.5 Flash."""
import os, sys, json, time, random, base64, urllib.request, urllib.error
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
CONFIG = json.loads((Path(__file__).resolve().parent / "comparisons.json").read_text())

IMAGEN_MODEL = "imagen-4.0-fast-generate-001"
TEXT_MODEL = "gemini-2.5-flash"


def gemini_generate(prompt: str, max_tokens: int = 8000) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{TEXT_MODEL}:generateContent?key={API_KEY}"
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.7},
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    return data["candidates"][0]["content"]["parts"][0]["text"]


def imagen_generate(prompt: str, output_path: Path) -> bool:
    if output_path.exists() and output_path.stat().st_size > 10_000:
        print(f"  Image exists: {output_path.name}")
        return True
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{IMAGEN_MODEL}:predict?key={API_KEY}"
    body = json.dumps({
        "instances": [{"prompt": prompt}],
        "parameters": {"sampleCount": 1, "aspectRatio": "16:9"},
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read())
        img_b64 = data["predictions"][0]["bytesBase64Encoded"]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(base64.b64decode(img_b64))
        print(f"  Image saved: {output_path.name} ({output_path.stat().st_size // 1024}KB)")
        return True
    except Exception as e:
        print(f"  Image failed: {e}")
        return False


SYSTEM_PROMPT = """You are an expert content writer for {site_name} ({site_url}).
Write a detailed, engaging comparison article in MDX format. The article compares {a} vs {b}.

RULES:
- Write ONLY the article body (NO frontmatter — that's handled separately)
- Start with an engaging intro paragraph (no heading)
- Use ## for major sections, ### for subsections
- Include a comparison table using markdown table syntax with | headers |
- Write 1500-2500 words
- Include internal links using relative paths like [anchor text](/slug-here) — make up 2-3 plausible internal links that fit the site's niche
- Use a conversational, authoritative tone — like an expert friend explaining the difference
- Include a "## The Verdict" or "## Our Verdict" section at the end
- Include a "## Can You Use/Have Both?" section where relevant
- NO affiliate links, NO external URLs
- NO frontmatter, NO import statements
- Structure: Intro → What Is A → What Is B → Head-to-Head Comparison Table → Key Differences Detailed → Who Should Choose A → Who Should Choose B → Can You Use Both → Verdict
- For the comparison table, include 6-8 factors relevant to the comparison
- End with a "**Related reading:**" line linking to 1-2 plausible related articles on the site
"""


def generate_article(site: str, topic: dict, pub_date: str, author: str) -> str:
    cfg = CONFIG[site]
    prompt = SYSTEM_PROMPT.format(
        site_name=cfg["site_name"],
        site_url=cfg["site_url"],
        a=topic["a"],
        b=topic["b"],
    )
    prompt += f"\n\nTitle: {topic['title']}\nCategory: {topic['category']}\nTags: {', '.join(topic['tags'])}\n\nWrite the article body now."

    print(f"  Generating article content...")
    body = gemini_generate(prompt)

    # Strip any accidental frontmatter
    if body.strip().startswith("---"):
        parts = body.strip().split("---", 2)
        if len(parts) >= 3:
            body = parts[2].strip()

    # Strip any accidental ```mdx fences
    body = body.strip()
    if body.startswith("```"):
        lines = body.split("\n")
        body = "\n".join(lines[1:])
    if body.endswith("```"):
        body = body[:-3].rstrip()

    # Build frontmatter
    fm_lines = [
        "---",
        f'title: "{topic["title"]}"',
        f'description: "A detailed comparison of {topic["a"]} and {topic["b"]}. Learn the key differences, pros and cons, and which one is right for you."',
        f"date: {pub_date}",
        f"category: {topic['category']}",
        "type: guide",
        f"tags: {json.dumps(topic['tags'])}",
        f"image: /images/{topic['slug']}.jpg",
        f'imageAlt: "Side-by-side comparison of {topic["a"]} and {topic["b"]}"',
        "draft: true",
        "locale: en",
        f'author: "{author}"',
    ]
    if "difficulty" in topic:
        fm_lines.append(f"difficulty: {topic['difficulty']}")
    fm_lines.append("---")

    return "\n".join(fm_lines) + "\n\n" + body + "\n"


def main():
    dry_run = "--dry-run" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    site_filter = args[0] if args else None

    today = date.today()
    generated = 0

    for site, cfg in CONFIG.items():
        if site_filter and site != site_filter:
            continue

        print(f"\n{'='*60}")
        print(f"Site: {cfg['site_name']} ({site})")
        print(f"{'='*60}")

        content_dir = BASE / site / "src" / "content" / "blog" / "en"
        image_dir = BASE / site / "public" / "images"

        if not content_dir.exists():
            # cosmetics uses different dir name
            if site == "cosmetics":
                content_dir = BASE / "cosmetics" / "src" / "content" / "blog" / "en"
            if not content_dir.exists():
                print(f"  Content dir not found: {content_dir}")
                continue

        for i, topic in enumerate(cfg["topics"]):
            slug = topic["slug"]
            mdx_path = content_dir / f"{slug}.mdx"

            if mdx_path.exists():
                print(f"\n  SKIP: {slug}.mdx already exists")
                continue

            print(f"\n  [{i+1}/{len(cfg['topics'])}] {slug}")

            # Stagger publish dates (1 day apart, starting tomorrow)
            pub_date = (today + timedelta(days=i + 1)).isoformat()
            author = cfg["authors"][i % len(cfg["authors"])]

            if dry_run:
                print(f"  DRY RUN: would generate {slug}.mdx (date: {pub_date}, author: {author})")
                continue

            # Generate hero image
            imagen_generate(topic["image_prompt"], image_dir / f"{slug}.jpg")
            time.sleep(2)

            # Generate article content
            content = generate_article(site, topic, pub_date, author)
            mdx_path.write_text(content)
            print(f"  Saved: {mdx_path.name} ({len(content)} chars)")
            generated += 1

            time.sleep(3)  # Rate limit

    print(f"\n{'='*60}")
    print(f"Done! Generated {generated} comparison articles.")
    if generated > 0:
        print("Articles saved as draft: true — publish by changing to draft: false")


if __name__ == "__main__":
    main()
