"""Minimal Markdown checks shared by generation and publication."""
import re
import sys
from pathlib import Path


def strip_article_wrapper(text):
    # Only unwrap an entire response, never a closing fence inside an article.
    match = re.fullmatch(r'\s*```(?:markdown|md|mdx)?[ \t]*\n(.*)\n```[ \t]*\s*', text, re.S)
    return match.group(1) if match else text


def unclosed_fence(text):
    opened = None
    for line in text.splitlines():
        match = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line)
        if not match:
            continue
        fence, rest = match.groups()
        if opened is None:
            opened = fence
        elif fence[0] == opened[0] and len(fence) >= len(opened) and not rest.strip():
            opened = None
    return opened is not None


if __name__ == '__main__':
    bad = [name for name in sys.argv[1:] if unclosed_fence(Path(name).read_text())]
    if bad:
        print('Unclosed Markdown fence; publication stopped: ' + ', '.join(bad))
        raise SystemExit(1)
