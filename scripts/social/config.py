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

# Pinterest — one account per satellite site
PINTEREST_ACCOUNTS = {
    "cosmetics": {
        "email": os.getenv("PINTEREST_GLOWCODED_EMAIL", ""),
        "password": os.getenv("PINTEREST_GLOWCODED_PASSWORD", ""),
    },
    "wellness": {
        "email": os.getenv("PINTEREST_ROOTEDGLOW_EMAIL", ""),
        "password": os.getenv("PINTEREST_ROOTEDGLOW_PASSWORD", ""),
    },
}

# Pin routing: which Pinterest account posts pins for each site.
# build-coded has no dedicated Pinterest account — its pins are
# posted from the rooted-glow account.
PINTEREST_ACCOUNT_MAP = {
    "cosmetics": "cosmetics",
    "wellness": "wellness",
    "build-coded": "wellness",
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
}

# ── Rate limits ──────────────────────────────────────────────

REDDIT_MAX_PER_DAY = 8
# Per-site daily pin cap. Total = 15 (5 glow-coded + 5 rooted-glow + 5
# build-coded). The rooted-glow Pinterest account handles wellness AND
# build-coded (= 10/day/account), glow-coded account handles 5/day.
PINTEREST_MAX_PER_DAY = 5
PINTEREST_DAILY_LIMITS = {
    "cosmetics": 5,
    "wellness": 5,
    "build-coded": 5,
}

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

