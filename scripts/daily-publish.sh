#!/usr/bin/env bash
# Daily Article Publisher for Satellite Websites
# Publishes one article per site per day by removing draft: true
# Also removes draft: true from all translated versions (es, de, el, ru, it, ar)

set -euo pipefail
cd "$(dirname "$0")/.."

# Load environment variables
set -a; source .env 2>/dev/null; set +a
# Pull latest to avoid conflicts
git pull --rebase --quiet origin main 2>/dev/null || true

echo "=== Daily Publish $(date) ==="

LOCALES="es de el ru it ar"
PUBLISHED=0
PUBLISHED_FILES=""

# Helper: remove draft: true from a file (cross-platform sed)
undraft() {
  local f="$1"
  if [[ "$OSTYPE" == darwin* ]]; then
    sed -i '' '/^draft: true$/d' "$f"
  else
    sed -i '/^draft: true$/d' "$f"
  fi
}

# Helper: undraft English article + all its translations
publish_article() {
  local article="$1"
  local label="$2"
  local filename
  filename=$(basename "$article")
  local blog_base
  blog_base=$(dirname "$(dirname "$article")")  # e.g. cosmetics/src/content/blog

  undraft "$article"
  echo "[$label] Published: $(basename "$article" .mdx)"
  PUBLISHED_FILES="$PUBLISHED_FILES $article"

  # Also undraft all translated versions
  for lang in $LOCALES; do
    local i18n_file="$blog_base/$lang/$filename"
    if [ -f "$i18n_file" ] && grep -q "^draft: true" "$i18n_file"; then
      undraft "$i18n_file"
      PUBLISHED_FILES="$PUBLISHED_FILES $i18n_file"
      echo "  [$label] Undrafted $lang translation"
    fi
  done
}

# Publish next draft from cosmetics (ordered by keyword value: vol desc, KD asc)
for article in \
  "cosmetics/src/content/blog/en/tirtir-cushion-foundation-shade-guide.mdx" \
  "cosmetics/src/content/blog/en/best-korean-moisturizers-sensitive-skin.mdx" \
  "cosmetics/src/content/blog/en/korean-eye-cream-guide.mdx" \
  "cosmetics/src/content/blog/en/best-korean-cleansing-oils.mdx" \
  "cosmetics/src/content/blog/en/aha-vs-bha-vs-pha-which-exfoliant.mdx" \
  "cosmetics/src/content/blog/en/vitamin-c-korean-skincare.mdx" \
  "cosmetics/src/content/blog/en/best-k-beauty-under-15.mdx" \
  "cosmetics/src/content/blog/en/best-anti-aging-korean-skincare-30s.mdx" \
  "cosmetics/src/content/blog/en/hydrating-routine-dry-winter-skin.mdx" \
  "cosmetics/src/content/blog/en/best-ceramide-creams-barrier-repair.mdx" \
  "cosmetics/src/content/blog/en/best-korean-lip-products-hydration.mdx" \
  "cosmetics/src/content/blog/en/best-pdrn-skincare-products.mdx" \
  "cosmetics/src/content/blog/en/best-korean-sheet-masks-by-skin-concern.mdx" \
  "cosmetics/src/content/blog/en/best-korean-products-hyperpigmentation-dark-spots.mdx" \
  "cosmetics/src/content/blog/en/best-korean-skincare-for-men.mdx" \
  "cosmetics/src/content/blog/en/best-korean-cushion-foundations-skin-type.mdx" \
  "cosmetics/src/content/blog/en/best-korean-cica-products-redness-sensitive-skin.mdx" \
  "cosmetics/src/content/blog/en/best-korean-cleansing-balms-oils-guide.mdx" \
  "cosmetics/src/content/blog/en/best-korean-toners-glass-skin.mdx" \
  "cosmetics/src/content/blog/en/best-korean-moisturizers-under-25.mdx" \
  "cosmetics/src/content/blog/en/medicube-age-r-devices-worth-it.mdx" \
  "cosmetics/src/content/blog/en/best-korean-body-care-products.mdx" \
  "cosmetics/src/content/blog/en/korean-hair-care-products-damage-repair.mdx" \
  "cosmetics/src/content/blog/en/best-korean-anti-aging-serums-every-budget.mdx"; do
  if [ -f "$article" ] && grep -q "^draft: true" "$article"; then
    publish_article "$article" "Glow Coded"
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
  "wellness/src/content/blog/en/post-workout-k-beauty-recovery-routine.mdx" \
  "wellness/src/content/blog/en/10-anti-inflammatory-meals-weight-loss.mdx" \
  "wellness/src/content/blog/en/5-recovery-tools-speed-muscle-healing.mdx" \
  "wellness/src/content/blog/en/foods-that-sharpen-focus-science-backed.mdx" \
  "wellness/src/content/blog/en/15-minute-morning-meditation-sequence.mdx" \
  "wellness/src/content/blog/en/how-to-start-cold-water-therapy.mdx" \
  "wellness/src/content/blog/en/10-high-protein-smoothie-recipes-recovery.mdx" \
  "wellness/src/content/blog/en/weekly-meal-prep-weight-loss.mdx" \
  "wellness/src/content/blog/en/7-evening-wind-down-rituals-deep-sleep.mdx" \
  "wellness/src/content/blog/en/10-warming-soups-gut-health-weight-loss.mdx" \
  "wellness/src/content/blog/en/breathwork-techniques-stress-recovery.mdx" \
  "wellness/src/content/blog/en/10-brain-snacks-boost-concentration.mdx" \
  "wellness/src/content/blog/en/intermittent-fasting-beginners-guide.mdx" \
  "wellness/src/content/blog/en/10-minute-body-scan-meditation-beginners.mdx" \
  "wellness/src/content/blog/en/anti-inflammatory-spice-blends-make-today.mdx" \
  "wellness/src/content/blog/en/how-to-make-fermented-kimchi-at-home.mdx"; do
  if [ -f "$article" ] && grep -q "^draft: true" "$article"; then
    publish_article "$article" "Rooted Glow"
    PUBLISHED=$((PUBLISHED + 1))
    break
  fi
done

if [ $PUBLISHED -gt 0 ]; then
  # Stage all published + undrafted files
  git add $PUBLISHED_FILES
  git commit -m "Publish daily articles ($(date +%Y-%m-%d))"
  git pull --rebase --quiet origin main 2>/dev/null || true
  git push origin main

  # Auto-translate newly published articles to all 6 locales
  TRANSLATE_SCRIPT="scripts/translate-content.py"
  if [ -f "$TRANSLATE_SCRIPT" ]; then
    echo "Running auto-translation for published articles..."
    for f in $PUBLISHED_FILES; do
      # Only translate English articles (skip i18n files)
      if echo "$f" | grep -q "/blog/en/"; then
        site=$(echo "$f" | cut -d/ -f1)
        python3 "$TRANSLATE_SCRIPT" --site "$site" --articles-only 2>&1 | tail -5 || true
      fi
    done
  fi

  if [ -f scripts/submit-indexnow.sh ]; then
    bash scripts/submit-indexnow.sh
  fi

  echo "Done! Published $PUBLISHED article(s) and deployed."
else
  echo "Nothing to publish today."
fi

# ---------------------------------------------------------------------------
# SEO morning brief — self-installs venv on first run, pings Telegram digest
# ---------------------------------------------------------------------------
if [ -f scripts/seo/morning_brief.py ]; then
  # Create venv + install claude-agent-sdk if missing (idempotent, ~30s first run)
  if [ ! -x .venv-seo/bin/python ]; then
    echo "[seo] bootstrapping .venv-seo/"
    python3 -m venv .venv-seo 2>/dev/null || true
    .venv-seo/bin/pip install -q --upgrade pip claude-agent-sdk 2>&1 | tail -3 || true
  fi

  if [ -x .venv-seo/bin/python ] && command -v claude >/dev/null 2>&1; then
    echo "[seo] running morning brief"
    .venv-seo/bin/python scripts/seo/morning_brief.py \
      >> scripts/seo/reports/cron.log 2>&1 || \
      echo "[seo] morning brief failed (see scripts/seo/reports/cron.log)"
  else
    echo "[seo] skipped — .venv-seo or claude CLI not ready"
  fi
fi
