#!/usr/bin/env bash
# Daily Article Publisher for Satellite Websites
# Publishes one article per site per day by removing draft: true
# Run via cron: 0 6 * * * /Users/kapi7/satellite-websites/scripts/daily-publish.sh

set -euo pipefail
cd /Users/kapi7/satellite-websites

# Pull latest to avoid conflicts
git pull --rebase --quiet origin main 2>/dev/null || true

echo "=== Daily Publish $(date) ==="

PUBLISHED=0
PUBLISHED_FILES=""

# Publish next draft from cosmetics (ordered by keyword value: vol desc, KD asc)
for article in \
  "cosmetics/src/content/blog/tirtir-cushion-foundation-shade-guide.mdx" \
  "cosmetics/src/content/blog/best-korean-moisturizers-sensitive-skin.mdx" \
  "cosmetics/src/content/blog/korean-eye-cream-guide.mdx" \
  "cosmetics/src/content/blog/best-korean-cleansing-oils.mdx" \
  "cosmetics/src/content/blog/aha-vs-bha-vs-pha-which-exfoliant.mdx" \
  "cosmetics/src/content/blog/vitamin-c-korean-skincare.mdx" \
  "cosmetics/src/content/blog/best-k-beauty-under-15.mdx" \
  "cosmetics/src/content/blog/best-anti-aging-korean-skincare-30s.mdx" \
  "cosmetics/src/content/blog/hydrating-routine-dry-winter-skin.mdx"; do
  if [ -f "$article" ] && grep -q "^draft: true" "$article"; then
    sed -i '' '/^draft: true$/d' "$article"
    echo "[Glow Coded] Published: $(basename "$article" .mdx)"
    PUBLISHED_FILES="$PUBLISHED_FILES $article"
    PUBLISHED=$((PUBLISHED + 1))
    break
  fi
done

# Publish next draft from wellness (ordered by keyword value: vol desc, KD asc)
for article in \
  "wellness/src/content/blog/best-double-cleansing-products.mdx" \
  "wellness/src/content/blog/double-cleansing-without-oil.mdx" \
  "wellness/src/content/blog/oil-cleansing-oily-skin.mdx" \
  "wellness/src/content/blog/bone-broth-benefits.mdx" \
  "wellness/src/content/blog/fermented-beetroot-kvass-probiotic-drink.mdx" \
  "wellness/src/content/blog/bone-broth-gut-health-collagen-connection.mdx" \
  "wellness/src/content/blog/korean-skincare-for-runners.mdx" \
  "wellness/src/content/blog/best-korean-products-stress-breakouts.mdx" \
  "wellness/src/content/blog/how-to-make-natural-fruit-soda.mdx" \
  "wellness/src/content/blog/heart-rate-zones-explained-train-smarter.mdx" \
  "wellness/src/content/blog/meditation-cortisol-stillness-heals-skin.mdx" \
  "wellness/src/content/blog/post-workout-k-beauty-recovery-routine.mdx"; do
  if [ -f "$article" ] && grep -q "^draft: true" "$article"; then
    sed -i '' '/^draft: true$/d' "$article"
    echo "[Rooted Glow] Published: $(basename "$article" .mdx)"
    PUBLISHED_FILES="$PUBLISHED_FILES $article"
    PUBLISHED=$((PUBLISHED + 1))
    break
  fi
done

if [ $PUBLISHED -gt 0 ]; then
  # Only stage the published articles — never git add -A
  git add $PUBLISHED_FILES
  git commit -m "Publish daily articles ($(date +%Y-%m-%d))"
  git push origin main

  if [ -f scripts/submit-indexnow.sh ]; then
    bash scripts/submit-indexnow.sh
  fi

  echo "Done! Published $PUBLISHED article(s) and deployed."
else
  echo "Nothing to publish today."
fi
