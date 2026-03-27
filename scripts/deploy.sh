#!/usr/bin/env bash
# Build both satellite sites, push to GitHub, and ping IndexNow.
# Usage: ./scripts/deploy.sh [--skip-build] [--skip-push] [--skip-indexnow]

set -euo pipefail
cd "$(dirname "$0")/.."

SKIP_BUILD=false
SKIP_PUSH=false
SKIP_INDEXNOW=false

for arg in "$@"; do
  case $arg in
    --skip-build) SKIP_BUILD=true ;;
    --skip-push) SKIP_PUSH=true ;;
    --skip-indexnow) SKIP_INDEXNOW=true ;;
  esac
done

# ── Build ──
if [ "$SKIP_BUILD" = false ]; then
  echo "=== Building cosmetics site ==="
  (cd cosmetics && npm run build)
  echo ""

  echo "=== Building wellness site ==="
  (cd wellness && npm run build)
  echo ""
else
  echo "Skipping build (--skip-build)"
fi

# ── Push ──
if [ "$SKIP_PUSH" = false ]; then
  echo "=== Pushing to GitHub ==="
  git add -A
  if git diff --cached --quiet; then
    echo "  No changes to commit."
  else
    git commit -m "Deploy: build and update satellite sites"
    git push
    echo "  Pushed to GitHub."
  fi
  echo ""
else
  echo "Skipping push (--skip-push)"
fi

# ── IndexNow ──
if [ "$SKIP_INDEXNOW" = false ]; then
  echo "=== Submitting to IndexNow ==="
  bash "$(dirname "$0")/submit-indexnow.sh"
else
  echo "Skipping IndexNow (--skip-indexnow)"
fi

echo "=== Deploy complete ==="
