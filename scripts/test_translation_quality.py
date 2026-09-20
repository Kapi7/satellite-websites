import os,importlib.util,tempfile
from pathlib import Path
os.environ['PYTHONUNBUFFERED']='1'
spec=importlib.util.spec_from_file_location('translate',Path(__file__).with_name('translate-content.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
with tempfile.TemporaryDirectory() as folder:
 root=Path(folder);en=root/'en';ar=root/'ar';en.mkdir();ar.mkdir()
 source=en/'sample.mdx';target=ar/'sample.mdx'
 source.write_text('---\ntitle: "Source"\ndescription: "Description"\ntags: ["guide"]\nlocale: en\n---\n'+('Public source text. '*1000)+'END_OF_COMPLETE_SOURCE')
 target.write_text('existing translation')
 m.call_gemini=lambda prompt:'```json\n{"body":"broken"}'
 assert not m.translate_article('build-coded','ar',source)
 assert target.read_text()=='existing translation'
 def valid(prompt):
  assert 'END_OF_COMPLETE_SOURCE' in prompt
  return 'TITLE: Translated "title"\nDESCRIPTION: Description\nIMAGE_ALT: Photo\nTAGS: guide\n\n'+('Translated paragraph. '*40)
 m.call_gemini=valid
 assert m.translate_article('build-coded','ar',source)
 assert '\\"title\\"' in target.read_text()
print('Translation checks passed: full source retained, malformed output rejected, existing file preserved, quotes escaped.')
# Cosmetic translations must reject copied prose before overwriting the existing file.
with tempfile.TemporaryDirectory() as folder:
 root=Path(folder);en=root/'en';es=root/'es';en.mkdir();es.mkdir()
 source=en/'sample.mdx';target=es/'sample.mdx'
 prose='This English paragraph contains a product recommendation with facts and qualifications that must be translated into the requested local language before it can be published. '*10
 source.write_text('---\ntitle: "Source"\ndescription: "Description"\ntags: ["guide"]\nlocale: en\n---\n'+prose)
 target.write_text('existing translation')
 m.call_gemini=lambda prompt:'TITLE: Título\nDESCRIPTION: Descripción\nIMAGE_ALT: Foto\nTAGS: [guía]\n\n'+prose
 assert not m.translate_article('cosmetics','es',source)
 assert target.read_text()=='existing translation'
print('Cosmetics: copied English prose rejected without overwriting the previous translation.')
