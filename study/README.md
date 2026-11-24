# Study toolkit

Code for the Inside Joke experiment in `docs/RESEARCH_PLAN.md`, section 3. The full procedure, with commands, is in `docs/STUDY_RUNBOOK.md`.

| Module | Job |
|---|---|
| `assign.py` | Seeded assignment: disclosure arm (blocks of 4), format, presentation order, GIF coin flip, generic item. Maps intake fields to prospect keys. |
| `generic_pool.py` | Builds the frozen pool of 6 generic GIFs per format (condition C). Never rebuilds a finished item. |
| `batch.py` | Generates A (GIF) and B (text) per participant from the top 2 concepts, with pinned art. Writes the screening log. Reports spend. |
| `text_only.py` | Renders B as an escaped email-style HTML snippet from Alex. |
| `pages.py` | Builds 1 static rating page per approved participant. |
| `analysis.py` | Collects answers into a long CSV, applies exclusions, runs H1 to H4, manipulation checks and M1, writes `results/`. |

Formats in the study: `meme` and `headline`. Conditions: A personalized GIF, B personalized text, C generic GIF.

Tests run offline: `.venv/bin/python -m unittest tests.test_study -v`.
