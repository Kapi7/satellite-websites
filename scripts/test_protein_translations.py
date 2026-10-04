"""Check the corrected published locale cohort and its unpublished Arabic version.

Run after building wellness. Requires beautifulsoup4; no network or production writes.
"""
import json,re
from pathlib import Path
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]/'wellness'
SLUG='best-protein-powders-clean-natural'
SOURCES={
 'https://www.fda.gov/food/dietary-supplements/information-consumers-using-dietary-supplements',
 'https://www.nsf.org/consumer-resources/articles/supplement-vitamin-certification',
 'https://ods.od.nih.gov/factsheets/WYNTK-Consumer/',
}
corrections={'fr':'Correction éditoriale','de':'Redaktionelle Korrektur','es':'Corrección editorial','it':'Rettifica editoriale','pt':'Correção editorial','nl':'Redactionele correctie','el':'Συντακτική διόρθωση','ru':'Редакционное исправление','ar':'تصحيح تحريري'}
for lang,label in corrections.items():
 strings=json.loads((ROOT/'src/i18n/translations'/(lang+'.json')).read_text())
 source=(ROOT/'src/content/blog'/lang/(SLUG+'.mdx')).read_text();fm=source.split('---',2)[1]
 assert label in source,lang
 assert '\ndate: 2026-04-13\n' in fm,lang
 assert '\nupdated: 2026-10-04\n' in fm,lang
 assert '\ntype: guide\n' in fm,lang
 assert all(url in source for url in SOURCES),lang
 assert not any(brand in source for brand in ['Transparent Labs','Momentous','Legion Whey','Naked Whey','Orgain']),lang
 route=ROOT/'dist'/lang/SLUG/'index.html'
 if lang=='ar':
  assert '\ndraft: true\n' in fm
  assert not route.exists(),'Arabic draft became a public route'
  for sitemap in (ROOT/'dist').glob('sitemap*.xml'):assert '/ar/'+SLUG+'/' not in sitemap.read_text()
  home=BeautifulSoup((ROOT/'dist/ar/index.html').read_text(),'lxml')
  assert strings['footer']['brandDesc'] in home.get_text(' ',strip=True)
  continue
 assert 'draft: true' not in fm
 page=BeautifulSoup(route.read_text(),'lxml');prose=page.select_one('.prose');assert prose is not None
 assert page.html['lang']==lang and page.html['dir']=='ltr',lang
 assert len(page.select('h1'))==1,lang
 title=json.loads(re.search(r'^title: (.+)$',fm,re.M)[1]);description=json.loads(re.search(r'^description: (.+)$',fm,re.M)[1])
 assert page.h1.get_text(' ',strip=True)==title,lang
 assert [x['content'] for x in page.select('meta[name=description]')]==[description],lang
 canonical=f'https://rooted-glow.com/{lang}/{SLUG}/'
 assert [x['href'] for x in page.select('link[rel=canonical]')]==[canonical],lang
 assert not any('noindex' in x.get('content','') for x in page.select('meta[name=robots]')),lang
 assert label in prose.get_text(),lang
 assert strings['footer']['brandDesc'] in page.get_text(' ',strip=True),lang
 assert strings['newsletter']['description'] in page.get_text(' ',strip=True),lang
 assert len(prose.select('table'))==1 and len(prose.select('tbody tr'))==6,lang
 assert {a['href'] for a in prose.select('a[href]')}==SOURCES,lang
 assert not page.select('nav.content-journey'),'English journey leaked'
 assert not page.select('section.mt-16.pt-12'),'Unreviewed related-card fallback returned'
 schemas=[json.loads(x.string) for x in page.select('script[type="application/ld+json"]')]
 article=next(x for x in schemas if x.get('@type')=='Article')
 assert article['author']['@type']=='Organization',lang
 assert article['datePublished'].startswith('2026-04-13'),lang
 assert article['dateModified'].startswith('2026-10-04'),lang
print('PASS: 8 translated public routes, source citations, metadata, dates, canonical/H1/schema, related-card suppression; Arabic remains unpublished.')
