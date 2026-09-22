"""Run after the Glow build: per-locale sitemap dates and purchase-path targets."""
from pathlib import Path
import re,xml.etree.ElementTree as E,json
root=Path(__file__).resolve().parent.parent/'cosmetics';ns={'s':'http://www.sitemaps.org/schemas/sitemap/0.9'};doc=E.parse(root/'dist/sitemap-0.xml');checked=0;errors=[]
for u in doc.findall('s:url',ns):
 url=u.findtext('s:loc',namespaces=ns);path=url.removeprefix('https://glow-coded.com/').strip('/');parts=path.split('/');lang=parts[0] if parts[0] in ['es','de','el','ru','it','ar','fr','nl','pt'] else 'en';slug=parts[-1];p=root/'src/content/blog'/lang/(slug+'.mdx')
 if not p.exists():continue
 head=p.read_text().split('---')[1];updated=re.search(r'^updated:\s*[\"\']?(\d{4}-\d{2}-\d{2})',head,re.M);date=re.search(r'^date:\s*[\"\']?(\d{4}-\d{2}-\d{2})',head,re.M);expected=(updated or date)[1];actual=u.findtext('s:lastmod',namespaces=ns) or '';checked+=1
 if not actual.startswith(expected):errors.append({'url':url,'expected':expected,'actual':actual})
print('Sitemap dates checked:',checked,'errors:',errors[:5]);assert not errors
products=json.loads((root/'src/data/mirai-edit.json').read_text())
for locale in ['en','de','es','el','ru','it','ar','fr','nl','pt']:
 base=root/'dist' if locale=='en' else root/'dist'/locale
 home=(base/'index.html').read_text();shop=(base/'shop/index.html').read_text()
 for product in products:
  guideLocale='en' if product['guideLocales']=='en' else locale
  target=root/'dist'/(('' if guideLocale=='en' else guideLocale+'/')+product['guide'])/'index.html'
  assert target.exists(),target
  assert (root/'public'/product['image'].lstrip('/')).exists()
  assert product['image'] in home and product['image'] in shop
 assert 'STAFF PICK' not in home
print('All 10 home/shop routes have real image assets and existing target guides.')
