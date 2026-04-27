#!/usr/bin/env python3
"""
Queue preview + product audit dashboard.

Runs a local HTTP server on http://localhost:4848 that shows:
  • All `draft: true` articles across the 3 satellite sites (the queue)
  • For each draft: title, hero, first paragraph, mirai-skin product count
  • A separate "Product audit" tab listing PUBLISHED articles that have
    zero or weak product coverage so we know which ones to enhance

Usage:
    python3 scripts/queue_preview.py                  # serve on :4848
    python3 scripts/queue_preview.py --audit-only     # CSV report, no server
    python3 scripts/queue_preview.py --port 5050      # different port
"""
from __future__ import annotations
import argparse
import http.server
import json
import re
import socketserver
import sys
from html import escape
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
SITES = {
    "glow-coded": {
        "dir": ROOT / "cosmetics",
        "domain": "glow-coded.com",
        "color": "#ff5a4c",
    },
    "rooted-glow": {
        "dir": ROOT / "wellness",
        "domain": "rooted-glow.com",
        "color": "#7e9e6f",
    },
    "build-coded": {
        "dir": ROOT / "build-coded",
        "domain": "build-coded.com",
        "color": "#d4a83a",
    },
}
CATALOG_PATH = Path("/Users/kapi7/mirai-meta-campaign/satellite-websites/.image-cache/products_catalog.json")


def load_catalog():
    try:
        data = json.loads(CATALOG_PATH.read_text())
        # Build set of valid product handles for fast lookup
        return {p.get("handle") for p in data if p.get("handle")}
    except Exception as e:
        print(f"[warn] catalog not loaded: {e}", file=sys.stderr)
        return set()


VALID_HANDLES = load_catalog()
print(f"[info] catalog loaded: {len(VALID_HANDLES)} product handles", file=sys.stderr)


FRONT_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.S)
PRODUCT_LINK_RE = re.compile(r"https?://(?:www\.)?mirai-skin\.com/products/([a-z0-9-]+)", re.I)


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
    # skip past intro h1 / first ## heading and grab first prose para
    parts = re.split(r"\n\s*\n", body, maxsplit=20)
    for p in parts:
        s = p.strip()
        if not s:
            continue
        if s.startswith("#") or s.startswith("import "):
            continue
        if s.startswith("!["):  # image-only block
            continue
        if s.startswith("[!["):  # affiliate image-link block
            continue
        return s[:max_chars] + ("…" if len(s) > max_chars else "")
    return ""


def product_links(body: str):
    """Returns list of (handle, valid?) tuples."""
    handles = PRODUCT_LINK_RE.findall(body)
    return [(h, h in VALID_HANDLES) for h in handles]


def collect_articles(en_only=True):
    """Returns dict: site_key → {drafts:[...], published:[...]} with parsed metadata."""
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
                "slug": f.stem,
                "title": fm.get("title", f.stem),
                "description": fm.get("description", ""),
                "date": fm.get("date", ""),
                "category": fm.get("category", ""),
                "type": fm.get("type", ""),
                "image": fm.get("image", ""),
                "author": fm.get("author", ""),
                "intro": first_paragraph(body),
                "products": product_links(body),
                "wordcount": len(body.split()),
                "path": str(f.relative_to(ROOT)),
            }
            (drafts if "draft: true" in (entry["intro"] or "") or _is_draft(f) else published).append(entry)
        out[key] = {"drafts": drafts, "published": published}
    return out


def _is_draft(path: Path) -> bool:
    try:
        with path.open() as fh:
            for line in fh:
                if line.strip() == "draft: true":
                    return True
                if line.strip() == "---" and fh.readline():  # past frontmatter
                    pass
        return False
    except Exception:
        return False


def render_html(data):
    rows = []
    site_summary = []
    grand_total_drafts = 0
    grand_no_product = 0

    for key, info in SITES.items():
        drafts = data[key]["drafts"]
        published = data[key]["published"]
        no_product_published = [a for a in published if len(a["products"]) == 0]
        invalid_product_published = [a for a in published if any(not v for _, v in a["products"])]
        grand_total_drafts += len(drafts)
        grand_no_product += len(no_product_published)
        site_summary.append({
            "key": key,
            "domain": info["domain"],
            "color": info["color"],
            "drafts": len(drafts),
            "published": len(published),
            "published_no_product": len(no_product_published),
            "published_with_invalid": len(invalid_product_published),
        })

    summary_html = "<div class='cards'>" + "".join(
        f"""<div class='card' style='border-color:{s["color"]}'>
              <div class='dom'>{s["domain"]}</div>
              <div class='big'>{s["drafts"]}</div>
              <div class='lbl'>drafts in queue</div>
              <hr>
              <div>📚 {s["published"]} published</div>
              <div class='warn'>⚠️ {s["published_no_product"]} with NO product link</div>
              <div class='warn'>❌ {s["published_with_invalid"]} with INVALID handle</div>
            </div>"""
        for s in site_summary
    ) + "</div>"

    # Queue table
    queue_rows = []
    for key, info in SITES.items():
        for a in data[key]["drafts"]:
            valid_count = sum(1 for _, v in a["products"] if v)
            invalid_count = sum(1 for _, v in a["products"] if not v)
            badge = ""
            if not a["products"]:
                badge = "<span class='b-red'>NO PRODUCTS</span>"
            elif invalid_count:
                badge = f"<span class='b-red'>{invalid_count} INVALID</span> <span class='b-green'>{valid_count} ok</span>"
            else:
                badge = f"<span class='b-green'>{valid_count} ✓</span>"
            img = f"<img src='https://{info['domain']}{a['image']}' loading='lazy' onerror='this.style.opacity=0.2'>" if a["image"] else "<div class='no-img'>no hero</div>"
            queue_rows.append(f"""
              <tr>
                <td><span class='pill' style='background:{info["color"]}'>{key}</span></td>
                <td class='img-cell'>{img}</td>
                <td>
                  <div class='ttl'>{escape(a["title"])}</div>
                  <div class='meta'>{escape(a["category"])} · {escape(a["type"])} · {a["wordcount"]} words · by {escape(a["author"])}</div>
                  <div class='intro'>{escape(a["intro"][:300])}</div>
                </td>
                <td>{badge}</td>
                <td><a href='/preview/{key}/{a["slug"]}' target='_blank'>Preview ↗</a></td>
              </tr>
            """)

    # Product-audit table — published articles missing real products
    audit_rows = []
    for key, info in SITES.items():
        for a in data[key]["published"]:
            valid_count = sum(1 for _, v in a["products"] if v)
            invalid_count = sum(1 for _, v in a["products"] if not v)
            if valid_count == 0 or invalid_count > 0:
                status = "NO PRODUCTS" if not a["products"] else f"{invalid_count} INVALID handles"
                live_url = f"https://{info['domain']}/{a['slug']}/"
                audit_rows.append(f"""
                  <tr>
                    <td><span class='pill' style='background:{info["color"]}'>{key}</span></td>
                    <td><a href='{live_url}' target='_blank'>{escape(a["title"])}</a></td>
                    <td>{escape(a["type"])}</td>
                    <td><span class='b-red'>{status}</span></td>
                    <td>{a["wordcount"]} w</td>
                  </tr>
                """)

    return f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<title>Satellite Queue + Product Audit</title>
<style>
  body {{ font: 14px/1.5 -apple-system, system-ui, sans-serif; background: #fafaf6; color: #222; padding: 24px; max-width: 1400px; margin: 0 auto; }}
  h1 {{ font-size: 28px; margin: 0 0 6px; }}
  h2 {{ font-size: 20px; margin: 32px 0 12px; }}
  .cards {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin: 16px 0 32px; }}
  .card {{ background: #fff; border: 2px solid; border-radius: 8px; padding: 16px; }}
  .card .dom {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 13px; color: #666; }}
  .card .big {{ font-size: 48px; font-weight: 700; line-height: 1; margin: 4px 0; }}
  .card .lbl {{ font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; color: #666; }}
  .card hr {{ border: none; border-top: 1px solid #eee; margin: 12px 0; }}
  .card .warn {{ color: #b34; font-size: 12px; margin-top: 4px; }}
  .tabs {{ display: flex; gap: 6px; margin: 16px 0; border-bottom: 2px solid #ddd; }}
  .tabs button {{ background: none; border: none; padding: 10px 18px; font-size: 14px; cursor: pointer; border-bottom: 3px solid transparent; margin-bottom: -2px; font-weight: 600; }}
  .tabs button.active {{ border-bottom-color: #222; }}
  .tab-pane {{ display: none; }}
  .tab-pane.active {{ display: block; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
  th, td {{ padding: 12px; text-align: left; vertical-align: top; border-bottom: 1px solid #eee; }}
  th {{ background: #f4f4ee; font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; }}
  .img-cell {{ width: 100px; }}
  .img-cell img {{ width: 90px; height: 60px; object-fit: cover; border-radius: 4px; border: 1px solid #ddd; }}
  .img-cell .no-img {{ width: 90px; height: 60px; background: #eee; display: flex; align-items: center; justify-content: center; font-size: 11px; color: #999; border-radius: 4px; }}
  .pill {{ color: #fff; padding: 3px 8px; border-radius: 999px; font-size: 11px; font-weight: 600; }}
  .ttl {{ font-weight: 600; font-size: 15px; }}
  .meta {{ color: #777; font-size: 12px; margin: 2px 0 6px; }}
  .intro {{ color: #555; font-size: 13px; }}
  .b-red {{ background: #fce4e4; color: #b22; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }}
  .b-green {{ background: #e2f4e4; color: #2a7; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }}
  a {{ color: #06f; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
</style>
</head><body>

<h1>📦 Satellite Queue + Product Audit</h1>
<div style='color:#666; font-size:13px;'>{grand_total_drafts} drafts queued · {grand_no_product} published articles missing product links</div>

{summary_html}

<div class='tabs'>
  <button class='active' onclick="show('queue')">Queue ({grand_total_drafts})</button>
  <button onclick="show('audit')">Product audit ({len(audit_rows)})</button>
</div>

<div id='queue' class='tab-pane active'>
  <table>
    <thead><tr><th>Site</th><th>Hero</th><th>Article</th><th>Products</th><th></th></tr></thead>
    <tbody>{''.join(queue_rows)}</tbody>
  </table>
</div>

<div id='audit' class='tab-pane'>
  <p style='color:#666; font-size:13px;'>Published articles where the body contains <b>no</b> mirai-skin.com product link, OR contains a link whose handle isn't in the live catalog of {len(VALID_HANDLES)} products.</p>
  <table>
    <thead><tr><th>Site</th><th>Article</th><th>Type</th><th>Status</th><th>Length</th></tr></thead>
    <tbody>{''.join(audit_rows)}</tbody>
  </table>
</div>

<script>
  function show(id) {{
    document.querySelectorAll('.tab-pane').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.tabs button').forEach(el => el.classList.remove('active'));
    document.getElementById(id).classList.add('active');
    event.target.classList.add('active');
  }}
</script>

</body></html>"""


def write_audit_csv(data, out_path: Path):
    import csv
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
    print(f"[csv] wrote {out_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=4848)
    ap.add_argument("--audit-only", action="store_true")
    ap.add_argument("--csv", type=Path, default=ROOT / "scripts" / "reports" / "product-audit.csv")
    args = ap.parse_args()

    data = collect_articles()

    # Always write CSV
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    write_audit_csv(data, args.csv)

    if args.audit_only:
        return

    html = render_html(data)
    out = ROOT / "scripts" / "reports" / "queue-preview.html"
    out.write_text(html)
    print(f"[html] wrote {out}")

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/" or self.path.startswith("/?"):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html.encode())
            elif self.path.startswith("/preview/"):
                # /preview/{site}/{slug} → redirect to the dev server URL
                _, _, site, slug = self.path.split("/", 3)
                ports = {"glow-coded": 4322, "rooted-glow": 4321, "build-coded": 4323}
                p = ports.get(site, 4322)
                self.send_response(302)
                self.send_header("Location", f"http://localhost:{p}/{slug}/")
                self.end_headers()
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, *a, **k):
            pass

    with socketserver.TCPServer(("127.0.0.1", args.port), Handler) as httpd:
        print(f"\n  📍 Queue dashboard: http://localhost:{args.port}\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nbye.")


if __name__ == "__main__":
    main()
