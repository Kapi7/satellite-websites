#!/usr/bin/env python3
"""
fetch_real_product_image — get an authentic running-shoe product photo for an article.

Strategy (per brand, fall through on failure):
  1. RunRepeat (cdn.runrepeat.com) — best source. Reviews almost every modern shoe and
     hosts 3000x2000 JPEGs of real product photography. URL-discoverable via search.
  2. Brand official page — scrape og:image meta tag.
  3. Amazon — scrape product page og:image (allowed for affiliates per Amazon
     Associates ToS section "Trademark and Image License").

Dependencies: stdlib + Pillow only.

Public API:
    fetch_real_product_image(brand, product, output_path) -> bool

CLI:
    python fetch_real_product_image.py "Nike" "Vomero Plus" path/to/out.jpg
"""

from __future__ import annotations

import re
import sys
import urllib.parse
import urllib.request
from io import BytesIO
from pathlib import Path
from typing import Iterable

from PIL import Image

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)

# Brands handled. Each entry tells us how to slugify the product for runrepeat.
SUPPORTED_BRANDS = {
    "nike", "asics", "hoka", "brooks", "new balance", "adidas", "saucony", "altra",
    "puma", "mizuno", "on", "on running",
}


def _http_get(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _slug(text: str) -> str:
    s = text.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _is_valid_image(data: bytes, min_width: int = 500) -> bool:
    if len(data) < 5_000:
        return False
    try:
        img = Image.open(BytesIO(data))
        img.verify()
    except Exception:
        return False
    try:
        img2 = Image.open(BytesIO(data))
        w, _ = img2.size
        if w < min_width:
            return False
        if img2.format not in {"JPEG", "PNG", "WEBP"}:
            return False
    except Exception:
        return False
    return True


def _save(data: bytes, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.open(BytesIO(data))
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGB")
    img.save(output_path, "JPEG", quality=88, optimize=True, progressive=True)


# --- source: runrepeat ----------------------------------------------------------

def _runrepeat_candidate_slugs(brand: str, product: str) -> Iterable[str]:
    full = _slug(f"{brand} {product}")
    yield full
    # Some pages include a year suffix e.g. -2025
    for y in (2026, 2025, 2024):
        yield f"{full}-{y}"


def _runrepeat_image(brand: str, product: str) -> bytes | None:
    for slug in _runrepeat_candidate_slugs(brand, product):
        page_url = f"https://runrepeat.com/{slug}"
        try:
            html = _http_get(page_url).decode("utf-8", "ignore")
        except Exception:
            continue
        # Look for a product_primary main image referenced on the page.
        m = re.search(
            r"https://cdn\.runrepeat\.com/storage/gallery/product_primary/\d+/[a-z0-9-]+-\d+-main\.jpg",
            html,
        )
        if not m:
            continue
        try:
            data = _http_get(m.group(0))
        except Exception:
            continue
        if _is_valid_image(data, min_width=1000):
            return data
    return None


# --- source: brand official og:image -------------------------------------------

BRAND_SEARCH_URLS = {
    "nike":        "https://www.nike.com/w?q={q}&vst={q}",
    "asics":       "https://www.asics.com/us/en-us/search/?q={q}",
    "hoka":        "https://www.hoka.com/en/us/search?q={q}",
    "brooks":      "https://www.brooksrunning.com/en_us/search?q={q}",
    "new balance": "https://www.newbalance.com/search/?q={q}",
    "adidas":      "https://www.adidas.com/us/search?q={q}",
    "saucony":     "https://www.saucony.com/en/search?q={q}",
    "altra":       "https://www.altrarunning.com/search?q={q}",
}


def _og_image_from_url(url: str) -> str | None:
    try:
        html = _http_get(url).decode("utf-8", "ignore")
    except Exception:
        return None
    m = re.search(
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        html,
        re.IGNORECASE,
    )
    if not m:
        m = re.search(
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
            html,
            re.IGNORECASE,
        )
    return m.group(1) if m else None


def _brand_image(brand: str, product: str) -> bytes | None:
    template = BRAND_SEARCH_URLS.get(brand.lower())
    if not template:
        return None
    q = urllib.parse.quote_plus(product)
    og = _og_image_from_url(template.format(q=q))
    if not og:
        return None
    try:
        data = _http_get(og)
    except Exception:
        return None
    return data if _is_valid_image(data) else None


# --- source: amazon ------------------------------------------------------------

def _amazon_image(brand: str, product: str) -> bytes | None:
    q = urllib.parse.quote_plus(f"{brand} {product}")
    search_url = f"https://www.amazon.com/s?k={q}&i=fashion"
    try:
        html = _http_get(search_url).decode("utf-8", "ignore")
    except Exception:
        return None
    m = re.search(r'https://m\.media-amazon\.com/images/I/[A-Za-z0-9_+\-]+\._[A-Z0-9_,]+_\.jpg', html)
    if not m:
        m = re.search(r'https://m\.media-amazon\.com/images/I/[A-Za-z0-9_+\-]+\.jpg', html)
    if not m:
        return None
    # Upgrade to large variant.
    url = re.sub(r'\._[A-Z0-9_,]+_\.jpg$', '._SL1500_.jpg', m.group(0))
    try:
        data = _http_get(url)
    except Exception:
        return None
    return data if _is_valid_image(data) else None


# --- public --------------------------------------------------------------------

def fetch_real_product_image(brand: str, product: str, output_path: Path) -> bool:
    """Try runrepeat, then brand site, then Amazon. Save valid image to output_path."""
    output_path = Path(output_path)
    for source_name, source in (
        ("runrepeat", _runrepeat_image),
        ("brand",     _brand_image),
        ("amazon",    _amazon_image),
    ):
        try:
            data = source(brand, product)
        except Exception as e:
            print(f"  [{source_name}] error: {e}", file=sys.stderr)
            continue
        if data:
            _save(data, output_path)
            print(f"  [{source_name}] saved {output_path} ({len(data)} bytes)", file=sys.stderr)
            return True
    return False


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: fetch_real_product_image.py BRAND PRODUCT OUTPUT_PATH", file=sys.stderr)
        return 2
    brand, product, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
    return 0 if fetch_real_product_image(brand, product, out) else 1


if __name__ == "__main__":
    sys.exit(main())
