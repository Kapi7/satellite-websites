#!/usr/bin/env python3
"""
Resubmit sitemaps to Google Search Console after a deploy.

Re-pings the sitemap URL for each verified property so GSC crawls recently
changed URLs sooner. Safe to run repeatedly — GSC just records a new
`lastSubmitted` timestamp.

Usage:
    python3 scripts/resubmit-sitemaps-gsc.py              # all sites
    python3 scripts/resubmit-sitemaps-gsc.py rooted-glow.com  # single site

Requires `~/.config/gsc-token.json` with webmasters scope.
"""

import json
import os
import sys
import urllib.parse
import urllib.request

TOKEN_FILE = os.environ.get("GSC_TOKEN_FILE", os.path.expanduser("~/.config/gsc-token.json"))

SITES = {
    "rooted-glow.com": {
        "property": "sc-domain:rooted-glow.com",
        "sitemaps": [
            "https://rooted-glow.com/sitemap-index.xml",
            "https://rooted-glow.com/sitemap-0.xml",
        ],
    },
    "glow-coded.com": {
        "property": "sc-domain:glow-coded.com",
        "sitemaps": [
            "https://glow-coded.com/sitemap-index.xml",
            "https://glow-coded.com/sitemap-0.xml",
        ],
    },
    "build-coded.com": {
        "property": "sc-domain:build-coded.com",
        "sitemaps": [
            "https://build-coded.com/sitemap-index.xml",
            "https://build-coded.com/sitemap-0.xml",
        ],
    },
}


def refresh_access_token():
    with open(TOKEN_FILE) as f:
        tok = json.load(f)
    data = urllib.parse.urlencode({
        "client_id": tok["client_id"],
        "client_secret": tok["client_secret"],
        "refresh_token": tok["refresh_token"],
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request(tok["token_uri"], data=data, method="POST")
    with urllib.request.urlopen(req) as r:
        new = json.loads(r.read())
    return new["access_token"]


def submit_sitemap(access_token: str, site_property: str, sitemap_url: str):
    # PUT /webmasters/v3/sites/{siteUrl}/sitemaps/{feedpath}
    site_enc = urllib.parse.quote(site_property, safe="")
    feed_enc = urllib.parse.quote(sitemap_url, safe="")
    url = f"https://www.googleapis.com/webmasters/v3/sites/{site_enc}/sitemaps/{feed_enc}"
    req = urllib.request.Request(url, method="PUT")
    req.add_header("Authorization", f"Bearer {access_token}")
    try:
        with urllib.request.urlopen(req) as r:
            return True, r.status
    except urllib.error.HTTPError as e:
        return False, f"{e.code} {e.reason}: {e.read().decode()[:200]}"
    except Exception as e:
        return False, str(e)


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else None
    access = refresh_access_token()
    print("✓ GSC access token refreshed")

    hosts = [target] if target else list(SITES.keys())
    for host in hosts:
        if host not in SITES:
            print(f"✗ Unknown site: {host}")
            continue
        cfg = SITES[host]
        print(f"\n=== {host} (property: {cfg['property']}) ===")
        for sm in cfg["sitemaps"]:
            ok, info = submit_sitemap(access, cfg["property"], sm)
            status = "✓" if ok else "✗"
            print(f"  {status} {sm} -> {info}")


if __name__ == "__main__":
    main()
