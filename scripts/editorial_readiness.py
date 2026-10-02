"""Read-only draft inventory. Passing automated checks is not editorial approval."""
import json
from pathlib import Path
from content_quality import validate
from require_article_hero import check
ROOT = Path(__file__).resolve().parents[1]
LOCALES = ['en','es','de','el','ru','it','ar','fr','nl','pt']
def inventory():
    result = {}
    for site in ['cosmetics','wellness','build-coded']:
        rows=[]
        for path in sorted((ROOT/site/'src/content/blog/en').glob('*.mdx')):
            import re
            if not re.search(r'^draft:\s*true\s*$',path.read_text().split('---',2)[1],re.M):continue
            blockers=[]
            for lang in LOCALES:
                translated=path.parent.parent/lang/path.name
                if not translated.exists():blockers.append(lang+': missing translation');continue
                error=check(translated)
                if error:blockers.append(lang+': '+error)
            if site=='cosmetics':blockers.extend(validate(path,True))
            rows.append({'slug':path.stem,'blockers':list(dict.fromkeys(blockers))})
        result[site]={'rawDrafts':len(rows),'automatedChecksPassing':sum(not r['blockers'] for r in rows),'editoriallyApprovedRunway':'not certified by this report','drafts':rows}
    return result
if __name__=='__main__':print(json.dumps(inventory(),ensure_ascii=False,indent=2))
