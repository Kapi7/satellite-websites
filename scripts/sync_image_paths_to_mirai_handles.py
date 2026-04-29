#!/usr/bin/env python3
"""
For every product image block in MDX:
    [![alt](/images/products/<image-slug>.jpg)](https://mirai-skin.com/products/<handle>)

if image-slug != handle, rewrite image-slug → handle so the on-disk file
(saved by download_missing_product_images.py as <handle>.jpg) is found.

For broken handles (those NOT in the Mirai catalog), do a fuzzy match
against the catalog and rewrite both the image-slug and the mirai URL
to the matched handle.

Usage:
    python3 scripts/sync_image_paths_to_mirai_handles.py --dry-run
    python3 scripts/sync_image_paths_to_mirai_handles.py
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITES = ["cosmetics", "wellness", "build-coded"]
CATALOG_PATH = Path("/Users/kapi7/mirai-meta-campaign/satellite-websites/.image-cache/products_catalog.json")


def load_catalog():
    data = json.loads(CATALOG_PATH.read_text())
    return [{"handle": p["handle"], "title": p.get("title", ""), "vendor": p.get("vendor", "")}
            for p in data if p.get("handle")]


CATALOG = load_catalog()
VALID_HANDLES = {p["handle"] for p in CATALOG}


# Match: [![alt](/images/products/<slug>.jpg)](https://mirai-skin.com/products/<handle>)
BLOCK_RE = re.compile(
    r"\[!\[([^\]]*)\]\(/images/products/([a-z0-9][a-z0-9-]*)\.(?:jpg|png|webp)\)\]\(https?://(?:www\.)?mirai-skin\.com/products/([a-z0-9][a-z0-9-]*)\)",
    re.I,
)


def fuzzy_match(bad: str, threshold=10):
    """Score each catalog handle by token overlap with the broken one. Return best match handle or None."""
    bad_tokens = set(bad.split("-"))
    best = (0, None)
    for p in CATALOG:
        h_tokens = set(p["handle"].split("-"))
        score = len(bad_tokens & h_tokens) * 2
        # bonus for handle prefix match
        if p["handle"].startswith(bad.split("-", 1)[0] + "-"):
            score += 3
        if score > best[0]:
            best = (score, p["handle"])
    return best[1] if best[0] >= threshold else None


def process_file(path: Path, dry_run: bool):
    text = path.read_text()
    original = text
    edits = []  # (image_slug, handle, replacement_handle, reason)

    def repl(m):
        alt, image_slug, handle = m.group(1), m.group(2), m.group(3)
        # Path is fine
        if image_slug == handle:
            return m.group(0)

        # Handle is valid → just sync the image slug to handle
        if handle in VALID_HANDLES:
            edits.append((image_slug, handle, handle, "image-path-sync"))
            return f"[![{alt}](/images/products/{handle}.jpg)](https://mirai-skin.com/products/{handle})"

        # Handle is invalid → fuzzy match
        best = fuzzy_match(handle)
        if best:
            edits.append((image_slug, handle, best, f"fuzzy→{best}"))
            return f"[![{alt}](/images/products/{best}.jpg)](https://mirai-skin.com/products/{best})"

        # Couldn't match; leave as-is
        edits.append((image_slug, handle, None, "no-match"))
        return m.group(0)

    new_text = BLOCK_RE.sub(repl, text)
    changed = new_text != original

    if edits:
        rel = path.relative_to(ROOT)
        print(f"\n  {rel}")
        for image_slug, handle, repl_handle, reason in edits:
            mark = "→" if repl_handle else "✗"
            print(f"    {mark} img={image_slug} handle={handle} | {reason}")

    if changed and not dry_run:
        path.write_text(new_text)

    return len([e for e in edits if e[2]]), len([e for e in edits if not e[2]])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    total_fixed = 0
    total_unmatched = 0
    files_changed = 0

    for site in SITES:
        en_dir = ROOT / site / "src" / "content" / "blog" / "en"
        if not en_dir.exists():
            continue
        for f in sorted(en_dir.glob("*.mdx")):
            text = f.read_text()
            # Quick check: does this file have a mismatched block?
            has_mismatch = False
            for m in BLOCK_RE.finditer(text):
                if m.group(2) != m.group(3):
                    has_mismatch = True
                    break
            if not has_mismatch:
                continue
            fixed, unmatched = process_file(f, args.dry_run)
            total_fixed += fixed
            total_unmatched += unmatched
            if fixed:
                files_changed += 1

    print(f"\n[done] {total_fixed} blocks fixed, {total_unmatched} unmatched, {files_changed} files {'would be ' if args.dry_run else ''}edited")


if __name__ == "__main__":
    main()
