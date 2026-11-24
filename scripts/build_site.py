#!/usr/bin/env python3
"""Refresh the GitHub Pages showcase from real runs.

    python scripts/build_site.py                 # newest dana-* and marcus-* runs in out/
    python scripts/build_site.py --dana out/dana-...-20261124-174047

Copies <format>.gif/.png into site/assets/<key>/ and writes site/assets/data.json
with only public, non-sensitive fields (no candidates, rejected concepts or ledger)."""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
FORMATS = ["meme", "headline", "comic", "card", "reply"]
PROSPECT_FIELDS = ["first_name", "last_name", "title", "company", "industry", "linkedin_headline", "notes"]
SHOWCASE = {"dana": "dana-brightwater-beverage-co-*", "marcus": "marcus-northpeak-logistics-*"}


def newest(pattern: str) -> pathlib.Path:
    runs = sorted((ROOT / "out").glob(pattern))
    runs = [r for r in runs if (r / "manifest.json").exists()]
    if not runs:
        sys.exit(f"no run matching out/{pattern}")
    return runs[-1]


def entry(run: pathlib.Path) -> dict:
    m = json.loads((run / "manifest.json").read_text())
    formats = {}
    for fmt in FORMATS:
        r = m["results"].get(fmt) or {}
        if not r.get("ok"):
            sys.exit(f"{run.name}: {fmt} did not finish ({r.get('error')}); pick a complete run")
        c = r["concept"]
        s = r["scores"].get(c["id"]) if isinstance(r.get("scores"), dict) else None
        formats[fmt] = {
            "email_line": r["email_line"], "alt_text": r["alt_text"],
            "mechanism": c.get("mechanism"), "joke_target": c.get("joke_target"),
            "grounding": c.get("grounding", []), "text": c.get("text", {}),
            "scores": {k: s[k] for k in ("funny", "specific", "kind", "glance", "total") if k in s}
            if isinstance(s, dict) else None,
            "gif_kb": r["gif_kb"], "seconds": r["seconds"], "art_backend": r["art_backend"],
        }
    return {"prospect": {k: m["prospect"].get(k, "") for k in PROSPECT_FIELDS},
            "context": m.get("context"), "total_seconds": m["total_seconds"],
            "cost_usd": m["cost_usd"], "formats": formats}


def main() -> int:
    ap = argparse.ArgumentParser()
    for key in SHOWCASE:
        ap.add_argument(f"--{key}", type=pathlib.Path, help=f"run folder for {key} (default: newest)")
    a = ap.parse_args()
    data = {"prospects": {}}
    for key, pattern in SHOWCASE.items():
        run = getattr(a, key) or newest(pattern)
        data["prospects"][key] = entry(run)
        dest = ROOT / "site" / "assets" / key
        dest.mkdir(parents=True, exist_ok=True)
        for fmt in FORMATS:
            for ext in ("gif", "png"):
                shutil.copy2(run / f"{fmt}.{ext}", dest / f"{fmt}.{ext}")
        print(f"{key}: {run.name}")
    (ROOT / "site" / "assets" / "data.json").write_text(json.dumps(data, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
