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

def structured_paragraphs(prompt):
 from google import genai
 from google.genai import types
 client=genai.Client(api_key=os.environ['GEMINI_API_KEY'])
 response=client.models.generate_content(model='gemini-2.5-flash-lite',contents=prompt,config=types.GenerateContentConfig(temperature=0.2,response_mime_type='application/json',response_schema=list[str],max_output_tokens=32768))
 return json.loads(response.text)

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
 for offset in range(0,len(copies),2):
  chunk=copies[offset:offset+2]
  tokens={}
  def protect(match):
   token='PRESERVEURL'+str(len(tokens))+'END';tokens[token]=match.group(0);return token
  protected=[re.sub(r'https?://[^\s)<>]+',protect,re.sub(r'(?<=\]\()[^)]+(?=\))',protect,paragraph)) for paragraph in chunk]
  prompt=f'''Translate each string in this JSON array. {t.LANG_INSTRUCTIONS[lang]}
Preserve the meaning, qualifications, markdown, all URLs and image paths exactly. PRESERVEURL-number-END tokens are immutable: copy each token verbatim exactly once in its original position; never translate or omit these tokens.
Return ONLY a JSON array of strings of the same length, in the same order. No English paragraphs left unchanged. Do not add claims, notes, facts or formatting wrappers.
{json.dumps(protected,ensure_ascii=False)}'''
  translated=structured_paragraphs(prompt)
  if not isinstance(translated,list) or len(translated)!=len(chunk):raise ValueError('Invalid translation array')
  for before,after in zip(chunk,translated):
   for token,url in tokens.items():after=after.replace(token,url)
   if not isinstance(after,str) or len(after.strip())<30 or sorted(links(before))!=sorted(links(after)):raise ValueError('Invalid paragraph or changed link: '+str(offset))
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
   except Exception as e:failures.append({'job':item,'error':str(e)[:300]});print('FAILED',*item,type(e).__name__,flush=True)
 (ROOT/'repair-results.json').write_text(json.dumps({'results':results,'failures':failures},indent=2))
 # Generate only from the two input photos reviewed by the editor. No publishing here.
 from google import genai
 from google.genai import types
 import io
 from PIL import Image
 client=genai.Client(api_key=os.environ['GEMINI_API_KEY'])
 folder=ROOT/'cosmetics/public/images/editorial';folder.mkdir(parents=True,exist_ok=True)
 for short,slug in [('galactomyces','galactomyces-skincare-guide'),('mugwort','mugwort-skincare-benefits')]:
  target=folder/(slug+'.jpg')
  if not target.exists():
   prompt="""Edit the supplied real product photograph into a premium K-beauty editorial hero. Preserve the exact bottle, packaging proportions, color, typography and ALL existing label text as photographed. Do not invent text, redraw lettering, add droplets on the product, or change the product. Extend the background into a LANDSCAPE 16:9 cream marble tabletop with gentle natural morning shadows, subtle warm cream and sage tones, a folded ivory linen cloth far to one side, and plenty of breathing room. The entire bottle including its cap and base must fit within the central 70% of image height, with at least 15% clear margin above and below. Keep the bottle's scale modest. No other products, no props overlapping the bottle, no overlays. High fidelity photography, calm soft light, crisp readable product label. This is a background edit of the supplied photograph, not a new imaginary product."""
   labels={
    'galactomyces': "mixsoon\nPremium\nGalactomyces Serum\nNatural Radiance Booster\nFor Dull Skin\nAlpha-Arbutin ·\nGlutathione · Niacinamide\n50 ml / 1.69 fl.oz.",
    'mugwort': "I'm From\nMugwort\nEssence\nGet calm, hydrated skin.\nClinically tested to calm the skin\nquickly and improve hydration.\n150 ml / 5.07 fl. oz."
   }
   prompt += " Keep the source bottle completely front-facing, at exactly the same angle and proportions as the reference, do not reconstruct it in perspective. The existing label text, transcribed ONLY to preserve it faithfully, is: "+labels[short]+". Especially preserve the volume conversion exactly: 1.69 for mixsoon, 5.07 for I'm From. ALL letters on the product must be correct and readable; these words belong ONLY on the original label, not as overlays. Keep product large enough to read but full bottle inside image with generous space above and below."
   response=client.models.generate_content(model='gemini-3-pro-image' ,contents=[prompt,types.Part.from_bytes(data=(ROOT/f'scripts/repair-inputs/{short}.jpg').read_bytes(),mime_type='image/jpeg')],config=types.GenerateContentConfig(response_modalities=['IMAGE','TEXT'],image_config=types.ImageConfig(aspect_ratio='16:9',image_size='4K')))
   for part in response.candidates[0].content.parts:
    if part.inline_data:
     image=Image.open(io.BytesIO(part.inline_data.data)).convert('RGB')
     # Resize only. Never crop the photographed product or composite replacements.
     image.thumbnail((2400,1350),Image.Resampling.LANCZOS);image.save(target,'JPEG',quality=95)
   if not target.exists():raise ValueError('No image returned')
 if failures:raise SystemExit(1)

if __name__=='__main__':main()
