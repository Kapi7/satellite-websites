#!/usr/bin/env python3
"""
For each glow-coded draft article, identify real Mirai-Skin catalog products
that fit the topic, and insert markdown image-link blocks at the right places
in the body.

Pipeline (per article):
  1. Read draft MDX (frontmatter + body).
  2. Filter the catalog to candidate products that match the article's topic
     keywords (brand names + ingredients + categories).
  3. Ask Gemini 2.5 Flash to pick 3-5 products and propose the section title
     where each should be inserted.
  4. Insert `[![Name](/images/products/{handle}.jpg)](https://mirai-skin.com/products/{handle})`
     immediately after the chosen section header.
  5. Save back. Always keeps draft:true.

Usage:
    python3 scripts/enhance_glow_coded_drafts.py --dry-run     # show plan
    python3 scripts/enhance_glow_coded_drafts.py --slug <slug> # one article
    python3 scripts/enhance_glow_coded_drafts.py               # all 30 drafts
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

API_KEY = os.environ.get("GEMINI_API_KEY", "")
if not API_KEY:
    print("ERROR: GEMINI_API_KEY not set"); sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
DRAFTS_DIR = ROOT / "cosmetics" / "src" / "content" / "blog" / "en"
CATALOG_PATH = Path("/Users/kapi7/mirai-meta-campaign/satellite-websites/.image-cache/products_catalog.json")
TEXT_MODEL = "gemini-2.5-flash"


def load_catalog():
    data = json.loads(CATALOG_PATH.read_text())
    products = []
    for p in data:
        if not p.get("handle") or not p.get("title"):
            continue
        products.append({
            "handle": p["handle"],
            "title": p["title"],
            "vendor": (p.get("vendor") or "").strip(),
            "type": (p.get("product_type") or "").strip(),
        })
    return products


CATALOG = load_catalog()


def parse_mdx(path: Path):
    text = path.read_text()
    m = re.match(r"^(---\s*\n.*?\n---\s*\n)(.*)$", text, re.S)
    if not m:
        return None
    return m.group(1), m.group(2)


def is_draft(frontmatter: str) -> bool:
    return bool(re.search(r"^draft:\s*true\s*$", frontmatter, re.M))


def filter_candidates(article_text: str, max_candidates=80):
    """Quickly narrow the 2746-product catalog to candidates that share keywords
    with the article. Reduces token cost for the Gemini call."""
    text = article_text.lower()
    # Extract distinctive tokens (length 4+, alphanumeric)
    tokens = set(re.findall(r"[a-z]{4,}", text))
    common = {"with", "from", "this", "that", "your", "skin", "korean", "beauty",
              "product", "products", "review", "guide", "every", "really", "they",
              "have", "their", "which", "these", "those", "more", "than", "best",
              "good", "well", "also", "into", "very", "much", "some", "like",
              "what", "when", "where", "while", "after", "before", "about"}
    tokens -= common

    scored = []
    for p in CATALOG:
        prod_text = (p["title"] + " " + p["vendor"] + " " + p["handle"]).lower()
        prod_tokens = set(re.findall(r"[a-z]{4,}", prod_text))
        overlap = len(tokens & prod_tokens)
        if overlap >= 2:
            scored.append((overlap, p))
    scored.sort(key=lambda x: -x[0])
    return [p for _, p in scored[:max_candidates]]


def gemini_pick_products(article_title: str, article_body: str, candidates: list, n=4):
    """Ask Gemini to pick the best 3-5 products from candidates for this article."""
    catalog_str = "\n".join(f'  "{p["handle"]}": "{p["title"]}" ({p["vendor"]})' for p in candidates)
    # Truncate body to stay under token budget
    body_excerpt = article_body[:8000]

    prompt = f"""You are picking real K-beauty products from a catalog to add as affiliate links inside an existing skincare article. Output strict JSON only.

ARTICLE TITLE: {article_title}

ARTICLE BODY (excerpt):
{body_excerpt}

CATALOG (handle: title (vendor)):
{catalog_str}

TASK: Pick 3 to {n} catalog products that genuinely fit this article's topic. They should be real, on-topic recommendations the reader would benefit from. For each product, also propose a section header *that already exists in the article body* (or "TL;DR winner" or "Our pick" if those are the natural section names) where the product image-link should be inserted right after.

Return ONLY this JSON shape (no prose, no fences):
{{
  "picks": [
    {{
      "handle": "<exact handle from catalog>",
      "name": "<short product name as it should appear in the link, max 50 chars>",
      "section": "<exact header text that exists in the article body — match verbatim>",
      "reason": "<5-15 word justification>"
    }}
  ]
}}

Rules:
- Use ONLY handles that appear in the catalog above.
- Pick 3-{n} products. Diversify (don't pick 5 of the same brand).
- Section MUST be an actual H2/H3 from the article. If you cannot find a fitting existing section, use "## Bottom line" (which exists in most articles).
- Prefer products explicitly named in the article body when possible.
"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{TEXT_MODEL}:generateContent?key={API_KEY}"
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 6000, "temperature": 0.3, "responseMimeType": "application/json"},
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})

    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                data = json.loads(r.read())
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            # Clean common Gemini JSON quirks: trailing commas, smart quotes, code fences
            text = text.strip()
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\s*", "", text)
                text = re.sub(r"\s*```$", "", text)
            text = text.replace(""", '"').replace(""", '"').replace("'", "'")
            text = re.sub(r",\s*([}\]])", r"\1", text)  # trailing commas
            try:
                return json.loads(text).get("picks", [])
            except json.JSONDecodeError as je:
                # Try to extract the first {...} block
                m = re.search(r"\{.*\}", text, re.S)
                if m:
                    try:
                        return json.loads(m.group(0)).get("picks", [])
                    except Exception:
                        pass
                print(f"    JSON parse failed at char {je.pos}; raw response length {len(text)}:")
                print(text[:1500])
                print("...END...")
                return []
        except urllib.error.HTTPError as e:
            if e.code in (429, 503):
                time.sleep(10 * (attempt + 1))
            else:
                print(f"    Gemini error {e.code}: {e.read().decode()[:200]}")
                return []
    return []


def insert_product_links(body: str, picks: list, valid_handles: set):
    """Insert image-link blocks after the matching section headers."""
    lines = body.split("\n")
    inserted = []
    skipped = []

    for pick in picks:
        handle = pick.get("handle", "").strip()
        name = pick.get("name", "").strip()
        section = pick.get("section", "").strip()

        if handle not in valid_handles:
            skipped.append((handle, "not in catalog"))
            continue

        # Build the image-link block
        link_block = f"\n[![{name}](/images/products/{handle}.jpg)](https://mirai-skin.com/products/{handle})\n"

        # Find the section header line
        section_clean = re.sub(r"^#+\s*", "", section).strip()
        target_idx = None
        for i, line in enumerate(lines):
            line_clean = re.sub(r"^#+\s*", "", line).strip()
            if line_clean.lower() == section_clean.lower() and line.startswith("#"):
                target_idx = i
                break

        if target_idx is None:
            # Fallback: append before "## Bottom line" if exists, else at end
            for i, line in enumerate(lines):
                if line.strip().lower().startswith(("## bottom line", "## the bottom line", "## final verdict")):
                    target_idx = i - 1  # insert just before
                    break
            if target_idx is None:
                target_idx = len(lines) - 1

        # Insert AFTER the header (next index)
        insert_at = target_idx + 1 if lines[target_idx].startswith("#") else target_idx
        lines.insert(insert_at, link_block)
        inserted.append((handle, name, section))

    return "\n".join(lines), inserted, skipped


def find_drafts():
    drafts = []
    for f in sorted(DRAFTS_DIR.glob("*.mdx")):
        parsed = parse_mdx(f)
        if not parsed:
            continue
        fm, body = parsed
        if not is_draft(fm):
            continue
        # Skip if already has product links
        if "mirai-skin.com/products/" in body:
            continue
        drafts.append((f, fm, body))
    return drafts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", help="Run for one slug only")
    ap.add_argument("--dry-run", action="store_true", help="Print plan, don't write")
    ap.add_argument("--limit", type=int, default=None, help="Process at most N drafts")
    args = ap.parse_args()

    valid_handles = {p["handle"] for p in CATALOG}
    print(f"[catalog] {len(CATALOG)} products loaded")

    drafts = find_drafts()
    if args.slug:
        drafts = [d for d in drafts if d[0].stem == args.slug]
    if args.limit:
        drafts = drafts[: args.limit]

    print(f"[queue] {len(drafts)} drafts without products to enhance\n")

    success = 0
    for path, fm, body in drafts:
        title_match = re.search(r'title:\s*"([^"]+)"', fm)
        title = title_match.group(1) if title_match else path.stem
        print(f"  → {path.stem}")
        print(f"    title: {title}")

        candidates = filter_candidates(title + "\n\n" + body, max_candidates=60)
        print(f"    candidates: {len(candidates)}")
        if not candidates:
            print("    SKIP: no candidates from catalog")
            continue

        picks = gemini_pick_products(title, body, candidates)
        if not picks:
            print("    SKIP: gemini returned no picks")
            continue

        print(f"    picks: {len(picks)}")
        new_body, inserted, skipped = insert_product_links(body, picks, valid_handles)
        for h, n, s in inserted:
            print(f"      ✓ {n} → after \"{s[:50]}\"  ({h})")
        for h, why in skipped:
            print(f"      ✗ {h}: {why}")

        if args.dry_run:
            print("    [dry-run] not writing\n")
            continue

        if inserted:
            path.write_text(fm + new_body)
            success += 1
            print(f"    SAVED ({len(inserted)} products inserted)\n")
        else:
            print(f"    NO INSERTS, file unchanged\n")

        time.sleep(2)  # rate-limit gentle on Gemini

    print(f"\n[done] {success}/{len(drafts)} drafts enhanced")


if __name__ == "__main__":
    main()
