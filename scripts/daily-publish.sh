#!/usr/bin/env bash
# Daily Article Publisher for Satellite Websites
# Publishes one article per site per day by removing draft: true
# Run via cron: 0 6 * * * /Users/kapi7/satellite-websites/scripts/daily-publish.sh

set -euo pipefail
cd "$(dirname "$0")/.."

# Load environment variables
set -a; source .env 2>/dev/null; set +a
# Pull latest to avoid conflicts
git pull --rebase --quiet origin main 2>/dev/null || true

echo "=== Daily Publish $(date) ==="

PUBLISHED=0
PUBLISHED_FILES=""

# Publish next draft from cosmetics (ordered by keyword value: vol desc, KD asc)
# Note: articles are now in blog/en/ subdirectory
for article in \
  "cosmetics/src/content/blog/en/tirtir-cushion-foundation-shade-guide.mdx" \
  "cosmetics/src/content/blog/en/best-korean-moisturizers-sensitive-skin.mdx" \
  "cosmetics/src/content/blog/en/korean-eye-cream-guide.mdx" \
  "cosmetics/src/content/blog/en/best-korean-cleansing-oils.mdx" \
  "cosmetics/src/content/blog/en/aha-vs-bha-vs-pha-which-exfoliant.mdx" \
  "cosmetics/src/content/blog/en/vitamin-c-korean-skincare.mdx" \
  "cosmetics/src/content/blog/en/best-k-beauty-under-15.mdx" \
  "cosmetics/src/content/blog/en/best-anti-aging-korean-skincare-30s.mdx" \
  "cosmetics/src/content/blog/en/hydrating-routine-dry-winter-skin.mdx"; do
  if [ -f "$article" ] && grep -q "^draft: true" "$article"; then
    if [[ "$OSTYPE" == darwin* ]]; then
      sed -i '' '/^draft: true$/d' "$article"
    else
      sed -i '/^draft: true$/d' "$article"
    fi
    echo "[Glow Coded] Published: $(basename "$article" .mdx)"
    PUBLISHED_FILES="$PUBLISHED_FILES $article"
    PUBLISHED=$((PUBLISHED + 1))
    break
  fi
done

# Publish next draft from wellness (ordered by keyword value: vol desc, KD asc)
for article in \
  "wellness/src/content/blog/en/best-double-cleansing-products.mdx" \
  "wellness/src/content/blog/en/double-cleansing-without-oil.mdx" \
  "wellness/src/content/blog/en/oil-cleansing-oily-skin.mdx" \
  "wellness/src/content/blog/en/bone-broth-benefits.mdx" \
  "wellness/src/content/blog/en/fermented-beetroot-kvass-probiotic-drink.mdx" \
  "wellness/src/content/blog/en/bone-broth-gut-health-collagen-connection.mdx" \
  "wellness/src/content/blog/en/korean-skincare-for-runners.mdx" \
  "wellness/src/content/blog/en/best-korean-products-stress-breakouts.mdx" \
  "wellness/src/content/blog/en/how-to-make-natural-fruit-soda.mdx" \
  "wellness/src/content/blog/en/heart-rate-zones-explained-train-smarter.mdx" \
  "wellness/src/content/blog/en/meditation-cortisol-stillness-heals-skin.mdx" \
  "wellness/src/content/blog/en/post-workout-k-beauty-recovery-routine.mdx"; do
  if [ -f "$article" ] && grep -q "^draft: true" "$article"; then
    if [[ "$OSTYPE" == darwin* ]]; then
      sed -i '' '/^draft: true$/d' "$article"
    else
      sed -i '/^draft: true$/d' "$article"
    fi
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
  git pull --rebase --quiet origin main 2>/dev/null || true
  git push origin main

  # Auto-translate newly published articles to all 6 locales
  TRANSLATE_SCRIPT="scripts/translate-content.py"
  if [ -f "$TRANSLATE_SCRIPT" ]; then
    echo "Running auto-translation for published articles..."
    for f in $PUBLISHED_FILES; do
      site=$(echo "$f" | cut -d/ -f1)
      python3 "$TRANSLATE_SCRIPT" --site "$site" --articles-only 2>&1 | tail -5 || true
    done
  fi

  if [ -f scripts/submit-indexnow.sh ]; then
    bash scripts/submit-indexnow.sh
  fi

  echo "Done! Published $PUBLISHED article(s) and deployed."
else
  echo "Nothing to publish today."
fi
