#!/usr/bin/env python3
"""
For every "X vs Y" article on glow-coded + rooted-glow:
  1. Parse X and Y terms from the slug ("anua-peach-niacinamide-vs-ordinary"
     → X="anua peach niacinamide", Y="ordinary").
  2. Find canonical X and Y product handles in the Mirai catalog (skip if Y
     is a non-Mirai brand like "ordinary", "skii", "peach-lily").
  3. Ensure the first 2 product image-link blocks in the article body link
     to the X and Y handles. If the article currently picks generic
     replacements, prepend the X and Y blocks before them so the sidebar
     features the right products.

Usage:
    python3 scripts/fix_comparison_article_products.py --dry-run
    python3 scripts/fix_comparison_article_products.py
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = Path("/Users/kapi7/mirai-meta-campaign/satellite-websites/.image-cache/products_catalog.json")

# Brands NOT in the Mirai catalog — skip the Y side if it matches one of these
NON_MIRAI = {
    "ordinary", "the-ordinary", "skii", "sk-ii", "peach-lily", "peach-and-lily",
    "drunk-elephant", "paula", "paulas-choice", "cerave", "neutrogena",
}


def load_catalog():
    return json.loads(CATALOG_PATH.read_text())


CATALOG = load_catalog()
VALID_HANDLES = {p.get("handle") for p in CATALOG if p.get("handle")}

# Build a set of brand tokens from vendor names so we can check that the
# slug references a real Mirai brand (not a generic concept like
# "snail-mucin-vs-centella" or "chemical-vs-mineral"). Concept comparisons
# should not get arbitrary products force-injected — that produces the
# user-visible mismatch this script is supposed to FIX, not introduce.
BRAND_TOKENS: set[str] = set()
for p in CATALOG:
    vendor = (p.get("vendor") or "").lower().strip()
    if not vendor:
        continue
    # "Beauty of Joseon" → "beauty", "joseon" / "Anua" → "anua" / etc.
    for tok in re.findall(r"[a-z][a-z0-9]+", vendor):
        if len(tok) >= 3 and tok not in {"the", "and", "co", "by", "of"}:
            BRAND_TOKENS.add(tok)


def slug_has_brand(slug: str) -> bool:
    return any(t in slug for t in BRAND_TOKENS)


def find_best_handle(query_terms: list[str]) -> tuple[str, str] | None:
    """Score every catalog product by token overlap with query_terms.
    Returns (handle, title) of the best match, or None if score < threshold."""
    qset = set(query_terms)
    best = (0, None, None)
    for p in CATALOG:
        h = (p.get("handle") or "").lower()
        t = (p.get("title") or "").lower()
        h_tokens = set(h.split("-"))
        t_tokens = set(re.findall(r"[a-z]+", t))
        h_score = len(qset & h_tokens) * 3       # handle match weighted higher
        t_score = len(qset & t_tokens)
        # Bonus: if all query terms appear in the handle
        if all(qt in h for qt in query_terms):
            h_score += 5
        score = h_score + t_score
        if score > best[0]:
            best = (score, p.get("handle"), p.get("title"))
    if best[0] >= 6:  # threshold
        return (best[1], best[2])
    return None


def parse_vs_slug(slug: str):
    """anua-peach-niacinamide-vs-ordinary → ('anua-peach-niacinamide', 'ordinary')"""
    m = re.match(r"^(.+?)-vs-(.+)$", slug)
    if not m:
        return None
    left, right = m.group(1), m.group(2)
    # Drop numeric/generic suffixes from the right side
    right = re.sub(r"-\d+(?:-[a-z]+)?$", "", right)
    return left, right


def is_non_mirai(brand_token: str) -> bool:
    if brand_token.lower() in NON_MIRAI:
        return True
    # Check first word of slug
    first = brand_token.split("-")[0].lower()
    return first in NON_MIRAI


def has_handle_in_body(body: str, handle: str) -> bool:
    return f"mirai-skin.com/products/{handle}" in body


PRODUCT_BLOCK_RE = re.compile(
    r"\[!\[([^\]]*)\]\(/images/products/[a-z0-9-]+\.(?:jpg|png|webp)\)\]\(https?://[^)]*mirai-skin\.com/products/([a-z0-9-]+)\)",
    re.I,
)


def build_block(handle: str, name: str) -> str:
    return f"[![{name}](/images/products/{handle}.jpg)](https://mirai-skin.com/products/{handle})"


def find_first_block_position(text: str) -> int | None:
    """Return char offset of the first product block, or None."""
    m = PRODUCT_BLOCK_RE.search(text)
    return m.start() if m else None


def find_first_h2_position(text: str) -> int | None:
    """Return char offset just after the first ## heading (good insertion point)."""
    for m in re.finditer(r"^## .+$", text, re.M):
        # Find end of paragraph after this h2
        rest = text[m.end():]
        para_end = rest.find("\n\n")
        if para_end == -1:
            return m.end()
        return m.end() + para_end + 2
    return None


def process_article(path: Path, dry_run: bool):
    fm_re = re.compile(r"^(---\s*\n.*?\n---\s*\n)(.*)$", re.S)
    text = path.read_text()
    m = fm_re.match(text)
    if not m:
        return None
    fm, body = m.group(1), m.group(2)

    slug = path.stem
    parsed = parse_vs_slug(slug)
    if not parsed:
        return None
    left_slug, right_slug = parsed

    # Skip concept comparisons — the slug must reference at least one real
    # Mirai brand on either side. Otherwise the fuzzy matcher will pick
    # plausible-but-irrelevant products and make the sidebar worse.
    if not (slug_has_brand(left_slug) or slug_has_brand(right_slug)):
        return {"slug": slug, "left": None, "right": None, "status": "skip-concept"}

    # Build search-term lists
    left_terms = left_slug.split("-")
    right_terms = right_slug.split("-")

    # Resolve each side
    left_match = find_best_handle(left_terms)
    right_match = find_best_handle(right_terms) if not is_non_mirai(right_slug) else None

    if not left_match and not right_match:
        return {"slug": slug, "left": None, "right": None, "status": "no-match"}

    blocks_to_add = []
    if left_match and not has_handle_in_body(body, left_match[0]):
        blocks_to_add.append(("left", left_match[0], left_match[1]))
    if right_match and not has_handle_in_body(body, right_match[0]):
        blocks_to_add.append(("right", right_match[0], right_match[1]))

    if not blocks_to_add:
        return {"slug": slug, "left": left_match, "right": right_match, "status": "already-present"}

    # Insert the new blocks BEFORE the first existing product block (so
    # they're picked up first by extractProducts which only reads the first 3)
    insert_pos = find_first_block_position(body)
    if insert_pos is None:
        # Fall back to inserting after the first H2's intro paragraph
        insert_pos = find_first_h2_position(body) or 0

    insertion = "\n\n".join(build_block(h, n) for _, h, n in blocks_to_add) + "\n\n"
    new_body = body[:insert_pos] + insertion + body[insert_pos:]

    if not dry_run:
        path.write_text(fm + new_body)

    return {
        "slug": slug,
        "left": left_match,
        "right": right_match,
        "added": [(h, n) for _, h, n in blocks_to_add],
        "status": "edited",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    sites = [
        ROOT / "cosmetics" / "src" / "content" / "blog" / "en",
        ROOT / "wellness" / "src" / "content" / "blog" / "en",
    ]
    edited, skipped = 0, 0
    for site_dir in sites:
        for f in sorted(site_dir.glob("*-vs-*.mdx")):
            result = process_article(f, args.dry_run)
            if not result:
                continue
            print(f"\n  {f.relative_to(ROOT)}")
            print(f"    left:  {result.get('left')}")
            print(f"    right: {result.get('right')}")
            print(f"    status: {result['status']}")
            if result.get("added"):
                for h, n in result["added"]:
                    print(f"      + {h}  ({n[:50]})")
                edited += 1
            else:
                skipped += 1

    print(f"\n[done] {edited} articles {'would be ' if args.dry_run else ''}edited, {skipped} skipped")


if __name__ == "__main__":
    main()
