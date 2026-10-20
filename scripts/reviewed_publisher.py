"""Publish explicit, hash-reviewed locale bundles; never generate content at release time."""
import argparse
import hashlib
import json
import os
import re
import subprocess
import time
import urllib.request
from datetime import date
from pathlib import Path
from content_quality import fingerprint, is_current, translation_structure, unchanged, external_links
from markdown_quality import unclosed_fence
from require_article_hero import check as hero_check

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'scripts/reviewed-releases.json'
SITES = {'cosmetics': ('glow-coded', 'glow-coded.com'), 'wellness': ('rooted-glow', 'rooted-glow.com'), 'build-coded': ('build-coded', 'build-coded.com')}
LOCALES = {'en','es','de','el','ru','it','ar','fr','nl','pt'}

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def article_path(item, lang):
    if item['site'] not in SITES or lang not in LOCALES or not re.fullmatch(r'[a-z0-9-]+', item['slug']):
        raise ValueError('Invalid release path')
    return ROOT / item['site'] / 'src/content/blog' / lang / (item['slug'] + '.mdx')

def validate(item):
    errors=[]
    if not item.get('reviewedAt') or not item.get('reviewNotes') or 'en' not in item.get('locales', {}):
        return ['Missing explicit editorial review or English source']
    source=article_path(item, 'en')
    for lang, approved in item['locales'].items():
        path=article_path(item,lang)
        if not path.exists():errors.append(f'{lang}: missing article');continue
        text=path.read_text()
        if fingerprint(text)!=approved.get('contentHash'):errors.append(f'{lang}: copy changed since review')
        if unclosed_fence(text):errors.append(f'{lang}: unclosed Markdown fence')
        error=hero_check(path)
        if error:errors.append(f'{lang}: {error}')
        fm=text.split('---',2)[1]
        m=re.search(r'^image:\s*[\"\']?([^\n\"\']+)',fm,re.M)
        hero=m.group(1).strip() if m else ''
        images=approved.get('images',{})
        if hero not in images:errors.append(f'{lang}: hero not visually reviewed')
        # Every in-body local image must also have a review record.
        body_images=re.findall(r'!\[[^\]]*\]\((/images/[^)\s]+)\)',text)
        for image in body_images:
            if image not in images:errors.append(f'{lang}: body image not reviewed: {image}')
        for image,record in images.items():
            public=(ROOT/item['site']/'public').resolve();asset=(public/image.lstrip('/')).resolve()
            if not image.startswith('/images/') or not asset.is_relative_to(public) or not asset.is_file():
                errors.append(f'{lang}: missing image {image}');continue
            if not record.get('sourceUrl') or not record.get('visualReview') or digest(asset)!=record.get('sha256'):
                errors.append(f'{lang}: image changed or lacks provenance: {image}')
        if lang!='en':
            if not is_current(source,path):errors.append(f'{lang}: stale translation')
            errors.extend(f'{lang}: {e}' for e in translation_structure(source.read_text(),text,lang))
            if unchanged(source.read_text(),text):errors.append(f'{lang}: untranslated paragraph')
            if external_links(source.read_text())!=external_links(text):errors.append(f'{lang}: changed source links')
    # An excluded existing translation must remain a draft: do not accidentally release it.
    for lang in LOCALES-set(item['locales']):
        path=article_path(item,lang)
        if path.exists() and not re.search(r'^draft:\s*true\s*$',path.read_text().split('---',2)[1],re.M):
            errors.append(f'{lang}: unreviewed translation is already public')
    return errors

def prepare(item):
    """Only approved files transition; retrying preserves the release date."""
    for lang in item['locales']:
        path=article_path(item,lang);text=path.read_text();parts=text.split('---',2)
        if re.search(r'^draft:\s*true\s*$',parts[1],re.M):
            parts[1]=re.sub(r'^draft:\s*true\s*$', 'draft: false', parts[1],flags=re.M)
            parts[1]=re.sub(r'^date:.*$', 'date: '+item['publishDate'],parts[1],flags=re.M)
            path.write_text('---'.join(parts))

def run(*args, cwd=ROOT):
    subprocess.run(args,cwd=cwd,check=True)

def commit_paths(paths,message):
    run('git','add','--',*[str(p.relative_to(ROOT)) for p in paths])
    if subprocess.run(['git','diff','--cached','--quiet'],cwd=ROOT).returncode:
        run('git','commit','-m',message)
        committed=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        run('bash','scripts/push-publisher.sh')
        return committed
    return subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()

def verify_live(item):
    host=SITES[item['site']][1]
    for lang,record in item['locales'].items():
        route=('/' if lang=='en' else '/'+lang+'/')+item['slug']+'/'
        req=urllib.request.Request('https://'+host+route,headers={'Cache-Control':'no-cache','User-Agent':'SatelliteReleaseVerifier/1.0'})
        with urllib.request.urlopen(req,timeout=40) as r:html=r.read().decode()
        if not all(marker in html for marker in item['liveMarkers']):raise RuntimeError('Live copy mismatch: '+host+route)
        if re.search(r'<meta[^>]+(?:name=[\"\']robots[\"\'][^>]+content=[\"\'][^\"\']*noindex|content=[\"\'][^\"\']*noindex[^>]+name=[\"\']robots)',html,re.I):
            raise RuntimeError('Live article is noindex: '+host+route)
        if 'https://'+host+route not in html:raise RuntimeError('Missing canonical URL: '+route)
        for image,approval in record['images'].items():
            with urllib.request.urlopen('https://'+host+image,timeout=40) as r:data=r.read()
            if hashlib.sha256(data).hexdigest()!=approval['sha256']:raise RuntimeError('Live image mismatch: '+image)
        print('LIVE VERIFIED https://'+host+route,flush=True)

def report(data):
    counts={site:0 for site in SITES}
    for item in data['articles']:
        if item['status']=='pending':counts[item['site']]+=1
    raw={site:sum(bool(re.search(r'^draft:\s*true\s*$',p.read_text().split('---',2)[1],re.M)) for p in (ROOT/site/'src/content/blog/en').glob('*.mdx')) for site in SITES}
    lines=[f'{site}: {counts[site]} explicitly reviewed pending releases; {raw[site]} raw drafts (not an approved runway)' for site in SITES]
    if not any(counts.values()):lines.append('::warning::No reviewed releases queued. Editorial replenishment is required; a successful no-op is not content freshness.')
    print('\n'.join(lines),flush=True)
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as out:out.write('\n\n'+'\n\n'.join(lines)+'\n')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',action='store_true');ap.add_argument('--prepare',action='store_true',help='Local preview only; no push/deploy');args=ap.parse_args()
    data=json.loads(MANIFEST.read_text());report(data)
    pending=[item for item in data['articles'] if item['status']=='pending' and item['publishDate']<=date.today().isoformat()]
    if not pending:return
    for item in pending:
        errors=validate(item)
        if errors:raise RuntimeError(item['slug']+': '+ '; '.join(errors))
    if not (args.run or args.prepare):
        print('Review checks passed. Dry run: no files, network services or notifications changed.');return
    if args.run:
        # Run only in a clean checkout. Never stage an unrelated local modification.
        dirty=subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT,text=True)
        if dirty.strip():raise RuntimeError('Release requires a clean tracked checkout')
        if not os.environ.get('CLOUDFLARE_API_TOKEN') or not os.environ.get('CLOUDFLARE_ACCOUNT_ID'):raise RuntimeError('Deployment credentials missing')
    for item in pending:prepare(item)
    if args.prepare:return
    sites=sorted({i['site'] for i in pending})
    for site in sites:
        run('npm','install' if site=='build-coded' else 'ci','--no-audit','--no-fund',cwd=ROOT/site)
        run('npm','run','build',cwd=ROOT/site)
    paths=[article_path(i,lang) for i in pending for lang in i['locales']]
    built_commit=commit_paths(paths,'Publish reviewed article batch')
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if sha != built_commit:
        for item in pending:
            if validate(item):raise RuntimeError('Review invalidated by concurrent source changes')
        for site in sites:run('npm','run','build',cwd=ROOT/site)
    for site in sites:
        project,host=SITES[site]
        run('npx','wrangler','pages','deploy','dist','--project-name='+project,'--branch=main','--commit-hash='+sha,'--commit-dirty=true',cwd=ROOT/site)
    for item in pending:
        for attempt in range(4):
            try:verify_live(item);break
            except Exception:
                if attempt==3:raise
                time.sleep(10)
    # Merge acknowledgements into the latest manifest; preserve concurrent new approvals.
    data=json.loads(MANIFEST.read_text())
    for item in pending:
        current=next(r for r in data['articles'] if r['site']==item['site'] and r['slug']==item['slug'])
        if current['locales'] != item['locales'] or current['publishDate'] != item['publishDate']:
            raise RuntimeError('Release approval changed during deployment')
        current['status']='verified';current['publishedCommit']=sha
    MANIFEST.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    commit_paths([MANIFEST],'Record verified live article release')
    report(data)

if __name__=='__main__':main()
