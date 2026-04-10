#!/usr/bin/env python3
"""
Translate satellite site content to 6 languages using Google Gemini API.
Usage: python3 scripts/translate-content.py [--site cosmetics|wellness] [--lang es|de|el|ru|it|ar] [--ui-only] [--articles-only]
"""

import json
import os
import re
import sys
import time
import argparse
from pathlib import Path

# Gemini API
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"

LOCALES = ["es", "de", "el", "ru", "it", "ar", "fr", "nl", "pt"]
BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_FILE = BASE_DIR / "scripts" / "translation-status.json"

# Per-language tone/style instructions
LANG_INSTRUCTIONS = {
    "es": """Translate to conversational Latin American Spanish.
- Use "tú" form, not "usted"
- Use colloquial phrasing that sounds natural to a Mexican or Colombian reader
- Skincare terms: many stay in English (serum, primer, highlighter) — only translate if a widely-used Spanish word exists
- Sound like a knowledgeable friend chatting about skincare, NOT a textbook""",

    "de": """Translate to modern casual German.
- Use "du" form, not "Sie"
- Avoid bureaucratic or stiff phrasing
- Keep a warm, approachable tone — like a beauty blogger, not a dermatology textbook
- Skincare terms: keep English terms where German readers would naturally use them (Serum, Moisturizer, Primer)""",

    "el": """Translate to modern demotic Greek (Δημοτική).
- Conversational tone, not academic or formal
- Use everyday Greek phrasing
- Skincare/beauty terms: keep English terms that Greeks commonly use (serum, primer, moisturizer, cleanser)
- Sound natural — like a Greek beauty influencer talking to friends""",

    "ru": """Translate to conversational Russian.
- Restructure sentences to sound native Russian — don't translate word-for-word
- Use a warm, friendly tone — like a beauty blogger on Telegram
- Skincare terms: use English borrowings where common (серум, праймер, консилер) but translate if a Russian equivalent is widely used
- Avoid overly formal or academic language""",

    "it": """Translate to warm, conversational Italian.
- Use "tu" form
- Use idiomatic Italian expressions where natural
- Skincare terms: keep English where Italians commonly use them (siero is fine for serum, but keep "primer", "highlighter" in English)
- Sound like a knowledgeable Italian friend sharing beauty tips""",

    "ar": """Translate to Modern Standard Arabic (فصحى) but keep it accessible and warm.
- NOT stiff newspaper/textbook style — write as if for a beauty/wellness blog targeting 20-35 year olds
- Skincare terms: keep English terms in parentheses when first used, then use the Arabic term
- Be naturally warm without being overly casual
- Remember: Arabic reads right-to-left, but keep all URLs, image paths, and code unchanged""",

    "fr": """Translate to conversational, modern French.
- Use "tu" form, not "vous"
- Use natural French phrasing — NOT word-for-word translation from English
- Skincare/DIY terms: keep English where French speakers commonly do (serum, primer, router, drill) — translate where natural
- Sound like a knowledgeable French friend sharing tips, NOT a dictionary""",

    "nl": """Translate to modern conversational Dutch.
- Use "je/jij" form, not "u"
- Keep a warm, informal tone — like a Dutch blogger, not a formal textbook
- Skincare/DIY terms: keep English borrowings where Dutch readers commonly use them (serum, primer, drill)
- Sound natural and direct — Dutch readers appreciate straightforwardness""",

    "pt": """Translate to conversational Brazilian Portuguese.
- Use "você" form (Brazilian, not European)
- Use colloquial Brazilian phrasing — avoid European Portuguese constructions
- Skincare/DIY terms: keep English borrowings where common in Brazil (serum, primer, drill)
- Sound like a Brazilian friend sharing beauty/DIY advice on Instagram""",
}

DOMAIN_GLOSSARY = """
SKINCARE DOMAIN GLOSSARY (keep these terms as-is in most languages unless a widely-used local term exists):
- Serum, Moisturizer, Cleanser, Toner, Essence, Ampoule, Emulsion
- SPF, UV, AHA, BHA, PHA, Retinol, Niacinamide, Hyaluronic Acid
- K-Beauty, Glass Skin, Double Cleansing, Sheet Mask
- Mirai (brand name — NEVER translate)
"""


def load_status():
    if STATUS_FILE.exists():
        return json.loads(STATUS_FILE.read_text())
    return {}


def save_status(status):
    STATUS_FILE.write_text(json.dumps(status, indent=2))


def call_gemini(prompt, max_retries=3):
    """Call Gemini API with retry logic."""
    import urllib.request
    import urllib.error

    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 16384,
        }
    })

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                GEMINI_URL,
                data=payload.encode(),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read())
                text = result["candidates"][0]["content"]["parts"][0]["text"]
                return text
        except Exception as e:
            print(f"  Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(5 * (attempt + 1))
            else:
                raise


def translate_ui_strings(site, lang):
    """Translate UI string JSON file."""
    en_path = BASE_DIR / site / "src" / "i18n" / "translations" / "en.json"
    target_path = BASE_DIR / site / "src" / "i18n" / "translations" / f"{lang}.json"

    en_data = json.loads(en_path.read_text())
    en_json_str = json.dumps(en_data, indent=2, ensure_ascii=False)

    prompt = f"""You are a professional translator for a beauty/wellness website.

{LANG_INSTRUCTIONS[lang]}

{DOMAIN_GLOSSARY}

Translate this JSON file from English. Keep the exact same JSON structure and keys — only translate the string values.

RULES:
- Keep JSON keys EXACTLY as they are (don't translate keys)
- Keep brand names as-is: "Glow Coded", "Rooted Glow", "Mirai"
- Keep email addresses as-is
- Translate naturally, not literally
- Output ONLY the JSON, no markdown code fences, no explanations

INPUT JSON:
{en_json_str}"""

    print(f"  Translating UI strings for {site} -> {lang}...")
    result = call_gemini(prompt)

    # Clean up: remove markdown code fences if present
    result = result.strip()
    if result.startswith("```"):
        result = re.sub(r'^```\w*\n?', '', result)
        result = re.sub(r'\n?```$', '', result)
    result = result.strip()

    # Validate JSON
    try:
        parsed = json.loads(result)
        target_path.write_text(json.dumps(parsed, indent=2, ensure_ascii=False))
        print(f"  ✓ {target_path.name} written")
    except json.JSONDecodeError as e:
        print(f"  ✗ Invalid JSON for {lang}: {e}")
        # Save raw for debugging
        target_path.with_suffix('.raw.txt').write_text(result)


def translate_article(site, lang, article_path):
    """Translate a single MDX article."""
    content = article_path.read_text()

    # Split frontmatter and body
    parts = content.split('---', 2)
    if len(parts) < 3:
        print(f"  ✗ Invalid frontmatter in {article_path.name}")
        return False

    frontmatter = parts[1]
    body = parts[2]

    # Extract translatable frontmatter fields
    title_match = re.search(r'^title:\s*"(.+)"', frontmatter, re.MULTILINE)
    desc_match = re.search(r'^description:\s*"(.+)"', frontmatter, re.MULTILINE)
    alt_match = re.search(r'^imageAlt:\s*(.+)', frontmatter, re.MULTILINE)
    tags_match = re.search(r'^tags:\s*\[(.+)\]', frontmatter, re.MULTILINE)

    title = title_match.group(1) if title_match else ""
    description = desc_match.group(1) if desc_match else ""
    image_alt = alt_match.group(1).strip() if alt_match else ""
    tags_str = tags_match.group(1) if tags_match else ""

    prompt = f"""You are a professional translator for a beauty/wellness blog.

{LANG_INSTRUCTIONS[lang]}

{DOMAIN_GLOSSARY}

Translate this blog article from English. I'll give you the frontmatter fields and body separately.

RULES FOR FRONTMATTER:
- Translate: title, description, imageAlt, tags
- Keep UNCHANGED: date, updated, category, type, image, draft, hub, affiliateProduct, routine
- Output the translated frontmatter fields as:
TITLE: [translated title]
DESCRIPTION: [translated description]
IMAGE_ALT: [translated alt text]
TAGS: [translated tag1, translated tag2, ...]

RULES FOR BODY:
- Translate all text content naturally
- PRESERVE all MDX syntax, component tags, HTML elements exactly as-is
- PRESERVE all URLs, image paths, and links — do NOT modify them
- PRESERVE markdown formatting (headers, bold, italic, lists, blockquotes)
- Internal links like (/some-slug/) should get the locale prefix: (/{lang}/some-slug/)
- Product links to mirai-skin.com stay UNCHANGED
- Keep ingredient/product names in English where appropriate

FRONTMATTER TO TRANSLATE:
Title: {title}
Description: {description}
ImageAlt: {image_alt}
Tags: {tags_str}

BODY TO TRANSLATE:
{body[:12000]}"""

    result = call_gemini(prompt)

    # Parse result
    try:
        lines = result.strip().split('\n')
        new_title = ""
        new_desc = ""
        new_alt = ""
        new_tags = ""
        body_start = 0

        for i, line in enumerate(lines):
            if line.startswith("TITLE:"):
                new_title = line[6:].strip()
            elif line.startswith("DESCRIPTION:"):
                new_desc = line[12:].strip()
            elif line.startswith("IMAGE_ALT:"):
                new_alt = line[10:].strip()
            elif line.startswith("TAGS:"):
                new_tags = line[5:].strip()
            elif line.strip() == "" and new_tags:
                body_start = i + 1
                break

        new_body = '\n'.join(lines[body_start:]) if body_start > 0 else result

        # Build new frontmatter
        new_fm = frontmatter
        if new_title and title_match:
            new_fm = new_fm.replace(f'title: "{title}"', f'title: "{new_title}"')
        if new_desc and desc_match:
            new_fm = new_fm.replace(f'description: "{description}"', f'description: "{new_desc}"')
        if new_alt and alt_match:
            new_fm = re.sub(r'^imageAlt:\s*.+', f'imageAlt: {new_alt}', new_fm, flags=re.MULTILINE)
        if new_tags and tags_match:
            # Format tags as array
            tag_items = [t.strip().strip('"').strip("'") for t in new_tags.split(',')]
            tags_formatted = json.dumps(tag_items, ensure_ascii=False)
            new_fm = re.sub(r'^tags:\s*\[.+\]', f'tags: {tags_formatted}', new_fm, flags=re.MULTILINE)

        # Update locale
        new_fm = re.sub(r'^locale:\s*\w+', f'locale: {lang}', new_fm, flags=re.MULTILINE)

        # Write translated file
        target_dir = article_path.parent.parent / lang
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / article_path.name

        target_file.write_text(f"---{new_fm}---\n{new_body}")
        return True

    except Exception as e:
        print(f"  ✗ Error parsing translation for {article_path.name}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Translate satellite site content")
    parser.add_argument("--site", choices=["cosmetics", "wellness", "build-coded"], help="Site to translate")
    parser.add_argument("--lang", choices=LOCALES, help="Target language")
    parser.add_argument("--ui-only", action="store_true", help="Only translate UI strings")
    parser.add_argument("--articles-only", action="store_true", help="Only translate articles")
    args = parser.parse_args()

    sites = [args.site] if args.site else ["cosmetics", "wellness", "build-coded"]
    langs = [args.lang] if args.lang else LOCALES
    status = load_status()

    for site in sites:
        print(f"\n{'='*60}")
        print(f"SITE: {site}")
        print(f"{'='*60}")

        # Translate UI strings
        if not args.articles_only:
            for lang in langs:
                key = f"{site}/ui/{lang}"
                if key in status and status[key] == "done":
                    print(f"  Skipping UI strings {lang} (already done)")
                    continue
                translate_ui_strings(site, lang)
                status[key] = "done"
                save_status(status)
                time.sleep(2)

        # Translate articles
        if not args.ui_only:
            blog_dir = BASE_DIR / site / "src" / "content" / "blog" / "en"
            articles = sorted(blog_dir.glob("*.mdx"))
            print(f"\n  Found {len(articles)} English articles to translate")

            for lang in langs:
                print(f"\n  --- Translating to {lang} ---")
                for i, article in enumerate(articles):
                    key = f"{site}/article/{lang}/{article.name}"
                    if key in status and status[key] == "done":
                        print(f"  [{i+1}/{len(articles)}] Skipping {article.name} (already done)")
                        continue

                    print(f"  [{i+1}/{len(articles)}] {article.name} -> {lang}")
                    try:
                        success = translate_article(site, lang, article)
                        if success:
                            status[key] = "done"
                            save_status(status)
                            print(f"  ✓ {article.name}")
                        else:
                            status[key] = "failed"
                            save_status(status)
                    except Exception as e:
                        print(f"  ✗ Failed: {e}")
                        status[key] = "failed"
                        save_status(status)

                    time.sleep(3)  # Rate limiting

    print(f"\n{'='*60}")
    print("Translation complete!")
    total = sum(1 for v in status.values() if v == "done")
    failed = sum(1 for v in status.values() if v == "failed")
    print(f"  Done: {total}, Failed: {failed}")


if __name__ == "__main__":
    main()
