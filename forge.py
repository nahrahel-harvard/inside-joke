#!/usr/bin/env python3
"""CLI: python forge.py examples/dana_brightwater.json --format all
Writes GIFs, PNG posters, manifest.json and a gallery index.html to out/<run>/."""
from __future__ import annotations

import argparse
import html
import json
import pathlib
import sys

from inside_joke.formats import FORMATS, ORDER
from inside_joke.pipeline import run


def gallery(manifest: dict) -> str:
    p = manifest["prospect"]
    cards = []
    for fmt in ORDER:
        r = manifest["results"].get(fmt)
        if not r:
            continue
        if not r["ok"]:
            cards.append(f'<div class="c"><h3>{FORMATS[fmt]["name"]}</h3><p class="err">{html.escape(r["error"] or "")}</p></div>')
            continue
        sc = r["scores"].get(r["concept"]["id"], {}) if isinstance(r["scores"], dict) else {}
        score = " · ".join(f"{k} {sc[k]}" for k in ("funny", "specific", "kind", "glance") if k in sc)
        cards.append(
            f'<div class="c"><h3>{FORMATS[fmt]["name"]}</h3>'
            f'<img src="{r["gif"]}" alt="{html.escape(r["alt_text"])}">'
            f'<p class="line">{html.escape(r["email_line"])}</p>'
            f'<p class="meta">{r["gif_kb"]} KB · {r["seconds"]} s · art: {r["art_backend"]}<br>{score}</p>'
            f'<p class="meta">mechanism: {html.escape(str(r["concept"].get("mechanism", "")))}</p></div>')
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Inside Joke: {html.escape(p.get('first_name', ''))}</title>
<style>body{{font:15px/1.45 -apple-system,system-ui,sans-serif;background:#f6f5f2;color:#1d1d1f;margin:0;padding:24px}}
h1{{font-size:20px;margin:0 0 4px}} .sub{{color:#666;margin:0 0 20px}}
.g{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:18px}}
.c{{background:#fff;border-radius:14px;padding:14px;box-shadow:0 1px 3px #0001}} .c img{{width:100%;border-radius:8px}}
h3{{margin:0 0 10px;font-size:15px}} .line{{font-style:italic}} .meta{{color:#777;font-size:12.5px;margin:4px 0}} .err{{color:#b3261e}}</style></head>
<body><h1>{html.escape(p.get('first_name', ''))} {html.escape(p.get('last_name', ''))}, {html.escape(p.get('title', ''))} at {html.escape(p.get('company', ''))}</h1>
<p class="sub">{manifest['total_seconds']} s total · ${manifest['cost_usd']} · {manifest['created']}</p>
<div class="g">{''.join(cards)}</div></body></html>"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate personalized GIFs for one prospect.")
    ap.add_argument("prospect_file", help='JSON file: {"prospect": {...}, "context": "..."} or a flat prospect object')
    ap.add_argument("--format", default="all", help="all, or comma list of: " + ",".join(ORDER))
    ap.add_argument("--context", help="conversation context (overrides the file's context)")
    ap.add_argument("--art", default="auto", choices=["auto", "image", "svg", "placeholder"])
    ap.add_argument("--fast", action="store_true", help="faster writer, skip the judge")
    ap.add_argument("--research", action="store_true", help="fetch the prospect's homepage first")
    ap.add_argument("--out", help="output folder")
    a = ap.parse_args()

    data = json.loads(pathlib.Path(a.prospect_file).read_text())
    prospect = data.get("prospect", data)
    context = a.context if a.context is not None else data.get("context")
    formats = ORDER if a.format == "all" else [f.strip() for f in a.format.split(",") if f.strip()]
    unknown = [f for f in formats if f not in ORDER]
    if unknown or not formats:
        ap.error(f"unknown format(s): {', '.join(unknown) or '(none given)'}; choose from {', '.join(ORDER)} or all")

    def show(ev):
        print(f"[{ev['t']:>5}s] {ev['format'] or '-':<8} {ev['stage']:<8} {ev['message']}", flush=True)

    m = run(prospect, formats, context=context, art=a.art, fast=a.fast, research=a.research,
            out_dir=pathlib.Path(a.out) if a.out else None, on_event=show)
    out = pathlib.Path(m["out_dir"])
    (out / "index.html").write_text(gallery(m))
    print(f"\nDone in {m['total_seconds']} s, cost ${m['cost_usd']}")
    for fmt, r in m["results"].items():
        status = f"{r['gif_kb']} KB, {r['seconds']} s, art={r['art_backend']}" if r["ok"] else f"FAILED: {r['error']}"
        print(f"  {fmt:<9} {status}")
    print(f"Gallery: {out / 'index.html'}")
    return 0 if any(r["ok"] for r in m["results"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
