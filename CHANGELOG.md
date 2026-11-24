# Changelog

All notable changes to this project are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## Unreleased

Nothing yet.

## 0.1.0 - 2026-11-24

First public version, built for Harvard CS 85 (Fall 2026), Module 7 option B.

### Added

- 5 GIF formats: Meme Desk, Future Headline, Three-Panel Day, Collector Card and Reply Reaction (`inside_joke/formats.py`, `inside_joke/render.py`).
- Concept stage with 3 parallel writer calls, 1 per assigned humor mechanism (incongruity, exaggeration, personification, or callback when there is conversation context), deterministic guardrails, and a judge from a different model family (`inside_joke/concept.py`).
- Guardrails: banned-topic word list, grounding citations checked against input field names, first name at most once, word limits, per-format shape checks, and a kindness bar of 7 on the judge's kind score.
- Generic mode for the study's control condition: no personal facts, and any grounding is a rejection.
- Art stage with 3 backends tried in order: OpenRouter image model, SVG drawn by a text model and rasterized with resvg, then an offline placeholder (`inside_joke/art.py`).
- Deterministic renderer and encoder: code draws every letter, 3 motion primitives (`calendar_flip`, `progress_bar`, `stamp`), a 950 KB size budget, and an Outlook-safe 20 ms first frame that shows the finished image (`inside_joke/render.py`).
- Pipeline that runs formats in parallel and writes `manifest.json` with every concept, score, rejection and ledger row (`inside_joke/pipeline.py`).
- CLI (`forge.py`) with a static gallery page, and a local web app (`serve.py`, `web/index.html`) with live progress, a run list and a rating endpoint.
- Optional homepage research (`--research`).
- Cost and latency ledger on every model call.
- Bundled OFL fonts in `fonts/` so output matches on macOS, Linux and CI.
- Pinned dependencies: `requirements.txt` for the pipeline, `requirements-study.txt` adding numpy and scipy for the study toolkit.
- Offline test suite: guardrails, renderer, LLM client, pipeline and web app. No API key or network needed.
- CI on Python 3.12 and 3.13, plus a job that renders all 5 formats offline and uploads the GIFs.
- Repo governance: LICENSE (MIT), CONTRIBUTING, SECURITY, CODE_OF_CONDUCT, GOVERNANCE, issue and pull request templates, CODEOWNERS and Dependabot.
- Docs: `docs/ARCHITECTURE.md`, `docs/PROCESS_LOG.md`, `docs/RESEARCH_PLAN.md`.

### Changed

- One writer call that produced all 3 concepts was replaced by 3 parallel calls, 1 per mechanism. Run 1 took 70 s for 5 formats; with this change and the reasoning budget below, run 3 took 32 s.
- "old" and "fired" were removed from the banned list after a false positive on "OLD" in run 1.
- Art prompts now ask for 1 single scene, after the image model drew a 4-panel grid inside each comic panel.
- Anthropic and Google Gemini models get a separate 1,024-token reasoning budget, because reasoning tokens count against `max_tokens` on OpenRouter.
- `config.openrouter_key()` reads only the `OPENROUTER_API_KEY` environment variable and the repo's `.env`, and raises `ConfigError` instead of exiting.
- Fonts default to the bundled files, with macOS system fonts as a fallback.

### Fixed

- Comic panels came back as grids because the pipeline appended the writer-facing `art_note` ("Three separate square panels") to the image prompt. Each format now has a separate image-only `composition` line, the "Panel:" prefix is now "Scene:", and `art.looks_like_grid` redraws once when it sees a grid. Tuned on real outputs: 6 of 9 known grids caught, 0 false alarms on 25 single-scene images (`tests/test_art_grid.py`).
- Kindness bar: when the judge runs, a concept it leaves unscored now gets a total of -1, the same as a kind score below 7.
- The SVG sanitizer strips every `href` that is not a `#fragment` link, and namespaced `image` and `feImage` elements.
- `serve.py` requires `Content-Type: application/json` on POST and a localhost `Host` header.
- Image calls no longer retry after a timeout or a 500. They retry only on 429, 502, 503 and connection failures.
- Grounding entries must be objects with `fact` and `field`.
- The first-name count is case-insensitive.
- Generic renders say "you" in place of the real name.
- A response cut off by `max_tokens` (`finish_reason` "length") now raises `LLMError` instead of being sent to JSON repair. In run 2 the writer returned only `{"` because 689 of 800 tokens went to reasoning.

### Known issues

- The Future Headline dateline and the Reply Reaction calendar use today's date, so the same input rendered on different days gives different GIFs.
- The ledger reports $0 for Claude Sonnet 5.5 on some OpenRouter accounts, so text cost is understated.
