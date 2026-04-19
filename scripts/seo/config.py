"""
SEO Backlink Automation — Configuration
Loads credentials from satellite-websites/.env
"""

import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# ── Site mapping ────────────────────────────────────────────

SITES = {
    "glow-coded": {
        "domain": "glow-coded.com",
        "name": "Glow Coded",
        "tagline": "K-Beauty Ingredient Research & Reviews",
        "email": os.getenv("OUTREACH_GLOWCODED_EMAIL", "info@albert-capital.com"),
        "niche": "K-beauty, skincare ingredients, Korean skincare routines",
        "topics": [
            "Korean beauty", "K-beauty", "skincare routine", "skincare",
            "skincare ingredients", "niacinamide", "retinol", "snail mucin",
            "sunscreen", "SPF", "glass skin", "skin barrier", "skin care",
            "anti-aging", "acne", "sensitive skin", "beauty routine",
            "moisturizer", "serum", "cleanser", "toner", "exfoliat",
            "wrinkle", "collagen", "hyaluronic", "vitamin C skin",
            "beauty tips", "cosmetics", "dermatolog",
        ],
    },
    "rooted-glow": {
        "domain": "rooted-glow.com",
        "name": "Rooted Glow",
        "tagline": "Where Wellness Meets Skin Health",
        "email": os.getenv("OUTREACH_ROOTEDGLOW_EMAIL", "avi@albert-capital.com"),
        "niche": "Gut-skin connection, ancestral nutrition, holistic wellness",
        "topics": [
            "gut health", "microbiome", "gut skin connection",
            "fermented foods", "adaptogens", "holistic health",
            "ancestral eating", "seed oils", "wellness routine",
            "sleep", "stress", "nutrition", "diet", "wellness",
            "running", "fitness", "exercise", "yoga", "meditation",
            "supplements", "vitamins", "probiotics", "inflammation",
            "mental health", "self-care", "healthy eating",
            "weight loss", "hormone", "immune system",
        ],
    },
    "build-coded": {
        "domain": "build-coded.com",
        "name": "Build Coded",
        "tagline": "DIY Projects, Decoded",
        "email": os.getenv("OUTREACH_BUILDCODED_EMAIL", ""),
        "niche": "DIY tutorials, woodworking, home improvement, electronics, crafts",
        "topics": [
            "DIY", "woodworking", "home improvement",
            "power tools", "hand tools", "workbench",
            "electronics projects", "Arduino", "Raspberry Pi",
            "3D printing", "epoxy resin", "furniture",
            "renovation", "smart home", "contractor",
            "plumbing", "electrical", "paint", "flooring",
            "garden", "outdoor", "patio", "deck",
            "repair", "remodel", "workshop", "crafts",
            "home project", "budget home", "tool review",
        ],
    },
}

# ── Account credentials ─────────────────────────────────────

ACCOUNTS = {
    "glow-coded": {
        "email": os.getenv("OUTREACH_GLOWCODED_EMAIL", "info@albert-capital.com"),
        "password": os.getenv("OUTREACH_GLOWCODED_PASSWORD",
                              os.getenv("PINTEREST_GLOWCODED_PASSWORD", "")),
        "first_name": "Emma",
        "last_name": "Rob",
        "display_name": "Emma Rob",
        "title": "Beauty Editor",
        "bio": "K-beauty ingredient researcher and skincare writer at Glow Coded. Covering Korean skincare science, ingredient analysis, and routine building.",
    },
    "rooted-glow": {
        "email": os.getenv("OUTREACH_ROOTEDGLOW_EMAIL", "avi@albert-capital.com"),
        "password": os.getenv("OUTREACH_ROOTEDGLOW_PASSWORD",
                              os.getenv("PINTEREST_ROOTEDGLOW_PASSWORD", "")),
        "first_name": "Mika",
        "last_name": "Shine",
        "display_name": "Mika Shine",
        "title": "Wellness Editor",
        "bio": "Wellness writer at Rooted Glow. Covering gut-skin science, ancestral nutrition, holistic health, and movement for everyday wellness.",
    },
    "build-coded": {
        "email": os.getenv("OUTREACH_BUILDCODED_EMAIL", ""),
        "password": os.getenv("OUTREACH_BUILDCODED_PASSWORD", ""),
        "first_name": "Jake",
        "last_name": "Miller",
        "display_name": "Jake Miller",
        "title": "DIY Editor",
        "bio": "DIY and maker writer at Build Coded. Covering woodworking, home improvement, electronics, and hands-on project tutorials.",
    },
}

# ── SMTP for outreach emails ────────────────────────────────

SMTP_CONFIG = {
    "glow-coded": {
        "server": os.getenv("SMTP_GLOWCODED_SERVER", ""),
        "port": int(os.getenv("SMTP_GLOWCODED_PORT", "587")),
        "email": os.getenv("OUTREACH_GLOWCODED_EMAIL", "info@albert-capital.com"),
        "password": os.getenv("SMTP_GLOWCODED_PASSWORD", ""),
    },
    "rooted-glow": {
        "server": os.getenv("SMTP_ROOTEDGLOW_SERVER", ""),
        "port": int(os.getenv("SMTP_ROOTEDGLOW_PORT", "587")),
        "email": os.getenv("OUTREACH_ROOTEDGLOW_EMAIL", "avi@albert-capital.com"),
        "password": os.getenv("SMTP_ROOTEDGLOW_PASSWORD", ""),
    },
    "build-coded": {
        "server": os.getenv("SMTP_BUILDCODED_SERVER", ""),
        "port": int(os.getenv("SMTP_BUILDCODED_PORT", "587")),
        "email": os.getenv("OUTREACH_BUILDCODED_EMAIL", ""),
        "password": os.getenv("SMTP_BUILDCODED_PASSWORD", ""),
    },
}

# ── IMAP for reading verification / HARO digests ────────────

IMAP_CONFIG = {
    "glow-coded": {
        "server": os.getenv("IMAP_GLOWCODED_SERVER", ""),
        "email": os.getenv("OUTREACH_GLOWCODED_EMAIL", "info@albert-capital.com"),
        "password": os.getenv("IMAP_GLOWCODED_PASSWORD", ""),
    },
    "rooted-glow": {
        "server": os.getenv("IMAP_ROOTEDGLOW_SERVER", ""),
        "email": os.getenv("OUTREACH_ROOTEDGLOW_EMAIL", "avi@albert-capital.com"),
        "password": os.getenv("IMAP_ROOTEDGLOW_PASSWORD", ""),
    },
    "build-coded": {
        "server": os.getenv("IMAP_BUILDCODED_SERVER", ""),
        "email": os.getenv("OUTREACH_BUILDCODED_EMAIL", ""),
        "password": os.getenv("IMAP_BUILDCODED_PASSWORD", ""),
    },
}

# ── Ahrefs API ──────────────────────────────────────────────

AHREFS_API_KEY = os.getenv("AHREFS_API_KEY", "")
AHREFS_BASE = "https://api.ahrefs.com/v3"

# Competitor domains to monitor for broken backlinks
COMPETITORS = {
    "glow-coded": [
        "sokoglam.com", "theklog.co", "peachandlily.com",
        "fiftyshadesofsnail.com", "snowwhiteandtheasianpear.com",
        "skincarebykari.com",
    ],
    "rooted-glow": [
        "wellnessmama.com", "marksdailyapple.com", "chriskresser.com",
        "paleoleap.com", "draxe.com",
    ],
    "build-coded": [
        "familyhandyman.com", "instructables.com", "woodmagazine.com",
        "thisoldhouse.com", "makezine.com",
        "popularmechanics.com", "diynetwork.com", "bobvila.com",
        "finewoodworking.com", "woodworkersjournal.com", "hackaday.com",
        "adafruit.com", "sparkfun.com", "hometalk.com",
    ],
}

# ── Gemini API for AI drafting ──────────────────────────────

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# ── Paths ───────────────────────────────────────────────────

SEO_DIR = Path(__file__).resolve().parent
OUTREACH_QUEUE = SEO_DIR / "outreach_queue.json"
OUTREACH_LOG = SEO_DIR / "outreach_log.json"
SIGNUP_STATUS = SEO_DIR / "signup_status.json"
BROWSER_STATE_DIR = SEO_DIR / "browser-state"

# ── Platforms to sign up on ─────────────────────────────────

SIGNUP_PLATFORMS = {
    "connectively": {
        "url": "https://www.connectively.us/signup",
        "type": "haro",
        "both_sites": True,
    },
    "qwoted": {
        "url": "https://www.qwoted.com/signup",
        "type": "haro",
        "both_sites": True,
    },
    "featured": {
        "url": "https://featured.com/signup",
        "type": "haro",
        "both_sites": True,
    },
    "terkel": {
        "url": "https://terkel.io/signup",
        "type": "haro",
        "both_sites": True,
    },
    "sourcebottle": {
        "url": "https://www.sourcebottle.com/register",
        "type": "haro",
        "both_sites": True,
    },
    "medium": {
        "url": "https://medium.com/m/signin",
        "type": "syndication",
        "both_sites": True,
    },
    "flipboard": {
        "url": "https://flipboard.com/signup",
        "type": "directory",
        "both_sites": True,
    },
    "bloglovin": {
        "url": "https://www.bloglovin.com/register",
        "type": "directory",
        "both_sites": True,
    },
    "blogarama": {
        "url": "https://www.blogarama.com/register",
        "type": "directory",
        "both_sites": True,
    },
    "feedspot": {
        "url": "https://www.feedspot.com/signup",
        "type": "directory",
        "both_sites": True,
    },
    "gravatar": {
        "url": "https://gravatar.com/signup",
        "type": "profile",
        "both_sites": True,
    },
    "aboutme": {
        "url": "https://about.me/signup",
        "type": "profile",
        "both_sites": True,
    },
}

# ── Resource page search queries ────────────────────────────

RESOURCE_SEARCHES = {
    "glow-coded": [
        '"skincare" "resources" inurl:resources',
        '"K-beauty" "useful links" OR "recommended sites"',
        '"skincare ingredients" "resources" OR "tools"',
        '"best skincare blogs" 2025 OR 2026',
        'allintitle: skincare ingredient checker tools',
        '"beauty school" "student resources" skincare',
        '"korean skincare" "resource" OR "guide" OR "links"',
    ],
    "rooted-glow": [
        '"gut health" "resources" inurl:resources',
        '"wellness blogs" "resources" intitle:resources',
        '"holistic health" "recommended reading"',
        '"ancestral health" "links" OR "blogroll"',
        '"running for beginners" "resources"',
        '"nutrition" "recommended blogs" OR "blogroll"',
        '"fermented foods" "resources" OR "guide"',
    ],
    "build-coded": [
        '"woodworking" "resources" inurl:resources',
        '"DIY" "recommended tools" OR "tool list"',
        '"home improvement" "resources" OR "links"',
        '"maker" "blogroll" OR "recommended blogs"',
        '"Arduino projects" "resources" OR "links"',
        '"woodworking blogs" "resources" 2025 OR 2026',
        '"DIY electronics" "resources" OR "beginners guide"',
        '"home renovation" "resources" inurl:resources',
        '"power tools" "recommended" OR "tool guide"',
        '"3D printing" "resources" OR "links"',
        '"DIY projects" "blogroll" OR "favorite blogs"',
        '"epoxy resin" "resources" OR "tutorials"',
        '"homesteading" "resources" inurl:resources',
        '"smart home" "DIY" "resources"',
        'allintitle: best DIY blogs 2025 OR 2026',
        '"handyman" "resources" OR "links"',
        '"workshop" "tool list" OR "recommended"',
    ],
}

# ── Browser settings ────────────────────────────────────────

BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-first-run",
    "--no-default-browser-check",
]

DELAY_SHORT = (0.5, 1.5)
DELAY_MEDIUM = (2.0, 4.0)
DELAY_LONG = (4.0, 8.0)
DELAY_PAGE_LOAD = (3.0, 6.0)
