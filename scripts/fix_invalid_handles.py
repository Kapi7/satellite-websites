#!/usr/bin/env python3
"""
For every glow-coded article that links to a mirai-skin.com/products/{handle}
where {handle} doesn't exist in the catalog, find the closest matching VALID
handle by fuzzy matching against catalog product titles, and rewrite the MDX.

Strategy:
  - Extract broken handle, normalize to keywords ("anua-heartleaf-cleansing-oil"
    → tokens [anua, heartleaf, cleansing, oil]).
  - For each catalog product, score by: (a) brand/vendor match, (b) shared tokens
    in handle/title, (c) tag match.
  - Pick best score; if confidence is low, mark UNCERTAIN and skip.
  - Rewrite the original MDX file replacing the broken URL.

Usage:
  python3 scripts/fix_invalid_handles.py --dry-run  # show proposed mappings
  python3 scripts/fix_invalid_handles.py            # apply edits
"""
from __future__ import annotations
import argparse
import csv
import json
import re
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = Path("/Users/kapi7/mirai-meta-campaign/satellite-websites/.image-cache/products_catalog.json")
PRODUCT_LINK_RE = re.compile(r"https?://(?:www\.)?mirai-skin\.com/products/([a-z0-9-]+)", re.I)
STOPWORDS = {"a", "the", "for", "and", "with", "of", "to", "in", "on", "ml", "g",
             "set", "kit", "pack", "size", "edition", "vs", "review", "guide", "best"}


def load_catalog():
    data = json.loads(CATALOG_PATH.read_text())
    products = []
    for p in data:
        h = p.get("handle")
        if not h:
            continue
        title = (p.get("title") or "").lower()
        vendor = (p.get("vendor") or "").lower()
        tags_raw = p.get("tags") or []
        if isinstance(tags_raw, str):
            tags = [t.strip().lower() for t in tags_raw.split(",")]
        else:
            tags = [str(t).lower() for t in tags_raw]
        ptype = (p.get("product_type") or "").lower()
        # Build token set
        tokens = set(re.findall(r"[a-z0-9]+", title)) - STOPWORDS
        tokens |= set(re.findall(r"[a-z0-9]+", h)) - STOPWORDS
        tokens |= set(re.findall(r"[a-z0-9]+", vendor)) - STOPWORDS
        products.append({
            "handle": h,
            "title": title,
            "vendor": vendor,
            "tokens": tokens,
            "tags": tags,
            "ptype": ptype,
        })
    return products


def tokens(handle: str):
    return set(re.findall(r"[a-z0-9]+", handle.lower())) - STOPWORDS


def score(broken_handle: str, broken_context_tokens: set, prod):
    """Higher = better match."""
    bh_toks = tokens(broken_handle)
    overlap = len(bh_toks & prod["tokens"])
    if overlap == 0:
        return 0
    s = overlap * 3
    # Brand match heavily boosts
    if prod["vendor"]:
        v_toks = set(re.findall(r"[a-z0-9]+", prod["vendor"]))
        if v_toks & bh_toks:
            s += 5
    # Context (article title) tokens overlap
    s += len(prod["tokens"] & broken_context_tokens) * 0.5
    # Penalize huge handles that match by chance
    if len(prod["tokens"]) > 30:
        s -= 1
    return s


def best_match(broken_handle, context_tokens, products, top_n=3):
    scored = []
    for p in products:
        sc = score(broken_handle, context_tokens, p)
        if sc > 0:
            scored.append((sc, p))
    scored.sort(key=lambda x: -x[0])
    return scored[:top_n]


def find_invalid(audit_csv: Path):
    rows = list(csv.DictReader(audit_csv.open()))
    return [r for r in rows if r["site"] == "glow-coded" and r["status"] == "invalid_handle"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    products = load_catalog()
    valid_handles = {p["handle"] for p in products}
    print(f"[catalog] {len(products)} products loaded")

    invalid = find_invalid(ROOT / "scripts" / "reports" / "product-audit.csv")
    print(f"[audit] {len(invalid)} glow-coded articles with invalid handles\n")

    fixes = []  # (path, broken_handle, new_handle, score, title)
    skipped = []

    for entry in invalid:
        path = ROOT / "cosmetics" / "src" / "content" / "blog" / "en" / f"{entry['slug']}.mdx"
        if not path.exists():
            skipped.append((entry["slug"], "file missing"))
            continue
        body = path.read_text()
        ctx_tokens = tokens(entry["slug"]) | tokens(entry["title"])

        # Find each broken handle in this article
        article_fixes = []
        for m in PRODUCT_LINK_RE.finditer(body):
            broken = m.group(1).lower()
            if broken in valid_handles:
                continue
            matches = best_match(broken, ctx_tokens, products)
            if not matches:
                article_fixes.append((broken, None, 0, "no candidates"))
                continue
            top_score, top = matches[0]
            confidence = "HIGH" if top_score >= 8 else ("MED" if top_score >= 4 else "LOW")
            article_fixes.append((broken, top["handle"], top_score, confidence))

        if article_fixes:
            print(f"  {entry['slug']}")
            for broken, new, sc, conf in article_fixes:
                if new:
                    print(f"    {broken}")
                    print(f"      → {new}  [{conf}, score {sc:.1f}]")
                else:
                    print(f"    {broken}  → SKIP ({conf})")
                    skipped.append((entry["slug"], f"no match for {broken}"))
            print()
            fixes.append((path, article_fixes))

    if args.dry_run:
        print("\n[dry-run] no files modified")
        return

    # Apply fixes
    applied = 0
    for path, article_fixes in fixes:
        body = path.read_text()
        original = body
        for broken, new, sc, conf in article_fixes:
            if not new or conf == "LOW":
                continue
            # Replace all occurrences in this article
            old_url = f"mirai-skin.com/products/{broken}"
            new_url = f"mirai-skin.com/products/{new}"
            body = body.replace(old_url, new_url)
        if body != original:
            path.write_text(body)
            applied += 1
            print(f"  [edit] {path.relative_to(ROOT)}")

    print(f"\n[done] {applied} files updated, {len(skipped)} skipped")


if __name__ == "__main__":
    main()
