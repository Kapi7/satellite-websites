"""Explicit one-off repair batch. Outputs remain artifacts until editorial review."""
import concurrent.futures
import importlib.util
import json
import os
import re
from pathlib import Path
os.environ['PYTHONUNBUFFERED']='1'
from content_quality import unchanged, is_current
from markdown_quality import unclosed_fence, normalize_mdx_breaks
ROOT=Path(__file__).resolve().parents[1]
BLOG=ROOT/'cosmetics/src/content/blog'
SLUGS=['tirtir-cushion-foundation-shade-guide','best-korean-lip-products-hydration','best-korean-sunscreens-oily-skin-no-white-cast','galactomyces-skincare-guide','mugwort-skincare-benefits']
spec=importlib.util.spec_from_file_location('translator',Path(__file__).with_name('translate-content.py'))
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)

def links(text):
 return re.findall(r'\]\(([^)]+)\)',text)

def job(item):
 lang,slug,mode=item
 source=BLOG/'en'/f'{slug}.mdx';target=BLOG/lang/source.name
 if mode=='full':
  if is_current(source,target):return {'lang':lang,'slug':slug,'mode':'current'}
  if not t.translate_article('cosmetics',lang,source):raise ValueError(f'translation failed: {lang}/{slug}')
  # Preserve all external destinations and image paths in a full translation.
  external=lambda text:sorted(u for u in links(text) if u.startswith(('https://','/images/')))
  if external(source.read_text()) != external(target.read_text()): raise ValueError(f'changed links: {lang}/{slug}')
  return {'lang':lang,'slug':slug,'mode':mode}
 old=target.read_text();copies=unchanged(source.read_text(),old)
 if not copies:return {'lang':lang,'slug':slug,'mode':'no-copy'}
 # Smaller chunks avoid truncation on pages with many copied paragraphs.
 new=old
 for offset in range(0,len(copies),6):
  chunk=copies[offset:offset+6]
  prompt=f'''Translate each string in this JSON array. {t.LANG_INSTRUCTIONS[lang]}
Preserve the meaning, qualifications, markdown, all URLs and image paths exactly.
Return ONLY a JSON array of strings of the same length, in the same order. No English paragraphs left unchanged. Do not add claims, notes, facts or formatting wrappers.
{json.dumps(chunk,ensure_ascii=False)}'''
  result=t.call_gemini(prompt).strip();result=re.sub(r'^```(?:json)?\s*|\s*```$','',result)
  translated=json.loads(result)
  if not isinstance(translated,list) or len(translated)!=len(chunk):raise ValueError('Invalid translation array')
  for before,after in zip(chunk,translated):
   if not isinstance(after,str) or len(after.strip())<30 or links(before)!=links(after):raise ValueError('Invalid paragraph or changed link')
   new=new.replace(before,after)
 new=normalize_mdx_breaks(new)
 if unchanged(source.read_text(),new) or unclosed_fence(new):raise ValueError('Incomplete paragraph repair')
 # A paragraph patch does not certify the surrounding translation as current.
 target.write_text(new)
 return {'lang':lang,'slug':slug,'mode':mode,'paragraphs':len(copies)}

def main():
 jobs=[(lang,slug,'full') for slug in SLUGS for lang in t.LOCALES]
 for lang in t.LOCALES:
  for target in sorted((BLOG/lang).glob('*.mdx')):
   source=BLOG/'en'/target.name
   if target.stem not in SLUGS and source.exists() and unchanged(source.read_text(),target.read_text()):jobs.append((lang,target.stem,'paragraphs'))
 results=[];failures=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
  futures={pool.submit(job,item):item for item in jobs}
  for future in concurrent.futures.as_completed(futures):
   item=futures[future]
   try: result=future.result();results.append(result);print('OK',*item,flush=True)
   except Exception as e:failures.append({'job':item,'error':type(e).__name__});print('FAILED',*item,type(e).__name__,flush=True)
 (ROOT/'repair-results.json').write_text(json.dumps({'results':results,'failures':failures},indent=2))
 # Generate only from the two input photos reviewed by the editor. No publishing here.
 from gemini_enhance_hero import gemini_enhance
 folder=ROOT/'cosmetics/public/images/editorial';folder.mkdir(parents=True,exist_ok=True)
 for short,slug in [('galactomyces','galactomyces-skincare-guide'),('mugwort','mugwort-skincare-benefits')]:
  target=folder/(slug+'.jpg')
  if not target.exists():gemini_enhance(ROOT/f'scripts/repair-inputs/{short}.jpg',target,'cosmetics')
 if failures:raise SystemExit(1)

if __name__=='__main__':main()
