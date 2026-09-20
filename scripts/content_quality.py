"""Deterministic Glow Coded publication checks; no API calls or model scores."""
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCALES = ('es', 'de', 'el', 'ru', 'it', 'ar', 'fr', 'nl', 'pt')

def split(text):
    parts = text.split('---', 2)
    if len(parts) != 3 or parts[0].strip():
        raise ValueError('Missing frontmatter')
    return parts[1], parts[2]

def fingerprint(text):
    fm, body = split(text)
    # Publication dates and draft transitions do not change translation meaning.
    fm = re.sub(r'^(?:date|updated|draft|translationSourceHash):[^\n]*\n?', '', fm, flags=re.M)
    return hashlib.sha256((fm.strip()+'\n'+body.strip()).encode()).hexdigest()

def paragraphs(text):
    body = split(text)[1]
    return [p for p in re.split(r'\n\s*\n', body) if len(p.split()) >= 25 and not p.lstrip().startswith(('#','|','![','[![','```'))]

def unchanged(source, target):
    normalized = {' '.join(p.split()) for p in paragraphs(source)}
    return [p for p in paragraphs(target) if ' '.join(p.split()) in normalized]

def is_current(source, target):
    if not target.exists():
        return False
    m = re.search(r'^translationSourceHash:\s*[\"\']?([a-f0-9]{64})', target.read_text(), re.M)
    return bool(m and m.group(1) == fingerprint(source.read_text()))

def stamp(source, target_text):
    fm, body = split(target_text)
    fm = re.sub(r'^translationSourceHash:[^\n]*\n?', '', fm, flags=re.M)
    return '---'+fm.rstrip()+'\ntranslationSourceHash: "'+fingerprint(source)+'"\n---'+body

def validate(source, require_image=False):
    errors = []
    text = source.read_text()
    for lang in LOCALES:
        target = source.parent.parent / lang / source.name
        if not is_current(source, target):
            errors.append(f'{lang}: missing or stale translation')
        if target.exists() and unchanged(text, target.read_text()):
            errors.append(f'{lang}: untranslated English paragraph')
    if require_image:
        fm, _ = split(text)
        m = re.search(r'^image:\s*[\"\']?([^\n\"\']+)', fm, re.M)
        image = m.group(1).strip() if m else ''
        public = ROOT / 'cosmetics/public' / image.lstrip('/')
        manifest = ROOT / 'cosmetics/src/data/image-approvals.json'
        approvals = json.loads(manifest.read_text()) if manifest.exists() else {}
        record = approvals.get(image, {})
        if not public.is_file() or record.get('sha256') != hashlib.sha256(public.read_bytes()).hexdigest() or not record.get('reviewedAt') or not record.get('sourceUrl'):
            errors.append('hero: missing current visual approval and product provenance')
    return errors

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source',type=Path)
    parser.add_argument('--current',type=Path)
    parser.add_argument('--require-image',action='store_true')
    args=parser.parse_args()
    if args.current:
        raise SystemExit(0 if is_current(args.source,args.current) else 1)
    errors=validate(args.source,args.require_image)
    for error in errors: print(f'{args.source.name}: {error}')
    raise SystemExit(bool(errors))

if __name__=='__main__': main()
