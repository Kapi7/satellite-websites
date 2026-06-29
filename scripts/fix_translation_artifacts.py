#!/usr/bin/env python3
"""
Repair translation-script artifacts in */src/content/blog/<locale>/*.mdx:
  1. "BODY TO TRANSLATE:" / similar prompt boilerplate leaked into body.
  2. Duplicate `---` separator immediately after closing frontmatter.
  3. Unescaped double-quotes inside YAML double-quoted strings.
  4. Pathologically long lines (>5000 chars) — typically a malformed table
     row that hangs Astro/MDX's GFM table parser. Splits runs of >=50
     spaces into paragraph breaks so the build progresses.
  5. '<' before a digit (e.g. '<2%') which MDX reads as a JSX tag.
  6. Unquoted YAML frontmatter values containing a colon.
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

# LLM tokenizer tokens that occasionally leak into translator output. MDX
# treats them as JSX tags and demands closing tags, breaking the build.
# Replace with a single space (they always appear mid-sentence).
LLM_TOKEN_TAG_RE = re.compile(r"</?(?:bos|eos|pad|unk|sep|cls|mask|s)>", re.I)

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


def fix_llm_token_tags(text):
    new, n = LLM_TOKEN_TAG_RE.subn(" ", text)
    return (new, n) if n else (text, 0)


def fix_long_lines(text):
    # Lines longer than 5000 chars are usually a malformed table row whose
    # trailing whitespace swallowed the next paragraph. Splitting on long
    # runs of spaces is a no-op for normal markdown (no legitimate line has
    # 50 consecutive spaces) but rescues the build.
    fixes = 0
    new_lines = []
    for line in text.splitlines(keepends=True):
        if len(line) > 5000 and re.search(r" {50,}", line):
            new_lines.append(re.sub(r" {50,}", "\n\n", line))
            fixes += 1
        else:
            new_lines.append(line)
    return ("".join(new_lines), fixes) if fixes else (text, 0)


def fix_lt_digit(text):
    """Escape `<` immediately preceding a digit (e.g. '<2%', '< 5 mg').
    MDX parses '<' as the start of a JSX tag, so '<2%' is a hard build
    error ('Unexpected character `2` before name'). Replaces with the
    HTML entity, which renders identically. Skips fenced + inline code."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        fm, body = "", text
    else:
        fm, body = text[m.start():m.end()], text[m.end():]
    blocks = []
    def stash(mm):
        blocks.append(mm.group(0))
        return f"\x00{len(blocks)-1}\x00"
    tmp = re.sub(r"```.*?```", stash, body, flags=re.S)
    tmp = re.sub(r"`[^`]*`", stash, tmp)
    tmp, n = re.subn(r"<(?=\s*\d)", "&lt;", tmp)
    for i, b in enumerate(blocks):
        tmp = tmp.replace(f"\x00{i}\x00", b)
    return (fm + tmp, n) if n else (text, 0)


def fix_orphan_closing_tags(text):
    """Strip orphan HTML closing tags (</div>, </span>, etc.) in the body that
    have no matching opener — a truncated-translation artifact that breaks MDX
    ('Unexpected closing slash'). Only removes a closing tag when the body has
    strictly more closes than opens for that tag. Skips code fences/spans."""
    m = FRONTMATTER_RE.match(text)
    fm, body = (text[:m.end()], text[m.end():]) if m else ("", text)
    blocks = []
    def stash(mm): blocks.append(mm.group(0)); return f"\x00{len(blocks)-1}\x00"
    scan = re.sub(r"```.*?```", stash, body, flags=re.S)
    scan = re.sub(r"`[^`]*`", stash, scan)
    fixes = 0
    for tag in ("div","span","p","section","article","ul","ol","li","table","tr","td"):
        opens = len(re.findall(rf"<{tag}[\s>]", scan))
        closes = len(re.findall(rf"</{tag}>", scan))
        while closes > opens:
            scan, n = re.subn(rf"</{tag}>", "", scan, count=1)
            if not n: break
            closes -= 1; fixes += 1
    if not fixes:
        return text, 0
    for i, b in enumerate(blocks):
        scan = scan.replace(f"\x00{i}\x00", b)
    return fm + scan, fixes


def fix_unquoted_yaml_colons(text):
    """Quote frontmatter values that contain an unquoted colon (e.g.
    `imageAlt: Foo: bar` breaks YAML parsing). Common translator artifact."""
    m = FRONTMATTER_RE.match(text)
    if not m: return text, 0
    fm = text[m.start():m.end()]
    body = text[m.end():]
    fixes = 0
    new_lines = []
    for line in fm.splitlines():
        mm = re.match(r"^([a-zA-Z][\w-]*:\s+)([^\"'\[\{].*)$", line)
        if mm and ":" in mm.group(2) and not mm.group(2).startswith(("|", ">")):
            safe = mm.group(2).replace('"', "'")
            new_lines.append(f'{mm.group(1)}"{safe}"')
            fixes += 1
        else:
            new_lines.append(line)
    return ("\n".join(new_lines) + "\n" + body, fixes) if fixes else (text, 0)


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
    text, long_n = fix_long_lines(text)
    text, tok_n = fix_llm_token_tags(text)
    text, yamlc_n = fix_unquoted_yaml_colons(text)
    text, ltd_n = fix_lt_digit(text)
    text, orphan_n = fix_orphan_closing_tags(text)
    text, quote_n = fix_unescaped_quotes(text)
    total = sep_n + leak_n + quote_n + long_n + tok_n + yamlc_n + ltd_n + orphan_n
    if total == 0:
        return None
    if not dry_run:
        path.write_text(text)
    return {"path": path, "leaks": leak_n, "seps": sep_n, "quotes": quote_n,
            "longs": long_n, "tokens": tok_n, "yaml_colons": yamlc_n, "lt_digit": ltd_n}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    fixed = 0
    totals = {"leaks": 0, "seps": 0, "quotes": 0, "longs": 0, "tokens": 0, "yaml_colons": 0, "lt_digit": 0}
    for site in SITE_DIRS:
        if not site.exists():
            continue
        for mdx in site.rglob("*.mdx"):
            r = process_file(mdx, args.dry_run)
            if not r:
                continue
            fixed += 1
            for k in totals:
                totals[k] += r[k]
    print(f"\n[done] {fixed} files {'would be ' if args.dry_run else ''}fixed")
    print(f"  prompt-leaks: {totals['leaks']}, duplicate ---: {totals['seps']}, "
          f"unescaped quotes: {totals['quotes']}, long lines: {totals['longs']}, "
          f"llm-token tags: {totals['tokens']}, yaml-colons: {totals['yaml_colons']}, "
          f"lt-digit: {totals['lt_digit']}")


if __name__ == "__main__":
    main()
