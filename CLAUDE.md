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
- **Hero images**: generate with AI or source editorially, save to `public/images/`
- Product images go in `public/images/products/` on BOTH sites

## Deploy
```bash
# Full deploy (build + push + IndexNow)
bash scripts/deploy.sh

# Skip specific steps
bash scripts/deploy.sh --skip-build
bash scripts/deploy.sh --skip-push
bash scripts/deploy.sh --skip-indexnow
```
