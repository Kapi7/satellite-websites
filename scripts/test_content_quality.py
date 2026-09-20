import tempfile
from pathlib import Path
from content_quality import fingerprint, unchanged, stamp, is_current
source='---\ntitle: "Guide"\ndate: 2026-01-01\ndraft: true\n---\n'+('English source with important qualifications and product facts. '*8)
assert fingerprint(source)==fingerprint(source.replace('draft: true','draft: false').replace('2026-01-01','2026-09-20'))
assert fingerprint(source)!=fingerprint(source.replace('qualifications','promises'))
assert len(unchanged(source,source))==1
assert not unchanged(source,'---\ntitle: X\n---\nTIRTIR Red Cushion 18g')
with tempfile.TemporaryDirectory() as d:
 s=Path(d)/'source.mdx';t=Path(d)/'target.mdx';s.write_text(source)
 assert not is_current(s,t)
 t.write_text(stamp(source,'---\nlocale: es\n---\nTexto traducido'))
 assert is_current(s,t)
 s.write_text(source.replace('facts','errors'))
 assert not is_current(s,t)
print('Content quality: stale, missing, untranslated prose, and publication-only changes verified.')
