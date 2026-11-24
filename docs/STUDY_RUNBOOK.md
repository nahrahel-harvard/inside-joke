# Study runbook

Step-by-step commands for running the Inside Joke study, from intake to results. The design is in `docs/RESEARCH_PLAN.md`, section 3. Every command runs from the project folder with the project venv.

```bash
cd ~/context/inside-joke
.venv/bin/pip install -r requirements-study.txt   # once
```

All study files live in `study_data/` (keep it out of git; it holds participant facts). Every command takes `--data-dir` if you want a different folder, for example `study_data/pilot`.

## Timeline

| Day | Step | Command section |
|---|---|---|
| Wed Nov 25 | Pilot with 2 or 3 people in `study_data/pilot`. Send the intake form. | 1 to 6 |
| Thu Nov 26 to Fri Nov 27 | Intake collects on its own. Optional: non-determinism runs (plan 3.11). | |
| Sat Nov 28 | Fix pilot problems. Pick the art backend (`image` or `svg`) and use it for everything after this. Build the generic pool. Freeze prompts and model versions. Build the Google Form. | 3 |
| Sun Nov 29 | Intake reminder. Dry-run the analysis on made-up data (`.venv/bin/python -m unittest tests.test_study`). | |
| Mon Nov 30 | Intake closes at noon. Assign, batch, screen every stimulus, build pages, send links by evening. | 2, 4, 5, 6 |
| Tue Dec 1 | Reminders. | |
| Wed Dec 2 | Ratings close at 9 pm. Collect, apply exclusions, run the analysis. | 7 |

## 1. Intake file

Export the intake Google Form to `study_data/intake.csv` with these column headers (rename them in the sheet before export):

| Column | Meaning |
|---|---|
| `code` | A random participant code you assign, letters, digits, `-` or `_` (for example `K7Q2`). Never a name. |
| `first_name` | First name or nickname |
| `role` | Role or title |
| `field` | Field or industry |
| `goal` | One thing they are working toward this term |
| `annoyance` | One recurring annoyance in that role |
| `tools` | Tools used daily |
| `is_persona` | `yes` if they ticked the persona box, blank otherwise |
| `email` | Optional. Read by nothing in the toolkit. Keep the code-to-email file separate and delete it after the last reminder. |

Keep rows in the order people submitted. Blocked randomization runs in intake order.

How the facts reach the pipeline (fixed for the whole study):

| Pipeline key | Built from |
|---|---|
| `first_name` | `first_name` |
| `title` | `role` |
| `industry` | `field` |
| `company` | `field` (the intake asks for no company, and the pipeline expects one) |
| `notes` | `Working toward: {goal}. Recurring annoyance: {annoyance}. Tools: {tools}.` |

Website research is always off in study mode.

## 2. Assign

Run once, after intake closes and before any stimulus exists. Pick a seed and write it in the process log.

```bash
.venv/bin/python -m study.assign --seed 20261130
```

This writes `study_data/assignments.csv` and `study_data/assignment_meta.json` (seed, intake checksum). The same intake and seed always give the same file. The command refuses to overwrite a different `assignments.csv` unless you pass `--force`; only do that if no stimulus has been generated.

What gets assigned:

- `arm`: `label` or `no_label`, in blocks of 4 (2 of each, shuffled), in intake order.
- `format`: alternates `meme` and `headline` within each arm.
- `order`: 1 of the 6 orders of A, B, C. Orders cycle through a seeded shuffle within each arm and format, so each order appears about equally often per arm and is not tied to 1 format. `pos_A`, `pos_B`, `pos_C` give each condition's item number.
- `gif_rank`: the seeded coin flip. `0` means the judge's top concept becomes the GIF (A) and the 2nd becomes text (B); `1` swaps them.
- `generic_item`: which of the 6 generic GIFs (0 to 5) the participant sees as C.

## 3. Generic pool (condition C)

Build once, after the art backend is chosen. 6 items per format, 12 in total.

```bash
.venv/bin/python -m study.generic_pool --art image     # or --art svg
```

Output: `study_data/generic/<format>/<i>.gif`, `<i>.png`, `<i>.json`. An item that exists is skipped, so rerunning never pays twice. Look at all 12 PNGs. To replace a bad item, delete its 3 files and rerun; only that item is rebuilt. Headline items print "SPECIAL EDITION FOR YOU" because they carry no name.

## 4. Batch generation (conditions A and B)

```bash
.venv/bin/python -m study.batch --art image --limit 3   # try a few first
.venv/bin/python -m study.batch --art image             # then everyone
```

- `--art` must be `image` or `svg`, the same backend as the generic pool. `auto` and `placeholder` are refused. If the image model fails and the art falls back to the placeholder, nothing is saved and the participant is marked `failed_art`; rerun later and only unfinished participants run again.
- For each participant the writer makes 3 concepts, retrying up to 3 rounds until 2 pass the guardrails. The judge scores them. The 2 best with a kind score of 7 or more are kept; `gif_rank` decides which is A.
- Output per participant in `study_data/stimuli/<code>/`: `A.gif`, `A.png`, `B.json`, `manifest.json` (all concepts, rejected concepts with reasons, judge scores, grounding counts, art backend, ledger rows, `cost_usd`).
- B is shown as a plain email from Alex. If the writer's `email_line` mentions an image ("made you a tiny comic"), it is dropped from B, since B has no image, and the screening log says so. A and C show the GIF alone.
- A participant whose concepts could not reach 2 passing after 3 rounds is marked `failed_concepts`. That is an exclusion rule in the plan, so batch does not retry them unless you pass `--retry-failed`.
- `--only K7Q2,M3P9` limits a run to named codes.

## 5. Screening (a human reads every stimulus)

Open `study_data/screening_log.csv` in a spreadsheet. Each new participant has status `pending_review`. For each row, open `stimuli/<code>/A.png` (and the GIF), read `B.json` (`text` and `html`), and look at the generic item they will see. Then set `status` to 1 of:

| Status | Meaning | What happens next |
|---|---|---|
| `approved` | Sent as is | `study.pages` builds their page |
| `regenerate` | Something is off (spelling, likeness, tone) | Next `study.batch` run moves the old files to `_old_<time>/` and makes new ones |
| `withheld` | Do not send | No page; record the reason |

Write the reason in `reason` and copy the decision to the screening table in the process log. Check by eye: names spelled right, no human likeness of the reader, nothing about appearance, age, health, family, religion or politics, no placeholder art.

## 6. Rating pages

```bash
.venv/bin/python -m study.pages                                   # download mode
.venv/bin/python -m study.pages --form-url 'PREFILL_TEMPLATE'     # Google Form mode
```

Only `approved` participants get a page: `study_data/pages/<code>/index.html` plus `item1.gif` and so on. File names never show the condition. The page shows the scenario sentence, Item 1, 2 and 3 in the assigned order, the label "Alex made this with an AI tool in about 20 seconds." under each item in the label arm only, the 10 rating rows per item, the attention row inside Item 2, and the end questions.

Host the `pages` folder anywhere static (for example a private GitHub Pages repo or a shared drive that serves HTML) and send each person the link to their own folder.

Returning answers, 2 ways:

- Download mode (default). The participant presses "Download my answers", which saves `<code>_answers.json`, and sends you that file. Put all files in `study_data/answers/`.
- Google Form mode. Make a Google Form whose questions are short-answer fields titled exactly with the answer keys below. Use "Get pre-filled link", fill each field with its own key in braces (for example `{code}`, `{item1_funny}`), copy the link, and pass it as `--form-url`. The page fills every `{key}` with the participant's answer and opens the form; they press Submit. `{code}` is required. The download button stays on the page as a fallback.

Answer keys: `code`, `started_at`, `submitted_at`, `seconds`, then for item positions 1 to 3 `item{p}_funny`, `item{p}_effort1`, `item{p}_effort2`, `item{p}_thoughtful`, `item{p}_specific`, `item{p}_creepy1`, `item{p}_creepy2`, `item{p}_kind`, `item{p}_glance`, `item{p}_reply`, plus `item2_attention`, then `mc_ai`, `mc_minutes`, `open_text`, `facts_type`. `seconds` is measured by the page from load to submit.

## 7. Collect and analyze

```bash
# download mode
.venv/bin/python -m study.analysis collect --json-dir study_data/answers --out study_data/ratings.csv
# Google Form mode: File > Download > CSV from the response sheet
.venv/bin/python -m study.analysis collect --wide-csv responses.csv --out study_data/ratings.csv

.venv/bin/python -m study.analysis run --ratings study_data/ratings.csv --builders CODE1,CODE2
```

`--builders` lists codes of anyone who helped build or test the tool (an exclusion rule). The run writes `results/summary.md` and `results/figures/*.png`.

What the run does, in the plan's order:

1. Exclusions, each counted in the participant flow: duplicate submissions (first kept, by `submitted_at`), incomplete answers, failed attention check (`item2_attention` is not 2), under 90 seconds, the same answer on all 30 stimulus rows, helped build. Participants marked `failed_concepts` are counted as excluded before rating.
2. Composites: effort = mean of effort1 and effort2; creepiness = mean of creepy1 and creepy2. If a pair correlates below .50, each item is also tested on its own.
3. H1 (effort A minus C), H3 (creepiness A minus C), H4 (funny A minus B): mean difference with 95% CI, dz, paired t, Wilcoxon, Holm across the 3.
4. H2: per-person effort gap (A minus C), label arm vs no-label arm, Welch t, Hedges g with 95% CI.
5. Manipulation checks: AI involvement by arm (Welch and Mann-Whitney), minutes by arm (medians, Mann-Whitney), item 5 A and B vs C.
6. Sensitivity: H1 to H4 again with real-facts participants only (persona if the intake box or the end question says so).
7. Order effects table, exploratory results, and M1: Spearman rho between judge scores (from the manifests) and mean human ratings per stimulus, with a 95% interval from 2,000 bootstrap resamples of participants, for all stimuli and for B alone.
8. Below 16 valid participants, the summary gives descriptives and plots only, with no tests. The mixed model runs only at 30 or more and needs `pandas` and `statsmodels`, which are not in the requirements; install them if you get there.

## Budget: $25 cap

Every model call is logged with its cost in the ledger, and each manifest stores the run total in `cost_usd` with the per-call rows in `ledger`. Failed attempts keep a `manifest_failed_<time>.json`, so their cost still counts.

```bash
.venv/bin/python -m study.batch --spend
```

prints total spend across `stimuli/` and `generic/`. Both `study.batch` and `study.generic_pool` stop before a participant or item would push the total past `--budget` (default 25). The smoke run on Nov 24 cost about $0.07 per generic item and $0.07 per participant with image art. If projected spend passes the cap, switch the whole study to `--art svg` (plan 3.12).

## File formats

| File | Written by | Columns or contents |
|---|---|---|
| `intake.csv` | you | `code, first_name, role, field, goal, annoyance, tools, is_persona, email` |
| `assignments.csv` | `study.assign` | `code, intake_index, seed, block, arm, format, order, pos_A, pos_B, pos_C, gif_rank, generic_item, is_persona` |
| `assignment_meta.json` | `study.assign` | seed, n, intake SHA-256, the 6 orders |
| `generic/<fmt>/<i>.json` | `study.generic_pool` | chosen concept, judge scores, all candidates, rejected concepts, `cost_usd`, `ledger` |
| `stimuli/<code>/manifest.json` | `study.batch` | assignment, prospect, `A` and `B` (concept, rank, judge scores, grounding count), all candidates, rejected, `attempts`, `art_backend`, `cost_usd`, `ledger` |
| `stimuli/<code>/B.json` | `study.batch` | `format, concept_id, text, email_line, email_line_dropped, mechanism, grounding, scores, html` |
| `screening_log.csv` | `study.batch`, then you | `code, status, reason, format, arm, art_backend, a_concept_id, b_concept_id, generic_item, a_text, b_text, cost_usd, updated` |
| `answers/<code>_answers.json` | rating page | the answer keys in section 6 |
| `ratings.csv` | `study.analysis collect` | one row per participant x item position: `code, position, funny, effort1, effort2, thoughtful, specific, creepy1, creepy2, kind, glance, reply, attention, mc_ai, mc_minutes, facts_type, seconds, submitted_at, open_text`. `attention` is filled on position 2 only; participant-level answers repeat on all 3 rows. Conditions come from `assignments.csv`, never from this file. |

## Smoke run record

On Nov 24 a fictional persona (code `SMOKE01`) and 1 generic meme item ran end to end with `--art image` in `study_data/smoke/`. Delete that folder before the real study or keep it as a record; nothing reads it unless you pass `--data-dir study_data/smoke`.
