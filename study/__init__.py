"""Study toolkit for the Inside Joke experiment (docs/RESEARCH_PLAN.md, section 3).

Pipeline of commands, each idempotent and driven by files under study_data/:
  assign -> generic_pool -> batch -> (human screening) -> pages -> analysis collect -> analysis run
See docs/STUDY_RUNBOOK.md."""
from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "study_data"
RESULTS_DIR = ROOT / "results"
STUDY_FORMATS = ("meme", "headline")
CONDITIONS = ("A", "B", "C")
ARMS = ("label", "no_label")
DISCLOSURE_LABEL = "Alex made this with an AI tool in about 20 seconds."
SCENARIO = "Imagine each of these arrived as the first email from Alex, a salesperson you have never met."
