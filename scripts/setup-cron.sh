#!/usr/bin/env bash
# Setup all satellite website cron jobs
# Run once: bash scripts/setup-cron.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

CRON_ENTRIES="
# Satellite websites daily article publisher — 6 AM daily
0 6 * * * ${SCRIPT_DIR}/daily-publish.sh >> ${SCRIPT_DIR}/publish.log 2>&1

# SEO index checker + Bing auto-submit — 15 min after publisher
15 6 * * * /opt/homebrew/bin/python3 ${SCRIPT_DIR}/check-index.py >> ${SCRIPT_DIR}/index-check.log 2>&1

# Weekly SEO report — Monday 8 AM
0 8 * * 1 /opt/homebrew/bin/python3 ${SCRIPT_DIR}/weekly-report.py >> ${SCRIPT_DIR}/reports/weekly-report.log 2>&1
"

# Remove any existing satellite website cron entries
EXISTING=$(crontab -l 2>/dev/null | grep -v "satellite-websites" | grep -v "Satellite websites" | grep -v "SEO index checker" | grep -v "Weekly SEO report")

# Combine existing + new
echo "$EXISTING" | cat - <(echo "$CRON_ENTRIES") | crontab -

echo "Cron jobs installed:"
crontab -l | grep -A1 "satellite\|SEO\|Weekly"
