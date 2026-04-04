#!/usr/bin/env python3
"""
Submit i18n (translated) URLs for both satellite websites to Bing Webmaster API.
Run daily until all URLs are submitted. Respects 100 URLs/day/site quota.

Usage: python3 bing_submit_i18n.py
"""
import json
import os
import urllib.request
import urllib.error
from datetime import date

API_KEY = os.environ.get("BING_API_KEY", "282fd9e402f641b9a21fe8c171b6925e")
ENDPOINT = f"https://ssl.bing.com/webmaster/api.svc/json/SubmitUrlBatch?apikey={API_KEY}"
LOCALES = ["es", "de", "el", "ru", "it", "ar"]
MAX_PER_DAY = 100
STATE_FILE = os.path.join(os.path.dirname(__file__), "bing_i18n_state.json")

COSMETICS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cosmetics", "src", "content", "blog", "en")
WELLNESS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "wellness", "src", "content", "blog", "en")

def build_i18n_urls(domain, blog_dir):
    slugs = sorted([f.replace(".mdx", "") for f in os.listdir(blog_dir) if f.endswith(".mdx")])
    urls = []
    for loc in LOCALES:
        urls.append(f"https://{domain}/{loc}/")
    for loc in LOCALES:
        urls.append(f"https://{domain}/{loc}/about/")
    for loc in LOCALES:
        urls.append(f"https://{domain}/{loc}/privacy/")
    for loc in LOCALES:
        for slug in slugs:
            urls.append(f"https://{domain}/{loc}/{slug}/")
    return urls

def submit_batch(site_url, url_list):
    payload = json.dumps({"siteUrl": site_url, "urlList": url_list}).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT, data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def main():
    state = load_state()
    today = str(date.today())

    sites = [
        ("glow-coded.com", "https://glow-coded.com", COSMETICS_DIR),
        ("rooted-glow.com", "https://rooted-glow.com", WELLNESS_DIR),
    ]

    for domain, site_url, blog_dir in sites:
        all_urls = build_i18n_urls(domain, blog_dir)
        site_state = state.get(domain, {"submitted": [], "last_date": ""})
        already = set(site_state.get("submitted", []))
        pending = [u for u in all_urls if u not in already]

        if not pending:
            print(f"{domain}: All {len(all_urls)} i18n URLs already submitted!")
            continue

        batch = pending[:MAX_PER_DAY]
        print(f"{domain}: Submitting {len(batch)} of {len(pending)} pending URLs ({len(already)} already done)")

        status, body = submit_batch(site_url, batch)
        print(f"  Response: {status} — {body}")

        if status == 200:
            already.update(batch)
            site_state["submitted"] = list(already)
            site_state["last_date"] = today
            state[domain] = site_state
            save_state(state)
            print(f"  Saved state. {len(pending) - len(batch)} URLs remaining.")
        else:
            print(f"  Submission failed. Will retry next run.")

    print(f"\nState saved to {STATE_FILE}")

if __name__ == "__main__":
    main()
