#!/usr/bin/env bash
# Submit all URLs from both sitemaps to IndexNow (Bing, Yandex, etc.)
# Usage: ./scripts/submit-indexnow.sh

set -euo pipefail

KEY="06f4ca1b5301485797bbe6c72a0f721f"

SITES=(
  "https://glow-coded.com"
  "https://rooted-glow.com"
)

for SITE in "${SITES[@]}"; do
  echo "=== Submitting URLs for $SITE ==="

  SITEMAP_URL="${SITE}/sitemap-0.xml"
  echo "Fetching sitemap: $SITEMAP_URL"

  # Extract URLs from sitemap XML
  URLS=$(curl -s "$SITEMAP_URL" | sed -n 's/.*<loc>\(.*\)<\/loc>.*/\1/p')

  if [ -z "$URLS" ]; then
    echo "  No URLs found in sitemap, trying sitemap-index.xml..."
    SITEMAP_URL="${SITE}/sitemap-index.xml"
    URLS=$(curl -s "$SITEMAP_URL" | sed -n 's/.*<loc>\(.*\)<\/loc>.*/\1/p')
  fi

  URL_COUNT=$(echo "$URLS" | wc -l | tr -d ' ')
  echo "  Found $URL_COUNT URLs"

  # Build JSON array of URLs
  URL_JSON=$(echo "$URLS" | python3 -c "
import sys, json
urls = [line.strip() for line in sys.stdin if line.strip()]
print(json.dumps(urls))
")

  HOST=$(echo "$SITE" | sed 's|https://||')

  # Submit to IndexNow API
  PAYLOAD="{\"host\":\"$HOST\",\"key\":\"$KEY\",\"keyLocation\":\"${SITE}/${KEY}.txt\",\"urlList\":$URL_JSON}"

  echo "  Submitting to IndexNow (Bing)..."
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "https://api.indexnow.org/indexnow" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD")
  echo "  Bing response: HTTP $HTTP_CODE"

  echo "  Submitting to IndexNow (Yandex)..."
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "https://yandex.com/indexnow" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD")
  echo "  Yandex response: HTTP $HTTP_CODE"

  echo ""
done

echo "Done. HTTP 200/202 = accepted. 422 = URLs already submitted recently."
