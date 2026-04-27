#!/usr/bin/env python3
"""
Queue preview + product audit dashboard.

Local HTTP server on http://localhost:4848:
  • Filter by site (All / glow-coded / rooted-glow / build-coded)
  • Inline draft preview (full markdown rendered to HTML, no dev server needed)
  • Product audit tab listing published articles missing real product links
  • Live-renders on each request (always shows current state)

Usage:
    python3 scripts/queue_preview.py                  # serve on :4848
    python3 scripts/queue_preview.py --port 5050
    python3 scripts/queue_preview.py --audit-only     # just write CSV
"""
from __future__ import annotations
import argparse
import csv
import http.server
import json
import re
import socketserver
import sys
from html import escape
from pathlib import Path
from urllib.parse import unquote, parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
SITES = {
    "glow-coded": {"dir": ROOT / "cosmetics", "domain": "glow-coded.com", "color": "#ff5a4c"},
    "rooted-glow": {"dir": ROOT / "wellness", "domain": "rooted-glow.com", "color": "#7e9e6f"},
    "build-coded": {"dir": ROOT / "build-coded", "domain": "build-coded.com", "color": "#d4a83a"},
}
CATALOG_PATH = Path("/Users/kapi7/mirai-meta-campaign/satellite-websites/.image-cache/products_catalog.json")
FRONT_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.S)
PRODUCT_LINK_RE = re.compile(r"https?://(?:www\.)?mirai-skin\.com/products/([a-z0-9-]+)", re.I)


def load_catalog():
    try:
        data = json.loads(CATALOG_PATH.read_text())
        return {p.get("handle") for p in data if p.get("handle")}
    except Exception as e:
        print(f"[warn] catalog not loaded: {e}", file=sys.stderr)
        return set()


VALID_HANDLES = load_catalog()


def parse_mdx(path: Path):
    text = path.read_text(errors="ignore")
    m = FRONT_RE.match(text)
    if not m:
        return None
    fm_raw, body = m.group(1), m.group(2)
    fm = {}
    for line in fm_raw.splitlines():
        if ":" in line and not line.startswith(" ") and not line.startswith("-"):
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip().strip('"')
    return fm, body


def first_paragraph(body: str, max_chars=400):
    parts = re.split(r"\n\s*\n", body, maxsplit=20)
    for p in parts:
        s = p.strip()
        if not s or s.startswith("#") or s.startswith("import ") or s.startswith("![") or s.startswith("[!["):
            continue
        return s[:max_chars] + ("…" if len(s) > max_chars else "")
    return ""


def product_links(body: str):
    handles = PRODUCT_LINK_RE.findall(body)
    return [(h, h in VALID_HANDLES) for h in handles]


def collect_articles():
    out = {}
    for key, info in SITES.items():
        en_dir = info["dir"] / "src" / "content" / "blog" / "en"
        drafts, published = [], []
        for f in sorted(en_dir.glob("*.mdx")):
            parsed = parse_mdx(f)
            if not parsed:
                continue
            fm, body = parsed
            entry = {
                "site": key,
                "slug": f.stem,
                "title": fm.get("title", f.stem),
                "description": fm.get("description", ""),
                "date": fm.get("date", ""),
                "category": fm.get("category", ""),
                "type": fm.get("type", ""),
                "image": fm.get("image", ""),
                "author": fm.get("author", ""),
                "draft": fm.get("draft", "false").strip().lower() == "true",
                "intro": first_paragraph(body),
                "body": body,
                "products": product_links(body),
                "wordcount": len(body.split()),
                "path": str(f.relative_to(ROOT)),
            }
            (drafts if entry["draft"] else published).append(entry)
        out[key] = {"drafts": drafts, "published": published}
    return out


# ── lightweight markdown → HTML renderer (just enough for previewing) ──
def md_to_html(md: str) -> str:
    lines = md.split("\n")
    html_lines = []
    in_list = False
    in_code = False
    in_para_buf = []

    def flush_para():
        if in_para_buf:
            text = " ".join(in_para_buf).strip()
            if text:
                html_lines.append(f"<p>{inline(text)}</p>")
            in_para_buf.clear()

    def inline(t):
        t = escape(t)
        t = re.sub(r"\[!\[([^\]]*)\]\(([^)]+)\)\]\(([^)]+)\)",
                   r'<a href="\3" target="_blank"><img src="\2" alt="\1" style="max-width:140px;border:1px solid #ddd;border-radius:6px;margin:6px 0"></a>', t)
        t = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)",
                   r'<img src="\2" alt="\1" style="max-width:100%;border-radius:6px;margin:8px 0">', t)
        t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)",
                   r'<a href="\2" target="_blank">\1</a>', t)
        t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
        t = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", t)
        t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
        return t

    for raw in lines:
        if raw.startswith("```"):
            flush_para()
            if in_code:
                html_lines.append("</pre>"); in_code = False
            else:
                html_lines.append("<pre>"); in_code = True
            continue
        if in_code:
            html_lines.append(escape(raw)); continue
        line = raw.rstrip()
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            flush_para()
            if in_list: html_lines.append("</ul>"); in_list = False
            level = len(m.group(1))
            html_lines.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
            continue
        m = re.match(r"^[-*]\s+(.*)$", line)
        if m:
            flush_para()
            if not in_list: html_lines.append("<ul>"); in_list = True
            html_lines.append(f"<li>{inline(m.group(1))}</li>")
            continue
        if line.strip() == "":
            flush_para()
            if in_list: html_lines.append("</ul>"); in_list = False
            continue
        if in_list: html_lines.append("</ul>"); in_list = False
        in_para_buf.append(line)

    flush_para()
    if in_list: html_lines.append("</ul>")
    if in_code: html_lines.append("</pre>")
    return "\n".join(html_lines)


BASE_CSS = """<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<title>Satellite Queue</title>
<style>
  body { font: 14px/1.55 -apple-system, system-ui, sans-serif; background: #fafaf6; color: #222; padding: 24px; max-width: 1300px; margin: 0 auto; }
  h1 { font-size: 28px; margin: 0 0 6px; }
  h2 { font-size: 22px; margin: 28px 0 10px; }
  h3 { font-size: 18px; margin: 24px 0 8px; }
  .cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin: 16px 0 20px; }
  .card { background: #fff; border: 2px solid; border-radius: 8px; padding: 14px; text-decoration: none; color: inherit; transition: transform 0.15s; display: block; }
  .card:hover { transform: translateY(-2px); }
  .card .dom { font: 12px ui-monospace, Menlo, monospace; color: #666; }
  .card .big { font-size: 40px; font-weight: 700; line-height: 1; margin: 4px 0; }
  .card .lbl { font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: #666; }
  .card hr { border: none; border-top: 1px solid #eee; margin: 10px 0; }
  .card .warn { color: #b34; font-size: 12px; margin-top: 2px; }
  .filter { display: flex; gap: 8px; flex-wrap: wrap; margin: 12px 0 16px; }
  .chip { padding: 7px 14px; border: 1.5px solid #ccc; border-radius: 999px; text-decoration: none; color: #222; font-size: 13px; background: #fff; transition: all 0.15s; }
  .chip:hover { border-color: var(--c, #444); }
  .chip.active { background: var(--c, #222); color: #fff; border-color: var(--c, #222); font-weight: 600; }
  .tabs { display: flex; gap: 4px; margin: 14px 0 0; border-bottom: 2px solid #ddd; }
  .tabs button { background: none; border: none; padding: 10px 18px; font-size: 14px; cursor: pointer; border-bottom: 3px solid transparent; margin-bottom: -2px; font-weight: 600; }
  .tabs button.active { border-bottom-color: #222; }
  .tab-pane { display: none; }
  .tab-pane.active { display: block; }
  table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.05); margin-top: 16px; }
  th, td { padding: 12px; text-align: left; vertical-align: top; border-bottom: 1px solid #eee; }
  th { background: #f4f4ee; font-size: 11px; text-transform: uppercase; letter-spacing: 0.04em; }
  .img-cell { width: 100px; }
  .img-cell img { width: 90px; height: 60px; object-fit: cover; border-radius: 4px; border: 1px solid #ddd; }
  .img-cell .no-img { width: 90px; height: 60px; background: #eee; display: flex; align-items: center; justify-content: center; font-size: 11px; color: #999; border-radius: 4px; }
  .pill { color: #fff; padding: 3px 8px; border-radius: 999px; font-size: 11px; font-weight: 600; }
  .ttl { font-weight: 600; font-size: 15px; }
  .ttl a { color: #222; text-decoration: none; }
  .ttl a:hover { color: #06f; }
  .meta { color: #777; font-size: 12px; margin: 2px 0 6px; }
  .intro { color: #555; font-size: 13px; }
  .b-red { background: #fce4e4; color: #b22; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
  .b-green { background: #e2f4e4; color: #2a7; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
  .btn-preview { background: #222; color: #fff !important; padding: 6px 14px; border-radius: 6px; font-size: 12px; text-decoration: none !important; font-weight: 600; }
  .btn-preview:hover { background: #06f; }
  a { color: #06f; text-decoration: none; }
  a:hover { text-decoration: underline; }
  .back { display: inline-block; padding: 8px 14px; background: #fff; border: 1px solid #ddd; border-radius: 6px; margin: 8px 0 16px; color: #222; font-size: 13px; }
  .back:hover { background: #f4f4ee; text-decoration: none; }
  .preview-head { display: flex; gap: 12px; align-items: center; margin: 12px 0; flex-wrap: wrap; }
  .desc { color: #555; font-size: 16px; max-width: 800px; margin: 4px 0 16px; }
  .hero { max-width: 720px; max-height: 380px; border-radius: 8px; margin: 12px 0; }
  .prods { background: #fff; border: 1px solid #ddd; border-radius: 6px; padding: 12px 16px; margin: 12px 0; font-size: 13px; }
  .prods code { background: #f4f4ee; padding: 1px 6px; border-radius: 3px; font-size: 12px; }
  article.prose { background: #fff; padding: 24px 32px; border: 1px solid #eee; border-radius: 8px; max-width: 760px; }
  article.prose img { max-width: 100%; height: auto; }
  article.prose pre { background: #f4f4ee; padding: 12px; border-radius: 6px; overflow-x: auto; }
  article.prose code { background: #f4f4ee; padding: 1px 5px; border-radius: 3px; font-size: 0.9em; }
  article.prose ul { padding-left: 24px; }
  article.prose li { margin: 4px 0; }
  article.prose p { margin: 12px 0; }
  article.prose strong { font-weight: 600; }
</style>
</head><body>
"""


def render_index(data, site_filter=None):
    site_summary = []
    grand_total_drafts = 0
    for key, info in SITES.items():
        drafts = data[key]["drafts"]
        published = data[key]["published"]
        no_product = [a for a in published if len(a["products"]) == 0]
        invalid_products = [a for a in published if any(not v for _, v in a["products"])]
        grand_total_drafts += len(drafts)
        site_summary.append({
            "key": key, "domain": info["domain"], "color": info["color"],
            "drafts": len(drafts), "published": len(published),
            "no_product": len(no_product), "invalid_products": len(invalid_products),
        })

    summary_html = "<div class='cards'>" + "".join(
        f"""<a class='card' href='/?site={s["key"]}' style='border-color:{s["color"]}'>
              <div class='dom'>{s["domain"]}</div>
              <div class='big'>{s["drafts"]}</div>
              <div class='lbl'>drafts in queue</div>
              <hr>
              <div>📚 {s["published"]} published</div>
              <div class='warn'>⚠️ {s["no_product"]} no product</div>
              <div class='warn'>❌ {s["invalid_products"]} invalid handle</div>
            </a>"""
        for s in site_summary
    ) + "</div>"

    chips = ["<div class='filter'>"]
    all_active = "" if site_filter else " active"
    chips.append(f"<a class='chip{all_active}' href='/'>All sites ({grand_total_drafts})</a>")
    for key, info in SITES.items():
        active = " active" if site_filter == key else ""
        n = len(data[key]["drafts"])
        c = info["color"]
        chips.append(f"<a class='chip{active}' style='--c:{c}' href='/?site={key}'>{key} ({n})</a>")
    chips.append("</div>")
    chips_html = "".join(chips)

    queue_rows = []
    for key, info in SITES.items():
        if site_filter and site_filter != key:
            continue
        for a in data[key]["drafts"]:
            valid_count = sum(1 for _, v in a["products"] if v)
            invalid_count = sum(1 for _, v in a["products"] if not v)
            if not a["products"]:
                badge = "<span class='b-red'>NO PRODUCTS</span>"
            elif invalid_count:
                badge = f"<span class='b-red'>{invalid_count} INVALID</span> <span class='b-green'>{valid_count} ok</span>"
            else:
                badge = f"<span class='b-green'>{valid_count} ✓</span>"
            img = (
                f"<img src='/static/{key}{a['image']}' loading='lazy' onerror=\"this.style.opacity=0.2\">"
                if a["image"] else "<div class='no-img'>no hero</div>"
            )
            queue_rows.append(f"""
              <tr>
                <td><span class='pill' style='background:{info["color"]}'>{key}</span></td>
                <td class='img-cell'>{img}</td>
                <td>
                  <div class='ttl'><a href='/preview?site={key}&slug={a["slug"]}'>{escape(a["title"])}</a></div>
                  <div class='meta'>{escape(a["date"])} · {escape(a["category"])} · {escape(a["type"])} · {a["wordcount"]} words · by {escape(a["author"])}</div>
                  <div class='intro'>{escape(a["intro"][:350])}</div>
                </td>
                <td>{badge}</td>
                <td><a class='btn-preview' href='/preview?site={key}&slug={a["slug"]}'>Preview →</a></td>
              </tr>
            """)
    if not queue_rows:
        queue_rows.append("<tr><td colspan='5' style='text-align:center; padding:40px; color:#999;'>No drafts in this filter.</td></tr>")

    audit_rows = []
    for key, info in SITES.items():
        if site_filter and site_filter != key:
            continue
        for a in data[key]["published"]:
            valid_count = sum(1 for _, v in a["products"] if v)
            invalid_count = sum(1 for _, v in a["products"] if not v)
            if valid_count == 0 or invalid_count > 0:
                status = "NO PRODUCTS" if not a["products"] else f"{invalid_count} INVALID"
                live_url = f"https://{info['domain']}/{a['slug']}/"
                audit_rows.append(f"""
                  <tr>
                    <td><span class='pill' style='background:{info["color"]}'>{key}</span></td>
                    <td><a href='/preview?site={key}&slug={a["slug"]}'>{escape(a["title"])}</a> &nbsp; <a href='{live_url}' target='_blank' style='font-size:12px;'>(live ↗)</a></td>
                    <td>{escape(a["type"])}</td>
                    <td><span class='b-red'>{status}</span></td>
                    <td>{a["wordcount"]} w</td>
                  </tr>
                """)
    if not audit_rows:
        audit_rows.append("<tr><td colspan='5' style='text-align:center; padding:40px; color:#999;'>Nothing flagged in this filter.</td></tr>")

    return BASE_CSS + f"""
<h1>📦 Queue + Product Audit</h1>
<div style='color:#666; font-size:13px;'>{grand_total_drafts} drafts across all sites — click any title for full preview</div>

{summary_html}
{chips_html}

<div class='tabs'>
  <button class='active' data-tab='queue'>Queue</button>
  <button data-tab='audit'>Product audit</button>
</div>

<div id='queue' class='tab-pane active'>
  <table>
    <thead><tr><th>Site</th><th>Hero</th><th>Article</th><th>Products</th><th></th></tr></thead>
    <tbody>{''.join(queue_rows)}</tbody>
  </table>
</div>

<div id='audit' class='tab-pane'>
  <table>
    <thead><tr><th>Site</th><th>Article</th><th>Type</th><th>Status</th><th>Length</th></tr></thead>
    <tbody>{''.join(audit_rows)}</tbody>
  </table>
</div>

<script>
document.querySelectorAll('.tabs button').forEach(b => b.onclick = () => {{
  document.querySelectorAll('.tab-pane').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tabs button').forEach(el => el.classList.remove('active'));
  document.getElementById(b.dataset.tab).classList.add('active');
  b.classList.add('active');
}});
</script>
</body></html>"""


def render_preview(article, site_key):
    info = SITES[site_key]
    body_html = md_to_html(article["body"])
    products_html = ""
    if article["products"]:
        products_html = "<div class='prods'><b>Mirai products linked:</b><br>" + "<br>".join(
            f"{'✅' if v else '❌'} <code>{escape(h)}</code>" for h, v in article["products"]
        ) + "</div>"
    hero_html = f"<img class='hero' src='/static/{site_key}{article['image']}'>" if article["image"] else ""
    return BASE_CSS + f"""
<a class='back' href='/?site={site_key}'>← back to {site_key} queue</a>
<div class='preview-head'>
  <span class='pill' style='background:{info["color"]}'>{site_key}</span>
  <span class='meta'>{escape(article["date"])} · {escape(article["category"])} · {escape(article["type"])} · {article["wordcount"]} words · by {escape(article["author"])}</span>
  {'<span class="b-red">DRAFT</span>' if article['draft'] else '<span class="b-green">PUBLISHED</span>'}
</div>
<h1>{escape(article["title"])}</h1>
<p class='desc'>{escape(article["description"])}</p>
{products_html}
{hero_html}
<article class='prose'>
{body_html}
</article>
<a class='back' href='/?site={site_key}'>← back to {site_key} queue</a>
</body></html>"""


def write_audit_csv(data, out_path: Path):
    with out_path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["site", "slug", "title", "type", "category", "wordcount", "valid_products", "invalid_products", "status", "live_url"])
        for key, info in SITES.items():
            for a in data[key]["published"]:
                v = sum(1 for _, ok in a["products"] if ok)
                inv = sum(1 for _, ok in a["products"] if not ok)
                if v == 0 or inv > 0:
                    status = "no_products" if not a["products"] else "invalid_handle"
                    w.writerow([key, a["slug"], a["title"], a["type"], a["category"], a["wordcount"], v, inv, status, f"https://{info['domain']}/{a['slug']}/"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=4848)
    ap.add_argument("--audit-only", action="store_true")
    ap.add_argument("--csv", type=Path, default=ROOT / "scripts" / "reports" / "product-audit.csv")
    args = ap.parse_args()

    args.csv.parent.mkdir(parents=True, exist_ok=True)
    data = collect_articles()
    write_audit_csv(data, args.csv)
    print(f"[csv] wrote {args.csv}")

    if args.audit_only:
        return

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            url = urlparse(self.path)
            qs = parse_qs(url.query)

            if url.path == "/":
                site_filter = qs.get("site", [None])[0]
                fresh = collect_articles()
                self._send_html(render_index(fresh, site_filter))
            elif url.path == "/preview":
                site = qs.get("site", [None])[0]
                slug = qs.get("slug", [None])[0]
                if not site or not slug or site not in SITES:
                    self.send_response(400); self.end_headers()
                    self.wfile.write(b"missing site or slug"); return
                fresh = collect_articles()
                article = next((a for a in fresh[site]["drafts"] + fresh[site]["published"] if a["slug"] == slug), None)
                if not article:
                    self.send_response(404); self.end_headers()
                    self.wfile.write(b"article not found"); return
                self._send_html(render_preview(article, site))
            elif url.path.startswith("/static/"):
                rest = url.path[len("/static/"):]
                site, _, file_path = rest.partition("/")
                if site not in SITES:
                    self.send_response(404); self.end_headers(); return
                full = SITES[site]["dir"] / "public" / unquote(file_path)
                if not full.exists() or not full.is_file():
                    self.send_response(404); self.end_headers(); return
                ext = full.suffix.lower()
                ct = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".svg": "image/svg+xml"}.get(ext, "application/octet-stream")
                self.send_response(200)
                self.send_header("Content-Type", ct)
                self.send_header("Cache-Control", "public, max-age=3600")
                self.end_headers()
                self.wfile.write(full.read_bytes())
            else:
                self.send_response(404); self.end_headers()

        def _send_html(self, body):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode())

        def log_message(self, *a, **k):
            pass

    with socketserver.TCPServer(("127.0.0.1", args.port), Handler) as httpd:
        print(f"\n  📍 Queue dashboard: http://localhost:{args.port}")
        print(f"     glow-coded:  http://localhost:{args.port}/?site=glow-coded")
        print(f"     rooted-glow: http://localhost:{args.port}/?site=rooted-glow")
        print(f"     build-coded: http://localhost:{args.port}/?site=build-coded\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nbye.")


if __name__ == "__main__":
    main()
