"""
Configuration for Reddit & Pinterest social automation.
Loads credentials from satellite-websites/.env
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# ── Credentials ──────────────────────────────────────────────

REDDIT_USERNAME = os.getenv("REDDIT_USERNAME", "")
REDDIT_PASSWORD = os.getenv("REDDIT_PASSWORD", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Pinterest — one account per satellite site, plus a dedicated commerce
# account for mirai-skin.com (the Shopify hub the satellites drive traffic to)
PINTEREST_ACCOUNTS = {
    "cosmetics": {
        "email": os.getenv("PINTEREST_GLOWCODED_EMAIL", ""),
        "password": os.getenv("PINTEREST_GLOWCODED_PASSWORD", ""),
    },
    "wellness": {
        "email": os.getenv("PINTEREST_ROOTEDGLOW_EMAIL", ""),
        "password": os.getenv("PINTEREST_ROOTEDGLOW_PASSWORD", ""),
    },
    "mirai": {
        "email": os.getenv("PINTEREST_MIRAI_EMAIL", ""),
        "password": os.getenv("PINTEREST_MIRAI_PASSWORD", ""),
    },
}

# Pin routing: which Pinterest account posts pins for each site.
# Each site posts ONLY to its own dedicated account so accounts stay topical
# (rooted-glow Pinterest = wellness/K-beauty crossover only, no DIY).
# build-coded has no Pinterest account yet — value is None so the schedule
# generator skips creating build-coded pins until a dedicated account exists.
# mirai uses its own dedicated commerce account.
PINTEREST_ACCOUNT_MAP = {
    "cosmetics": "cosmetics",
    "wellness": "wellness",
    "build-coded": None,  # no dedicated account yet; do NOT route to wellness
    "mirai": "mirai",
}

# ── Paths ────────────────────────────────────────────────────

SOCIAL_DIR = Path(__file__).resolve().parent
BROWSER_STATE_DIR = SOCIAL_DIR / "browser-state"
DATA_DIR = SOCIAL_DIR / "data"
REDDIT_SCHEDULE = SOCIAL_DIR / "reddit_schedule.json"
PINTEREST_SCHEDULE = SOCIAL_DIR / "pinterest_schedule.json"

COSMETICS_BLOG = PROJECT_ROOT / "cosmetics" / "src" / "content" / "blog"
WELLNESS_BLOG = PROJECT_ROOT / "wellness" / "src" / "content" / "blog"
BUILDCODED_BLOG = PROJECT_ROOT / "build-coded" / "src" / "content" / "blog"
COSMETICS_IMAGES = PROJECT_ROOT / "cosmetics" / "public" / "images"
WELLNESS_IMAGES = PROJECT_ROOT / "wellness" / "public" / "images"
BUILDCODED_IMAGES = PROJECT_ROOT / "build-coded" / "public" / "images"

# ── Site domains ─────────────────────────────────────────────

SITES = {
    "cosmetics": "glow-coded.com",
    "wellness": "rooted-glow.com",
    "build-coded": "build-coded.com",
    # Pseudo-site for Pinterest pinning to commerce hub (no local repo content)
    "mirai": "mirai-skin.com",
}

# ── Subreddit mapping by article category ────────────────────

SUBREDDIT_MAP = {
    # Cosmetics categories
    "skincare": ["SkincareAddiction", "AsianBeauty", "KoreanBeauty"],
    "ingredients": ["SkincareAddiction", "AsianBeauty"],
    "reviews": ["AsianBeauty", "SkincareAddiction", "KoreanBeauty"],
    "how-tos": ["SkincareAddiction", "AsianBeauty", "beauty"],
    # Wellness categories
    "nutrition": ["nutrition", "EatCheapAndHealthy", "fermentation"],
    "movement": ["running", "bodyweightfitness", "flexibility"],
    "k-beauty": ["AsianBeauty", "KoreanBeauty", "SkincareAddiction"],
    "natural-health": ["naturalhealth", "Meditation", "sleep"],
}

# ── Pinterest board mapping by site + category ───────────────

PINTEREST_BOARD_MAP = {
    "cosmetics": {
        "skincare": "Skincare Routines",
        "ingredients": "K-Beauty Ingredients",
        "reviews": "Product Reviews",
        "how-tos": "Skincare Tips",
    },
    "wellness": {
        "nutrition": "Nutrition & Recipes",
        "movement": "Fitness & Movement",
        "k-beauty": "Korean Beauty",
        "natural-health": "Natural Wellness",
    },
    "build-coded": {
        "woodworking": "Woodworking Projects",
        "home-improvement": "Home Improvement DIY",
        "electronics": "Electronics & Maker",
        "crafts": "DIY Crafts",
    },
    # mirai keys here are PRODUCT TYPES (from Shopify product_type field),
    # not blog categories. Boards are created on Pinterest first; the
    # poster picks the matching board name when uploading the pin.
    "mirai": {
        "sunscreen": "Best Korean Sunscreens",
        "moisturizer": "Moisturizers & Barrier Repair",
        "cleanser": "Cleansing & Double Cleanse",
        "serum": "Serums & Essences",
        "toner": "Toners & Glass Skin",
        "mask": "Masks & Treatments",
        "makeup": "K-Beauty Makeup",
        "_default": "Korean Skincare Essentials",
    },
}

# ── Rate limits ──────────────────────────────────────────────

REDDIT_MAX_PER_DAY = 50
# Per-site daily pin cap. Total = 10 (5 glow-coded + 5 rooted-glow + 0
# build-coded + 3 mirai). build-coded is set to 0 until it gets its own
# Pinterest account — DO NOT route DIY content to the rooted-glow account.
PINTEREST_MAX_PER_DAY = 5
PINTEREST_DAILY_LIMITS = {
    "cosmetics": 5,
    "wellness": 5,
    "build-coded": 0,  # paused — no dedicated Pinterest account yet
    "mirai": 3,  # commerce account: start conservative, raise after 2-week perf data
}

# Pinterest UTM parameters for mirai pins (so GA4 attributes Pinterest traffic)
PINTEREST_MIRAI_UTM = {
    "utm_source": "pinterest",
    "utm_medium": "pin",
    "utm_campaign": "organic",
    # utm_content is set per-pin to the pin slug (e.g. "pin-042")
}

# Path to the Mirai Shopify product catalog (external — outside this repo).
# Generated by mirai-meta-campaign. JSON list, ~2,746 products.
MIRAI_PRODUCT_CATALOG = Path(
    os.getenv("MIRAI_PRODUCT_CATALOG",
              "/Users/kapi7/mirai-meta-campaign/satellite-websites/.image-cache/products_catalog.json")
)
MIRAI_PIN_IMAGES_DIR = SOCIAL_DIR / "pin-images" / "mirai"

# ── Browser settings ────────────────────────────────────────

BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-first-run",
    "--no-default-browser-check",
]

# Human-like delay ranges (seconds)
DELAY_SHORT = (0.5, 1.5)
DELAY_MEDIUM = (2.0, 4.0)
DELAY_LONG = (4.0, 8.0)
DELAY_PAGE_LOAD = (3.0, 6.0)

