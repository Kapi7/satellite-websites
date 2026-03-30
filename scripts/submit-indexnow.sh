#!/usr/bin/env bash
# Submit all URLs from both sitemaps to IndexNow (Bing, Yandex, etc.)
# Also submits to Bing Webmaster API for direct indexing
# Usage: ./scripts/submit-indexnow.sh

set -euo pipefail

KEY="06f4ca1b5301485797bbe6c72a0f721f"
BING_API_KEY="282fd9e402f641b9a21fe8c171b6925e"

SITES=(
  "https://glow-coded.com"
  "https://rooted-glow.com"
)

for SITE in "${SITES[@]}"; do
  echo "=== Submitting URLs for $SITE ==="

  SITEMAP_URL="${SITE}/sitemap-0.xml"
  echo "Fetching sitemap: $SITEMAP_URL"

  # Extract URLs using python (handles single-line XML)
  URL_JSON=$(curl -s "$SITEMAP_URL" | python3 -c "
import sys, re, json
xml = sys.stdin.read()
urls = re.findall(r'<loc>([^<]+)</loc>', xml)
print(json.dumps(urls))
")

  URL_COUNT=$(echo "$URL_JSON" | python3 -c "import sys,json; print(len(json.loads(sys.stdin.read())))")
  echo "  Found $URL_COUNT URLs"

  HOST=$(echo "$SITE" | sed 's|https://||')

  # IndexNow submission
  PAYLOAD="{\"host\":\"$HOST\",\"key\":\"$KEY\",\"keyLocation\":\"${SITE}/${KEY}.txt\",\"urlList\":$URL_JSON}"

  echo "  Submitting to IndexNow (Bing)..."
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "https://api.indexnow.org/indexnow" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD")
  echo "  Bing IndexNow response: HTTP $HTTP_CODE"

  echo "  Submitting to IndexNow (Yandex)..."
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "https://yandex.com/indexnow" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD")
  echo "  Yandex response: HTTP $HTTP_CODE"

  # Bing Webmaster API direct URL submission
  echo "  Submitting to Bing Webmaster API..."
  BING_PAYLOAD="{\"siteUrl\":\"${SITE}/\",\"urlList\":$URL_JSON}"
  BING_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "https://ssl.bing.com/webmaster/api.svc/json/SubmitUrlBatch?apikey=$BING_API_KEY" \
    -H "Content-Type: application/json" \
    -d "$BING_PAYLOAD")
  echo "  Bing Webmaster API response: HTTP $BING_CODE"

  echo ""
done

echo "Done. HTTP 200/202 = accepted. 422 = URLs already submitted recently."
