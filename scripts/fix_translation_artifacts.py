#!/usr/bin/env python3
"""
Repair translation-script artifacts in */src/content/blog/<locale>/*.mdx:
  1. "BODY TO TRANSLATE:" / similar prompt boilerplate leaked into body.
  2. Duplicate `---` separator immediately after closing frontmatter.
  3. Unescaped double-quotes inside YAML double-quoted strings.
"""
from __future__ import annotations
import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE_DIRS = [
    ROOT / "cosmetics" / "src" / "content" / "blog",
    ROOT / "wellness" / "src" / "content" / "blog",
    ROOT / "build-coded" / "src" / "content" / "blog",
]

PROMPT_LEAK_RES = [
    re.compile(r"^\s*BODY TO TRANSLATE:\s*\n", re.M),
    re.compile(r"^\s*TRANSLATE THE FOLLOWING:\s*\n", re.M),
    re.compile(r"^\s*Here is the translation:\s*\n", re.M),
    re.compile(r"^\s*Translation:\s*\n", re.M),
    re.compile(r"^```(?:markdown|md|mdx)?\s*\n(?=#)", re.M),
]

FRONTMATTER_RE = re.compile(r"^(---\s*\n.*?\n---\s*\n)", re.S)


def fix_double_separator(text):
    m = FRONTMATTER_RE.match(text)
    if not m:
        return text, 0
    fm_end = m.end()
    rest = text[fm_end:]
    new_rest, n = re.subn(r"^(?:---\s*\n)+", "", rest)
    return (text[:fm_end] + new_rest, n) if n else (text, 0)


def fix_prompt_leak(text):
    fixed = text
    total = 0
    for pat in PROMPT_LEAK_RES:
        fixed, n = pat.subn("", fixed)
        total += n
    fixed, n = re.subn(r"\n```\s*$", "\n", fixed)
    total += n
    return fixed, total


def fix_unescaped_quotes(text):
    m = FRONTMATTER_RE.match(text)
    if not m:
        return text, 0
    fm = text[m.start():m.end()]
    body = text[m.end():]
    fixes = 0
    new_lines = []
    for line in fm.splitlines():
        match = re.match(r'^(\s*[a-zA-Z][\w-]*:\s*)"(.*)"(\s*)$', line)
        if not match:
            new_lines.append(line)
            continue
        prefix, value, suffix = match.group(1), match.group(2), match.group(3)
        if '"' in value:
            new_value = value.replace('"', "'")
            new_lines.append(f'{prefix}"{new_value}"{suffix}')
            fixes += 1
        else:
            new_lines.append(line)
    return "\n".join(new_lines) + "\n" + body, fixes


def process_file(path, dry_run):
    text = original = path.read_text()
    text, sep_n = fix_double_separator(text)
    text, leak_n = fix_prompt_leak(text)
    text, quote_n = fix_unescaped_quotes(text)
    total = sep_n + leak_n + quote_n
    if total == 0:
        return None
    if not dry_run:
        path.write_text(text)
    return {"path": path, "leaks": leak_n, "seps": sep_n, "quotes": quote_n}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    fixed = 0
    totals = {"leaks": 0, "seps": 0, "quotes": 0}
    for site in SITE_DIRS:
        if not site.exists():
            continue
        for mdx in site.rglob("*.mdx"):
            r = process_file(mdx, args.dry_run)
            if not r:
                continue
            fixed += 1
            totals["leaks"] += r["leaks"]
            totals["seps"] += r["seps"]
            totals["quotes"] += r["quotes"]
    print(f"\n[done] {fixed} files {'would be ' if args.dry_run else ''}fixed")
    print(f"  prompt-leaks: {totals['leaks']}, duplicate ---: {totals['seps']}, unescaped quotes: {totals['quotes']}")


if __name__ == "__main__":
    main()
