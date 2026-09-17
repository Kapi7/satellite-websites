"""Ensure cleanup preserves valid escaped metadata in saved translations."""
import json
import tempfile
from pathlib import Path
from fix_translation_artifacts import fix_unescaped_quotes, process_file

for value in ['""', 'A "quoted" title', 'A path C:\\folder', 'Plain text']:
    source = '---\ntitle: ' + json.dumps(value) + '\n---\n\nBody.\n'
    cleaned, count = fix_unescaped_quotes(source)
    assert cleaned == source and count == 0, (source, cleaned)
malformed = '---\ntitle: "A "quoted" title"\n---\n\nBody.\n'
cleaned, count = fix_unescaped_quotes(malformed)
assert count == 1 and json.loads(cleaned.splitlines()[1][7:]) == "A 'quoted' title"
root = Path(__file__).resolve().parent.parent
source = (root/'cosmetics/src/content/blog/de/keep-a-skincare-product-notebook.mdx').read_text()
with tempfile.TemporaryDirectory() as directory:
    target = Path(directory)/'article.mdx'
    target.write_text(source)
    process_file(target, False)
    once = target.read_text()
    process_file(target, False)
    assert once == target.read_text()
    alt = next(line for line in once.splitlines() if line.startswith('imageAlt: '))
    assert json.loads(alt[10:]) == '""'
print('PASS: escaped metadata preserved, malformed quotes repaired, cleanup idempotent on affected draft.')
