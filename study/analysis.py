"""Analysis for the Inside Joke study (plan sections 3.7 to 3.10).

2 steps:

  collect   turns returned answers into one long ratings CSV (one row per
            participant x item position). Sources: a folder of downloaded
            <code>_answers.json files and/or a Google Sheets CSV export whose
            column headers are the answer keys (see the runbook).
  run       applies the exclusion rules, computes composites and runs H1 to H4,
            manipulation checks and M1; writes results/summary.md and figures.

    .venv/bin/python -m study.analysis collect --json-dir study_data/answers --out study_data/ratings.csv
    .venv/bin/python -m study.analysis run --ratings study_data/ratings.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import pathlib
from collections import defaultdict

import numpy as np
from scipy import stats

from . import DATA_DIR, RESULTS_DIR
from .assign import read_assignments, truthy
from .batch import read_log
from .pages import ITEM_KEYS

RATING_COLUMNS = (["code", "position"] + ITEM_KEYS +
                  ["attention", "mc_ai", "mc_minutes", "facts_type", "seconds", "submitted_at", "open_text"])
MIN_SECONDS = 90
MIN_N_FOR_TESTS = 16
MIN_N_FOR_MIXED = 30
COMPOSITE_R = 0.50
M1_DIMS = {"funny": "funny", "specific": "specific", "kind": "kind", "glance": "glance"}
BOOT = 2000


# ============ collect ============

def _rows_from_answers(p: dict) -> list[dict]:
    rows = []
    for pos in (1, 2, 3):
        r = {"code": p.get("code", ""), "position": pos}
        for k in ITEM_KEYS:
            r[k] = p.get(f"item{pos}_{k}", "")
        r["attention"] = p.get(f"item{pos}_attention", "") if pos == 2 else ""
        for k in ("mc_ai", "mc_minutes", "facts_type", "seconds", "submitted_at", "open_text"):
            r[k] = p.get(k, "")
        rows.append(r)
    return rows


def collect(json_dir: pathlib.Path | None, wide_csv: pathlib.Path | None) -> list[dict]:
    payloads = []
    if json_dir:
        for f in sorted(json_dir.glob("*.json")):
            payloads.append(json.loads(f.read_text(encoding="utf-8")))
    if wide_csv:
        with open(wide_csv, newline="", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                r = {k.strip(): v for k, v in r.items() if k}
                if not r.get("submitted_at") and r.get("Timestamp"):
                    r["submitted_at"] = r["Timestamp"]
                payloads.append(r)
    rows = []
    for p in payloads:
        rows.extend(_rows_from_answers(p))
    return rows


def write_ratings(rows: list[dict], out: pathlib.Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=RATING_COLUMNS, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


# ============ load + exclusions ============

def _num(v):
    try:
        x = float(str(v).strip())
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def load_ratings(path: pathlib.Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def group_submissions(rows: list[dict]) -> dict[str, list[list[dict]]]:
    """code -> list of submissions (each 3 rows), in submission order."""
    by = defaultdict(lambda: defaultdict(list))
    order = {}
    for i, r in enumerate(rows):
        key = (r.get("submitted_at") or "", )
        by[r["code"]][key].append(r)
        order.setdefault((r["code"], key), i)
    out = {}
    for code, subs in by.items():
        keys = sorted(subs, key=lambda k: (k[0] or "~", order[(code, k)]))
        out[code] = [subs[k] for k in keys]
    return out


def participant_record(code: str, sub: list[dict], a: dict) -> dict | None:
    """Return a clean per-participant record, or None if incomplete."""
    by_pos = {int(float(r["position"])): r for r in sub if _num(r.get("position")) is not None}
    if sorted(by_pos) != [1, 2, 3]:
        return None
    cond_rows = {}
    for cond in "ABC":
        r = by_pos[a[f"pos_{cond}"]]
        vals = {k: _num(r.get(k)) for k in ITEM_KEYS}
        if any(v is None or not 1 <= v <= 7 for v in vals.values()):
            return None
        vals["effort"] = (vals["effort1"] + vals["effort2"]) / 2
        vals["creepy"] = (vals["creepy1"] + vals["creepy2"]) / 2
        cond_rows[cond] = vals
    first = by_pos[1]
    facts = str(first.get("facts_type") or "").strip().lower()
    return {
        "code": code, "arm": a["arm"], "format": a["format"], "order": a["order"],
        "generic_item": a["generic_item"],
        "persona": truthy(a.get("is_persona")) or facts == "persona",
        "attention": _num(by_pos[2].get("attention")),
        "seconds": _num(first.get("seconds")),
        "mc_ai": _num(first.get("mc_ai")), "mc_minutes": _num(first.get("mc_minutes")),
        "open_text": first.get("open_text", ""),
        "by_cond": cond_rows,
        "by_pos": {p: {k: _num(by_pos[p].get(k)) for k in ITEM_KEYS} for p in (1, 2, 3)},
    }


def apply_exclusions(rows: list[dict], assignments: dict[str, dict], *, builders: set[str],
                     screening: dict[str, dict]) -> tuple[list[dict], dict]:
    flow = {"rating_submissions": 0, "participants_with_ratings": 0, "unknown_code": 0,
            "duplicate_submissions_dropped": 0, "incomplete": 0, "attention_check": 0,
            "under_90_seconds": 0, "same_answer_all_30": 0, "helped_build": 0,
            "failed_concepts_before_rating": sum(1 for r in screening.values() if r.get("status") == "failed_concepts"),
            "assigned": len(assignments),
            "approved": sum(1 for r in screening.values() if r.get("status") == "approved")}
    subs = group_submissions(rows)
    flow["rating_submissions"] = sum(len(v) for v in subs.values())
    flow["participants_with_ratings"] = len(subs)
    valid = []
    for code, s in subs.items():
        if code not in assignments:
            flow["unknown_code"] += 1
            continue
        flow["duplicate_submissions_dropped"] += len(s) - 1
        rec = participant_record(code, s[0], assignments[code])   # keep the first submission
        if rec is None:
            flow["incomplete"] += 1
        elif rec["attention"] != 2:
            flow["attention_check"] += 1
        elif rec["seconds"] is None or rec["seconds"] < MIN_SECONDS:
            flow["under_90_seconds"] += 1
        elif len({v for p in rec["by_pos"].values() for v in p.values()}) == 1:
            flow["same_answer_all_30"] += 1
        elif code in builders:
            flow["helped_build"] += 1
        else:
            valid.append(rec)
    flow["valid"] = len(valid)
    return valid, flow


# ============ statistics ============

def paired(x, y) -> dict:
    x, y = np.asarray(x, float), np.asarray(y, float)
    d = x - y
    n = len(d)
    out = {"n": n, "mean_x": float(x.mean()) if n else float("nan"), "mean_y": float(y.mean()) if n else float("nan"),
           "mean_diff": float(d.mean()) if n else float("nan")}
    if n < 2:
        return {**out, "sd_diff": float("nan"), "ci": (float("nan"),) * 2, "dz": float("nan"), "t": float("nan"),
                "p_t": float("nan"), "w": float("nan"), "p_w": float("nan")}
    sd = float(d.std(ddof=1))
    se = sd / math.sqrt(n)
    tc = float(stats.t.ppf(0.975, n - 1))
    out.update({"sd_diff": sd, "ci": (out["mean_diff"] - tc * se, out["mean_diff"] + tc * se),
                "dz": out["mean_diff"] / sd if sd > 0 else float("nan")})
    if sd > 0:
        t = stats.ttest_rel(x, y)
        out.update({"t": float(t.statistic), "p_t": float(t.pvalue)})
    else:
        out.update({"t": float("nan"), "p_t": float("nan")})
    try:
        w = stats.wilcoxon(d)
        out.update({"w": float(w.statistic), "p_w": float(w.pvalue)})
    except ValueError:
        out.update({"w": float("nan"), "p_w": float("nan")})
    return out


def holm(ps: dict[str, float]) -> dict[str, float]:
    items = sorted(((p if not math.isnan(p) else 1.0), k) for k, p in ps.items())
    m = len(items)
    adj, running = {}, 0.0
    for i, (p, k) in enumerate(items):
        running = max(running, min(1.0, (m - i) * p))
        adj[k] = running
    return adj


def welch_hedges(a, b) -> dict:
    a, b = np.asarray(a, float), np.asarray(b, float)
    n1, n2 = len(a), len(b)
    out = {"n1": n1, "n2": n2, "mean1": float(a.mean()) if n1 else float("nan"),
           "mean2": float(b.mean()) if n2 else float("nan")}
    out["mean_diff"] = out["mean1"] - out["mean2"]
    if n1 < 2 or n2 < 2:
        return {**out, "t": float("nan"), "p": float("nan"), "df": float("nan"), "ci": (float("nan"),) * 2,
                "g": float("nan"), "g_ci": (float("nan"),) * 2}
    v1, v2 = a.var(ddof=1), b.var(ddof=1)
    se = math.sqrt(v1 / n1 + v2 / n2)
    df = (v1 / n1 + v2 / n2) ** 2 / ((v1 / n1) ** 2 / (n1 - 1) + (v2 / n2) ** 2 / (n2 - 1)) if se > 0 else float("nan")
    t = stats.ttest_ind(a, b, equal_var=False) if se > 0 else None
    tc = float(stats.t.ppf(0.975, df)) if se > 0 else float("nan")
    sp = math.sqrt(((n1 - 1) * v1 + (n2 - 1) * v2) / (n1 + n2 - 2))
    d = out["mean_diff"] / sp if sp > 0 else float("nan")
    j = 1 - 3 / (4 * (n1 + n2) - 9)
    g = j * d
    g_se = math.sqrt((n1 + n2) / (n1 * n2) + g ** 2 / (2 * (n1 + n2))) if not math.isnan(g) else float("nan")
    out.update({"t": float(t.statistic) if t else float("nan"), "p": float(t.pvalue) if t else float("nan"),
                "df": df, "ci": (out["mean_diff"] - tc * se, out["mean_diff"] + tc * se),
                "g": g, "g_ci": (g - 1.96 * g_se, g + 1.96 * g_se)})
    return out


def mann_whitney(a, b) -> dict:
    a, b = [x for x in a if x is not None], [x for x in b if x is not None]
    out = {"n1": len(a), "n2": len(b), "median1": float(np.median(a)) if a else float("nan"),
           "median2": float(np.median(b)) if b else float("nan"), "mean1": float(np.mean(a)) if a else float("nan"),
           "mean2": float(np.mean(b)) if b else float("nan")}
    try:
        r = stats.mannwhitneyu(a, b, alternative="two-sided")
        out.update({"u": float(r.statistic), "p": float(r.pvalue)})
    except ValueError:
        out.update({"u": float("nan"), "p": float("nan")})
    return out


def _spearman(x, y) -> float:
    if len(x) < 3 or len(set(x)) < 2 or len(set(y)) < 2:
        return float("nan")
    return float(stats.spearmanr(x, y).statistic)


# ============ M1 ============

def judge_rows(valid: list[dict], data_dir: pathlib.Path) -> list[dict]:
    """One row per (participant, condition) with judge scores and human ratings."""
    out = []
    generic_cache = {}
    for rec in valid:
        man_p = data_dir / "stimuli" / rec["code"] / "manifest.json"
        man = json.loads(man_p.read_text()) if man_p.exists() else {}
        for cond in "ABC":
            if cond in "AB":
                scores = (man.get(cond) or {}).get("scores") or {}
                sid = f"{rec['code']}:{cond}"
                gcount = (man.get(cond) or {}).get("grounding_count")
            else:
                key = (rec["format"], rec["generic_item"])
                if key not in generic_cache:
                    gp = data_dir / "generic" / rec["format"] / f"{rec['generic_item']}.json"
                    gm = json.loads(gp.read_text()) if gp.exists() else {}
                    cid = (gm.get("concept") or {}).get("id")
                    generic_cache[key] = (gm.get("scores") or {}).get(cid) or {}
                scores = generic_cache[key]
                sid = f"generic:{rec['format']}:{rec['generic_item']}"
                gcount = 0
            if not scores:
                continue
            out.append({"code": rec["code"], "cond": cond, "stimulus": sid, "grounding_count": gcount,
                        "judge": {d: _num(scores.get(d)) for d in M1_DIMS},
                        "human": {h: rec["by_cond"][cond][h] for h in M1_DIMS.values()},
                        "creepy": rec["by_cond"][cond]["creepy"]})
    return out


def _agg_rho(rows: list[dict], dim: str) -> float:
    acc = defaultdict(list)
    judge = {}
    for r in rows:
        j = r["judge"][dim]
        if j is None:
            continue
        acc[r["stimulus"]].append(r["human"][M1_DIMS[dim]])
        judge[r["stimulus"]] = j
    keys = sorted(acc)
    return _spearman([judge[k] for k in keys], [float(np.mean(acc[k])) for k in keys])


def m1(rows: list[dict], *, seed: int = 0, boot: int = BOOT) -> dict:
    """Spearman rho between judge score and mean human rating per stimulus, with a
    95% bootstrap interval that resamples participants."""
    rng = np.random.default_rng(seed)
    by_code = defaultdict(list)
    for r in rows:
        by_code[r["code"]].append(r)
    codes = sorted(by_code)
    out = {}
    for dim in M1_DIMS:
        rho = _agg_rho(rows, dim)
        reps = []
        if codes and not math.isnan(rho):
            for _ in range(boot):
                pick = rng.choice(len(codes), size=len(codes), replace=True)
                sample = []
                for n_i, idx in enumerate(pick):
                    for r in by_code[codes[idx]]:
                        # duplicated participants keep their own copies of A and B
                        sample.append({**r, "stimulus": r["stimulus"] if r["cond"] == "C" else f"{r['stimulus']}#{n_i}"})
                v = _agg_rho(sample, dim)
                if not math.isnan(v):
                    reps.append(v)
        ci = (float(np.percentile(reps, 2.5)), float(np.percentile(reps, 97.5))) if len(reps) > 50 else (float("nan"),) * 2
        n_stim = len({r["stimulus"] for r in rows if r["judge"][dim] is not None})
        out[dim] = {"rho": rho, "ci": ci, "n_stimuli": n_stim, "n_participants": len(codes)}
    return out


# ============ figures ============

def figures(valid: list[dict], jrows: list[dict], fig_dir: pathlib.Path) -> list[str]:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return []
    fig_dir.mkdir(parents=True, exist_ok=True)
    made = []

    def paired_fig(name, measure, c1, c2, title):
        x = np.array([r["by_cond"][c1][measure] for r in valid])
        y = np.array([r["by_cond"][c2][measure] for r in valid])
        fig, ax = plt.subplots(figsize=(4.2, 4.2))
        jit = np.random.default_rng(1).uniform(-0.06, 0.06, len(x))
        for i in range(len(x)):
            ax.plot([0 + jit[i], 1 + jit[i]], [x[i], y[i]], color="#9aa4b2", lw=0.8, alpha=0.6)
        ax.scatter(np.zeros(len(x)) + jit, x, s=14, color="#2f6fed", zorder=3)
        ax.scatter(np.ones(len(y)) + jit, y, s=14, color="#d9822b", zorder=3)
        for pos, v in ((0, x), (1, y)):
            if len(v) > 1:
                m, se = v.mean(), v.std(ddof=1) / math.sqrt(len(v))
                tc = stats.t.ppf(0.975, len(v) - 1)
                ax.errorbar(pos + 0.22, m, yerr=tc * se, fmt="o", color="#1d1d1f", capsize=4, zorder=4)
        ax.set_xticks([0, 1], [f"{c1}", f"{c2}"])
        ax.set_ylim(0.5, 7.5)
        ax.set_ylabel(measure)
        ax.set_title(title, fontsize=10)
        fig.tight_layout()
        fig.savefig(fig_dir / name, dpi=150)
        plt.close(fig)
        made.append(name)

    if valid:
        paired_fig("h1_effort_A_vs_C.png", "effort", "A", "C", "H1: effort, personalized GIF vs generic GIF")
        paired_fig("h3_creepy_A_vs_C.png", "creepy", "A", "C", "H3: creepiness, personalized GIF vs generic GIF")
        paired_fig("h4_funny_A_vs_B.png", "funny", "A", "B", "H4: funny, personalized GIF vs text only")
        fig, ax = plt.subplots(figsize=(4.2, 4.2))
        for i, arm in enumerate(("no_label", "label")):
            d = np.array([r["by_cond"]["A"]["effort"] - r["by_cond"]["C"]["effort"] for r in valid if r["arm"] == arm])
            if not len(d):
                continue
            ax.scatter(np.full(len(d), i) + np.random.default_rng(2).uniform(-0.08, 0.08, len(d)), d, s=14,
                       color="#2f6fed" if arm == "no_label" else "#d9822b")
            if len(d) > 1:
                tc = stats.t.ppf(0.975, len(d) - 1)
                ax.errorbar(i + 0.25, d.mean(), yerr=tc * d.std(ddof=1) / math.sqrt(len(d)), fmt="o", color="#1d1d1f", capsize=4)
        ax.axhline(0, color="#9aa4b2", lw=0.8)
        ax.set_xticks([0, 1], ["no label", "AI label"])
        ax.set_ylabel("effort A minus C")
        ax.set_title("H2: disclosure and the effort gap", fontsize=10)
        fig.tight_layout()
        fig.savefig(fig_dir / "h2_disclosure.png", dpi=150)
        plt.close(fig)
        made.append("h2_disclosure.png")
    if jrows:
        fig, axes = plt.subplots(2, 2, figsize=(7, 7))
        colors = {"A": "#2f6fed", "B": "#2a9d8f", "C": "#d9822b"}
        for ax, dim in zip(axes.flat, M1_DIMS):
            for cond in "ABC":
                pts = [(r["judge"][dim], r["human"][M1_DIMS[dim]]) for r in jrows if r["cond"] == cond and r["judge"][dim] is not None]
                if pts:
                    jx = np.random.default_rng(3).uniform(-0.12, 0.12, len(pts))
                    ax.scatter([p[0] + j for p, j in zip(pts, jx)], [p[1] for p in pts], s=14, color=colors[cond], label=cond)
            ax.set_xlabel(f"judge {dim} (1 to 10)")
            ax.set_ylabel(f"human {M1_DIMS[dim]} (1 to 7)")
            ax.set_title(dim, fontsize=10)
        axes.flat[0].legend(fontsize=8)
        fig.suptitle("M1: judge vs human", fontsize=11)
        fig.tight_layout()
        fig.savefig(fig_dir / "m1_judge_vs_human.png", dpi=150)
        plt.close(fig)
        made.append("m1_judge_vs_human.png")
    return made


# ============ report ============

def _f(x, nd=2):
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{nd}f}"


def _p(x):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a"
    return "< .001" if x < 0.001 else f"{x:.3f}"


def _peq(x):
    v = _p(x)
    return f"p {v}" if v.startswith("<") else f"p = {v}"


def _paired_line(label, r, p_holm=None):
    s = (f"| {label} | {r['n']} | {_f(r['mean_x'])} | {_f(r['mean_y'])} | {_f(r['mean_diff'])} "
         f"[{_f(r['ci'][0])}, {_f(r['ci'][1])}] | {_f(r['dz'])} | {_f(r['t'])} | {_p(r['p_t'])} | {_p(r['p_w'])} |")
    return s + (f" {_p(p_holm)} |" if p_holm is not None else " |")


def analyze(valid: list[dict], flow: dict, data_dir: pathlib.Path, *, tests: bool | None = None) -> dict:
    n = len(valid)
    tests = n >= MIN_N_FOR_TESTS if tests is None else tests
    res = {"n": n, "flow": flow, "tests": tests}

    def col(cond, m, rs=valid):
        return [r["by_cond"][cond][m] for r in rs]

    measures = ITEM_KEYS + ["effort", "creepy"]
    res["descriptives"] = {cond: {m: (float(np.mean(col(cond, m))) if n else float("nan"),
                                      float(np.std(col(cond, m), ddof=1)) if n > 1 else float("nan"))
                                  for m in measures} for cond in "ABC"}
    allrows = [r["by_cond"][c] for r in valid for c in "ABC"]
    res["composite_r"] = {}
    for comp, (i1, i2) in (("effort", ("effort1", "effort2")), ("creepy", ("creepy1", "creepy2"))):
        x, y = [r[i1] for r in allrows], [r[i2] for r in allrows]
        r_ = float(stats.pearsonr(x, y).statistic) if len(x) > 2 and len(set(x)) > 1 and len(set(y)) > 1 else float("nan")
        res["composite_r"][comp] = r_
    res["order"] = {p: {m: float(np.mean([r["by_pos"][p][m] for r in valid])) if n else float("nan")
                        for m in ("funny", "effort1", "creepy1", "reply")} for p in (1, 2, 3)}

    def hyp(rs):
        h = {"H1": paired(col("A", "effort", rs), col("C", "effort", rs)),
             "H3": paired(col("A", "creepy", rs), col("C", "creepy", rs)),
             "H4": paired(col("A", "funny", rs), col("B", "funny", rs))}
        adj = holm({k: v["p_t"] for k, v in h.items()})
        for k in h:
            h[k]["p_holm"] = adj[k]
        da = [r["by_cond"]["A"]["effort"] - r["by_cond"]["C"]["effort"] for r in rs if r["arm"] == "label"]
        dn = [r["by_cond"]["A"]["effort"] - r["by_cond"]["C"]["effort"] for r in rs if r["arm"] == "no_label"]
        h["H2"] = welch_hedges(da, dn)
        return h

    res["hyp"] = hyp(valid)
    res["items_split"] = {}
    for comp, items in (("effort", ("effort1", "effort2")), ("creepy", ("creepy1", "creepy2"))):
        r_ = res["composite_r"][comp]
        if not math.isnan(r_) and r_ < COMPOSITE_R:
            res["items_split"][comp] = {i: paired(col("A", i), col("C", i)) for i in items}
    real = [r for r in valid if not r["persona"]]
    res["sensitivity_n"] = len(real)
    res["sensitivity"] = hyp(real) if real else None
    lab = [r for r in valid if r["arm"] == "label"]
    nol = [r for r in valid if r["arm"] == "no_label"]
    res["manip"] = {
        "ai": welch_hedges([r["mc_ai"] for r in lab if r["mc_ai"] is not None],
                           [r["mc_ai"] for r in nol if r["mc_ai"] is not None]),
        "ai_mw": mann_whitney([r["mc_ai"] for r in lab], [r["mc_ai"] for r in nol]),
        "minutes": mann_whitney([r["mc_minutes"] for r in lab], [r["mc_minutes"] for r in nol]),
        "specific_A_C": paired(col("A", "specific"), col("C", "specific")),
        "specific_B_C": paired(col("B", "specific"), col("C", "specific")),
    }
    res["explore"] = {"reply": {c: float(np.mean(col(c, "reply"))) if n else float("nan") for c in "ABC"}}
    jrows = judge_rows(valid, data_dir)
    res["jrows"] = jrows
    res["m1_all"] = m1(jrows) if jrows else None
    res["m1_B"] = m1([r for r in jrows if r["cond"] == "B"]) if jrows else None
    pers = [r for r in jrows if r["cond"] in "AB" and r["grounding_count"] is not None]
    res["explore"]["grounding_vs_creepy_rho"] = _spearman([r["grounding_count"] for r in pers], [r["creepy"] for r in pers])
    res["explore"]["creepy_vs_funny_rho_AB"] = _spearman(
        [r["by_cond"][c]["creepy"] for r in valid for c in "AB"], [r["by_cond"][c]["funny"] for r in valid for c in "AB"])
    res["mixed"] = mixed_model(valid) if n >= MIN_N_FOR_MIXED and tests else "not run (n below 30)"
    return res


def mixed_model(valid: list[dict]):
    try:
        import pandas as pd
        import statsmodels.formula.api as smf
    except ImportError:
        return "not run: pandas and statsmodels are not installed (pip install pandas statsmodels)"
    recs = []
    letters_pos = {}
    for r in valid:
        letters = r["order"].split("-")
        for c in "ABC":
            letters_pos[c] = letters.index(c) + 1
            recs.append({"code": r["code"], "cond": c, "arm": r["arm"], "position": letters_pos[c],
                         "effort": r["by_cond"][c]["effort"]})
    df = pd.DataFrame(recs)
    fit = smf.mixedlm("effort ~ C(cond, Treatment('C')) * arm + position", df, groups=df["code"]).fit()
    return str(fit.summary())


def write_summary(res: dict, out: pathlib.Path, fig_names: list[str], fig_note: str) -> None:
    n, fl = res["n"], res["flow"]
    L = ["# Inside Joke study results", ""]
    L += ["## Participant flow", "",
          f"- Assigned: {fl['assigned']}",
          f"- Could not be given 2 passing concepts (excluded before rating): {fl['failed_concepts_before_rating']}",
          f"- Approved and sent a rating page: {fl['approved']}",
          f"- Participants with any ratings: {fl['participants_with_ratings']} ({fl['rating_submissions']} submissions)",
          f"- Unknown code: {fl['unknown_code']}",
          f"- Duplicate submissions dropped (first kept): {fl['duplicate_submissions_dropped']}",
          f"- Excluded, incomplete answers: {fl['incomplete']}",
          f"- Excluded, failed attention check: {fl['attention_check']}",
          f"- Excluded, under {MIN_SECONDS} seconds: {fl['under_90_seconds']}",
          f"- Excluded, same answer to all 30 stimulus items: {fl['same_answer_all_30']}",
          f"- Excluded, helped build or test the tool: {fl['helped_build']}",
          f"- **Valid participants: {n}**", ""]
    if not res["tests"]:
        L += [f"Fewer than {MIN_N_FOR_TESTS} valid participants. As the plan states, this report gives "
              "descriptive statistics and plots only, with no significance tests.", ""]
    L += ["## Descriptives by condition", "",
          "| Measure | A personalized GIF | B personalized text | C generic GIF |", "|---|---|---|---|"]
    for m in ITEM_KEYS + ["effort", "creepy"]:
        cells = " | ".join(f"{_f(res['descriptives'][c][m][0])} ({_f(res['descriptives'][c][m][1])})" for c in "ABC")
        L.append(f"| {m} | {cells} |")
    L += ["", "Mean (SD), 1 to 7 scale.", "",
          f"Composite check: effort items r = {_f(res['composite_r']['effort'])}, creepiness items r = "
          f"{_f(res['composite_r']['creepy'])}. Below {COMPOSITE_R:.2f} means the 2 items are reported separately.", ""]
    hdr = ["| Test | n | Mean 1 | Mean 2 | Difference [95% CI] | dz | t | p (t) | p (Wilcoxon) | p (Holm) |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    h = res["hyp"]
    if res["tests"]:
        L += ["## Confirmatory tests", ""] + hdr
        L.append(_paired_line("H1 effort, A minus C", h["H1"], h["H1"]["p_holm"]))
        L.append(_paired_line("H3 creepiness, A minus C", h["H3"], h["H3"]["p_holm"]))
        L.append(_paired_line("H4 funny, A minus B", h["H4"], h["H4"]["p_holm"]))
        h2 = h["H2"]
        L += ["", "H2, effort gap (A minus C) in the AI label arm minus the no-label arm, Welch t-test:", "",
              f"- Label arm mean gap {_f(h2['mean1'])} (n = {h2['n1']}); no-label arm mean gap {_f(h2['mean2'])} (n = {h2['n2']}).",
              f"- Difference {_f(h2['mean_diff'])} [{_f(h2['ci'][0])}, {_f(h2['ci'][1])}], t({_f(h2['df'], 1)}) = {_f(h2['t'])}, {_peq(h2['p'])}.",
              f"- Hedges g = {_f(h2['g'])} [{_f(h2['g_ci'][0])}, {_f(h2['g_ci'][1])}]. The predicted direction is negative.",
              "- Power for this test is low at this sample size, so it is read as a direction and an interval.", ""]
        for comp, items in res["items_split"].items():
            L += [f"{comp.capitalize()} items correlate below {COMPOSITE_R:.2f}, so each item is tested separately:", ""] + hdr
            for i, r in items.items():
                L.append(_paired_line(f"{i}, A minus C", r))
            L.append("")
        s = res["sensitivity"]
        L += ["## Sensitivity: real-facts participants only", "", f"n = {res['sensitivity_n']}.", ""]
        if s and res["sensitivity_n"] >= 2:
            L += hdr
            for k, lab in (("H1", "H1 effort, A minus C"), ("H3", "H3 creepiness, A minus C"), ("H4", "H4 funny, A minus B")):
                L.append(_paired_line(lab, s[k], s[k]["p_holm"]))
            L += ["", f"H2 Hedges g = {_f(s['H2']['g'])} [{_f(s['H2']['g_ci'][0])}, {_f(s['H2']['g_ci'][1])}].", ""]
        mc = res["manip"]
        L += ["## Manipulation checks", "",
              f"- AI involvement, label arm {_f(mc['ai']['mean1'])} vs no-label arm {_f(mc['ai']['mean2'])}: "
              f"difference {_f(mc['ai']['mean_diff'])} [{_f(mc['ai']['ci'][0])}, {_f(mc['ai']['ci'][1])}], "
              f"Welch {_peq(mc['ai']['p'])}, Mann-Whitney {_peq(mc['ai_mw']['p'])}.",
              f"- Estimated minutes, median label arm {_f(mc['minutes']['median1'], 1)} vs no-label arm "
              f"{_f(mc['minutes']['median2'], 1)}, Mann-Whitney U = {_f(mc['minutes']['u'], 1)}, {_peq(mc['minutes']['p'])}.",
              f"- Personalization (item 5): A minus C {_f(mc['specific_A_C']['mean_diff'])} "
              f"[{_f(mc['specific_A_C']['ci'][0])}, {_f(mc['specific_A_C']['ci'][1])}], {_peq(mc['specific_A_C']['p_t'])}; "
              f"B minus C {_f(mc['specific_B_C']['mean_diff'])} [{_f(mc['specific_B_C']['ci'][0])}, "
              f"{_f(mc['specific_B_C']['ci'][1])}], {_peq(mc['specific_B_C']['p_t'])}.", ""]
        L += ["## Mixed model", "", "```", str(res["mixed"]), "```", ""]
    else:
        L += ["## Differences, descriptive only", "",
              f"- H1 effort, A minus C: {_f(h['H1']['mean_diff'])} (SD {_f(h['H1']['sd_diff'])}, n = {h['H1']['n']})",
              f"- H3 creepiness, A minus C: {_f(h['H3']['mean_diff'])} (SD {_f(h['H3']['sd_diff'])})",
              f"- H4 funny, A minus B: {_f(h['H4']['mean_diff'])} (SD {_f(h['H4']['sd_diff'])})",
              f"- H2 effort gap, label arm {_f(h['H2']['mean1'])} (n = {h['H2']['n1']}) vs no-label arm "
              f"{_f(h['H2']['mean2'])} (n = {h['H2']['n2']})", ""]
    L += ["## Order effects (mean by position)", "", "| Position | funny | effort1 | creepy1 | reply |", "|---|---|---|---|---|"]
    for p in (1, 2, 3):
        o = res["order"][p]
        L.append(f"| {p} | {_f(o['funny'])} | {_f(o['effort1'])} | {_f(o['creepy1'])} | {_f(o['reply'])} |")
    L += ["", "## M1: judge vs human agreement", ""]
    if res["m1_all"]:
        L += ["Spearman rho between the judge score and the mean human rating per stimulus. 95% interval from "
              f"{BOOT} bootstrap resamples of participants. Working threshold: rho of at least .40 with an interval that excludes 0.", "",
              "| Dimension | rho, all stimuli [95% CI] | stimuli | rho, B only [95% CI] | stimuli |", "|---|---|---|---|---|"]
        for d in M1_DIMS:
            a_, b_ = res["m1_all"][d], res["m1_B"][d]
            L.append(f"| {d} | {_f(a_['rho'])} [{_f(a_['ci'][0])}, {_f(a_['ci'][1])}] | {a_['n_stimuli']} | "
                     f"{_f(b_['rho'])} [{_f(b_['ci'][0])}, {_f(b_['ci'][1])}] | {b_['n_stimuli']} |")
        L += ["", "The judge scores text only and never sees the art, so B is the cleanest comparison. "
              "Participants only saw concepts the judge ranked in the top 2 with kind 7 or more, which restricts the range.", ""]
    else:
        L += ["No judge scores were found in the stimulus manifests.", ""]
    ex = res["explore"]
    L += ["## Exploratory (labeled as such)", "",
          f"- Reply intent means: A {_f(ex['reply']['A'])}, B {_f(ex['reply']['B'])}, C {_f(ex['reply']['C'])}.",
          f"- Grounded facts count vs creepiness (A and B stimuli), Spearman rho = {_f(ex['grounding_vs_creepy_rho'])}.",
          f"- Creepiness vs funny within A and B, Spearman rho = {_f(ex['creepy_vs_funny_rho_AB'])}.", ""]
    L += ["## Figures", ""]
    L += [f"- figures/{name}" for name in fig_names] if fig_names else [f"- {fig_note}"]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L) + "\n", encoding="utf-8")


def run(*, ratings: pathlib.Path, data_dir: pathlib.Path, out_dir: pathlib.Path, builders: set[str] | None = None,
        tests: bool | None = None) -> dict:
    assignments = {a["code"]: a for a in read_assignments(data_dir / "assignments.csv")}
    screening = read_log(data_dir / "screening_log.csv")
    valid, flow = apply_exclusions(load_ratings(ratings), assignments, builders=builders or set(), screening=screening)
    res = analyze(valid, flow, data_dir, tests=tests)
    try:
        import matplotlib  # noqa: F401
        figs, note = figures(valid, res["jrows"], out_dir / "figures"), ""
    except ImportError:
        figs, note = [], "matplotlib is not installed, so figures were skipped."
    write_summary(res, out_dir / "summary.md", figs, note)
    res["figures"] = figs
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Inside Joke study analysis.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect", help="build the long ratings CSV from returned answers")
    c.add_argument("--json-dir", type=pathlib.Path, default=None)
    c.add_argument("--wide-csv", type=pathlib.Path, default=None, help="Google Sheets export with answer-key headers")
    c.add_argument("--out", type=pathlib.Path, default=DATA_DIR / "ratings.csv")
    r = sub.add_parser("run", help="exclusions, tests, M1, summary.md and figures")
    r.add_argument("--ratings", type=pathlib.Path, default=DATA_DIR / "ratings.csv")
    r.add_argument("--data-dir", type=pathlib.Path, default=DATA_DIR)
    r.add_argument("--out", type=pathlib.Path, default=RESULTS_DIR)
    r.add_argument("--builders", default="", help="comma-separated codes of people who helped build or test the tool")
    a = ap.parse_args(argv)
    if a.cmd == "collect":
        if not a.json_dir and not a.wide_csv:
            ap.error("give --json-dir and/or --wide-csv")
        rows = collect(a.json_dir, a.wide_csv)
        write_ratings(rows, a.out)
        print(f"wrote {len(rows)} rows ({len(rows) // 3} submissions) to {a.out}")
        return 0
    res = run(ratings=a.ratings, data_dir=a.data_dir, out_dir=a.out,
              builders={x.strip() for x in a.builders.split(",") if x.strip()})
    print(f"valid participants: {res['n']}; summary at {a.out / 'summary.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
