# Contributing

Thanks for looking. Inside Joke is a Harvard CS 85 final project with 1 maintainer, so the process is small and written down here and in [GOVERNANCE.md](GOVERNANCE.md).

## Set up

```bash
git clone https://github.com/nahrahel-harvard/inside-joke
cd inside-joke
make setup        # creates .venv and installs pinned dependencies
make test         # offline suite, no API key needed
make demo         # renders all 5 formats with placeholder art into out/demo
```

Python 3.11 or newer. CI runs 3.12 and 3.13. The GIF pipeline depends only on Pillow and resvg-py (`requirements.txt`); everything else is the standard library. The study toolkit's analysis adds numpy, scipy and matplotlib (`requirements-study.txt`), and `make setup` installs both files. Keep it that way unless a pull request explains why a new dependency is worth it.

To call real models, copy `.env.example` to `.env` and set `OPENROUTER_API_KEY`. Tests must never need it.

## Before you open a pull request

1. `make test` passes with no API key set.
2. `make lint` passes (ruff, line length 110).
3. New behavior has a test. Tests use `unittest`, run offline, and fake every model call by patching `llm._post`, `concept.pick` or `art.make_art`.
4. `CHANGELOG.md` has a line under "Unreleased".
5. Fill in the pull request template.

## Rules for examples, fixtures and screenshots

- Use fictional people and companies only. `examples/` and `tests/fixtures.py` show the pattern.
- Never commit output made for a real person, and never commit `out/` or `docs/private/`.
- Art must never depict a real person's likeness.

## Changes that need extra review

These follow the process in [GOVERNANCE.md](GOVERNANCE.md):

- The banned-topic list, the grounding rule, word limits, or the kindness bar in `inside_joke/concept.py`.
- The writer or judge prompts in `inside_joke/concept.py`.
- Any default in `MODELS` in `inside_joke/config.py`.
- Anything that sends new personal data to a model provider.

## Where things live

| You want to change | Edit |
|---|---|
| A format's fields, word limits or art note | `inside_joke/formats.py` |
| How a format looks or moves | `inside_joke/render.py` |
| Writer, judge, guardrails | `inside_joke/concept.py` |
| Art backends and fallback order | `inside_joke/art.py` |
| Model routing, fonts, API key loading | `inside_joke/config.py` |
| The orchestration and manifest | `inside_joke/pipeline.py` |
| CLI | `forge.py` |
| Web app | `serve.py`, `web/index.html` |

[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) explains how the pieces fit.

## Commit messages

Short imperative subject, for example `render: keep stamp inside the frame on 16:9`. Prefix with the module name when it helps.

## Conduct

By taking part you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).
