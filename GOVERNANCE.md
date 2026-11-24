# Governance

Inside Joke writes jokes about real people's jobs. The rules that keep those jokes kind are part of the product, so they are versioned, reviewed and tested like code. This file says who decides, how changes land, and what the guardrail policy is.

## Who decides

| Role | Who | Decides |
|---|---|---|
| Maintainer | Nahrahel Louis ([@nahrahel-harvard](https://github.com/nahrahel-harvard)) | Merges, releases, guardrail policy, model defaults, study protocol |
| Course staff | Dr. Christopher Thorpe and the CS 85 TA | Advisory on scope and on the human-subjects question in [docs/RESEARCH_PLAN.md](docs/RESEARCH_PLAN.md) section 4. Their guidance overrides the maintainer on anything involving study participants. |
| Contributors | Anyone who opens an issue or pull request | Proposals only |

`.github/CODEOWNERS` assigns every path to the maintainer, so every pull request needs the maintainer's review.

## How changes are reviewed

1. Open an issue first for anything bigger than a bug fix, so the idea is discussed before code is written.
2. Open a pull request from a branch. Fill in the template.
3. CI must pass: ruff, the offline unittest suite on Python 3.12 and 3.13, and the offline render job that produces all 5 GIFs.
4. The maintainer reviews. Guardrail and model changes also need the evidence listed below.
5. Squash-merge to `main`. Add the change to `CHANGELOG.md`.

The maintainer may push small fixes (typos, docs, dependency bumps from Dependabot) directly when CI is green, and records them in `CHANGELOG.md`.

## Guardrail policy

This policy is the governed artifact. The code that enforces it lives in `inside_joke/concept.py`, and `tests/test_guardrails.py` pins its behavior. A change to either one is a policy change.

### 1. Banned topics

A concept is rejected when its on-image text or `email_line` contains any of these words, matched as whole words and case-insensitive:

| Area | Words |
|---|---|
| Body and appearance | fat, skinny, bald, ugly, sexy |
| Age | elderly, boomer, boomers |
| Health and life events | pregnant (and other words starting with "pregnan"), death, dead, funeral, cancer, suicide (and other words starting with "suicid"), therapy, diagnosis (and other words starting with "diagnos"), drunk, hungover |
| Family | divorce (and other words starting with "divorc") |
| Employer bad news | layoff, layoffs, laid off, lawsuit, lawsuits, sued |
| Identity and beliefs | religion (and other words starting with "religio"), racism (and other words starting with "racis"), politics (and other words starting with "politic"), democrat, democrats, republican, republicans |

"old" and "fired" were removed on 2026-11-24 after the first real run rejected a good meme for "OLD". "old spreadsheet" and "fired off the forecast" are harmless; `tests/test_guardrails.py` keeps them allowed. Age jokes are still caught by "elderly" and "boomer" and by the kindness bar.

The writer prompt also forbids jokes about the reader's looks, age, gender, race, religion, health, family, politics, or their employer's failures. The word list is the deterministic backstop for that prompt rule.

### 2. Grounding rule

Every personal detail in a concept must appear in its `grounding` list with the exact input field it came from (`title`, `notes`, `conversation`, and so on). Code rejects a concept when:

- `grounding` is empty (the joke is not personalized), or
- a grounding entry cites a field that is absent from the input, or
- it cites `conversation` when no conversation context was given.

Each grounding entry must be an object with `fact` and `field`. The first name may appear at most once across the on-image text, counted case-insensitively. In generic mode the rule flips: any grounding entry is a rejection, because a generic joke must use no personal facts, and renders say "you" in place of the real name.

### 3. Kindness bar

A judge from a different model family than the writer scores each passing concept from 1 to 10 on funny, specific, kind and glance. When the judge runs:

- A concept with a kind score below 7 gets a total of -1 and is ranked out.
- A concept the judge leaves unscored is treated the same way (total -1).
- If every concept is below the bar, the format fails with an error and no GIF is made.

The judge does not run with `--fast`, or when only 1 concept passes the guardrails. If the judge call errors, the first passing concept is used. In those 3 cases no kindness score exists, which is 1 reason human review (section 4) is the final gate.

### 4. Human review before anything reaches a real person

Human review is the final gate. The tool never sends anything. Every GIF lands in `out/` for a person to read first. The rule for anyone using this code:

- A human reads the on-image text, the art, the `email_line` and the alt text of every GIF before it goes to a real person.
- During the CS 85 study, the maintainer reads every stimulus before a participant sees it and logs any withheld or regenerated item in `study_data/screening_log.csv`, which `study/batch.py` writes (gitignored with the rest of `study_data/`).
- Art must never show a real person's likeness. Any GIF made with placeholder art is regenerated before it is shown to a participant.

### 5. Model-change policy

A change to any default in `MODELS` (`inside_joke/config.py`), or to a prompt in `concept.py` or `art.py`, needs:

1. A pull request that names the old and new model or prompt.
2. Before and after runs on both example personas (`examples/dana_brightwater.json`, `examples/marcus_northpeak.json`) with all 5 formats, reporting wall-clock seconds, cost, repair count, guardrail rejections and judge totals from `manifest.json`.
3. The judge stays a different model family from the writer.
4. `finish_reason` handling still holds: a truncated response raises an error and is never repaired into a fragment. `tests/test_llm.py` covers this.
5. An entry in the version log in [docs/PROCESS_LOG.md](docs/PROCESS_LOG.md).

Environment overrides (`IJ_WRITER`, `IJ_JUDGE` and the rest) are for experiments and need no review. Study runs record the models used in each `manifest.json` under `settings.models`.

During the study period, models are frozen once the pilot ends. A mid-study model change is a protocol deviation and goes in the deviations table of the process log.

### 6. Cost cap

- Every model call is written to the ledger with its cost, and every `manifest.json` carries `cost_usd`.
- The spending cap for the whole CS 85 study is $25, from [docs/RESEARCH_PLAN.md](docs/RESEARCH_PLAN.md) section 3.12. If projected spend passes the cap, switch the art backend to SVG and stop adding runs until the maintainer decides.
- Measured cost on real runs was about $0.10 per GIF (about $0.48 for 5 formats), and about $0.067 per GIF with `--fast`. The ledger understates text cost on accounts where Claude Sonnet 5.5 reports $0, so treat ledger totals as a floor.

### 7. Data retention

- Prospect facts, conversation context and outputs stay on the machine that ran the tool, in `out/`. `out/` is gitignored and never committed.
- Study participants' facts are kept on 1 laptop and deleted by Dec 18 2026, as the consent text in the research plan states. Ratings are stored under a random code; the file linking codes to email addresses is separate and deleted after the last reminder.
- Prospect facts are sent to OpenRouter and the model providers it routes to (Anthropic, Google) to make each GIF. Do not enter anything you would not put on a public profile.
- `docs/private/` holds the maintainer's private notes and real run logs. It is gitignored.
- `study_data/` (participant intake, assignments, ratings) and `results/` are gitignored, so participant data cannot be pushed by accident. Publish only group-level results, by copying them into `docs/` on purpose.
- Examples, tests and screenshots in this repo use fictional people and companies only.

## Changing this file

Changes to GOVERNANCE.md follow the same pull request process and need a line in `CHANGELOG.md`.
