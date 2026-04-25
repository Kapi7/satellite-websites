#!/usr/bin/env python3
"""Pick Mirai products for the Pinterest pin pipeline.

Selects N products from the Shopify catalog spread across product-type buckets
that map to our Pinterest boards. Vendor-balanced so we don't pin only one
brand. Skips products without images. Output is a JSON list of trimmed
product dicts ready for build_mirai_pin_images.py.

Usage:
  python3 select_mirai_products.py [--count 60] [--out picked.json]
  python3 select_mirai_products.py --count 3 --out /tmp/sample-3.json
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import MIRAI_PRODUCT_CATALOG, PINTEREST_BOARD_MAP

# product_type (Shopify field) → Pinterest board key
# Each substring match routes the product to a board. First match wins.
TYPE_TO_BOARD = [
    (r"sun ?(screen|stick|cushion|cream|lotion|gel|essence)", "sunscreen"),
    (r"\bspf\b", "sunscreen"),
    (r"cleansing (oil|balm|foam|gel|water|powder|tissue|pad)", "cleanser"),
    (r"\bcleanser\b", "cleanser"),
    (r"\b(moisturi[sz]er|cream|lotion|emulsion|sleeping mask)\b", "moisturizer"),
    (r"\b(serum|ampoule|essence)\b", "serum"),
    (r"\btoner\b", "toner"),
    (r"\b(mask|sheet mask|wash[- ]?off|patch)\b", "mask"),
    (r"\b(cushion|bb cream|cc cream|foundation|tint|lip|eyeshadow)\b", "makeup"),
]


def board_for(product_type: str) -> str:
    pt = (product_type or "").lower().strip()
    for pattern, board in TYPE_TO_BOARD:
        if re.search(pattern, pt):
            return board
    return "_default"


def first_image_src(product: dict) -> str | None:
    images = product.get("images") or []
    for img in images:
        src = img.get("src") if isinstance(img, dict) else None
        if src and isinstance(src, str):
            return src
    return None


def first_variant_price(product: dict) -> str | None:
    variants = product.get("variants") or []
    for v in variants:
        if isinstance(v, dict):
            price = v.get("price")
            if price:
                return str(price)
    return None


def trim_product(p: dict, board: str) -> dict:
    return {
        "id": p.get("id"),
        "handle": p.get("handle"),
        "title": p.get("title", "").strip(),
        "vendor": (p.get("vendor") or "").strip(),
        "product_type": (p.get("product_type") or "").strip(),
        "tags": p.get("tags") or [],
        "image_src": first_image_src(p),
        "price": first_variant_price(p),
        "board": board,
        "url": f"https://mirai-skin.com/products/{p.get('handle')}",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=60, help="Total products to pick")
    ap.add_argument("--out", type=Path, default=Path("/tmp/mirai-picked.json"))
    ap.add_argument("--catalog", type=Path, default=MIRAI_PRODUCT_CATALOG)
    args = ap.parse_args()

    if not args.catalog.exists():
        print(f"ERROR: catalog not at {args.catalog}", file=sys.stderr)
        return 2

    catalog = json.loads(args.catalog.read_text())
    print(f"loaded {len(catalog)} products")

    # Bucket by board
    buckets: dict[str, list[dict]] = defaultdict(list)
    for p in catalog:
        if not first_image_src(p):
            continue  # skip imageless
        board = board_for(p.get("product_type", ""))
        buckets[board].append(p)
    print(f"bucketed: {[(k, len(v)) for k, v in sorted(buckets.items())]}")

    # Even split, vendor-balanced selection
    boards = list(PINTEREST_BOARD_MAP["mirai"].keys())  # includes _default
    per_board = max(1, args.count // len(boards))

    picked: list[dict] = []
    for board in boards:
        candidates = buckets.get(board, [])
        if not candidates:
            continue
        # Sort by created_at desc (newest first)
        candidates.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        # Round-robin through vendors so we don't pile up one brand
        vendor_seen: set[str] = set()
        chosen: list[dict] = []
        # First pass: one per vendor
        for p in candidates:
            v = (p.get("vendor") or "").strip().lower()
            if v not in vendor_seen:
                chosen.append(p)
                vendor_seen.add(v)
                if len(chosen) >= per_board:
                    break
        # Second pass: top up if vendor-pass didn't fill quota
        if len(chosen) < per_board:
            for p in candidates:
                if p not in chosen:
                    chosen.append(p)
                    if len(chosen) >= per_board:
                        break
        for p in chosen:
            picked.append(trim_product(p, board))

    # Cap to the user's requested count
    picked = picked[: args.count]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(picked, indent=2))
    print(f"\nselected {len(picked)} products → {args.out}")
    print(f"breakdown by board:")
    by_board: dict[str, int] = defaultdict(int)
    for p in picked:
        by_board[p["board"]] += 1
    for b, n in sorted(by_board.items()):
        print(f"  {b}: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
