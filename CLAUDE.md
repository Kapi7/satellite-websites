# Satellite Websites — Project Guide

## Overview
Two Astro 6 static sites that drive organic traffic to **mirai-skin.com** through content marketing + affiliate links.

| Site | Domain | Focus |
|------|--------|-------|
| Glow Coded | glow-coded.com | K-beauty, skincare reviews, ingredient guides |
| Rooted Glow | rooted-glow.com | Wellness, nutrition, movement + k-beauty crossover |

## Architecture
```
satellite-websites/
├── cosmetics/          # Glow Coded (Astro)
├── wellness/           # Rooted Glow (Astro)
├── shared/             # Shared affiliate links, SEO utils, content templates
├── scripts/
│   ├── deploy.sh           # Build both → git push → IndexNow
│   ├── daily-publish.sh    # Cron: remove draft:true from next article, build, push
│   └── submit-indexnow.sh  # Submit sitemaps to Bing + Yandex
└── CLAUDE.md
```

## Tech Stack
- **Astro 6.0.8** with MDX content collections
- **Tailwind CSS 4.0.0**
- **Pagefind** for search
- **Cloudflare Pages** — auto-deploys from GitHub push
- **IndexNow** — key: `06f4ca1b5301485797bbe6c72a0f721f`

## Content Schemas

### Glow Coded (`cosmetics/src/content.config.ts`)
- Categories: `skincare | ingredients | reviews | how-tos`
- Types: `hub | guide | listicle | review | routine`

### Rooted Glow (`wellness/src/content.config.ts`)
- Categories: `nutrition | movement | k-beauty | natural-health`
- Types: `hub | guide | listicle | review | routine`

### Frontmatter fields
```yaml
title: string (required)
description: string (required)
date: date (required)
category: enum (required)
type: enum (required)
tags: string[] (default [])
image: string (optional, path like /images/hero.jpg)
imageAlt: string (optional)
draft: boolean (default false)
hub: string (optional, slug of parent hub article)
affiliateProduct: string (optional)
```

## Content Rules
- **Hub/spoke model**: child articles set `hub: parent-slug` in frontmatter
- **Cross-site links**: full URLs (`https://rooted-glow.com/slug/`)
- **Internal links**: relative paths (`/slug/`)
- **Product links**: `[![Name](/images/products/img.jpg)](https://mirai-skin.com/products/handle)`
- **NEVER** use "miraiskincare.com" — always `mirai-skin.com`
- Trailing slashes always enabled

## Publishing Workflow
1. Write articles in batches (14 days), set all but Day 1 as `draft: true`
2. Cron runs `daily-publish.sh` at 6 AM — finds next draft, removes `draft: true`, builds, pushes, IndexNow
3. Manual deploy: `bash scripts/deploy.sh`

## Image Sources
- **Product images**: downloaded from Shopify CDN via product catalog at `/Users/kapi7/mirai-meta-campaign/satellite-websites/.image-cache/products_catalog.json` (JSON list of 2746 products)
- Product images go in `public/images/products/` on BOTH sites
- **Hero images**: save to `public/images/{slug}.jpg`, 1200×675 JPEG

### Hero image rules (HARD)
- **If the article features REAL products** (any listicle, comparison, or review where named mirai-skin SKUs appear inline) → the hero MUST use the AI-enhancement pipeline so the actual product is visible, not an AI-styled fake with gibberish labels:
  - **`scripts/gemini_enhance_hero.py`** is THE canonical tool. Picks the first mirai-linked product from the article body, downloads its real Shopify photo, sends that ONE photo to Gemini 2.5 Flash Image which preserves the bottle + label pixel-perfect while building a luxurious editorial scene around it (marble surface, soft light, droplets, herbal sprigs). Works for ALL product articles — listicles, reviews, comparisons. Has `--include-published` flag for non-draft work.
  - **NEVER use `compose_hero_pil.py`** — it pre-composites multiple products via PIL which makes the bottles smaller and flatter than the single-product Gemini-enhance result the user prefers. (Quoting the user: "we said no pil just gemini enhance we send him the photo and he will enhance".)
  - The pipeline is dead-simple: one real product photo → Gemini → enhanced editorial scene. No compositing, no grids, no PIL.
- **If the article is abstract or topic-only** (ingredient explainer, how-to without specific products, hub pages) → pure Imagen 4.0 is fine
- **NEVER** ship a product-listicle hero made with raw Imagen — the labels come out as gibberish ("NIACINANE", "CLEANSING IAM", etc.) which looks AI and undermines trust
- **ALWAYS** visually verify generated heroes via Read tool before commit; Imagen has a ~14% silent-failure rate where it returns a thematically-adjacent stock photo instead of the requested subject

## Deploy
```bash
# Full deploy (build + push + IndexNow)
bash scripts/deploy.sh

# Skip specific steps
bash scripts/deploy.sh --skip-build
bash scripts/deploy.sh --skip-push
bash scripts/deploy.sh --skip-indexnow
```
