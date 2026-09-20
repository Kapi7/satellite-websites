"""Exercise the actual shell function without network, secrets or repository edits."""
import subprocess,tempfile
from pathlib import Path
script=Path(__file__).with_name('daily-publish.sh').read_text()
function=script.split('publish_article() {',1)[1].split('# Publish next draft from cosmetics',1)[0]
with tempfile.TemporaryDirectory() as folder:
 root=Path(folder);(root/'scripts').mkdir()
 (root/'scripts/markdown_quality.py').write_text('raise SystemExit(0)')
 (root/'scripts/content_quality.py').write_text('raise SystemExit(1)')
 for site in ['cosmetics','wellness']:
  p=root/site/'src/content/blog/en/example.mdx';p.parent.mkdir(parents=True);p.write_text('---\ndraft: true\n---\nDraft text')
 shell='''set -euo pipefail
LOCALES="es de el ru it ar fr nl pt"
PREFLIGHT_FAILED=0
BLOCKED_COSMETICS=0
PUBLISHED_FILES=""
undraft() { echo "$1" >> undrafted; }
publish_article() {'''+function+'''
if publish_article cosmetics/src/content/blog/en/example.mdx "Glow Coded"; then exit 11; fi
[ "$PREFLIGHT_FAILED" = 1 ]
[ "$BLOCKED_COSMETICS" = 1 ]
[ ! -f undrafted ]
[ -z "$PUBLISHED_FILES" ]
publish_article wellness/src/content/blog/en/example.mdx "Rooted Glow"
grep -q '^wellness/' undrafted
'''
 subprocess.run(['bash','-c',shell],cwd=root,check=True,capture_output=True,text=True)
 assert 'draft: true' in (root/'cosmetics/src/content/blog/en/example.mdx').read_text()
print('Publishing gate: rejected Glow draft stays unpublished; unrelated site can continue.')
