#!/usr/bin/env python3
"""
Refresh striking-distance articles: insert TL;DR + FAQ blocks (only if missing),
bump the `date:` to today to trigger a recrawl. Never rewrites existing content
— Gemini only generates the additions; we splice them in.

Usage:
    python3 scripts/refresh_striking_distance.py --site build-coded --slug <slug>
    python3 scripts/refresh_striking_distance.py --site build-coded --slugs s1,s2,s3
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    print("ERROR: GEMINI_API_KEY not set"); sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
SITES = {
    "cosmetics":   ROOT / "cosmetics",
    "wellness":    ROOT / "wellness",
    "build-coded": ROOT / "build-coded",
}
TEXT_MODEL = "gemini-2.5-flash"


def parse_mdx(path: Path):
    text = path.read_text()
    m = re.match(r"^(---\s*\n.*?\n---\s*\n)(.*)$", text, re.S)
    if not m:
        return None
    return m.group(1), m.group(2)


def extract_field(frontmatter: str, key: str) -> str:
    m = re.search(rf'^{key}:\s*"?([^"\n]+)"?$', frontmatter, re.M)
    return m.group(1).strip() if m else ""


def has_tldr(body: str) -> bool:
    # TL;DR-ish patterns Gemini might already have inserted
    return bool(re.search(r"^\*\*Quick answer|^\*\*TL;DR|^## (TL;DR|Quick)", body, re.M | re.I))


def has_faq(body: str) -> bool:
    return bool(re.search(r"^## (Frequently Asked|FAQ|Common Questions)", body, re.M | re.I))


def gemini(prompt: str, max_tokens: int = 4000) -> str | None:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{TEXT_MODEL}:generateContent?key={API_KEY}"
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.4},
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                data = json.loads(r.read())
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except urllib.error.HTTPError as e:
            if e.code in (429, 503):
                time.sleep(8 * (attempt + 1))
            else:
                print(f"  gemini error {e.code}: {e.read().decode()[:200]}")
                return None
    return None


def gen_tldr(title: str, description: str, body_excerpt: str) -> str | None:
    prompt = (
        f"Write a single 'Quick answer' TL;DR paragraph (50-80 words) for this DIY blog article. "
        f"Direct answer first, no fluff, written in second person, no headings or bullets. "
        f"Output the paragraph only — start with **Quick answer:** in bold and continue inline.\n\n"
        f"Title: {title}\nDescription: {description}\n\nArticle excerpt (first ~500 words):\n{body_excerpt[:2500]}"
    )
    return gemini(prompt, max_tokens=1500)


def gen_faq(title: str, description: str, body_excerpt: str) -> str | None:
    prompt = (
        f"Write an FAQ section for this DIY blog article. Output 8-10 question/answer pairs in this exact MDX format:\n"
        f"## Frequently Asked Questions\n\n"
        f"**Question text?**\n\n"
        f"Answer in 2-3 sentences. Direct, useful, conversational. No fluff.\n\n"
        f"**Next question?**\n\n"
        f"Answer ...\n\n"
        f"Output the heading and the 8-10 Q/A pairs only — no other text. Each question phrased like real Google searches "
        f"about this topic. Each answer 2-3 sentences. Make each answer practically useful for a DIYer.\n\n"
        f"Title: {title}\nDescription: {description}\n\nArticle excerpt (for context):\n{body_excerpt[:3000]}"
    )
    return gemini(prompt, max_tokens=2500)


def insert_tldr(body: str, tldr: str) -> str:
    """Insert TL;DR right after the first paragraph (before any heading)."""
    lines = body.split("\n")
    # Find end of first paragraph (line where next non-empty line starts with #)
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    # Skip frontmatter-ish content if any
    while i < len(lines) and not lines[i].strip().startswith("#"):
        # End of paragraph = blank line
        if i + 1 < len(lines) and not lines[i + 1].strip():
            # Insert after this blank line
            i += 2
            break
        i += 1
    # Insert tldr
    lines.insert(i, tldr.strip() + "\n")
    return "\n".join(lines)


def insert_faq(body: str, faq: str) -> str:
    """Insert FAQ before the LAST heading section if it's named like a conclusion;
    otherwise append at end."""
    # Find a "## Bottom Line" / "## Final" / "## Conclusion" heading
    m = re.search(r"^(## (?:Bottom [Ll]ine|Final|Conclusion|The Bottom Line).*?)$", body, re.M)
    if m:
        idx = m.start()
        return body[:idx] + faq.strip() + "\n\n" + body[idx:]
    # else append
    if not body.endswith("\n"):
        body += "\n"
    return body + "\n" + faq.strip() + "\n"


def update_date(frontmatter: str, today: str) -> str:
    return re.sub(r"^date:\s*.+$", f"date: {today}", frontmatter, flags=re.M)


def add_updated(frontmatter: str, today: str) -> str:
    if re.search(r"^updated:", frontmatter, re.M):
        return re.sub(r"^updated:\s*.+$", f"updated: {today}", frontmatter, flags=re.M)
    # insert after date:
    return re.sub(r"(^date:\s*[^\n]+\n)", r"\1updated: " + today + "\n", frontmatter, count=1, flags=re.M)


def process(site_key: str, slug: str, dry_run: bool = False):
    path = SITES[site_key] / "src" / "content" / "blog" / "en" / f"{slug}.mdx"
    if not path.exists():
        print(f"  SKIP: {path} not found")
        return
    parsed = parse_mdx(path)
    if not parsed:
        print(f"  SKIP: bad frontmatter")
        return
    fm, body = parsed
    title = extract_field(fm, "title")
    description = extract_field(fm, "description")
    print(f"\n=== {site_key}/{slug} ===")
    print(f"  title: {title}")

    today = time.strftime("%Y-%m-%d")
    new_body = body
    actions = []

    if not has_tldr(new_body):
        print("  generating TL;DR ...")
        tldr = gen_tldr(title, description, new_body)
        if tldr:
            new_body = insert_tldr(new_body, tldr)
            actions.append("tldr")
        else:
            print("  TL;DR generation FAILED — skipping")

    if not has_faq(new_body):
        print("  generating FAQ ...")
        faq = gen_faq(title, description, new_body)
        if faq:
            # Strip any code fences or extra prose Gemini sometimes adds
            faq = faq.strip()
            if faq.startswith("```"):
                faq = re.sub(r"^```\w*\n?", "", faq)
                faq = re.sub(r"\n?```$", "", faq)
            new_body = insert_faq(new_body, faq)
            actions.append("faq")
        else:
            print("  FAQ generation FAILED — skipping")

    new_fm = update_date(fm, today)
    new_fm = add_updated(new_fm, today)
    actions.append(f"date={today}")

    if dry_run:
        print(f"  [dry-run] would write {len(new_body) - len(body)} new chars; actions: {', '.join(actions)}")
        return

    path.write_text(new_fm + new_body)
    print(f"  SAVED ({len(new_body) - len(body)} new chars; {', '.join(actions)})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True, choices=list(SITES.keys()))
    ap.add_argument("--slug", help="single slug")
    ap.add_argument("--slugs", help="comma-separated list")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    slugs = []
    if args.slug:
        slugs = [args.slug]
    elif args.slugs:
        slugs = [s.strip() for s in args.slugs.split(",")]
    else:
        print("specify --slug or --slugs"); sys.exit(1)

    for slug in slugs:
        process(args.site, slug, args.dry_run)
        time.sleep(2)


if __name__ == "__main__":
    main()
