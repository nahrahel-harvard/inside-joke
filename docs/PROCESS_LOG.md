# Process log

CS 85, Fall 2026, Module 7 option B. The first entries record the prototype runs on Nov 24 2026. The empty sections at the end follow the template in [RESEARCH_PLAN.md](RESEARCH_PLAN.md) section 9; add 1 entry per work session.

All runs below used fictional personas: Dana (a supply chain director at a fictional beverage company) and Marcus (a VP of Sales at a fictional logistics company).

## Session entries

### Run 1: first end-to-end run

- Date and time: Nov 24 2026, 17:35
- Goal for this session: generate all 5 formats for 1 persona end to end and measure time and cost.
- Tool used: Claude Code.
- What I asked for, in my words: run the pipeline on the Dana example with every format.
- What I got: 5 GIFs in 70 s for $0.48. 1 Sonnet 5.5 call wrote all 3 concepts per format and took 23 to 26 s. Every call needed a JSON repair. The image model drew a 4-panel grid inside each comic panel. The guardrail rejected a good meme because it contained the word "OLD".
- Did it work? Partly.
- How I checked: read the gallery page, the manifest and the ledger rows.
- What I changed next and why: split the writer into 3 parallel calls with 1 assigned humor mechanism each, so the stage takes as long as 1 short call and the 3 concepts must differ. Removed "old" and "fired" from the banned list. Told the image model to draw 1 single scene.
- Time spent:

### Run 2: parallel writers

- Date and time: Nov 24 2026
- Goal for this session: confirm the fan-out made the concept stage faster and cleaner.
- Tool used: Claude Code.
- What I asked for, in my words: rerun all 5 formats with 3 writer calls per format, 1 per mechanism (incongruity, exaggeration, personification, or callback when there is conversation context).
- What I got: 35 s total, but 15 of 33 writer calls needed a JSON repair and the comic failed.
- Did it work? Partly.
- How I checked: inspected 1 raw writer response. It was only `{"`. Claude Sonnet 5.5 on OpenRouter makes reasoning mandatory ("Reasoning is mandatory for this endpoint and cannot be disabled"), and reasoning tokens count against `max_tokens`: 689 of 800 tokens were reasoning. The Gemini 3.6 Flash judge did the same and returned `finish_reason` "length".
- What I changed next and why: gave anthropic/ and google/gemini models a separate 1,024-token reasoning budget, and made `finish_reason` "length" a hard error so a fragment is never repaired into a fake concept.
- Time spent:

### Runs 3 and 4: reasoning budget

- Date and time: Nov 24 2026
- Goal for this session: confirm the reasoning budget removed the repairs, on 2 different personas.
- Tool used: Claude Code.
- What I asked for, in my words: run all 5 formats for Dana, then for Marcus.
- What I got: Dana: 32 s wall clock for all 5 formats in parallel, 0 repairs, 0 guardrail rejections, $0.49. Marcus: 31 s, judge totals 6.25 to 9.15 on the 10-point weighted scale, $0.48. Across all real runs that day: 22 to 32 s per format, 30 to 32 s wall clock for 5 formats, GIFs 113 to 392 KB, about $0.10 per GIF.
- Did it work? Yes.
- How I checked: manifest.json for each run (ledger rows, `rejected`, scores) and the gallery page.
- What I changed next and why: moved to governance, tests and bundled fonts so the repo runs on any machine and in CI without an API key.
- Time spent:

### Comic grids traced to the prompt

- Date and time: Nov 24 2026
- Goal for this session: find out why comic panels still came back as grids after the single-scene style rule.
- Tool used: Claude Code.
- What I got: the pipeline appended each format's writer-facing `art_note` to the image prompt. For the comic that note begins "Three separate square panels", so the image model drew panels inside each panel.
- Did it work? Yes, after 3 changes.
- How I checked: read the final image prompts in the ledger, then tuned a grid detector on real outputs: it caught 6 of 9 known grids and raised 0 false alarms on 25 single-scene images.
- What I changed next and why: a separate image-only `composition` line per format; the "Panel:" prefix renamed to "Scene:"; `art.looks_like_grid` redraws once when it sees a grid. `tests/test_art_grid.py` pins the detector.
- Time spent:

## Prompts that worked

| Date | Stage (writer, judge, art, code) | Prompt or key sentence | What it produced | Why I think it worked |
|---|---|---|---|---|
| Nov 24 | writer | "MECHANISM TO USE: exaggeration: blow one real pain from their facts up to absurd scale" (1 mechanism per call) | 3 concepts per format that differed from each other, in parallel | Each call had 1 job and a short output, so it was faster and the 3 drafts could not converge on 1 idea |
| Nov 24 | art | "One single illustration filling the whole canvas: never a comic grid, multi-panel layout, or storyboard." | 1 scene per comic panel | Named the exact failure from run 1 |
| Nov 24 | code | Separate reasoning budget of 1,024 tokens for anthropic/ and google/gemini models | 0 repairs in run 3 | Reasoning no longer ate the output budget |

## Prompts that failed

| Date | Stage | Prompt or key sentence | What went wrong | Why (what was ambiguous or missing) | Fix |
|---|---|---|---|---|---|
| Nov 24 | writer | 1 call wrote all 3 concepts | 23 to 26 s per call, and every call needed a JSON repair | 1 long output per call; the repairs were not diagnosed until run 2 | 3 parallel calls, 1 mechanism each |
| Nov 24 | art | Comic panel prompts with no single-scene rule | The image model drew a 4-panel grid inside each comic panel | The model read "comic" as "draw a comic strip" | Added the single-illustration sentence to the art style |
| Nov 24 | art | Comic image prompt ended with the writer-facing note "Three separate square panels" | Panels came back as grids | The image model read a layout note meant for the writer | Image-only `composition` line, "Scene:" prefix, grid check with 1 redraw |
| Nov 24 | writer and judge | `max_tokens` 800 with no reasoning budget | Writer returned only `{"`; judge hit `finish_reason` "length" | Reasoning is mandatory on this endpoint and counts against `max_tokens` (689 of 800 tokens) | Separate reasoning budget; hard error on "length" |

When a prompt fails, ask the model why, and paste its answer here.

## Non-determinism observations

| Date | Same input, how many runs | What varied | What stayed the same | What I did about it |
|---|---|---|---|---|
| Nov 24 | Runs 1 to 3, with code changes between runs | Repair count (every call in run 1; 15 of 33 writer calls in run 2; 0 in run 3) and total time (70 s, 35 s, 32 s) | The format specs, the guardrails, and the renderer | Traced the repairs to truncated output and fixed the token budget |

## Guardrail log

| Date | Concept (short) | Rule that fired | Correct rejection or false alarm? | Action |
|---|---|---|---|---|
| Nov 24 | A meme using the word "OLD" about a tool, not a person | banned topic word: OLD | False alarm | Removed "old" and "fired" from the list; added a regression test that "old spreadsheet" and "fired off" pass |

## Version log

| Version | Date | What changed | Why | Evidence it was better |
|---|---|---|---|---|
| v0 | Nov 24 | 1 writer call for 3 concepts | First build | Baseline: 70 s, $0.48, every call repaired |
| v1 | Nov 24 | 3 parallel writer calls, 1 per mechanism; "old" and "fired" unbanned; single-scene art | Speed, variety, a false positive, comic grid | 35 s, but 15 of 33 writer calls repaired and the comic failed |
| v2 | Nov 24 | 1,024-token reasoning budget; hard error on `finish_reason` "length" | Truncated output | 32 s, 0 repairs, 0 rejections (Dana); 31 s (Marcus) |
| v3 | Nov 24 | Image-only `composition` line, "Scene:" prefix, grid check with 1 redraw | Comic panels came back as grids | Detector: 6 of 9 known grids caught, 0 false alarms on 25 single-scene images |
| v0.1.0 | Nov 24 | Bundled fonts, offline tests, CI, governance docs | Portable public repo | Offline test suite passes with no API key; CI renders all 5 formats on Linux |

## Deviations from the plan

| Date | Planned | What I did | Reason |
|---|---|---|---|
| | | | |

## Stimulus screening log (study only)

| Participant code | Stimulus | Sent as is / regenerated / withheld | Reason |
|---|---|---|---|
| | | | |

## Numbers to capture for the write-up

Filled from runs 1 to 4 where known. Replace with study numbers when they exist.

- Median and 90th percentile generation time: (prototype: 22 to 32 s per format; 30 to 32 s wall clock for 5 formats; `--fast` 15.6 to 16.9 s per GIF)
- Mean cost per GIF: (prototype: about $0.10; `--fast` about $0.067; image calls about $0.067 each; Sonnet cost reports as $0, so this is a floor)
- Largest GIF size: (prototype: 392 KB)
- First-attempt guardrail pass rate:
- Runs with no usable concept:
- Art backend used, by count:
- Total spend:

## Template for new entries

Copy this block for each new work session.

### Session entry

- Date and time:
- Goal for this session (1 sentence):
- Tool used (Claude Code, chat, other):
- What I asked for, in my words:
- What I got:
- Did it work? (yes / partly / no)
- How I checked:
- What I changed next and why:
- Time spent:

### Prompts that worked

| Date | Stage (writer, judge, art, code) | Prompt or key sentence | What it produced | Why I think it worked |
|---|---|---|---|---|
| | | | | |

### Prompts that failed

| Date | Stage | Prompt or key sentence | What went wrong | Why (what was ambiguous or missing) | Fix |
|---|---|---|---|---|---|
| | | | | | |

### Non-determinism observations

| Date | Same input, how many runs | What varied | What stayed the same | What I did about it |
|---|---|---|---|---|
| | | | | |

### Guardrail log

| Date | Concept (short) | Rule that fired | Correct rejection or false alarm? | Action |
|---|---|---|---|---|
| | | | | |

### Stimulus screening log (study only)

| Participant code | Stimulus | Sent as is / regenerated / withheld | Reason |
|---|---|---|---|
| | | | |

### Version log

| Version | Date | What changed | Why | Evidence it was better |
|---|---|---|---|---|
| | | | | |

### Deviations from the plan

| Date | Planned | What I did | Reason |
|---|---|---|---|
| | | | |
