"""Batch generation of personalized stimuli (conditions A and B).

For each participant in assignments.csv without finished stimuli:
  concept stage with min_passing=2 -> top 2 concepts that pass guardrails and the
  judge's kind bar -> the seeded coin flip (gif_rank) picks which one becomes the
  GIF (A); the other becomes the text-only email (B).
Writes study_data/stimuli/<code>/{A.gif, A.png, B.json, manifest.json} and a
screening_log.csv row with status pending_review.

Art is pinned (--art image or --art svg). Placeholder art is never saved.
Research fetching is always off. Idempotent: finished participants are skipped.

    .venv/bin/python -m study.batch --art image --limit 5
    .venv/bin/python -m study.batch --spend
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import pathlib
import shutil
import sys
import time

from inside_joke import art as art_mod
from inside_joke import concept, llm, render
from inside_joke.config import MODELS
from inside_joke.formats import FORMATS

from . import DATA_DIR, STUDY_FORMATS
from .assign import intake_to_prospect, read_assignments, read_intake
from .text_only import email_line_for_text, render_html

PINNED_ARTS = ("image", "svg")
SCREEN_COLUMNS = ["code", "status", "reason", "format", "arm", "art_backend", "a_concept_id", "b_concept_id",
                  "generic_item", "a_text", "b_text", "cost_usd", "updated"]
DONE_STATUSES = {"pending_review", "approved", "withheld"}
TERMINAL_FAIL = "failed_concepts"   # exclusion rule: no 2 passing concepts after 3 attempts
DEFAULT_BUDGET = 25.0
EST_PER_PARTICIPANT = 0.35


class PlaceholderArt(RuntimeError):
    pass


def check_art(mode: str) -> str:
    if mode not in PINNED_ARTS:
        raise ValueError(f"art must be pinned to one of {PINNED_ARTS} for the study, got {mode!r}. "
                         "'auto' can fall through to another backend and confound the study.")
    return mode


def art_prompts(fmt: str, c: dict) -> list[str]:
    """Same prompt assembly as pipeline.run, so study stimuli match the prototype."""
    spec = FORMATS[fmt]
    prompts = c.get("art_prompts") if spec["panels"] > 1 else [c.get("art_prompt", "")]
    return [f"{p}\n\nComposition: {spec['composition']}" for p in prompts]


def render_concept(fmt: str, c: dict, mode: str, ledger, render_prospect: dict,
                   gif_path: pathlib.Path, png_path: pathlib.Path) -> tuple[dict, str]:
    """Draw art with the pinned backend, render and encode. Raises PlaceholderArt
    (and writes nothing) if the backend fell back to the placeholder."""
    check_art(mode)
    spec = FORMATS[fmt]
    arts, backend = art_mod.make_art(art_prompts(fmt, c), spec["art_size"], spec["aspect"], mode, ledger, fmt)
    if backend == "placeholder" or backend != mode:
        raise PlaceholderArt(f"art backend fell back to {backend!r} (pinned {mode!r}); nothing saved")
    frames = render.render(fmt, arts, c["text"], render_prospect)
    gif_path.parent.mkdir(parents=True, exist_ok=True)
    info = render.encode(frames, gif_path, png_path)
    return info, backend


def slim(c: dict) -> dict:
    return {k: c.get(k) for k in ("id", "mechanism", "joke_target", "grounding", "text", "art_prompt",
                                  "alt_text", "email_line")}


def top_two(res: dict) -> list[dict]:
    """The 2 highest-ranked concepts that passed guardrails and the kind bar."""
    scores = res.get("scores") or {}
    if not scores or scores.get("_error"):
        raise RuntimeError(f"judge did not run, so the kind bar was not applied: {scores.get('_error', 'no scores')}"[:300])
    ok = [c for c in res["ranked"] if (scores.get(c["id"]) or {}).get("total", -1) >= 0]
    if len(ok) < 2:
        raise LookupError(f"only {len(ok)} concept(s) passed guardrails and the kind bar")
    return ok[:2]


# ---------- screening log ----------

def read_log(path: pathlib.Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        return {r["code"]: r for r in csv.DictReader(f)}


def write_log(path: pathlib.Path, rows: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=SCREEN_COLUMNS, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for r in rows.values():
            w.writerow({k: r.get(k, "") for k in SCREEN_COLUMNS})
    tmp.replace(path)


# ---------- spend ----------

def spend(data_dir: pathlib.Path) -> dict:
    """Sum cost_usd over every saved study manifest (stimuli and generic pool),
    including failed attempts, which keep a manifest too."""
    total, by = 0.0, {"stimuli": 0.0, "generic": 0.0}
    n = {"stimuli": 0, "generic": 0}
    for kind, pattern in (("stimuli", "stimuli/*/manifest*.json"), ("stimuli", "stimuli/*/_old_*/manifest*.json"),
                          ("generic", "generic/*/*.json")):
        for p in data_dir.glob(pattern):
            try:
                c = float(json.loads(p.read_text()).get("cost_usd") or 0)
            except (ValueError, json.JSONDecodeError):
                continue
            by[kind] += c
            n[kind] += 1
            total += c
    return {"total_usd": round(total, 4), "stimuli_usd": round(by["stimuli"], 4),
            "generic_usd": round(by["generic"], 4), "manifests": n}


# ---------- one participant ----------

def run_one(a: dict, prospect: dict, *, art: str, out_dir: pathlib.Path, fast: bool = False) -> dict:
    """Generate A and B for one participant. Returns the manifest (status ok or failed).
    Never raises for model or art failures; they become a failed manifest."""
    check_art(art)
    fmt = a["format"]
    if fmt not in STUDY_FORMATS:
        raise ValueError(f"format {fmt!r} is not a study format")
    t0 = time.time()
    ledger = llm.Ledger()
    facts = dict(prospect)  # research is always off: facts are exactly what the participant typed
    man = {"code": a["code"], "created": dt.datetime.now().isoformat(timespec="seconds"),
           "assignment": a, "prospect": prospect, "format": fmt,
           "settings": {"art": art, "fast": fast, "research": False, "min_passing": 2, "models": MODELS}}
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        res = concept.pick(facts, fmt, None, fast=fast, ledger=ledger, min_passing=2)
        two = top_two(res)
        a_c, b_c = (two[0], two[1]) if int(a["gif_rank"]) == 0 else (two[1], two[0])
        scores = res.get("scores") or {}
        info, backend = render_concept(fmt, a_c, art, ledger, prospect, out_dir / "A.gif", out_dir / "A.png")
        b = {"format": fmt, "concept_id": b_c["id"], "text": b_c.get("text"), "email_line": b_c.get("email_line", ""),
             "mechanism": b_c.get("mechanism"), "grounding": b_c.get("grounding"), "scores": scores.get(b_c["id"])}
        b["email_line_dropped"] = bool(b["email_line"]) and not email_line_for_text(b["email_line"])
        b["html"] = render_html(b, prospect)
        (out_dir / "B.json").write_text(json.dumps(b, indent=2, ensure_ascii=False))
        man.update({
            "status": "ok", "art_backend": backend, "gif": info,
            "A": {**slim(a_c), "rank": two.index(a_c), "scores": scores.get(a_c["id"]),
                  "grounding_count": len(a_c.get("grounding") or [])},
            "B": {**slim(b_c), "rank": two.index(b_c), "scores": scores.get(b_c["id"]),
                  "grounding_count": len(b_c.get("grounding") or [])},
            "b_email_line_dropped": b["email_line_dropped"],
            "scores": scores, "ranked_ids": [c["id"] for c in res["ranked"]],
            "candidates": [slim(c) for c in res["candidates"]],
            "rejected": [{**slim(c), "problems": c.get("problems")} for c in res["rejected"]],
            "attempts": max([int(str(c["id"])[1:].split("c")[0]) for c in res["candidates"] + res["rejected"]
                             if str(c.get("id", "")).startswith("r")] or [1]),
        })
    except LookupError as e:
        man.update({"status": TERMINAL_FAIL, "error": str(e)})
    except PlaceholderArt as e:
        man.update({"status": "failed_art", "error": str(e)})
    except Exception as e:  # noqa: BLE001  a model or network failure; retried on the next run
        msg = f"{e.__class__.__name__}: {e}"[:500]
        man.update({"status": TERMINAL_FAIL if "every concept failed guardrails" in msg or "kindness bar" in msg
                    else "failed_error", "error": msg})
    if man["status"] != "ok":
        for name in ("A.gif", "A.png", "B.json"):
            (out_dir / name).unlink(missing_ok=True)
    man["seconds"] = round(time.time() - t0, 2)
    man["cost_usd"] = ledger.cost
    man["ledger"] = ledger.rows
    name = "manifest.json" if man["status"] == "ok" else f"manifest_failed_{time.strftime('%Y%m%d-%H%M%S')}.json"
    (out_dir / name).write_text(json.dumps(man, indent=2, ensure_ascii=False, default=str))
    return man  # failed manifests are kept: their cost still counts toward spend


def is_finished(code: str, data_dir: pathlib.Path, log: dict[str, dict], retry_failed: bool) -> bool:
    st = (log.get(code) or {}).get("status", "")
    if st == "regenerate":
        return False
    if st in DONE_STATUSES and (data_dir / "stimuli" / code / "manifest.json").exists():
        return True
    if st == TERMINAL_FAIL and not retry_failed:
        return True
    return False


def archive_for_regen(stim: pathlib.Path) -> None:
    if (stim / "manifest.json").exists():
        dest = stim / f"_old_{time.strftime('%Y%m%d-%H%M%S')}"
        dest.mkdir()
        for name in ("A.gif", "A.png", "B.json", "manifest.json"):
            if (stim / name).exists():
                shutil.move(str(stim / name), dest / name)


def run_batch(*, data_dir: pathlib.Path, intake: pathlib.Path, art: str, limit: int | None = None,
              budget: float = DEFAULT_BUDGET, retry_failed: bool = False, only: list[str] | None = None,
              log=print) -> list[dict]:
    check_art(art)
    assignments = read_assignments(data_dir / "assignments.csv")
    facts = {r["code"]: r for r in read_intake(intake)}
    log_path = data_dir / "screening_log.csv"
    screen = read_log(log_path)
    done = []
    todo = [a for a in assignments if not is_finished(a["code"], data_dir, screen, retry_failed)
            and (not only or a["code"] in only)]
    if limit is not None:
        todo = todo[:max(0, limit)]
    for a in todo:
        code = a["code"]
        if code not in facts:
            log(f"{code}: not in intake, skipped")
            continue
        spent = spend(data_dir)["total_usd"]
        if spent + EST_PER_PARTICIPANT > budget:
            log(f"stopping: spent ${spent:.2f}, next participant would pass the ${budget:.2f} cap")
            break
        stim = data_dir / "stimuli" / code
        if (screen.get(code) or {}).get("status") == "regenerate":
            archive_for_regen(stim)
        log(f"{code}: generating {a['format']} with {art} art")
        man = run_one(a, intake_to_prospect(facts[code]), art=art, out_dir=stim)
        row = {"code": code, "format": a["format"], "arm": a["arm"], "generic_item": a["generic_item"],
               "cost_usd": man["cost_usd"], "updated": dt.datetime.now().isoformat(timespec="seconds")}
        if man["status"] == "ok":
            b_note = "B email_line dropped (it mentioned an image)" if man.get("b_email_line_dropped") else ""
            row.update({"status": "pending_review", "reason": b_note, "art_backend": man["art_backend"],
                        "a_concept_id": man["A"]["id"], "b_concept_id": man["B"]["id"],
                        "a_text": json.dumps(man["A"]["text"], ensure_ascii=False),
                        "b_text": json.dumps(man["B"]["text"], ensure_ascii=False)})
        else:
            row.update({"status": man["status"], "reason": man.get("error", "")[:300]})
        screen[code] = row
        write_log(log_path, screen)
        log(f"{code}: {row['status']} (${man['cost_usd']:.3f}, {man['seconds']} s) {row.get('reason', '')}")
        done.append(man)
    return done


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Generate personalized study stimuli (A and B).")
    ap.add_argument("--art", choices=["image", "svg", "auto", "placeholder"], default=None,
                    help="art backend, must be image or svg (auto and placeholder are refused)")
    ap.add_argument("--data-dir", type=pathlib.Path, default=DATA_DIR)
    ap.add_argument("--intake", type=pathlib.Path, default=None)
    ap.add_argument("--limit", type=int, default=None, help="process at most this many participants")
    ap.add_argument("--only", default="", help="comma-separated participant codes")
    ap.add_argument("--budget", type=float, default=DEFAULT_BUDGET, help="stop before total spend passes this (USD)")
    ap.add_argument("--retry-failed", action="store_true",
                    help="also retry participants marked failed_concepts (normally an exclusion)")
    ap.add_argument("--spend", action="store_true", help="print total study spend and exit")
    a = ap.parse_args(argv)
    if a.spend:
        print(json.dumps(spend(a.data_dir), indent=2))
        return 0
    if a.art is None:
        ap.error("--art is required (image or svg)")
    try:
        check_art(a.art)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    run_batch(data_dir=a.data_dir, intake=a.intake or a.data_dir / "intake.csv", art=a.art, limit=a.limit,
              budget=a.budget, retry_failed=a.retry_failed, only=[c for c in a.only.split(",") if c])
    print(json.dumps(spend(a.data_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
