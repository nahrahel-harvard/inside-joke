"""One call from prospect facts to finished GIFs. Formats run in parallel; each
format is: concept (write 3 -> guardrails -> judge) -> art -> render -> encode.
Contract is documented in README and relied on by serve.py."""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from . import art as art_mod
from . import concept, llm, render
from .config import MODELS, ROOT
from .formats import FORMATS, ORDER
from .research import fetch_site

PROSPECT_KEYS = ["first_name", "last_name", "title", "company", "domain", "industry", "location",
                 "linkedin_headline", "notes", "brand_color"]


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40] or "prospect"


def run(prospect: dict, formats: list[str], *, context: str | None = None, art: str = "auto",
        fast: bool = False, research: bool = False, out_dir: pathlib.Path | None = None,
        on_event: Callable[[dict], None] | None = None, generic: bool = False,
        min_passing: int = 1) -> dict:
    t0 = time.time()
    lock = threading.Lock()

    def emit(fmt, stage, message):
        if on_event:
            with lock:
                on_event({"format": fmt, "stage": stage, "message": message, "t": round(time.time() - t0, 2)})

    prospect = {k: str(prospect.get(k) or "").strip() for k in PROSPECT_KEYS if prospect.get(k)}
    context = (context or "").strip() or None
    formats = [f for f in ORDER if f in formats]
    slug = _slug(f"{prospect.get('first_name', '')}-{prospect.get('company', '')}")
    out_dir = pathlib.Path(out_dir or ROOT / "out" / f"{slug}-{time.strftime('%Y%m%d-%H%M%S')}")
    out_dir.mkdir(parents=True, exist_ok=True)
    ledger = llm.Ledger()

    facts = dict(prospect)
    facts.pop("brand_color", None)  # styling only, never joke material
    if research and prospect.get("domain"):
        emit(None, "research", f"reading {prospect['domain']}")
        facts["site_snippet"] = fetch_site(prospect["domain"])

    def one(fmt: str) -> dict:
        spec = FORMATS[fmt]
        ft = time.time()
        if spec.get("needs_context") and not context and not generic:
            return {"ok": False, "error": "needs conversation context", "seconds": 0}
        try:
            emit(fmt, "concept", "writing 3 concepts")
            res = concept.pick(facts, fmt, context, fast=fast, ledger=ledger, generic=generic,
                               min_passing=min_passing)
            c = res["chosen"]
            prompts = c.get("art_prompts") if spec["panels"] > 1 else [c.get("art_prompt", "")]
            if fmt == "comic" and c["text"].get("cast"):
                prompts = [f"Recurring character: {c['text']['cast']}. Scene: {p}" for p in prompts]
            prompts = [f"{p}\n\nComposition: {spec['composition']}" for p in prompts]
            emit(fmt, "art", f"drawing {len(prompts)} panel(s) via {art}")
            arts, backend = art_mod.make_art(prompts, spec["art_size"], spec["aspect"], art, ledger, fmt)
            emit(fmt, "render", f"animating ({backend} art)")
            # Generic jokes must not carry the real name, company or brand color.
            shown = {"first_name": "you"} if generic else prospect
            frames = render.render(fmt, arts, c["text"], shown)
            info = render.encode(frames, out_dir / f"{fmt}.gif", out_dir / f"{fmt}.png")
            emit(fmt, "done", f"{info['gif_kb']} KB in {round(time.time() - ft, 1)} s")
            return {"ok": True, "error": None, "gif": f"{fmt}.gif", "png": f"{fmt}.png",
                    "gif_kb": info["gif_kb"], "frames": info["frames"], "seconds": round(time.time() - ft, 2),
                    "art_backend": backend, "concept": c, "scores": res["scores"],
                    "ranked_ids": [x["id"] for x in res["ranked"]],
                    "candidates": res["candidates"], "rejected": res["rejected"],
                    "email_line": c.get("email_line", ""), "alt_text": c.get("alt_text", "")}
        except Exception as e:
            emit(fmt, "error", str(e)[:300])
            return {"ok": False, "error": f"{e.__class__.__name__}: {e}"[:500], "seconds": round(time.time() - ft, 2)}

    with ThreadPoolExecutor(max_workers=max(1, len(formats))) as ex:
        results = dict(zip(formats, ex.map(one, formats)))

    manifest = {
        "slug": out_dir.name, "out_dir": str(out_dir.resolve()), "created": dt.datetime.now().isoformat(timespec="seconds"),
        "prospect": prospect, "context": context, "settings": {"art": art, "fast": fast, "research": research, "generic": generic,
                                                               "models": MODELS},
        "total_seconds": round(time.time() - t0, 2), "cost_usd": ledger.cost,
        "results": results, "ledger": ledger.rows,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False, default=str))
    return manifest
