# Satellite Websites — Next Steps

## Current Status (March 29, 2026)
- **Batch 1 published**: 28 articles (14 per site), Days 1 live, Days 2-14 scheduled via cron
- **Cron active**: `0 6 * * *` runs daily-publish.sh — one article per site per day
- **Batch 1 ends**: April 11, 2026 (Day 14)
- **Next batch needed by**: April 8 (3 days buffer to write Batch 2)

---

## Immediate (This Week)

### 1. Replace Placeholder Hero Images
The 28 hero images are copies of existing ones. Generate proper unique images:
- **Cosmetics**: Use product photos → Gemini enhance → editorial flatlay style
- **Wellness**: Use Gemini Imagen 4.0 → lifestyle editorial photos
- Drop in with the **same filenames** — no code changes needed
- Files: `cosmetics/public/images/` and `wellness/public/images/`

### 2. Google Search Console
- [ ] Verify both domains in GSC if not already done
- [ ] Submit sitemaps: `glow-coded.com/sitemap-index.xml` and `rooted-glow.com/sitemap-index.xml`
- [ ] Check indexing status in 3-5 days — ensure new URLs are being picked up
- [ ] Monitor "Pages" report for any crawl errors or excluded pages

### 3. Verify Daily Publish Cron
- [ ] Check `scripts/publish.log` tomorrow after 6 AM to confirm Day 2 published
- [ ] Verify the sites updated on Cloudflare

---

## Week 2 (April 1-7)

### 4. Plan Batch 2 Content Calendar
Write the next 14-day batch for both sites (Days 15-28). Priorities:
- **Glow Coded**: Fill gaps — no content yet on sheet masks deep-dive, double cleansing guide, Korean lip care, SPF reapplication guide, serum layering advanced
- **Rooted Glow**: Fill gaps — yoga for beginners, cold exposure/ice bath guide, sleep optimization, magnesium guide, gut-friendly meal prep
- Continue cross-linking between both sites and to mirai-skin.com products

### 5. Ahrefs Baseline
- [ ] Pull DR, backlinks, referring domains for both sites
- [ ] Identify which keywords (if any) are starting to rank
- [ ] Run content gap analysis vs competitor K-beauty content sites

### 6. Internal Linking Audit
- [ ] Ensure all existing articles cross-link properly
- [ ] Update hub pages with links to new spoke articles as they go live
- [ ] Add "Related Articles" links at bottom of each post

---

## Week 3-4 (April 8-18)

### 7. Write & Schedule Batch 2
- Same process: write 14 articles per site, set as draft, daily-publish.sh handles the rest
- Update `daily-publish.sh` with the new article paths

### 8. Performance Review
- [ ] GSC: Which pages are indexed? Which have impressions?
- [ ] Any pages with impressions but low CTR? → Rewrite titles/descriptions
- [ ] Which categories are getting traction? → Double down on those

### 9. Backlink Building
- [ ] Guest post opportunities in K-beauty/wellness spaces
- [ ] Reddit/forum distribution (genuine value, not spam)
- [ ] Submit to relevant directories and aggregators

---

## Month 2-3 (April-May)

### 10. Scale Content
- Target: 100+ articles per site by end of May
- Continue daily publishing cadence
- Add new content types: product comparisons, "alternatives to" posts, seasonal guides

### 11. Monetization Optimization
- [ ] Track which articles drive the most clicks to mirai-skin.com
- [ ] A/B test CTA placements and product image positions
- [ ] Add more product links to high-traffic articles

### 12. Technical Improvements
- [ ] Add structured data (Article schema, FAQ schema) if not already present
- [ ] Improve page speed scores
- [ ] Add author pages with E-E-A-T signals
- [ ] Consider adding a newsletter signup

---

## Content Batch Tracker

| Batch | Articles | Dates | Status |
|-------|----------|-------|--------|
| 1 | 28 (14+14) | Mar 29 — Apr 11 | ACTIVE (publishing daily) |
| 2 | TBD | Apr 12 — Apr 25 | NOT STARTED — plan by Apr 8 |
| 3 | TBD | Apr 26 — May 9 | NOT STARTED |
