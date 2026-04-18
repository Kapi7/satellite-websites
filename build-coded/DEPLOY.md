# Build Coded — Redesign Deploy & GSC Playbook

**Goal:** ship the mobile redesign to https://build-coded.com without losing ANY of the existing SEO equity (ranked pages, sitemap coverage, GSC data, crawl budget, hreflang).

---

## 0. Current state (verified 2026-04-18)

| Item | Status |
|------|--------|
| Live domain | `https://build-coded.com` (200 OK, Cloudflare) |
| Hosting | Cloudflare Pages, project name `build-coded`, deployed via `wrangler pages deploy` (NOT GitHub-integration) |
| Sitemap | `https://build-coded.com/sitemap-index.xml` → `sitemap-0.xml` (live) |
| robots.txt | Live, points to sitemap |
| hreflang | 10 locales (en + es, de, el, ru, it, ar, fr, nl, pt) already set |
| Canonicals | Present on every page |
| schema.org JSON-LD | Present (Organization + WebSite + per-page Article) |
| BingSiteAuth.xml | Present in `public/` → Bing webmaster already verified |
| IndexNow key | `06f4ca1b5301485797bbe6c72a0f721f.txt` in `public/` |
| GA4 | Placeholder `G-MP5LPFNBN5` — real property not yet created |
| GSC verification | **No meta tag in live HTML** → either DNS/HTML-file verified, or not yet verified. Needs confirmation. |
| Daily auto-publisher | `scripts/daily-publish.sh` runs via cron; calls wrangler on build-coded changes |
| Uncommitted redesign | 13 files in `build-coded/` (desktop + mobile work) — not yet pushed |

---

## 1. Pre-deploy safety checks (do not skip)

These run locally and prevent the two most common SEO-killers: URL churn and broken hreflang.

### 1.1 URL parity — no page may disappear
The redesign must serve every URL that exists today. Compare old vs new sitemap:

```bash
# Capture today's live URLs
curl -s https://build-coded.com/sitemap-0.xml | grep -oE '<loc>[^<]+</loc>' | sed 's/<[^>]*>//g' | sort > /tmp/build-coded-live-urls.txt

# Build locally and capture new URLs
cd /Users/kapi7/satellite-websites/build-coded
npm run build
grep -oE '<loc>[^<]+</loc>' dist/sitemap-0.xml | sed 's/<[^>]*>//g' | sort > /tmp/build-coded-new-urls.txt

# Pages that exist today but would 404 after deploy (MUST BE EMPTY)
comm -23 /tmp/build-coded-live-urls.txt /tmp/build-coded-new-urls.txt
```

If the diff is non-empty, either restore the page or add a `301` to `public/_redirects` for each removed URL.

### 1.2 Hreflang, canonical, schema spot-check
Pick 3 page types (homepage, article, category) and confirm they all still have:
- `<link rel="canonical" href="..."/>`
- 10 `<link rel="alternate" hreflang="..." href="..."/>` + 1 `x-default`
- At least 1 `<script type="application/ld+json">` block
- `<title>` and `<meta name="description">` populated

```bash
for url in / /how-to-build-workbench/ /category/woodworking/; do
  echo "=== $url ==="
  grep -c 'rel="canonical"' dist${url}index.html
  grep -c 'hreflang=' dist${url}index.html
  grep -c 'application/ld+json' dist${url}index.html
done
```
Expected: canonical=1, hreflang=11, ld+json≥1 per page.

### 1.3 Mobile render (mobile-first indexing — critical)
Google ranks the mobile version first. The new mobile layout must pass:

```bash
cd /Users/kapi7/satellite-websites/build-coded
npm run dev  # then open http://localhost:4323/ at 390px width
```
Manually verify at 390×844:
- [ ] Homepage: all sections render, tab bar fixed at bottom
- [ ] Article page: content readable, tab bar doesn't cover last content
- [ ] Category page: cards stack to 1 column
- [ ] Tool-finder, cost-calc, idea-generator: forms usable
- [ ] Tab bar highlights correct tab on each route (HOME/PROJECTS/TOOL FIND/MORE)
- [ ] No horizontal scrollbar on body

Also run Lighthouse on a throttled mobile profile:
```bash
npx lighthouse http://localhost:4323/ --preset=desktop --output=json --output-path=/tmp/lh-desktop.json --quiet
npx lighthouse http://localhost:4323/ --preset=mobile --output=json --output-path=/tmp/lh-mobile.json --quiet
```
Targets: LCP < 2.5s, CLS < 0.1, INP < 200ms, no render-blocking resources critical path.

### 1.4 Verify translations landed
Every new i18n key must be present in all 10 locale JSONs, or mobile shows raw `home.volIssue` text:

```bash
for loc in en es de el ru it ar fr nl pt; do
  count=$(grep -c '"volIssue"\|"mobileNav"' src/i18n/translations/${loc}.json)
  echo "$loc: $count"
done
```
Expected: each locale prints `2`.

### 1.5 Build with no errors
```bash
npm run build
```
Must exit 0. Warnings about Vite version are fine (known harmless).

---

## 2. Deploy

Cloudflare Pages is used in **direct wrangler upload mode** (not GitHub-integration). This means pushing to git does NOT auto-deploy — you must run wrangler explicitly.

### 2.1 Commit the redesign (doesn't deploy, but keeps source-of-truth)
```bash
cd /Users/kapi7/satellite-websites
git status  # review — should include only the files you want
git diff --stat build-coded/  # sanity check

# Stage ONLY build-coded changes (avoid mixing with cosmetics work in flight)
git add build-coded/src build-coded/DEPLOY.md

git commit -m "Build Coded: ship mobile redesign (separate mobile layout + tab bar)"
git push origin main
```

### 2.2 Deploy the built artifact to Cloudflare Pages
```bash
cd /Users/kapi7/satellite-websites/build-coded
npm run build
npx wrangler pages deploy dist --project-name=build-coded --commit-dirty=true
```

Wrangler will print a preview URL (e.g. `https://abc123.build-coded.pages.dev`) and the production URL `https://build-coded.com`.

### 2.3 Purge Cloudflare cache (so visitors see the new build immediately)
```bash
# If you have Cloudflare API token exported:
curl -X POST "https://api.cloudflare.com/client/v4/zones/$CF_ZONE_ID/purge_cache" \
  -H "Authorization: Bearer $CF_API_TOKEN" \
  -H "Content-Type: application/json" \
  --data '{"purge_everything":true}'
```
Or use the Cloudflare dashboard → Caching → Configuration → Purge Everything.

---

## 3. Post-deploy verification (5 min after deploy)

```bash
# 1. Live site returns 200
curl -sI https://build-coded.com/ | head -1

# 2. Sitemap still accessible
curl -sI https://build-coded.com/sitemap-index.xml | head -1
curl -s https://build-coded.com/sitemap-0.xml | grep -c '<url>'

# 3. Key rankings pages still exist (spot check top 5)
for slug in / /how-to-build-workbench/ /best-miter-saws-beginners-to-pro/ /category/woodworking/ /tool-finder/; do
  echo "$slug $(curl -sI https://build-coded.com$slug | head -1)"
done

# 4. Mobile render via Google-like UA
curl -s -A "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 Chrome/120 Mobile" \
  https://build-coded.com/ | grep -E 'bc-mobile-home|bc-tab-bar' | head -3
```

Submit the updated sitemap to search engines:
```bash
# IndexNow (Bing, Yandex — immediate)
cd /Users/kapi7/satellite-websites && bash scripts/submit-indexnow.sh
```

---

## 4. Google Search Console — connect with zero mistakes

### 4.1 Decide property type

**Recommended: URL-prefix property** `https://build-coded.com/` — simpler verification, works with Cloudflare, and lets you add a separate `https://www.build-coded.com/` property later if needed. Domain properties require DNS TXT verification and Cloudflare DNS-proxy can make verification flaky.

### 4.2 Check if a property already exists (before creating a duplicate)

1. Log in to https://search.google.com/search-console at `itay@aiotechnologies.com` (account used for Glow Coded per project memory) and also at `info@albert-capital.com` (outreach email).
2. Look for `build-coded.com` in the property dropdown.
3. If it exists **and** is verified → skip to 4.4. If it exists but **unverified** → re-run verification (4.3). If it does not exist → add it then verify (4.3).

### 4.3 Verify ownership — HTML file method (safest for Astro + Cloudflare Pages)

This method does NOT touch DNS and cannot be broken by Cloudflare proxy/cache tiers. It is also the method least likely to be undone by future redesigns.

**Step-by-step:**
1. Search Console → Add property → URL-prefix → enter `https://build-coded.com/` → continue.
2. Google offers several verification methods. Pick **"HTML file"**. Download the file `google<hash>.html` — it will look like `google1234567890abcdef.html` with content `google-site-verification: google1234567890abcdef.html`.
3. Place it in the Astro public dir:
   ```bash
   mv ~/Downloads/google*.html /Users/kapi7/satellite-websites/build-coded/public/
   ```
4. Rebuild + redeploy:
   ```bash
   cd /Users/kapi7/satellite-websites/build-coded
   npm run build
   npx wrangler pages deploy dist --project-name=build-coded --commit-dirty=true
   ```
5. Confirm it serves (should return 200 and the file contents):
   ```bash
   curl https://build-coded.com/google<hash>.html
   ```
6. Back in Search Console → **Verify**. Google should return "Ownership verified."
7. Commit the file so it's not lost:
   ```bash
   git add public/google*.html
   git commit -m "GSC: add google-site-verification file"
   git push origin main
   ```
8. Keep the file in `public/` forever — Google re-checks periodically and will un-verify if it disappears.

**Why not the meta tag method?** Works, but needs a code change to `Base.astro`. Fine alternative if preferred — add this line in the `<head>`:
```astro
<meta name="google-site-verification" content="YOUR_GOOGLE_CODE" />
```
Then rebuild + deploy. Same outcome, one fewer static file.

**Why not DNS TXT?** The domain DNS is on Cloudflare. It works, but DNS propagation can take up to 48h, and if you later move DNS, verification breaks silently. HTML file is more portable.

### 4.4 Submit the sitemap

After verification is successful:
1. Search Console → **Sitemaps** (left menu) → enter `sitemap-index.xml` → Submit.
2. Google should show "Success" within a few minutes. Coverage stats start populating in 24–72h.

Do NOT submit `sitemap-0.xml` directly — the index file is canonical and Google will discover all children from it.

### 4.5 Set international targeting

1. Search Console → Settings → International targeting → Language tab: confirm hreflang errors panel is clean. With 10 locales, Google may flag missing return tags — this should auto-resolve since our hreflang is reciprocal (every locale links back to every other).
2. Country tab: leave unset (content is global, English-primary).

### 4.6 Submit the top rankings pages for immediate re-indexing

After deploy, page HTML changed for every URL (desktop + mobile layouts). Tell Google about it:

1. Search Console → URL Inspection → paste each top-performing URL → "Request Indexing".
2. Priority order (use GSC Performance tab to find yours, or start with):
   - `/` (homepage)
   - `/category/woodworking/`
   - `/category/home-improvement/`
   - `/category/electronics/`
   - `/category/crafts/`
   - Top 5 traffic-driving article URLs (find in GSC → Performance → Pages, sort by clicks).

This can be bulk-automated later via the Indexing API, but one-off manual requests for the top ~20 is enough.

---

## 5. Post-deploy SEO monitoring (first 2 weeks)

| When | Check | Action if bad |
|------|-------|--------------|
| +1 hr | `curl https://build-coded.com/` returns 200, HTML contains new `bc-mobile-home` class (UA mobile) | Re-deploy or roll back |
| +1 hr | Cloudflare cache purged; visitors see new build | Purge again |
| +24 hr | Search Console → Coverage: no spike in "Not Found (404)" | Investigate diff vs 1.1; add redirects |
| +48 hr | Search Console → Core Web Vitals: no new "Poor URLs" | Run Lighthouse, identify regressor |
| +7 days | Search Console → Performance: impressions/clicks not down >15% vs prior 7 days | Check rendering (`URL Inspection → Live Test`); verify no noindex accidentally added |
| +14 days | Bing Webmaster Tools: crawl errors, sitemap still accepted | Re-submit sitemap if stale |

Set a calendar reminder for +7d and +14d.

---

## 6. Rollback (if something breaks)

Cloudflare Pages keeps every deployment as a rollback target.

```bash
# List recent deployments
npx wrangler pages deployment list --project-name=build-coded | head -20

# Roll back via dashboard: Cloudflare → Pages → build-coded → Deployments →
# click the last good deployment → "Rollback to this deployment"
```

Rollback is instant (< 1 min) and doesn't purge any SEO data.

---

## 7. What NOT to do

- ❌ Don't change URL slugs of existing articles
- ❌ Don't remove or rename pages without a 301 in `public/_redirects`
- ❌ Don't remove `hreflang`, `canonical`, `schema.org`, `llms.txt`, `BingSiteAuth.xml`, or the IndexNow key file
- ❌ Don't set `robots: "noindex"` on any existing page
- ❌ Don't change the default locale or the `prefixDefaultLocale: false` setting — that would suddenly move every English URL to `/en/...`
- ❌ Don't delete the `google<hash>.html` verification file once it's live
- ❌ Don't commit `.env` or any credentials
- ❌ Don't run `wrangler pages deploy` without first running `npm run build` — wrangler uploads whatever is in `dist/`, stale or not
- ❌ Don't deploy on a Friday afternoon if avoidable
