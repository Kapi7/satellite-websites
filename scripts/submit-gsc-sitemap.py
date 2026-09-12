#!/usr/bin/env python3
"""Re-submit sitemap-index.xml to GSC for all 3 satellite sites.
Submission helps discovery; it does not guarantee crawling, indexing, or rankings.
"""
import json, os, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

TOKEN = Path(os.environ.get("GSC_TOKEN_FILE", str(Path.home() / ".config" / "gsc-token.json")))
SITES = [
    ("sc-domain:glow-coded.com",  "https://glow-coded.com/sitemap-index.xml"),
    ("sc-domain:rooted-glow.com", "https://rooted-glow.com/sitemap-index.xml"),
    ("sc-domain:build-coded.com", "https://build-coded.com/sitemap-index.xml"),
]

def token():
    td = json.loads(TOKEN.read_text())
    exp = datetime.fromisoformat(td["expiry"].replace("Z", "+00:00"))
    now = datetime.now(exp.tzinfo) if exp.tzinfo else datetime.now()
    if now >= exp:
        body = urllib.parse.urlencode({
            "client_id": td["client_id"], "client_secret": td["client_secret"],
            "refresh_token": td["refresh_token"], "grant_type": "refresh_token"}).encode()
        r = json.loads(urllib.request.urlopen("https://oauth2.googleapis.com/token", data=body, timeout=30).read())
        td["token"] = r["access_token"]
        td["expiry"] = (datetime.now() + timedelta(seconds=r["expires_in"])).isoformat()
        TOKEN.write_text(json.dumps(td, indent=2))
    return td["token"]

def main():
    t = token()
    ok = 0
    for site, sm in SITES:
        url = f"https://www.googleapis.com/webmasters/v3/sites/{urllib.parse.quote(site, safe='')}/sitemaps/{urllib.parse.quote(sm, safe='')}"
        try:
            urllib.request.urlopen(urllib.request.Request(url, method="PUT",
                headers={"Authorization": f"Bearer {t}"}), timeout=30)
            print(f"  ✓ {sm}")
            ok += 1
        except Exception as e:
            print(f"  ✗ {sm}: {type(e).__name__}")
    print(f"[gsc-sitemap] {ok}/{len(SITES)} re-submitted")
    return 0 if ok == len(SITES) else 1

if __name__ == "__main__":
    raise SystemExit(main())
