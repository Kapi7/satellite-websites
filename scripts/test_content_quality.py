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

# A current hash must not bypass language checks.
import content_quality as quality
with tempfile.TemporaryDirectory() as d:
 root=Path(d);en=root/'cosmetics/src/content/blog/en';en.mkdir(parents=True)
 s=en/'sample.mdx';s.write_text(source)
 for locale in quality.LOCALES:
  t=en.parent/locale/s.name;t.parent.mkdir();t.write_text(stamp(source,source))
 assert all('untranslated English' in e for e in quality.validate(s))
 original_root=quality.ROOT;quality.ROOT=root
 try:
  assert any('hero:' in e for e in quality.validate(s,True))
 finally:quality.ROOT=original_root
print('Content quality: matching source hashes do not hide English copies; missing image approval blocks publication.')
from content_quality import translation_structure
reference='---\nlocale: en\n---\n**Affiliate disclosure:** We may earn a commission.\n\n## Choice\nText\n\n## Cautions\nText'
translated='---\nlocale: ru\n---\nТекст\n\n## Выбор\nТекст'
errors=translation_structure(reference,translated,'ru')
assert len(errors)==2
complete='---\nlocale: ru\n---\nМы можем получить комиссию.\n\n## Выбор\nТекст\n\n## Предостережения\nТекст'
assert not translation_structure(reference,complete,'ru')
print('Translation structure: dropped sections and missing commission disclosure are rejected.')
