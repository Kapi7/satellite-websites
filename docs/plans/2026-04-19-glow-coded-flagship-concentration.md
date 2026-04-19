# Glow-Coded — Flagship Concentration Plan

**Date:** 2026-04-19
**Context:** Ahrefs DR 10, 22 refdomains, 0 US organic keywords in Ahrefs index. GSC shows thin long-tail impressions across ~60 URLs, no single page has earned page-1 authority. Strategy to date has been broad publishing; this plan replaces it with a concentration play.

## Thesis

At DR 10, SEO link equity must be **concentrated**, not **scattered**. Every internal link, every new backlink anchor, and every editorial mention should point at 3 flagship URLs until one of them breaks into top-10 for a money term. One flagship in top-10 is worth 50 articles at pos 40.

## The 3 flagships

Selected by intersection of: (a) commercial intent toward mirai-skin.com, (b) current GSC striking-distance signal, (c) defensible content depth already on page.

| # | URL | Primary keyword | Current GSC pos | Target pos |
|---|---|---|---|---|
| 1 | `/best-korean-sunscreens-oily-skin-no-white-cast/` | best korean sunscreen for oily skin | ~22 | **top 10 in 90d** |
| 2 | `/best-korean-moisturizers-sensitive-skin/` | korean moisturizer for sensitive skin | ~13 | **top 5 in 90d** |
| 3 | `/cosrx-snail-mucin-vs-torriden-dive-in-serum/` | cosrx vs torriden | ~9 | **top 3 in 60d** |

Flagship #3 is the fastest path to a win — already pos 9 with strong commercial-comparison intent.

## Tactics (in execution order)

### Phase A — Internal link concentration (this week)

1. **Audit every blog post** on glow-coded for outbound internal links. Redirect 80% of "related reading" and in-body contextual links to flow into the 3 flagships via natural anchor text.
2. **Hub landing pages** (`/category/skincare/`, `/category/reviews/`) — add a prominent above-the-fold card for each flagship.
3. **Homepage** — ensure all 3 flagships appear in "This week in the feed" or top category rails for 30 days.
4. **Cross-site links from rooted-glow** — each flagship gets 2 new contextual links from relevant rooted-glow articles (snail mucin, sunscreen, sensitive skin pieces).

Exit criteria: every flagship has ≥15 internal inbound links with primary-keyword-aligned anchors.

### Phase B — Backlink anchor concentration (next 2 weeks)

Edit `scripts/seo/backlink_autopilot.py` outreach templates so **every new glow-coded pitch** requests a link to one of the 3 flagships (rotate). Stop pitching for homepage or other article links until the 3 are each at 15+ referring domains.

- Current: 22 refdomains spread across ~10 URLs.
- Target: 15 refdomains each to the 3 flagships = 45 concentrated, within 60 days.

### Phase C — Content sharpening (next 2 weeks)

For each flagship:
- Add TL;DR "Quick Answer" block at top (answer-first ranks better at pos 8–20).
- Add comparison section capturing long-tail intent (e.g. "vs", "worth it", "safe for").
- Expand FAQ with 8–12 keyword-rich questions for FAQ schema harvest.
- Update `date:` frontmatter to trigger Google recrawl.
- Verify product images and mirai-skin.com affiliate links are present.

Pattern proven on `snail-mucin-everything-you-need-to-know.mdx` (rooted-glow) on 2026-04-19.

### Phase D — External signal amplification (ongoing)

- Pinterest pins: 3 new pins per flagship per week, all pointing to the flagship URL.
- Reddit: targeted comment contributions in `/r/SkincareAddiction`, `/r/AsianBeauty` linking flagships when relevant.
- Newsletter: feature one flagship per edition as the anchor article.

## What to stop doing

- Publishing net-new glow-coded articles until any flagship crosses pos 10. Every writer-hour currently spent on new posts is diverted from concentration work.
- Outreach for non-flagship URLs (except the 3 already-queued HARO campaigns).
- Refreshing articles outside the 3 flagships.

## Measurement

Check **weekly** (not daily — noise floor too high):
- GSC position for the 3 primary keywords
- Ahrefs refdomain count on each flagship URL
- GSC impressions on each flagship

Success: one flagship crosses pos 10 in GSC by 2026-06-01. If none do, the thesis is wrong and we revisit.

## Files to touch when executing

- `cosmetics/src/pages/index.astro` (homepage rails)
- `cosmetics/src/content/blog/en/best-korean-sunscreens-oily-skin-no-white-cast.mdx`
- `cosmetics/src/content/blog/en/best-korean-moisturizers-sensitive-skin.mdx`
- `cosmetics/src/content/blog/en/cosrx-snail-mucin-vs-torriden-dive-in-serum.mdx`
- `scripts/seo/backlink_autopilot.py` (pitch templates if they hardcode URLs)
- `scripts/social/` (Pinterest/Reddit schedules)
