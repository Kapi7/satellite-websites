#!/usr/bin/env bash
# Release reviewed content only. Preparation, translations and replenishment are editorial work.
# A dry/empty queue is reported explicitly; unreviewed drafts never enter this release path.
set -euo pipefail
cd "$(dirname "$0")/.."
export DISABLE_OUTBOUND_NOTIFICATIONS=1
python3 scripts/reviewed_publisher.py --run
