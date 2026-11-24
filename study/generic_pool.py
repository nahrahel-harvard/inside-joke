"""Condition C: a frozen pool of 6 generic office-life GIFs per study format.

Writes study_data/generic/<fmt>/<i>.gif, <i>.png and <i>.json (concept, judge
scores, cost, ledger). An item whose GIF exists is never regenerated, so paid
calls are not repeated; delete an item's 3 files to rebuild just that item.

    .venv/bin/python -m study.generic_pool --art image
    .venv/bin/python -m study.generic_pool --art image --formats meme --count 1   # smoke
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys
import time

from inside_joke import concept, llm
from inside_joke.config import MODELS

from . import DATA_DIR, STUDY_FORMATS
from .assign import GENERIC_POOL_SIZE
from .batch import DEFAULT_BUDGET, PlaceholderArt, check_art, render_concept, slim, spend

# The headline renderer prints "SPECIAL EDITION FOR <first_name>". Generic items
# carry no name, so the display-only prospect reads "FOR YOU". The writer and the
# judge never see it.
RENDER_PROSPECT = {"first_name": "you"}
EST_PER_ITEM = 0.15


def build_item(fmt: str, i: int, *, art: str, out: pathlib.Path) -> dict:
    check_art(art)
    ledger = llm.Ledger()
    t0 = time.time()
    man = {"format": fmt, "item": i, "created": dt.datetime.now().isoformat(timespec="seconds"),
           "settings": {"art": art, "generic": True, "research": False, "min_passing": 2, "models": MODELS}}
    gif, png = out / f"{i}.gif", out / f"{i}.png"
    try:
        res = concept.pick({}, fmt, None, fast=False, ledger=ledger, generic=True, min_passing=2)
        scores = res.get("scores") or {}
        if not scores or scores.get("_error"):
            raise RuntimeError(f"judge did not score this item: {scores.get('_error', 'no scores')}"[:300])
        ok = [c for c in res["ranked"] if (scores.get(c["id"]) or {}).get("total", -1) >= 0]
        if not ok:
            raise RuntimeError("no generic concept passed the kind bar")
        c = ok[0]
        info, backend = render_concept(fmt, c, art, ledger, RENDER_PROSPECT, gif, png)
        man.update({"status": "ok", "art_backend": backend, "gif": info, "concept": slim(c),
                    "scores": scores, "ranked_ids": [x["id"] for x in res["ranked"]],
                    "candidates": [slim(x) for x in res["candidates"]],
                    "rejected": [{**slim(x), "problems": x.get("problems")} for x in res["rejected"]]})
    except PlaceholderArt as e:
        man.update({"status": "failed_art", "error": str(e)})
    except Exception as e:  # noqa: BLE001
        man.update({"status": "failed_error", "error": f"{e.__class__.__name__}: {e}"[:500]})
    if man["status"] != "ok":
        gif.unlink(missing_ok=True)
        png.unlink(missing_ok=True)
    man.update({"seconds": round(time.time() - t0, 2), "cost_usd": ledger.cost, "ledger": ledger.rows})
    name = f"{i}.json" if man["status"] == "ok" else f"{i}_failed_{time.strftime('%Y%m%d-%H%M%S')}.json"
    (out / name).write_text(json.dumps(man, indent=2, ensure_ascii=False, default=str))
    return man


def build_pool(*, data_dir: pathlib.Path, art: str, formats=STUDY_FORMATS, count: int = GENERIC_POOL_SIZE,
               budget: float = DEFAULT_BUDGET, log=print) -> list[dict]:
    check_art(art)
    made = []
    for fmt in formats:
        if fmt not in STUDY_FORMATS:
            raise ValueError(f"{fmt} is not a study format")
        out = data_dir / "generic" / fmt
        out.mkdir(parents=True, exist_ok=True)
        for i in range(count):
            if (out / f"{i}.gif").exists() and (out / f"{i}.json").exists():
                log(f"{fmt}/{i}: exists, skipped")
                continue
            spent = spend(data_dir)["total_usd"]
            if spent + EST_PER_ITEM > budget:
                log(f"stopping: spent ${spent:.2f}, next item would pass the ${budget:.2f} cap")
                return made
            man = build_item(fmt, i, art=art, out=out)
            log(f"{fmt}/{i}: {man['status']} (${man['cost_usd']:.3f}, {man['seconds']} s) {man.get('error', '')}")
            made.append(man)
    return made


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build the frozen generic GIF pool (condition C).")
    ap.add_argument("--art", choices=["image", "svg", "auto", "placeholder"], required=True)
    ap.add_argument("--data-dir", type=pathlib.Path, default=DATA_DIR)
    ap.add_argument("--formats", default=",".join(STUDY_FORMATS))
    ap.add_argument("--count", type=int, default=GENERIC_POOL_SIZE, help="items 0..count-1 per format")
    ap.add_argument("--budget", type=float, default=DEFAULT_BUDGET)
    a = ap.parse_args(argv)
    try:
        check_art(a.art)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    build_pool(data_dir=a.data_dir, art=a.art, formats=[f for f in a.formats.split(",") if f],
               count=min(a.count, GENERIC_POOL_SIZE), budget=a.budget)
    print(json.dumps(spend(a.data_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
