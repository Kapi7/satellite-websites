#!/usr/bin/env python3
"""
Generate reddit_schedule.json and pinterest_schedule.json
from MDX article frontmatter and PROMO-REDDIT.md.
"""

import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (
    COSMETICS_BLOG, WELLNESS_BLOG, BUILDCODED_BLOG,
    COSMETICS_IMAGES, WELLNESS_IMAGES, BUILDCODED_IMAGES,
    SITES, SUBREDDIT_MAP, PINTEREST_BOARD_MAP,
    REDDIT_SCHEDULE, PINTEREST_SCHEDULE,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def parse_frontmatter(mdx_path):
    """Extract YAML frontmatter from MDX file."""
    text = mdx_path.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return None
    fm = {}
    for line in match.group(1).splitlines():
        # Simple YAML parsing for flat keys
        m = re.match(r'^(\w[\w-]*):\s*(.+)$', line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            # Remove quotes
            val = val.strip('"').strip("'")
            # Parse arrays
            if val.startswith("["):
                val = [v.strip().strip('"').strip("'") for v in val.strip("[]").split(",")]
            # Parse booleans
            elif val == "true":
                val = True
            elif val == "false":
                val = False
            fm[key] = val
    return fm


def get_articles(blog_dir, images_dir, site_key):
    """Get all published articles with their metadata."""
    articles = []
    domain = SITES[site_key]
    for mdx in sorted(blog_dir.glob("*.mdx")):
        fm = parse_frontmatter(mdx)
        if not fm or fm.get("draft") is True:
            continue
        slug = mdx.stem
        image_raw = fm.get("image", "")
        image_name = image_raw.removeprefix("/images/") if image_raw else ""
        image_path = images_dir / image_name if image_name else None
        articles.append({
            "slug": slug,
            "title": fm.get("title", slug),
            "description": fm.get("description", ""),
            "category": fm.get("category", ""),
            "type": fm.get("type", ""),
            "tags": fm.get("tags", []),
            "date": fm.get("date", ""),
            "site": site_key,
            "domain": domain,
            "url": f"https://{domain}/{slug}/",
            "image_path": str(image_path) if image_path and image_path.exists() else None,
            "image_name": image_name,
        })
    return articles


def parse_promo_reddit():
    """Parse PROMO-REDDIT.md into structured entries."""
    promo_file = PROJECT_ROOT / "PROMO-REDDIT.md"
    text = promo_file.read_text(encoding="utf-8")

    entries = []
    # Split by "### Post N:" pattern
    post_blocks = re.split(r"### Post (\d+):", text)
    # post_blocks: ['header', '1', 'content', '2', 'content', ...]
    for i in range(1, len(post_blocks), 2):
        post_num = int(post_blocks[i])
        block = post_blocks[i + 1]

        # Extract subreddit from preceding ## header
        # Look backwards in original text
        title_line = block.split("\n")[0].strip()

        # Find thread search terms
        search_match = re.search(r"\*\*Find a thread asking about:\*\*\s*(.+)", block)
        search_terms = search_match.group(1).strip() if search_match else ""

        # Find comment text
        comment_match = re.search(r"\*\*Comment:\*\*\s*\n\n(.*?)(?=\n---|\Z)", block, re.DOTALL)
        comment = comment_match.group(1).strip() if comment_match else ""

        # Find URL in comment
        url_match = re.search(r"https?://[\w.-]+/[\w-]+/?", comment)
        url = url_match.group(0) if url_match else ""

        # Determine subreddit from context
        subreddit = ""
        # Search backwards in original text for the ## r/ header
        pos = text.find(f"### Post {post_num}:")
        before = text[:pos]
        sub_match = re.findall(r"## r/(\w+)", before)
        if sub_match:
            subreddit = sub_match[-1]

        entries.append({
            "post_num": post_num,
            "title": title_line,
            "subreddit": subreddit,
            "search_terms": search_terms,
            "comment": comment,
            "url": url,
        })

    return entries


def generate_reddit_schedule():
    """Generate Reddit posting schedule.

    Merge behaviour: any existing entries in reddit_schedule.json are
    preserved exactly (keeps karma posts, posted/failed status, dates).
    Only new articles/promo posts not already in the schedule get appended.
    """
    promo_entries = parse_promo_reddit()

    # Load existing schedule (if any) and index by a stable key.
    # Karma entries use topic+subreddit as key; promo entries use URL.
    existing = []
    if REDDIT_SCHEDULE.exists():
        try:
            with open(REDDIT_SCHEDULE) as f:
                existing = json.load(f)
        except Exception:
            existing = []

    existing_urls = {
        e["url"].rstrip("/") for e in existing
        if e.get("url") and e.get("comment_type", "link") == "link"
    }
    existing_karma_keys = {
        (e.get("subreddit", ""), e.get("topic", ""))
        for e in existing if e.get("comment_type") == "value"
    }
    next_id = max((e.get("id", 0) for e in existing), default=0) + 1

    # Get all published articles for auto-generating beyond the 9 pre-written
    all_articles = []
    all_articles.extend(get_articles(COSMETICS_BLOG, COSMETICS_IMAGES, "cosmetics"))
    all_articles.extend(get_articles(WELLNESS_BLOG, WELLNESS_IMAGES, "wellness"))

    # Track URLs already covered by promo entries
    promo_urls = {e["url"].rstrip("/") for e in promo_entries}

    # Start new appended entries the day after the latest existing date
    today = datetime.now().date()
    latest_date = today
    for e in existing:
        try:
            d = datetime.fromisoformat(e["scheduled_date"]).date()
            if d > latest_date:
                latest_date = d
        except Exception:
            pass

    # Start date: Monday on or after (latest_date + 1)
    start_seed = latest_date + timedelta(days=1)
    days_until_monday = (7 - start_seed.weekday()) % 7
    start_date = start_seed + timedelta(days=days_until_monday)

    schedule = []  # only NEW entries get appended here

    # Schedule pre-written posts first (Mon/Wed/Fri)
    post_days = [0, 2, 4]  # Mon=0, Wed=2, Fri=4
    week = 0
    day_idx = 0

    for entry in promo_entries:
        if entry["url"].rstrip("/") in existing_urls:
            continue  # already in schedule
        post_date = start_date + timedelta(weeks=week, days=post_days[day_idx])
        schedule.append({
            "id": next_id + len(schedule),
            "type": "pre-written",
            "comment_type": "link",
            "post_num": entry["post_num"],
            "subreddit": entry["subreddit"],
            "search_terms": entry["search_terms"],
            "comment": entry["comment"],
            "url": entry["url"],
            "scheduled_date": post_date.isoformat(),
            "status": "pending",
        })
        day_idx += 1
        if day_idx >= len(post_days):
            day_idx = 0
            week += 1

    # Auto-generate entries for remaining articles (skip if already covered)
    remaining = [
        a for a in all_articles
        if a["url"].rstrip("/") not in promo_urls
        and a["url"].rstrip("/") not in existing_urls
    ]
    for article in remaining:
        category = article["category"]
        subreddits = SUBREDDIT_MAP.get(category, ["SkincareAddiction"])
        subreddit = subreddits[len(schedule) % len(subreddits)]

        # Generate search terms from tags
        tags = article.get("tags", [])
        search_terms = ", ".join(tags[:3]) if tags else article["title"].lower()

        # Generate a helpful comment template
        comment = (
            f"This is a great question. I found a really thorough guide on this topic "
            f"that covers everything step by step.\n\n"
            f"Key takeaway from what I've learned: the most important thing is consistency "
            f"rather than using expensive products.\n\n"
            f"Here's the full breakdown if you want more detail: {article['url']}"
        )

        post_date = start_date + timedelta(weeks=week, days=post_days[day_idx])
        schedule.append({
            "id": next_id + len(schedule),
            "type": "auto-generated",
            "comment_type": "link",
            "subreddit": subreddit,
            "search_terms": search_terms,
            "comment": comment,
            "url": article["url"],
            "article_title": article["title"],
            "scheduled_date": post_date.isoformat(),
            "status": "pending",
        })
        day_idx += 1
        if day_idx >= len(post_days):
            day_idx = 0
            week += 1

    # Return existing + newly appended entries, preserving karma + posted status
    return existing + schedule


def generate_pinterest_schedule():
    """Generate Pinterest pinning schedule, merging with existing schedule.

    Per-site cadence is driven by config.PINTEREST_DAILY_LIMITS and the
    routing in config.PINTEREST_ACCOUNT_MAP. Sites whose account-map value
    is None OR whose daily limit is 0 are skipped entirely (no pins
    generated). Currently: glow-coded 5/day, rooted-glow 5/day, build-coded
    paused (no dedicated account), mirai handled by a separate flow.

    Merge behaviour: existing pins (matched by URL) are preserved exactly,
    keeping their status/posted_at/scheduled_date. Only new articles not
    already in the schedule get new pending entries appended, starting
    the day after the latest existing scheduled_date.
    """
    import math
    from config import PINTEREST_ACCOUNT_MAP, PINTEREST_DAILY_LIMITS

    def site_active(site_key):
        return (PINTEREST_ACCOUNT_MAP.get(site_key) is not None
                and PINTEREST_DAILY_LIMITS.get(site_key, 0) > 0)

    cosmetics = get_articles(COSMETICS_BLOG / "en", COSMETICS_IMAGES, "cosmetics") if site_active("cosmetics") else []
    wellness = get_articles(WELLNESS_BLOG / "en", WELLNESS_IMAGES, "wellness") if site_active("wellness") else []
    buildcoded = []
    if site_active("build-coded") and BUILDCODED_BLOG.exists():
        buildcoded = get_articles(BUILDCODED_BLOG / "en", BUILDCODED_IMAGES, "build-coded")

    # Load existing schedule (if any) and index by URL
    existing = []
    if PINTEREST_SCHEDULE.exists():
        try:
            with open(PINTEREST_SCHEDULE) as f:
                existing = json.load(f)
        except Exception:
            existing = []

    existing_by_url = {p["url"].rstrip("/"): p for p in existing}
    def _id_as_int(x):
        try: return int(x)
        except (TypeError, ValueError): return 0
    next_id = max((_id_as_int(p.get("id", 0)) for p in existing), default=0) + 1

    # Determine start date for NEW pins: day after the latest scheduled date
    today = datetime.now().date()
    latest_date = today
    for p in existing:
        try:
            d = datetime.fromisoformat(p["scheduled_date"]).date()
            if d > latest_date:
                latest_date = d
        except Exception:
            pass
    start_date = latest_date + timedelta(days=1)
    daily_per_site = 5

    # Build per-site queues of NEW articles only (those not already in the schedule)
    def filter_new(articles):
        return [
            a for a in articles
            if a["image_path"] and a["url"].rstrip("/") not in existing_by_url
        ]

    queues = {
        "cosmetics": filter_new(cosmetics),
        "wellness": filter_new(wellness),
        "build-coded": filter_new(buildcoded),
    }

    max_days = max((math.ceil(len(q) / daily_per_site) for q in queues.values() if q), default=0)

    new_pins = []
    for day_offset in range(max_days):
        pin_date = start_date + timedelta(days=day_offset)
        for site_key, queue in queues.items():
            start = day_offset * daily_per_site
            day_batch = queue[start : start + daily_per_site]
            for article in day_batch:
                category = article["category"]
                site_boards = PINTEREST_BOARD_MAP.get(article["site"], {})
                domain_name = article["domain"].split(".")[0].replace("-", " ").title()
                board = site_boards.get(category, f"{domain_name} — General")

                new_pins.append({
                    "id": next_id,
                    "title": article["title"],
                    "description": article["description"],
                    "url": article["url"],
                    "image_path": article["image_path"],
                    "board": board,
                    "site": article["site"],
                    "domain": article["domain"],
                    "category": category,
                    "tags": article.get("tags", []),
                    "scheduled_date": pin_date.isoformat(),
                    "status": "pending",
                })
                next_id += 1

    # Return existing + new, preserving all statuses
    return existing + new_pins


def main():
    print("Generating Reddit schedule...")
    reddit = generate_reddit_schedule()
    with open(REDDIT_SCHEDULE, "w") as f:
        json.dump(reddit, f, indent=2)
    print(f"  -> {len(reddit)} entries written to {REDDIT_SCHEDULE.name}")

    pre = sum(1 for e in reddit if e["type"] == "pre-written")
    auto = sum(1 for e in reddit if e["type"] == "auto-generated")
    print(f"     {pre} pre-written (from PROMO-REDDIT.md)")
    print(f"     {auto} auto-generated")

    print("\nGenerating Pinterest schedule...")
    pinterest = generate_pinterest_schedule()
    with open(PINTEREST_SCHEDULE, "w") as f:
        json.dump(pinterest, f, indent=2)
    print(f"  -> {len(pinterest)} entries written to {PINTEREST_SCHEDULE.name}")

    # Summary by board
    boards = {}
    for p in pinterest:
        boards[p["board"]] = boards.get(p["board"], 0) + 1
    for board, count in sorted(boards.items()):
        print(f"     {board}: {count} pins")

    # Date range
    if pinterest:
        dates = [p["scheduled_date"] for p in pinterest]
        print(f"\n  Date range: {min(dates)} to {max(dates)}")


if __name__ == "__main__":
    main()
