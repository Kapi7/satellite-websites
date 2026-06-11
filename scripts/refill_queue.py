#!/usr/bin/env python3
"""
Self-refilling draft queue for the daily publisher.

Root cause of the June 2026 content stall: the publisher drains one draft per
site per day, queue_health.py only *warns* on low runway, and nothing *refills*
the queue. When the last hand-made batch drained, the queue sat at zero and no
new content shipped.

This closes the loop. For each site:
  1. Count remaining `draft: true` English articles (runway in days).
  2. If runway < THRESHOLD, take the next unused topics from the per-site
     backlog (scripts/topic-backlog/<site>.json) — skipping any whose slug
     already exists — and generate them as drafts via gen_articles_batch.py
     (BATCH_DRAFT=true, stagger-dated into the future).

Idempotent and non-fatal: a topic whose .mdx already exists is skipped by the
generator, so re-running never duplicates. Exits 0 even on error so it never
blocks the publisher.

Usage:
    python3 scripts/refill_queue.py            # refill sites under threshold
    python3 scripts/refill_queue.py --dry-run  # report only, generate nothing
    python3 scripts/refill_queue.py --threshold 7 --batch 5
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
BACKLOG_DIR = SCRIPTS / "topic-backlog"
SITES = ["cosmetics", "wellness", "build-coded"]

sys.path.insert(0, str(SCRIPTS / "social"))
try:
    from tg import notify as tg_notify
except Exception:
    def tg_notify(msg, level="info", title=None):
        return False


def count_drafts(site: str) -> int:
    en = ROOT / site / "src" / "content" / "blog" / "en"
    n = 0
    for f in en.glob("*.mdx"):
        head = f.read_text()[:600]
        if re.search(r"^draft:\s*true\s*$", head, re.M):
            n += 1
    return n


def existing_slugs(site: str) -> set[str]:
    en = ROOT / site / "src" / "content" / "blog" / "en"
    return {f.stem for f in en.glob("*.mdx")}


def load_backlog(site: str) -> list[dict]:
    f = BACKLOG_DIR / f"{site}.json"
    if not f.exists():
        return []
    return json.loads(f.read_text())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=int, default=int(os.environ.get("REFILL_THRESHOLD", "7")),
                    help="Refill a site when its draft runway drops below this (days).")
    ap.add_argument("--batch", type=int, default=int(os.environ.get("REFILL_BATCH", "5")),
                    help="How many drafts to generate per refill.")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    summary = []
    for site in SITES:
        if not (ROOT / site / "src" / "content" / "blog" / "en").is_dir():
            continue
        runway = count_drafts(site)
        if runway >= args.threshold:
            summary.append(f"{site}: {runway} drafts — OK")
            continue

        backlog = load_backlog(site)
        have = existing_slugs(site)
        # next unused topics, in backlog order, that don't already exist
        pending = [t for t in backlog if t.get("slug") and t["slug"] not in have]
        take = pending[: args.batch]

        if not take:
            summary.append(f"{site}: {runway} drafts — LOW but backlog EMPTY (add topics to topic-backlog/{site}.json)")
            continue

        slugs = ", ".join(t["slug"] for t in take)
        if args.dry_run:
            summary.append(f"{site}: {runway} drafts — would generate {len(take)}: {slugs}")
            continue

        # Write a temp spec slice and hand it to the existing batch generator.
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
            json.dump(take, tf)
            spec_path = tf.name
        env = {**os.environ, "BATCH_DRAFT": "true", "BATCH_DATE_MODE": "stagger"}
        try:
            subprocess.run([sys.executable, str(SCRIPTS / "gen_articles_batch.py"), spec_path],
                           env=env, check=False)
            summary.append(f"{site}: {runway} drafts — generated {len(take)}: {slugs}")
        except Exception as e:
            summary.append(f"{site}: refill FAILED — {type(e).__name__}: {e}")
        finally:
            os.unlink(spec_path)

    report = "Queue refill\n" + "\n".join(summary)
    print(report)
    try:
        tg_notify(report, level="info", title="Queue refill")
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
