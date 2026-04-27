"""Mirai Pinterest theme catalog — 30 distinct themes for the 30-day pipe.

Each theme = 1 Pinterest pin idea. Themes can be rendered with multiple
product variants (different product subsets from the same filter) to
produce unique pin images sharing the same headline.

Schema:
  slug:           machine id, used in filenames + utm_content
  headline:       main pin headline (DM Sans Bold display)
  subhead:        smaller line (DM Sans Medium)
  product_filter: callable(product) -> bool — picks candidates from catalog
  product_count:  N products to compose into the scene
  pin_url:        destination on mirai-skin.com (collection / category)
  prompt:         styling prompt sent to Gemini 2.5 Flash Image
  cta:            small CTA chip text
  board:          Pinterest board name (must match auto-created boards)
"""
from dataclasses import dataclass


def _ptype(p): return (p.get("product_type") or "").lower()
def _title(p): return (p.get("title") or "").lower()
def _tags(p): return [str(t).lower() for t in (p.get("tags") or [])]
def _vendor(p): return (p.get("vendor") or "").lower()


# ── Atomic filters (granular product type detection) ──────────────────
def is_sunscreen(p):
    pt = _ptype(p)
    return any(k in pt for k in ["sun ", "sunscreen", "sun cream", "sun stick", "sun gel", "sun fluid", "sun essence", "spf"])

def is_moisturizer(p):
    pt = _ptype(p)
    if is_sunscreen(p): return False
    if any(k in pt for k in ["cleans", "serum", "ampoule", "toner", "mask", "patch", "cushion"]): return False
    return any(k in pt for k in ["moisturi", "lotion", "emulsion", "ceramide"]) or pt in ("cream", "face cream")

def is_cleanser(p):
    if is_sunscreen(p): return False
    return "cleans" in _ptype(p)

def is_cleansing_oil(p):
    return "cleansing oil" in _ptype(p) or "cleansing balm" in _ptype(p)

def is_foam_cleanser(p):
    pt = _ptype(p)
    return ("foam" in pt and "clean" in pt) or "cleansing gel" in pt

def is_serum(p):
    pt = _ptype(p)
    if is_sunscreen(p): return False
    return ("serum" in pt or "ampoule" in pt) and "sun" not in pt

def is_essence(p):
    pt = _ptype(p)
    return "essence" in pt and "sun" not in pt

def is_toner(p):
    return "toner" in _ptype(p)

def is_pad(p):
    return "pad" in _ptype(p)

def is_sheet_mask(p):
    """Mirai catalog lists most as 'facial mask' or 'mask pack' (sheet/wrap variants)."""
    pt = _ptype(p)
    return pt in ("facial mask", "sheet mask", "mask pack")

def is_sleeping_mask(p):
    pt = _ptype(p)
    return "sleeping" in pt and "mask" in pt

def is_clay_mask(p):
    """Wash-off / clay / mud / pack masks. Use product_type + title keywords."""
    pt = _ptype(p)
    if "mask" not in pt and "pack" not in pt: return False
    text = _title(p) + " " + " ".join(_tags(p))
    return any(k in text for k in ["clay", "mud", "wash off", "wash-off", "peel", "pack mask"])

def is_eye_cream(p):
    pt = _ptype(p)
    return "eye cream" in pt or "eye serum" in pt or "eye patch" in pt

def is_eye_patch(p):
    return "eye patch" in _ptype(p) or "eye mask" in _ptype(p)

def is_pimple_patch(p):
    return "patch" in _ptype(p) and ("acne" in _title(p) or "pimple" in _title(p) or "spot" in _title(p))

def is_lip(p):
    return "lip" in _ptype(p)

def is_cushion(p):
    return "cushion" in _ptype(p)

def is_bb_cc(p):
    return "bb cream" in _ptype(p) or "cc cream" in _ptype(p) or "bb cushion" in _ptype(p)

def is_setting_mist(p):
    return "mist" in _ptype(p)

def is_men(p):
    return "men" in _ptype(p)


# Composite filters (keyword search across title + tags)
def by_keyword(*keywords):
    """Returns a filter that matches if ANY keyword appears in title OR tags."""
    kws = [k.lower() for k in keywords]
    def f(p):
        text = _title(p) + " " + " ".join(_tags(p))
        return any(k in text for k in kws)
    return f


def has_ceramide(p): return any(k in (_title(p) + " " + " ".join(_tags(p))) for k in ["ceramide"])
def has_centella(p): return any(k in (_title(p) + " " + " ".join(_tags(p))) for k in ["centella", "cica", "heartleaf", "houttuynia"])
def has_niacinamide(p): return any(k in (_title(p) + " " + " ".join(_tags(p))) for k in ["niacinamide"])
def has_snail(p): return any(k in (_title(p) + " " + " ".join(_tags(p))) for k in ["snail", "mucin"])
def has_vitamin_c(p): return any(k in (_title(p) + " " + " ".join(_tags(p))) for k in ["vitamin c", "vita c", "vitamin-c"])
def has_retinol(p): return any(k in (_title(p) + " " + " ".join(_tags(p))) for k in ["retinol", "bakuchiol"])
def has_pdrn(p): return "pdrn" in (_title(p) + " " + " ".join(_tags(p)))
def has_propolis(p): return "propolis" in (_title(p) + " " + " ".join(_tags(p)))
def has_hyaluronic(p): return any(k in (_title(p) + " " + " ".join(_tags(p))) for k in ["hyalur", "ha "])
def _first_variant_price(p):
    for v in (p.get("variants") or []):
        if isinstance(v, dict) and v.get("price"):
            try: return float(v["price"])
            except: pass
    if p.get("price"):
        try: return float(p["price"])
        except: pass
    return None

def is_under_25(p):
    pr = _first_variant_price(p)
    return pr is not None and pr < 25

def is_under_15(p):
    pr = _first_variant_price(p)
    return pr is not None and pr < 15


def both(*fs):
    return lambda p: all(f(p) for f in fs)
def any_of(*fs):
    return lambda p: any(f(p) for f in fs)


@dataclass
class Theme:
    slug: str
    headline: str
    subhead: str
    product_filter: callable
    product_count: int
    pin_url: str
    prompt: str
    cta: str
    board: str


# Reusable scene fragments
SCENE_TAIL_PT = (
    "Create a single tall portrait 2:3 vertical Pinterest pin image (1024x1536). "
    "The products should look exactly like these reference photos — same bottles, "
    "labels, brand names, colors. Do not redraw labels or text on packaging. "
    "Premium magazine-quality flat-lay photography. Leave generous empty space at "
    "the very top 25% of the image for headline text to be added later. "
    "No text overlays, no watermarks."
)

SCENE_MARBLE = "warm cream marble surface with soft natural light from upper-left, gentle organic shadows, sprig of green leaves and a folded white linen napkin as accents"
SCENE_LINEN = "warm cream linen fabric with soft natural light, gentle wrinkle shadows, a small white ceramic dish with cream and a soft cotton round as accents"
SCENE_STONE = "warm beige stone bathroom counter with subtle water-droplet reflections, soft morning light from above, folded white washcloth and small white ceramic spoon as accents"
SCENE_TILE = "soft warm pink tile surface with morning light, small ceramic dish with white cream, fresh flower petal accent"
SCENE_GLASS = "frosted glass surface with morning sunbeams catching the texture, small dewdrops, eucalyptus leaves accent"


def make_prompt(scene: str, layout: str = "editorial asymmetry, slightly tilted, slightly overlapping") -> str:
    return (
        f"Place these Korean skincare products on {scene}. "
        f"Arrange the products with {layout} — like a high-end skincare magazine spread. "
        f"{SCENE_TAIL_PT}"
    )


# Mirai-skin.com collection URLs
COL = "https://mirai-skin.com/collections"
URL_SUN = f"{COL}/sun-protection"
URL_MOIST = f"{COL}/moisturizers"
URL_CLEAN = f"{COL}/cleansers"
URL_SERUM = f"{COL}/serums-essences-ampoule"
URL_TONER = f"{COL}/toners"
URL_MASK = f"{COL}/masks-treatments"
URL_MAKEUP = f"{COL}/makeup"
URL_ALL = f"{COL}/all-products"


# ── 30 themes for 30 days × 3 product variants each = 90 unique pins ──
THEMES: list[Theme] = [
    # ── Sunscreens ──
    Theme("sunscreens-no-white-cast", "Korean Sunscreens", "that don't leave a white cast",
          is_sunscreen, 4, URL_SUN, make_prompt(SCENE_MARBLE), "Shop the edit at Mirai", "Best Korean Sunscreens"),
    Theme("sunscreens-oily-acne", "Sunscreens for Oily Skin", "no shine, no white cast, no breakouts",
          both(is_sunscreen, any_of(by_keyword("oily", "acne", "matte", "oil-free", "sebum", "shine"), lambda p: "matte" in _ptype(p))), 4, URL_SUN,
          make_prompt(SCENE_MARBLE), "Shop the edit at Mirai", "Best Korean Sunscreens"),
    Theme("sunscreens-sensitive", "Korean SPF for Sensitive Skin", "fragrance-free, calm, daily wearable",
          both(is_sunscreen, any_of(by_keyword("sensitive", "calm", "fragrance-free"), has_centella)), 4, URL_SUN,
          make_prompt(SCENE_LINEN), "Shop the edit at Mirai", "Best Korean Sunscreens"),
    Theme("sun-sticks", "Korean Sun Sticks", "the on-the-go SPF you'll actually reapply",
          both(is_sunscreen, by_keyword("stick")), 4, URL_SUN,
          make_prompt(SCENE_MARBLE), "Shop the edit at Mirai", "Best Korean Sunscreens"),

    # ── Moisturizers ──
    Theme("moisturizers-sensitive", "Korean Moisturizers", "for sensitive, reactive skin",
          is_moisturizer, 4, URL_MOIST,
          make_prompt(SCENE_LINEN), "Shop the edit at Mirai", "Moisturizers & Barrier Repair"),
    Theme("ceramide-moisturizers", "Ceramide Moisturizers", "for barrier repair you can feel",
          both(is_moisturizer, has_ceramide), 4, URL_MOIST,
          make_prompt(SCENE_LINEN), "Shop the edit at Mirai", "Moisturizers & Barrier Repair"),
    Theme("centella-moisturizers", "Centella Moisturizers", "for redness, recovery, calm skin",
          both(is_moisturizer, has_centella), 4, URL_MOIST,
          make_prompt(SCENE_GLASS), "Shop the edit at Mirai", "Moisturizers & Barrier Repair"),
    Theme("snail-moisturizers", "Snail Mucin Picks", "the K-beauty cult ingredient",
          has_snail, 4, URL_MOIST,
          make_prompt(SCENE_MARBLE), "Shop the edit at Mirai", "Moisturizers & Barrier Repair"),

    # ── Cleansers ──
    Theme("double-cleanse", "The Double Cleanse", "four Korean cleansers worth keeping",
          is_cleanser, 4, URL_CLEAN,
          make_prompt(SCENE_STONE), "Shop the edit at Mirai", "Cleansing & Double Cleanse"),
    Theme("cleansing-oils", "Korean Cleansing Oils", "step one of the K-beauty routine",
          is_cleansing_oil, 4, URL_CLEAN,
          make_prompt(SCENE_GLASS), "Shop the edit at Mirai", "Cleansing & Double Cleanse"),
    Theme("foam-cleansers", "Korean Foam Cleansers", "step two: gentle, low-pH, low-stripping",
          is_foam_cleanser, 4, URL_CLEAN,
          make_prompt(SCENE_STONE), "Shop the edit at Mirai", "Cleansing & Double Cleanse"),
    Theme("cleansers-sensitive", "Cleansers for Sensitive Skin", "no fragrance, no sting, no tightness",
          both(is_cleanser, any_of(by_keyword("sensitive", "gentle"), has_centella)), 4, URL_CLEAN,
          make_prompt(SCENE_LINEN), "Shop the edit at Mirai", "Cleansing & Double Cleanse"),

    # ── Serums & essences ──
    Theme("vitamin-c-serums", "Vitamin C Korean Serums", "brighten, even tone, glass-skin glow",
          both(is_serum, has_vitamin_c), 4, URL_SERUM,
          make_prompt(SCENE_MARBLE), "Shop the edit at Mirai", "Serums & Essences"),
    Theme("niacinamide-serums", "Niacinamide Serums", "for dark spots and pore texture",
          both(any_of(is_serum, is_essence), has_niacinamide), 4, URL_SERUM,
          make_prompt(SCENE_TILE), "Shop the edit at Mirai", "Serums & Essences"),
    Theme("snail-essences", "Snail Mucin Essences", "barrier-friendly hydration",
          both(any_of(is_serum, is_essence), has_snail), 4, URL_SERUM,
          make_prompt(SCENE_GLASS), "Shop the edit at Mirai", "Serums & Essences"),
    Theme("retinol-bakuchiol", "Retinol & Bakuchiol", "anti-aging without the irritation",
          both(any_of(is_serum, is_essence), has_retinol), 4, URL_SERUM,
          make_prompt(SCENE_LINEN), "Shop the edit at Mirai", "Serums & Essences"),
    Theme("pdrn-serums", "PDRN Skincare", "the salmon-DNA ingredient everyone is talking about",
          has_pdrn, 4, URL_SERUM,
          make_prompt(SCENE_MARBLE), "Shop the edit at Mirai", "Serums & Essences"),
    Theme("propolis-essences", "Propolis Picks", "the K-beauty hydrator with antioxidant power",
          has_propolis, 4, URL_SERUM,
          make_prompt(SCENE_TILE), "Shop the edit at Mirai", "Serums & Essences"),

    # ── Toners ──
    Theme("toners-glass-skin", "Toners for Glass Skin", "the K-beauty step nobody talks about",
          is_toner, 4, URL_TONER,
          make_prompt(SCENE_GLASS), "Shop the edit at Mirai", "Toners & Glass Skin"),
    Theme("toners-pads", "Korean Toner Pads", "single-step exfoliation that works",
          is_pad, 4, URL_TONER,
          make_prompt(SCENE_MARBLE), "Shop the edit at Mirai", "Toners & Glass Skin"),

    # ── Masks ──
    Theme("sheet-masks", "Korean Sheet Masks", "the at-home spa step",
          is_sheet_mask, 4, URL_MASK,
          make_prompt(SCENE_LINEN), "Shop the edit at Mirai", "Masks & Treatments"),
    Theme("sleeping-masks", "Sleeping Masks", "skincare that works while you sleep",
          is_sleeping_mask, 4, URL_MASK,
          make_prompt(SCENE_LINEN), "Shop the edit at Mirai", "Masks & Treatments"),
    Theme("eye-patches", "Korean Eye Patches", "depuff, hydrate, brighten — under-eye in 15 minutes",
          any_of(is_eye_cream, is_eye_patch), 4, URL_MASK,
          make_prompt(SCENE_MARBLE), "Shop the edit at Mirai", "Masks & Treatments"),
    Theme("clay-masks", "Wash-Off Korean Masks", "for pores, oil control, skin reset",
          is_clay_mask, 4, URL_MASK,
          make_prompt(SCENE_STONE), "Shop the edit at Mirai", "Masks & Treatments"),

    # ── Makeup ──
    Theme("cushions", "Korean Cushion Foundations", "your-skin-but-better in one compact",
          is_cushion, 4, URL_MAKEUP,
          make_prompt(SCENE_TILE), "Shop the edit at Mirai", "K-Beauty Makeup"),
    Theme("bb-cc-creams", "BB & CC Creams", "lightweight skin-tints with skincare benefits",
          is_bb_cc, 4, URL_MAKEUP,
          make_prompt(SCENE_TILE), "Shop the edit at Mirai", "K-Beauty Makeup"),
    Theme("lip-products", "K-Beauty Lip Picks", "tinted balms, lacquers, sleeping masks",
          is_lip, 4, URL_MAKEUP,
          make_prompt(SCENE_MARBLE), "Shop the edit at Mirai", "K-Beauty Makeup"),

    # ── Cross-category curations (Korean Skincare Essentials) ──
    Theme("glass-skin-routine", "Glass Skin in 5 Products", "the routine that gets you there",
          any_of(is_toner, is_essence, has_snail, is_moisturizer, is_sunscreen), 5, URL_ALL,
          make_prompt(SCENE_GLASS), "Shop the edit at Mirai", "Korean Skincare Essentials"),
    Theme("kbeauty-under-25", "K-Beauty Under $25", "real picks, no compromise",
          is_under_25, 5, URL_ALL,
          make_prompt(SCENE_MARBLE), "Shop the edit at Mirai", "Korean Skincare Essentials"),
    Theme("anti-aging-30s", "Anti-Aging Korean Picks", "the routine for your 30s",
          any_of(both(is_serum, has_retinol), both(is_moisturizer, has_ceramide), has_pdrn), 5, URL_ALL,
          make_prompt(SCENE_LINEN), "Shop the edit at Mirai", "Korean Skincare Essentials"),
]
