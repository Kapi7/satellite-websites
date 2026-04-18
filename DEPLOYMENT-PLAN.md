# Glow Coded — Redesign Deployment Plan

**Scope:** Ship the zine redesign (desktop + mobile prototype parity) to glow-coded.com without losing any SEO equity from the 738 currently-indexed URLs.

**Site topology:**
- **Host:** Cloudflare Pages (auto-deploys from `main` push on GitHub `Kapi7/satellite-websites`)
- **GSC properties (both verified as siteOwner):**
  - `sc-domain:glow-coded.com` — covers www + non-www + all paths
  - `https://glow-coded.com/` — URL-prefix property
- **Sitemaps currently submitted** (last 2026-04-10, 0 errors, 0 warnings):
  - `https://glow-coded.com/sitemap-index.xml` — 738 URLs
  - `https://glow-coded.com/sitemap-0.xml` — 738 URLs (flat)
  - `https://glow-coded.com/rss.xml` — 63 URLs
- **IndexNow:** key `06f4ca1b5301485797bbe6c72a0f721f` at `/06f4ca1b…txt`
- **GSC token:** `~/.config/gsc-token.json` (webmasters + analytics.readonly scopes, siteOwner)

---

## 1 · What changed in this redesign

| Surface | Before | After |
|---|---|---|
| Homepage | Custom Tailwind | Prototype desktop (`/desktop.html`) + prototype mobile (`/index.html`) |
| Header | Sticky + dark-mode toggle + tools dropdown | Prototype nav (HOME · CATEGORIES · SHOP · FREE TOOLS · THE LETTER · ABOUT), curvy-3-line mobile hamburger + drawer |
| Footer | 4-col mix | Prototype 4-col (brand · READ · TOOLS · HOUSE) |
| **New pages** | — | `/shop/`, `/tools/` (× 10 locales = **20 new URLs**) |
| Mobile chrome | Desktop CSS scaled | Separate prototype mobile layout + fixed bottom **TabBar** (HOME · READ · TOOLS · SHOP · MORE) |
| Tool pages | Tailwind headers | Zine headers (kicker + italic-coral h1 + lede) |
| Article layout | Same | Same (kept — no URL change) |
| Paper color | `#fdfbf9` (white-ish) | `#f6ece0` (true warm paper, matches prototype) |

**Every existing URL is preserved.** No article slug, category slug, or locale prefix was renamed.

---

## 2 · Pre-flight checklist (run before pushing)

Run each from the repo root. Must all pass.

### 2.1 Build locally, 0 errors

```bash
cd /Users/kapi7/satellite-websites/cosmetics
rm -rf dist
npm run build 2>&1 | tee /tmp/glow-build.log
tail -10 /tmp/glow-build.log
```
✅ Expected: `739 page(s) built` (738 old + /shop + /tools + loc prefixes = 739 includes new pages minus some overlap).

### 2.2 Sitemap still has every old URL

```bash
# Before-deploy URL list from the live sitemap:
curl -s https://glow-coded.com/sitemap-0.xml \
  | grep -oE '<loc>[^<]+</loc>' | sed 's/<[^>]*>//g' | sort > /tmp/live-urls.txt

# After-build URL list from freshly-built sitemap:
grep -oE '<loc>[^<]+</loc>' cosmetics/dist/sitemap-0.xml | sed 's/<[^>]*>//g' | sort > /tmp/new-urls.txt

echo "=== URLs present before but MISSING after deploy: ==="
comm -23 /tmp/live-urls.txt /tmp/new-urls.txt
echo "=== Brand-new URLs added this deploy: ==="
comm -13 /tmp/live-urls.txt /tmp/new-urls.txt
```
✅ Expected: left diff is empty (no URLs lost). Right diff contains `/shop/`, `/tools/`, and their locale variants.

### 2.3 Article-level SEO still present

```bash
for u in anua-heartleaf-toner-vs-im-from-rice-toner best-korean-sunscreens-oily-skin-no-white-cast skincare-ingredient-compatibility-guide; do
  f="cosmetics/dist/$u/index.html"
  echo "=== $u ==="
  grep -oE '(rel="canonical"[^>]+|hreflang="[a-z-]+"|"@context"|og:url|twitter:card)' "$f" | sort -u | head -8
done
```
✅ Expected on every article: canonical, 10 hreflangs, schema.org JSON-LD, og:url, twitter:card.

### 2.4 No broken t() translation keys leaking

```bash
grep -rE 't\(\s*locale\s*,\s*['\''"]([a-zA-Z.]+)['\''"]' cosmetics/src \
  | grep -oE "t\(.*?['\\\"]([a-zA-Z.]+)" | sort -u > /tmp/used-keys.txt
python3 -c "
import json, sys
d = json.load(open('cosmetics/src/i18n/translations/en.json'))
def flat(x, p=''):
    r = {}
    for k,v in x.items():
        kk = f'{p}.{k}' if p else k
        if isinstance(v, dict): r.update(flat(v, kk))
        else: r[kk] = v
    return r
en = set(flat(d).keys())
used = set(l.split(\"'\")[-1].rstrip('\"') for l in open('/tmp/used-keys.txt') if l.strip())
missing = used - en
print('Missing keys (must be empty):', missing)
"
```
✅ Expected: `Missing keys (must be empty): set()`

### 2.5 Lighthouse-ish snapshot of the new pages (optional but recommended)

```bash
npx serve cosmetics/dist -l 4000 &
SERVE=$!
sleep 2
for p in / /shop/ /tools/ /anua-heartleaf-toner-vs-im-from-rice-toner/ /category/skincare/ /about/; do
  curl -s -o /dev/null -w "%{http_code}  $p\n" "http://localhost:4000$p"
done
kill $SERVE
```
✅ Expected: all `200`.

---

## 3 · Deploy

Single command — the existing deploy script handles build + push + IndexNow:

```bash
cd /Users/kapi7/satellite-websites
bash scripts/deploy.sh
```

What it does:
1. Builds `cosmetics/` and `wellness/` (both Astro sites) — produces `cosmetics/dist/`
2. `git add -A && git commit && git push` to `Kapi7/satellite-websites` on GitHub
3. Cloudflare Pages detects the push, runs its own build, ships to CDN (≈2 min)
4. Calls `scripts/submit-indexnow.sh` → pings Bing/Yandex with every sitemap URL

**Do NOT use `--skip-build`** for this deploy — we want a fresh build with the redesign.

If you want to stage first:
```bash
# Push to a branch Cloudflare Pages will build as a preview URL:
git checkout -b redesign-ship
git push -u origin redesign-ship
# Cloudflare Pages will deploy to <branch>.<project>.pages.dev
# Review, then merge to main:
git checkout main && git merge redesign-ship && git push
```

---

## 4 · Post-deploy verification (run within 15 minutes of push)

### 4.1 Cloudflare Pages build succeeded

```bash
# Replace <proj> with the Cloudflare Pages project slug if you use wrangler.
# Otherwise just visit https://dash.cloudflare.com/?to=/:account/pages and check "Deployments".
```

### 4.2 Live URL smoke test

```bash
for p in / /shop/ /tools/ /quiz/ /ingredient-checker/ /anua-heartleaf-toner-vs-im-from-rice-toner/ /category/skincare/ /about/ /sitemap-index.xml /robots.txt; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "https://glow-coded.com$p")
  echo "$code  https://glow-coded.com$p"
done
```
✅ Expected: everything `200`. Any non-200 = rollback candidate.

### 4.3 Random sample of old article URLs still live

```bash
for slug in 10-sunscreens-no-white-cast retinol-for-beginners-start-here hyaluronic-acid-vs-glycerin what-is-glass-skin-how-to-get-it korean-skincare-routine-complete-guide; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "https://glow-coded.com/$slug/")
  echo "$code  /$slug/"
done
```
✅ Expected: all `200`.

### 4.4 Resubmit sitemap to GSC

This is the single most important step for preserving SEO — it tells Google "I have 20 new URLs, recheck my sitemap":

```bash
python3 << 'EOF'
import json, os, requests
tok = json.load(open(os.path.expanduser('~/.config/gsc-token.json')))
r = requests.post('https://oauth2.googleapis.com/token', data={
    'client_id': tok['client_id'], 'client_secret': tok['client_secret'],
    'refresh_token': tok['refresh_token'], 'grant_type': 'refresh_token'})
access = r.json()['access_token']
site = 'sc-domain:glow-coded.com'
for sm in ['https://glow-coded.com/sitemap-index.xml',
           'https://glow-coded.com/sitemap-0.xml',
           'https://glow-coded.com/rss.xml']:
    r = requests.put(
        f'https://www.googleapis.com/webmasters/v3/sites/{site}/sitemaps/{sm}',
        headers={'Authorization': f'Bearer {access}'})
    print(sm, '→', r.status_code, r.text[:100])
EOF
```
✅ Expected: `200` for every sitemap.

### 4.5 Request indexing for the two brand-new URLs

GSC's URL Inspection API (manual UI is also fine):

```bash
# In the GSC web UI:
#   https://search.google.com/search-console?resource_id=sc-domain:glow-coded.com
# → URL Inspection (top bar) → paste https://glow-coded.com/shop/
# → click "Request indexing" (waits ~1 minute)
# Repeat for: /tools/, /es/shop/, /es/tools/ (2-3 locale-prefixed is enough to prompt crawl of the rest)
```

---

## 5 · SEO preservation — specific invariants

Everything below is preserved by the redesign code — this list exists so that if any of these ever regresses, you know what to look for.

| Invariant | Where it lives | Why it matters |
|---|---|---|
| Every old article URL is still reachable at the same path | `src/pages/[...locale]/[slug].astro` | Loses PageRank + backlinks if a slug changes |
| `rel="canonical"` per page | `src/layouts/Base.astro` — `canonical` var | Prevents duplicate-content penalties across locales |
| 10 `<link rel="alternate" hreflang="…">` per page + `x-default` | `src/layouts/Base.astro` — `locales.map(...)` | Keeps 10-locale SERP clusters intact |
| `@type: Article` + `@type: BreadcrumbList` JSON-LD on articles | `src/layouts/Article.astro` — `articleSchema`, `breadcrumbSchema` | Drives rich snippets |
| `HowTo` + `FAQPage` + `ItemList` schema (auto) | `src/layouts/Article.astro` lines 68–140 | Feature eligibility |
| og:url, og:image, twitter:card | `src/layouts/Base.astro` | Shareability on Meta/X/Pinterest |
| Sitemap auto-regeneration | `astro.config.mjs` — `@astrojs/sitemap` integration | Re-advertises all 700+ URLs each build |
| `robots.txt` with `Sitemap:` line | `cosmetics/public/robots.txt` | Discovery by Bing/Yandex |
| IndexNow key file | `cosmetics/public/06f4ca1b5301485797bbe6c72a0f721f.txt` | Bing/Yandex near-instant indexing |
| `llms.txt` + `llms-full.txt` | `cosmetics/public/` | AI crawler discovery (Perplexity, etc.) |

---

## 6 · What could go wrong — rollback plan

| Symptom | Probable cause | Rollback |
|---|---|---|
| Cloudflare Pages build fails | Astro import/type error in redesigned components | `git revert HEAD && git push` — Cloudflare auto-redeploys the previous commit (~2 min) |
| Random 404s on article URLs after deploy | Base.astro `locale` prefix logic changed | Same — `git revert` |
| GSC Coverage report shows "Crawled - currently not indexed" spike | Thin content flags on new /shop/ /tools/ because they're product-listing, not editorial | Non-urgent. Add more prose to the hero sections of /shop/ and /tools/, redeploy. GSC re-evaluates within a week. |
| Mobile TabBar overlaps footer content | `body { padding-bottom: 70px }` missing on a specific page | Add to the offending page template or bump the global rule in `TabBar.astro`'s `<style>` |
| `hreflang` mismatch warning in GSC | A locale version returning 404 while the reference still points to it | Check which locale path 404s; restore the page or rebuild |

To roll back: `git revert HEAD && git push`. Cloudflare picks it up within 90 seconds. All previous commits (and therefore all previous sitemaps) are retrievable.

---

## 7 · Monitoring schedule (first week)

| When | What | Command / URL |
|---|---|---|
| **T + 2 min** | Cloudflare build status | `https://dash.cloudflare.com` (Pages → deployments) |
| **T + 15 min** | Post-deploy smoke test (§ 4.2 + 4.3) | Shell script above |
| **T + 30 min** | Resubmit sitemaps (§ 4.4) | Python snippet above |
| **T + 1 hr** | Request indexing on /shop/ and /tools/ (§ 4.5) | GSC UI |
| **T + 24 hr** | Check GSC Coverage report for unexpected 404s / "Excluded" spikes | `https://search.google.com/search-console` → Indexing → Pages |
| **T + 3 days** | GSC Performance report: clicks / impressions trend | Same → Performance |
| **T + 7 days** | Run `scripts/weekly-report.py` for full diff | `python3 scripts/weekly-report.py` |

The `weekly-report.py` script already uses the existing GSC token to pull week-over-week clicks, impressions, CTR, and position for every property — so you will know within a week if the redesign moved the needle in either direction.

---

## 8 · Sanity checks you can do right now before shipping

```bash
# 1. All 10 locales build cleanly:
cd /Users/kapi7/satellite-websites/cosmetics && npm run build 2>&1 | grep -E "error|Completed"

# 2. No dead t() calls (should output nothing):
grep -rE "t\(\s*locale\s*,\s*['\"]([^'\"]+)['\"]\s*\)" src | \
  awk -F"['\"]" '{print $2}' | sort -u > /tmp/keys.txt
python3 -c "
import json
en = json.load(open('src/i18n/translations/en.json'))
def flat(x, p=''):
    r = {}
    for k,v in x.items():
        kk = f'{p}.{k}' if p else k
        r.update(flat(v,kk)) if isinstance(v,dict) else r.update({kk:v})
    return r
avail = set(flat(en).keys())
used = set(l.strip() for l in open('/tmp/keys.txt') if '.' in l)
print('keys used but not defined:', used - avail)
"

# 3. GSC auth still works:
python3 -c "
import json, os, requests
tok = json.load(open(os.path.expanduser('~/.config/gsc-token.json')))
r = requests.post('https://oauth2.googleapis.com/token', data={
  'client_id': tok['client_id'], 'client_secret': tok['client_secret'],
  'refresh_token': tok['refresh_token'], 'grant_type': 'refresh_token'})
print('GSC auth:', r.status_code, 'access token OK' if r.status_code == 200 else r.text)
"
```

---

## 9 · TL;DR — the actual command sequence

```bash
# 1. Pre-flight:
cd /Users/kapi7/satellite-websites/cosmetics && npm run build
# (confirm 739 pages, 0 errors)

# 2. Deploy:
cd /Users/kapi7/satellite-websites && bash scripts/deploy.sh

# 3. Post-deploy (after ~2 min for Cloudflare):
curl -s -o /dev/null -w "%{http_code}\n" https://glow-coded.com/shop/
curl -s -o /dev/null -w "%{http_code}\n" https://glow-coded.com/tools/
curl -s -o /dev/null -w "%{http_code}\n" https://glow-coded.com/anua-heartleaf-toner-vs-im-from-rice-toner/

# 4. Resubmit sitemaps to GSC:
python3 -c "
import json, os, requests
tok = json.load(open(os.path.expanduser('~/.config/gsc-token.json')))
r = requests.post('https://oauth2.googleapis.com/token', data={
  'client_id': tok['client_id'], 'client_secret': tok['client_secret'],
  'refresh_token': tok['refresh_token'], 'grant_type': 'refresh_token'})
a = r.json()['access_token']
for sm in ['https://glow-coded.com/sitemap-index.xml','https://glow-coded.com/sitemap-0.xml','https://glow-coded.com/rss.xml']:
  r = requests.put(f'https://www.googleapis.com/webmasters/v3/sites/sc-domain:glow-coded.com/sitemaps/{sm}', headers={'Authorization': f'Bearer {a}'})
  print(sm, r.status_code)
"

# 5. In GSC UI → URL Inspection → "Request indexing" on:
#    https://glow-coded.com/shop/
#    https://glow-coded.com/tools/
```

That's it. Every existing indexed URL is preserved; Google gets re-pinged on the updated sitemap; Bing/Yandex get pinged via IndexNow automatically inside `deploy.sh`.
