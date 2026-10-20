"""Read-only draft inventory. Passing automated checks is not editorial approval."""
import json
from pathlib import Path
from content_quality import validate
from require_article_hero import check
from reviewed_publisher import validate as validate_release
ROOT = Path(__file__).resolve().parents[1]
LOCALES = ['en','es','de','el','ru','it','ar','fr','nl','pt']
def inventory():
    result = {}
    manifest = ROOT / "scripts/reviewed-releases.json"
    approvals = json.loads(manifest.read_text())["articles"] if manifest.exists() else []
    for site in ['cosmetics','wellness','build-coded']:
        rows=[]
        for path in sorted((ROOT/site/'src/content/blog/en').glob('*.mdx')):
            import re
            if not re.search(r'^draft:\s*true\s*$',path.read_text().split('---',2)[1],re.M):continue
            reviewed = next((r for r in approvals if r['site']==site and r['slug']==path.stem and r['status']=='pending'), None)
            if reviewed:
                rows.append({'slug':path.stem,'reviewedLocales':list(reviewed['locales']), 'blockers':validate_release(reviewed)})
                continue
            blockers=[]
            for lang in LOCALES:
                translated=path.parent.parent/lang/path.name
                if not translated.exists():blockers.append(lang+': missing translation');continue
                error=check(translated)
                if error:blockers.append(lang+': '+error)
            blockers.extend(validate(path,site=='cosmetics'))
            rows.append({'slug':path.stem,'blockers':list(dict.fromkeys(blockers))})
        result[site]={'rawDrafts':len(rows),'automatedChecksPassing':sum(not r['blockers'] for r in rows),'editoriallyApprovedRunway':'not certified by this report','drafts':rows}
    return result
if __name__=='__main__':print(json.dumps(inventory(),ensure_ascii=False,indent=2))
