"""Seeded assignment of every participant to arm, format, presentation order,
GIF concept rank and generic item (plan section 3.6). Run once, before any
stimulus is generated:

    .venv/bin/python -m study.assign --intake study_data/intake.csv --seed 20261130

Same intake + same seed always gives a byte-identical assignments.csv.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import itertools
import json
import pathlib
import random
import secrets
import sys

from . import ARMS, DATA_DIR, STUDY_FORMATS

INTAKE_COLUMNS = ["code", "first_name", "role", "field", "goal", "annoyance", "tools", "is_persona"]
ORDERS = ["-".join(p) for p in itertools.permutations("ABC")]  # the 6 presentation orders
GENERIC_POOL_SIZE = 6
ASSIGN_COLUMNS = ["code", "intake_index", "seed", "block", "arm", "format", "order",
                  "pos_A", "pos_B", "pos_C", "gif_rank", "generic_item", "is_persona"]
TRUTHY = {"1", "true", "yes", "y", "x", "checked", "persona"}


def truthy(v) -> bool:
    return str(v or "").strip().lower() in TRUTHY


def read_intake(path: pathlib.Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit(f"{path}: no rows")
    missing = [c for c in INTAKE_COLUMNS if c not in rows[0]]
    if missing:
        raise SystemExit(f"{path}: missing columns {missing}")
    seen = set()
    clean = []
    for i, r in enumerate(rows):
        r = {k: (v or "").strip() for k, v in r.items() if k}
        code = r["code"]
        if not code or not code.replace("-", "").replace("_", "").isalnum():
            raise SystemExit(f"{path}: row {i + 2} has a bad code {code!r} (letters, digits, - and _ only)")
        if code in seen:
            raise SystemExit(f"{path}: duplicate code {code}")
        seen.add(code)
        for k in ("first_name", "role", "field"):
            if not r.get(k):
                raise SystemExit(f"{path}: row {i + 2} ({code}) is missing {k}")
        clean.append(r)
    return clean


def intake_to_prospect(row: dict) -> dict:
    """Map the 6 intake facts onto the pipeline's prospect keys. Email is never copied.
    The intake has no company question, so company falls back to the field."""
    notes = (f"Working toward: {row.get('goal', '').strip()}. "
             f"Recurring annoyance: {row.get('annoyance', '').strip()}. "
             f"Tools: {row.get('tools', '').strip()}.")
    field = row.get("field", "").strip()
    return {
        "first_name": row.get("first_name", "").strip(),
        "title": row.get("role", "").strip(),
        "company": (row.get("company") or "").strip() or field,
        "industry": field,
        "notes": notes,
    }


def assign(rows: list[dict], seed: int) -> list[dict]:
    rng = random.Random(seed)
    n = len(rows)
    # 1. Disclosure arm: blocks of 4 in intake order, 2 per arm in each block.
    arms: list[str] = []
    blocks: list[int] = []
    b = 0
    while len(arms) < n:
        block = [ARMS[0], ARMS[0], ARMS[1], ARMS[1]]
        rng.shuffle(block)
        arms.extend(block)
        blocks.extend([b + 1] * 4)
        b += 1
    arms, blocks = arms[:n], blocks[:n]
    # 2. Format alternates within arm, starting format drawn per arm.
    start = {a: rng.randrange(2) for a in ARMS}
    # 3. Orders cycle through a seeded shuffle of the 6 permutations, separately in
    #    each arm x format cell, so order is balanced within arm and not tied to format.
    cycles = {}
    for a in ARMS:
        for f in STUDY_FORMATS:
            perm = list(ORDERS)
            rng.shuffle(perm)
            cycles[(a, f)] = perm
    arm_count = {a: 0 for a in ARMS}
    cell_count = {k: 0 for k in cycles}
    out = []
    for i, (row, arm, blk) in enumerate(zip(rows, arms, blocks)):
        fmt = STUDY_FORMATS[(start[arm] + arm_count[arm]) % 2]
        arm_count[arm] += 1
        order = cycles[(arm, fmt)][cell_count[(arm, fmt)] % 6]
        cell_count[(arm, fmt)] += 1
        letters = order.split("-")
        out.append({
            "code": row["code"], "intake_index": i + 1, "seed": seed, "block": blk, "arm": arm,
            "format": fmt, "order": order,
            "pos_A": letters.index("A") + 1, "pos_B": letters.index("B") + 1, "pos_C": letters.index("C") + 1,
            "gif_rank": rng.randrange(2),          # 0: top-ranked concept becomes the GIF (A)
            "generic_item": rng.randrange(GENERIC_POOL_SIZE),
            "is_persona": "1" if truthy(row.get("is_persona")) else "0",
        })
    return out


def to_csv(assignments: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=ASSIGN_COLUMNS, lineterminator="\n")
    w.writeheader()
    w.writerows(assignments)
    return buf.getvalue()


def read_assignments(path: pathlib.Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k in ("intake_index", "seed", "block", "pos_A", "pos_B", "pos_C", "gif_rank", "generic_item"):
            r[k] = int(r[k])
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Seeded study assignment (plan 3.6).")
    ap.add_argument("--intake", type=pathlib.Path, default=None, help="intake CSV (default <data-dir>/intake.csv)")
    ap.add_argument("--data-dir", type=pathlib.Path, default=DATA_DIR)
    ap.add_argument("--seed", type=int, default=None, help="record this; a new random seed is drawn if omitted")
    ap.add_argument("--force", action="store_true", help="overwrite an existing, different assignments.csv")
    a = ap.parse_args(argv)
    intake = a.intake or a.data_dir / "intake.csv"
    rows = read_intake(intake)
    seed = a.seed if a.seed is not None else secrets.randbelow(10 ** 9)
    text = to_csv(assign(rows, seed))
    a.data_dir.mkdir(parents=True, exist_ok=True)
    out = a.data_dir / "assignments.csv"
    if out.exists() and out.read_text(encoding="utf-8") != text and not a.force:
        print(f"{out} already exists and differs. Assignments are fixed before stimuli are made; "
              "pass --force only if no stimulus has been generated yet.", file=sys.stderr)
        return 2
    out.write_text(text, encoding="utf-8")
    meta = {"seed": seed, "n": len(rows), "intake_file": str(intake),
            "intake_sha256": hashlib.sha256(intake.read_bytes()).hexdigest(),
            "orders": ORDERS, "formats": list(STUDY_FORMATS), "generic_pool_size": GENERIC_POOL_SIZE}
    (a.data_dir / "assignment_meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    counts = {}
    for r in read_assignments(out):
        counts[(r["arm"], r["format"])] = counts.get((r["arm"], r["format"]), 0) + 1
    print(f"seed {seed}: wrote {len(rows)} assignments to {out}")
    for k in sorted(counts):
        print(f"  {k[0]:9s} {k[1]:9s} {counts[k]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
