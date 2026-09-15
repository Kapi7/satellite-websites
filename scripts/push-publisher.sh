#!/usr/bin/env bash
# Preserve concurrent commits and local build byproducts; never force-push.
set -euo pipefail
for attempt in 1 2 3 4 5; do
  if ! git pull --rebase --autostash origin main; then
    echo "::error::Publisher integration failed; resolve the conflict before retrying. Content is retained." >&2
    exit 1
  fi
  if [ -n "$(git ls-files -u)" ]; then
    echo "::error::Publisher autostash has conflicts; content is retained." >&2
    exit 1
  fi
  if git push origin HEAD:main; then
    exit 0
  fi
  if [ "$attempt" -lt 5 ]; then sleep "$attempt"; fi
done
echo "::error::Publisher push failed after five attempts; content is retained." >&2
exit 1
