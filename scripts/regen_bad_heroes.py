#!/usr/bin/env python3
"""One-off driver: regenerate the bad heroes found in the 2026-06-10 visual audit.

Reads /tmp/bad_heroes.txt (site-relative image paths). For each image:
- finds the owning EN article by matching the `image:` frontmatter field
- if the article links mirai-skin products -> gemini_enhance_hero route,
  picking a product handle NOT already used by another article's hero so
  adjacent cards never show the same bottle
- otherwise -> Imagen 4.0 with a strict no-readable-text prompt built from
  the article title

Usage: python3 scripts/regen_bad_heroes.py [--limit N]
"""
from __future__ import annotations
import argparse
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from gemini_enhance_hero import (  # noqa: E402
    client, parse_mdx, download_product_image, gemini_enhance, PRODUCT_LINK_RE, SITES,
)
from google.genai import types  # noqa: E402

from PIL import Image  # noqa: E402  (resize only, no compositing)
import io

IMAGEN_SCENES = {
    "cosmetics": "Premium K-beauty editorial photography, cream marble surface, soft natural light.",
    "wellness": "Warm natural-wellness editorial photography, linen and oak textures, soft morning light.",
    "build-coded": "Clean workshop editorial photography, birch plywood bench, soft window light.",
}

# slug -> forced product handle (comparison articles must show a compared product;
# some og:images are store placeholders that Gemini turns into fake bottles)
HANDLE_OVERRIDES = {
    "torriden-dive-in-vs-laneige-cream-skin": "torriden-dive-in-serum-50ml",
    "niacinamide-vs-vitamin-c": "cosrx-the-vitamin-c-23-serum-20ml",
    "best-korean-ampoules-2026": "round-lab-camellia-deep-collagen-firming-ampoule-30ml",
    # round-3: source photos whose labels garble on every Gemini roll -> swap to
    # products whose photos have rendered cleanly elsewhere
    "post-laser-korean-skincare-routine": "dr-jart-cicapair-intensive-soothing-repair-serum-30ml",
    "teenage-acne-k-beauty-routine": "cosrx-salicylic-acid-daily-gentle-cleanser-150ml",
    "double-cleansing-why-and-how": "cosrx-low-ph-good-morning-gel-cleanser-150ml",
    "k-beauty-night-routine-glowing-skin": "cosrx-advanced-snail-96-mucin-power-essence-100ml",
    "oil-cleansing-oily-skin": "anua-heartleaf-pore-control-cleansing-oil-200ml",
    "korean-skincare-for-runners": "beauty-joseon-relief-sun-ricex1",
    "snail-mucin-benefits-skin-barrier-science": "cosrx-advanced-snail-96-mucin-power-essence-100ml",
    "mixsoon-vs-beauty-of-joseon-minimalist-k-beauty": "beauty-of-joseon-ginseng-essence-water-150ml",
}

# slugs whose topic is not a skincare product even though the article links one
FORCE_IMAGEN = {
    "bone-broth-collagen-skin-elasticity",
    "gut-health-skin-axis-fermented-foods",
    "retinol-for-beginners-start-here",
}

NO_TEXT = (
    " IMPORTANT: absolutely no readable text anywhere in the image - no product labels, "
    "no logos, no brand names, no book spines with text, no packaging text, no signs. "
    "Any bottles, jars, tools or devices must be completely unlabeled and generic. No people's faces."
)


def imagen_generate(prompt: str, out_path: Path) -> bool:
    try:
        resp = client.models.generate_images(
            model="imagen-4.0-generate-001",
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1, aspect_ratio="16:9", output_mime_type="image/jpeg",
            ),
        )
        if not resp.generated_images:
            return False
        img = Image.open(io.BytesIO(resp.generated_images[0].image.image_bytes)).convert("RGB")
        img = img.resize((1200, 675), Image.LANCZOS)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(out_path, "JPEG", quality=92)
        return True
    except Exception as e:
        print(f"      imagen error: {e}")
        return False


def build_article_index(list_path="/tmp/bad_heroes.txt"):
    """Map (site, image-basename) -> article info, and collect handles already on good heroes."""
    index = {}
    used_handles = set()
    bad_images = {line.strip() for line in open(list_path) if line.strip()}
    bad_keys = set()
    for b in bad_images:
        site = b.split("/")[0]
        bad_keys.add((site, Path(b).name))
    for site, site_dir in SITES.items():
        for f in sorted((site_dir / "src" / "content" / "blog" / "en").glob("*.mdx")):
            fm, body = parse_mdx(f)
            if not fm:
                continue
            img_m = re.search(r"^image:\s*(\S+)", fm, re.M)
            if not img_m:
                continue
            img_name = Path(img_m.group(1)).name
            title_m = re.search(r'title:\s*"([^"]+)"', fm)
            cat_m = re.search(r"^category:\s*(\S+)", fm, re.M)
            handles = list(dict.fromkeys(PRODUCT_LINK_RE.findall(body)))
            info = {
                "site": site, "slug": f.stem,
                "title": title_m.group(1) if title_m else f.stem,
                "category": cat_m.group(1) if cat_m else "",
                "image_rel": img_m.group(1).strip(), "handles": handles,
            }
            index[(site, img_name)] = info
            # heroes that stay: their first handle is "taken"
            if (site, img_name) not in bad_keys and handles:
                used_handles.add(handles[0])
    return index, used_handles, bad_images


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--list", default="/tmp/bad_heroes.txt")
    args = ap.parse_args()

    index, used_handles, bad_images = build_article_index(args.list)
    bad = sorted(bad_images)
    if args.limit:
        bad = bad[: args.limit]

    ok, fail = 0, 0
    for rel in bad:
        site = rel.split("/")[0]
        key = (site, Path(rel).name)
        info = index.get(key)
        out_path = ROOT / rel
        if not info:
            print(f"  !! no article found for {rel} - SKIP")
            fail += 1
            continue
        print(f"  -> [{site}] {info['slug']}")

        done = False
        if info["handles"] and info["slug"] not in FORCE_IMAGEN:
            if info["slug"] in HANDLE_OVERRIDES:
                pick = HANDLE_OVERRIDES[info["slug"]]
            elif "-vs-" in info["slug"]:
                # comparison heroes must show one of the compared products
                pick = info["handles"][0]
            else:
                # pick the first handle not used by another article's hero
                pick = next((h for h in info["handles"] if h not in used_handles), info["handles"][0])
            p = download_product_image(pick)
            if p is None:
                # fall through remaining handles
                for h in info["handles"]:
                    if h == pick:
                        continue
                    p = download_product_image(h)
                    if p:
                        pick = h
                        break
            if p:
                print(f"     gemini-enhance with product: {pick}")
                done = gemini_enhance(p, out_path, site=site)
                if done:
                    used_handles.add(pick)

        if not done:
            prompt = (
                f"Editorial 16:9 landscape hero photograph for a blog article titled "
                f"\"{info['title']}\". Show the literal subject of the title as an attractive, "
                f"realistic scene. {IMAGEN_SCENES[site]}{NO_TEXT}"
            )
            print("     imagen (no-text abstract)")
            done = imagen_generate(prompt, out_path)

        if done:
            ok += 1
            print(f"     SAVED {rel}")
        else:
            fail += 1
            print(f"     FAILED {rel}")
        time.sleep(2)

    print(f"\n[done] {ok} regenerated, {fail} failed of {len(bad)}")


if __name__ == "__main__":
    main()
