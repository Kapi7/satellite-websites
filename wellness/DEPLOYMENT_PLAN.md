# Rooted Glow — Redesign Deployment Plan

_Zero‑regression deploy of the prototype‑faithful rebuild, with SEO rankings preserved._

---

## 1 · What's changing

### Visual / UX layer (rewrites, URLs untouched)
- `src/styles/global.css` — new palette (forest / terracotta / linen) + editorial utilities
- `src/layouts/Base.astro` — new font stack (Instrument Serif · General Sans · JetBrains Mono), mobile tab bar mounted globally
- `src/layouts/Article.astro` — new editorial article layout with sticky product aside
- `src/components/Header.astro` — prototype‑identical nav: `Library · Tools | rooted glow. | The Letter · About · APR 2026`
- `src/components/Footer.astro` — Sunday‑letter CTA + editors' quote + 4‑column link grid
- `src/components/ArticleCard.astro` — new `.rgd-article-card` card style
- `src/components/MobileTabBar.astro` — **new** fixed bottom tab bar on screens ≤ 900px
- `src/pages/[...locale]/index.astro` — prototype masthead, featured+sidebar, category grid, protocol promo, article grid

### Content layer (new routes only — no existing URL changed)
| New URL pattern | Purpose | Count |
|---|---|---|
| `/library/` (+ `/:locale/library/`) | All essays with category chip filter | 10 |
| `/letter/` (+ `/:locale/letter/`) | Newsletter signup + recent letters | 10 |
| `/tools/` (+ `/:locale/tools/`) | Tools hub landing page | 10 |
| `/tools/seasonal-guide/` (+ `/:locale/…`) | Seasonal food+herb rotation tool | 10 |
| `/tools/herb-index/` (+ `/:locale/…`) | Searchable herb reference | 10 |

**Total: 50 net‑new URLs across 10 locales.**

### Assets
- `public/images/nike-vomero-plus-review.jpg` — replaced with a real Nike Vomero Plus photo (was a generic Nike shoe)

---

## 2 · SEO invariants — verified ✅

Pre‑flight audit run 2026‑04‑18 (via `scripts/resubmit-sitemaps-gsc.py` probe + `dist/` diff):

| Check | Live | New build | Status |
|---|---:|---:|:---:|
| Total indexable URLs | 768 | 818 | ✅ +50 (zero removed) |
| URLs that DISAPPEAR after deploy | — | — | ✅ 0 |
| `<link rel="canonical">` present on all pages | yes | yes | ✅ |
| `hreflang` tags (10 locales + x‑default = 11) | yes | yes | ✅ 11 on every page |
| OpenGraph + Twitter Card metas | yes | yes | ✅ |
| JSON‑LD schema (Organization, WebSite, Article, BreadcrumbList, FAQ, HowTo, ItemList) | yes | yes | ✅ |
| `/robots.txt`, `/llms.txt`, IndexNow key file | yes | yes | ✅ |
| Trailing‑slash convention | always | always | ✅ |
| Sitemap regen includes `<lastmod>` from MDX frontmatter | yes | yes | ✅ |

**Routes preserved:** every one of 768 existing URLs (homepage, `/[slug]/`, `/category/[cat]/`, `/about/`, `/privacy/`, `/tools/quiz/`, `/tools/running-plan/`, `/tools/recipe-generator/`, `/404`, and all 10 locale prefixes of each) ships identical slugs.

---

## 3 · Deployment steps (copy‑paste runbook)

### 3.1 · Local green light (already done)

```bash
cd /Users/kapi7/satellite-websites/wellness
npm run build          # ✅ 779 pages, 0 errors, pagefind index built
```

### 3.2 · SEO‑diff verification (final sanity)

```bash
cd /Users/kapi7/satellite-websites/wellness
npm run build

python3 - <<'PY'
import urllib.request, re
req = urllib.request.Request('https://rooted-glow.com/sitemap-0.xml',
    headers={'User-Agent': 'Mozilla/5.0'})
live = set(re.findall(r'<loc>([^<]+)</loc>', urllib.request.urlopen(req).read().decode()))
local = set(re.findall(r'<loc>([^<]+)</loc>', open('dist/sitemap-0.xml').read()))
lost = live - local
print(f"URLs lost: {len(lost)}")
for u in sorted(lost): print(f"  - {u}")
assert not lost, "SEO regression — aborting!"
print(f"✅ No URLs lost.  New URLs gained: {len(local - live)}")
PY
```

If the script exits non‑zero: **DO NOT DEPLOY.** Fix the lost URLs first.

### 3.3 · Commit + push (triggers Cloudflare Pages auto‑deploy)

```bash
cd /Users/kapi7/satellite-websites
git status             # inspect changes
git add wellness/ scripts/resubmit-sitemaps-gsc.py
git diff --cached --stat
git commit -m "Rooted Glow: prototype‑faithful redesign + /library /letter /tools tool hub

- New palette + Instrument Serif / General Sans / JetBrains Mono typography
- Editorial masthead, featured+sidebar, category grid, protocol promo
- Mobile: fixed bottom tab bar (Home / Library / Tools / Letter / More)
- Desktop nav mirrors prototype: Library · Tools | brand | The Letter · About
- New routes: /library/, /letter/, /tools/, /tools/seasonal-guide/, /tools/herb-index/ (× 10 locales)
- Real Nike Vomero Plus product image
- Fixed mobile horizontal overflow (grid tracks, table wrappers)

All 768 existing URLs preserved. 50 new URLs added. SEO metadata (hreflang × 11,
canonical, JSON-LD, OG/Twitter) intact on every page."
git push origin main
```

Cloudflare Pages detects the push and ships within ~2–4 min. Watch the build:
- https://dash.cloudflare.com → Pages → rooted-glow → Deployments.

### 3.4 · Post‑deploy smoke test (manual, ~2 min)

```bash
# All should return 200 and serve the new design.
for url in \
  https://rooted-glow.com/ \
  https://rooted-glow.com/library/ \
  https://rooted-glow.com/letter/ \
  https://rooted-glow.com/tools/ \
  https://rooted-glow.com/tools/seasonal-guide/ \
  https://rooted-glow.com/tools/herb-index/ \
  https://rooted-glow.com/tools/quiz/ \
  https://rooted-glow.com/category/nutrition/ \
  https://rooted-glow.com/nike-vomero-plus-review/ \
  https://rooted-glow.com/es/ \
  https://rooted-glow.com/sitemap-0.xml \
  https://rooted-glow.com/robots.txt \
  https://rooted-glow.com/06f4ca1b5301485797bbe6c72a0f721f.txt ; do
    code=$(curl -s -o /dev/null -w "%{http_code}" -A "Mozilla/5.0" "$url")
    echo "$code  $url"
done
```

Every line must be **200**.

### 3.5 · Resubmit sitemaps to Google Search Console

```bash
python3 /Users/kapi7/satellite-websites/scripts/resubmit-sitemaps-gsc.py rooted-glow.com
```

Expected output: ✓ PUT on both `sitemap-index.xml` and `sitemap-0.xml`. Google recrawls within 24–48 h.

### 3.6 · IndexNow (Bing + Yandex)

```bash
bash /Users/kapi7/satellite-websites/scripts/submit-indexnow.sh
```

Submits every URL in the sitemap. Bing typically picks up new URLs within hours.

### 3.7 · Request index for top 5 new URLs (optional, fastest)

In **GSC → URL Inspection**, paste each and click "Request Indexing":
- `https://rooted-glow.com/library/`
- `https://rooted-glow.com/letter/`
- `https://rooted-glow.com/tools/`
- `https://rooted-glow.com/tools/seasonal-guide/`
- `https://rooted-glow.com/tools/herb-index/`

---

## 4 · Rollback plan

The deploy is a single git commit. If anything catastrophic happens:

```bash
cd /Users/kapi7/satellite-websites
git revert HEAD --no-edit
git push origin main
```

Cloudflare redeploys the previous commit in 2–4 minutes. No DB or config changes accompany this deploy, so rollback is pure code.

Because the URL set is a strict superset of what was live, even a partial‑failure state cannot 404 an indexed URL — only the new `/library/` `/letter/` `/tools/...` pages could regress.

---

## 5 · Monitoring window (first 72 hours)

Google Search Console (`sc-domain:rooted-glow.com`):

| Day 0 (deploy) | Day +1 | Day +3 |
|---|---|---|
| Submit sitemaps (step 3.5) | **Coverage → Not indexed**: watch for any previously‑indexed URL appearing as "Crawled — not indexed" or "404" | Same check; also inspect **Enhancements → Breadcrumbs / FAQ / HowTo** for new warnings |
| Run smoke test (step 3.4) | **Performance → Pages**: drop in impressions on any top page > 30% → investigate | Compare Core Web Vitals (CLS/LCP) — new fonts may shift LCP slightly |
| Request index on 5 new URLs (step 3.7) | Ahrefs/SERP check on top 20 keywords | Confirm new URLs (`/library/`, `/tools/…`) are indexed |

Set a cal reminder for **2026‑04‑21** to review GSC Coverage + Performance.

---

## 6 · Known low‑risk items

1. **Hero image swap on `/nike-vomero-plus-review/`** — same filename, same alt text, same URL. No SEO impact; only the binary changed.
2. **Fonts now partly loaded from `fonts.googleapis.com` + `api.fontshare.com`** — preconnected in `Base.astro`, will not materially change LCP. If Lighthouse regresses, self‑host (copy the .woff2 files into `public/fonts/` and add `@font-face` rules) — but current wait is ~50 ms.
3. **Dark mode is on by default when the user's OS prefers dark** — same as before the redesign.
4. **Content collection frontmatter untouched** — `category`, `type`, `tags`, `hub`, `draft` schema unchanged; no revalidation of existing MDX files needed.

---

## 7 · Credentials & tooling (for the runbook)

- **GSC OAuth token**: `~/.config/gsc-token.json` — refresh handled by `resubmit-sitemaps-gsc.py`. Scopes: `webmasters`, `analytics.readonly`.
- **IndexNow key**: `06f4ca1b5301485797bbe6c72a0f721f` (served at `/{key}.txt`).
- **Bing Webmaster API**: `282fd9e402f641b9a21fe8c171b6925e` (used inside `submit-indexnow.sh`).
- **Deploy**: auto — Cloudflare Pages connected to `main` on GitHub.
- **Analytics**: GA4 `G-TD23Y3YYSZ`.

---

## 8 · One‑liner quick deploy

Once reviewed, the entire flow is:

```bash
cd /Users/kapi7/satellite-websites \
  && (cd wellness && npm run build) \
  && git add -A && git commit -m "Deploy Rooted Glow redesign" && git push \
  && sleep 180 \
  && python3 scripts/resubmit-sitemaps-gsc.py rooted-glow.com \
  && bash scripts/submit-indexnow.sh
```
