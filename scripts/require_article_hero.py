"""Reject new articles with absent or broken local hero assets; not a visual approval."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def check(article):
    article = Path(article).resolve()
    try:
        site = article.relative_to(ROOT).parts[0]
        frontmatter = article.read_text().split("---", 2)[1]
    except (ValueError, IndexError, OSError):
        return "unreadable article or frontmatter"
    match = re.search(r"^image:\s*([^\n]*)", frontmatter, re.M)
    image = match.group(1).strip().strip("\"'") if match else ""
    public = (ROOT / site / "public").resolve()
    asset = (public / image.lstrip("/")).resolve()
    if not image.startswith("/images/") or not asset.is_relative_to(public) or not asset.is_file():
        return "missing local hero image; review a suitable asset before publication"
    return None

if __name__ == "__main__":
    errors = [(p, check(p)) for p in sys.argv[1:]]
    for path, error in errors:
        if error:
            print(f"{path}: {error}")
    raise SystemExit(1 if not errors or any(e for _, e in errors) else 0)
