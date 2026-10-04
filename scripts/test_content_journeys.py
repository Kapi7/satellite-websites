"""Validate built contextual navigation, publication gates and corrected evidence labels."""
import argparse, json
from pathlib import Path
from html.parser import HTMLParser

ROOT=Path(__file__).resolve().parents[1]
class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.in_nav=False;self.links=[];self.canonical=[];self.h1=0;self.schemas=[];self.in_json=False
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='nav' and 'content-journey' in a.get('class',''):self.in_nav=True
        if tag=='a' and self.in_nav:self.links.append(a.get('href'))
        if tag=='link' and a.get('rel')=='canonical':self.canonical.append(a.get('href'))
        if tag=='h1':self.h1+=1
        if tag=='script' and a.get('type')=='application/ld+json':self.in_json=True
    def handle_endtag(self,tag):
        if tag=='nav':self.in_nav=False
        if tag=='script':self.in_json=False
    def handle_data(self,data):
        if self.in_json:self.schemas.append(json.loads(data))

args=argparse.ArgumentParser()
args.add_argument('--site', choices=['cosmetics','wellness','build-coded'])
site=args.parse_args().site
count=links=0
for folder,domain in [('cosmetics','glow-coded.com'),('wellness','rooted-glow.com'),('build-coded','build-coded.com')]:
    if site and folder != site: continue
    root=ROOT/folder;mapping=json.loads((root/'src/data/content-journeys.json').read_text())
    for slug,steps in mapping.items():
        page=Page();page.feed((root/'dist'/slug/'index.html').read_text())
        assert page.h1==1,(folder,slug,'h1')
        assert page.canonical==[f'https://{domain}/{slug}/'],(folder,slug,'canonical')
        assert page.links==[f'/{s["slug"]}/' for s in steps],(folder,slug,'journey targets')
        for step in steps:
            target=root/'dist'/step['slug']/'index.html'
            assert target.exists(),target
            assert step['slug']!=slug,'self link'
        article=next(s for s in page.schemas if s.get('@type')=='Article')
        assert article['author']['@type']=='Organization',article['author']
        for lang in ['de','es','fr','el','ru','it','ar','nl','pt']:
            translated=root/'dist'/lang/slug/'index.html'
            if translated.exists():
                foreign=Page();foreign.feed(translated.read_text());assert not foreign.links,(folder,slug,lang,'English journey leaked')
        count+=1;links+=len(steps)
    # No draft may leak into a generated route via the new navigation.
    for source in (root/'src/content/blog/en').glob('*.mdx'):
        if '\ndraft: true' in source.read_text().split('---',2)[1]:
            assert not (root/'dist'/source.stem/'index.html').exists(),source
if not site or site == 'wellness':
    protein=(ROOT/'wellness/dist/best-protein-powders-clean-natural/index.html').read_text()
    assert 'How to Compare Protein Powders: Labels, Testing and Cost' in protein
    assert '14 Tested Picks' not in protein
    assert 'Editorial correction, 3 October 2026' in protein
print(f'PASS: {count} configured pages, {links} contextual links; canonical/H1/schema, translation isolation, draft exclusion and protein correction.')
