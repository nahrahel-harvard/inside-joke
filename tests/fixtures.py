"""Shared offline fixtures: a fictional prospect, fixed on-image text for every
format, and fake concept-stage output. No network, no API key.

Also a tiny CLI used by CI and `make demo` to render all 5 formats with
placeholder art:

    python tests/fixtures.py --out out/demo
"""
from __future__ import annotations

import argparse
import copy
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inside_joke import art, render  # noqa: E402
from inside_joke.formats import FORMATS, ORDER  # noqa: E402

# Fictional person and company.
PROSPECT = {
    "first_name": "Dana",
    "last_name": "Okafor",
    "title": "Director of Supply Chain Planning",
    "company": "Brightwater Beverage Co.",
    "industry": "Beverage manufacturing",
    "notes": "Posted that the weekly S&OP meeting ran 3 hours.",
    "brand_color": "#0f8b8d",
}

CONTEXT = 'Dana replied: "We are in an ERP migration until March. Circle back in Q2?"'

SAMPLE_TEXT = {
    "meme": {"top": "WHEN THE S&OP MEETING HITS HOUR THREE",
             "bottom": "AND THE FORECAST STARTS FORECASTING YOU"},
    "headline": {"publication": "The Pallet Ledger", "kicker": "Planning desk",
                 "headline": "Weekly S&OP meeting ends early, attendees report confusion",
                 "dek": "Witnesses say the agenda was followed in order, a first for the quarter."},
    "comic": {"captions": ["Monday: the forecast looks calm.", "Tuesday: the forecast has opinions.",
                           "Friday: the forecast asks for a raise."],
              "cast": "a cheerful clipboard with round glasses"},
    "card": {"card_title": "The Forecast Whisperer", "card_class": "Supply Chain Tactician",
             "stats": [{"label": "Pallet sense", "value": 94}, {"label": "Meeting stamina", "value": 88},
                       {"label": "Spreadsheet calm", "value": 97}],
             "special_move": {"name": "Demand Sense",
                              "text": "Predicts a stockout two weeks before anyone opens the dashboard."},
             "flavor": "The forecast fears her, and the forecast is right."},
    "reply": {"beat1": "Circle back in Q2, after the ERP migration?",
              "beat2": "Calendar flipped. The sparkling tea can wait too.",
              "prop": "calendar_flip", "prop_value": "APR"},
}


def sample_concept(fmt: str, cid: str = "r1c1") -> dict:
    """A concept shaped like the writer's output, with fixed text."""
    c = {
        "id": cid,
        "mechanism": "exaggeration",
        "joke_target": "the 3-hour S&OP meeting",
        "grounding": [{"fact": "S&OP meeting ran 3 hours", "field": "notes"}],
        "text": copy.deepcopy(SAMPLE_TEXT[fmt]),
        "alt_text": "A cartoon clipboard looking tired at a long meeting.",
        "email_line": "Made you something for the next long planning meeting.",
    }
    if FORMATS[fmt]["panels"] > 1:
        c["art_prompts"] = ["a calm clipboard", "a clipboard with opinions", "a clipboard asking for a raise"]
    else:
        c["art_prompt"] = "a cheerful clipboard in a meeting room"
    return c


def placeholder_arts(fmt: str):
    spec = FORMATS[fmt]
    return [art.placeholder(spec["art_size"], i) for i in range(spec["panels"])]


def render_all(out_dir: pathlib.Path) -> dict[str, dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    results = {}
    for fmt in ORDER:
        t0 = time.time()
        frames = render.render(fmt, placeholder_arts(fmt), SAMPLE_TEXT[fmt], PROSPECT)
        info = render.encode(frames, out_dir / f"{fmt}.gif", out_dir / f"{fmt}.png")
        results[fmt] = {**info, "seconds": round(time.time() - t0, 3)}
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description="Render all 5 formats offline with placeholder art.")
    ap.add_argument("--out", default=str(ROOT / "out" / "demo"))
    a = ap.parse_args()
    out = pathlib.Path(a.out)
    results = render_all(out)
    worst = 0
    for fmt, r in results.items():
        print(f"{fmt:<9} {r['gif_kb']:>4} KB  {r['frames']:>3} frames  {r['seconds']} s")
        worst = max(worst, r["gif_kb"])
    print(f"Wrote {len(results)} GIFs to {out}")
    return 0 if worst < 1024 else 1


if __name__ == "__main__":
    sys.exit(main())
