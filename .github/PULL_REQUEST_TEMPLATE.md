## What changed

<!-- 1 to 3 sentences. Link the issue if there is one. -->

## Why

## Type of change

- [ ] Bug fix
- [ ] New feature or format
- [ ] Guardrail change (banned topics, grounding rule, kindness bar, word limits)
- [ ] Model change (any default in `inside_joke/config.py` MODELS)
- [ ] Docs or repo housekeeping

## Checklist

- [ ] `make test` passes locally with no API key set
- [ ] `make lint` passes
- [ ] Tests added or updated for the change
- [ ] `CHANGELOG.md` updated under "Unreleased"
- [ ] No real person, client, or company appears in code, tests, examples, or screenshots
- [ ] No secrets, `.env` contents, or files from `out/` or `docs/private/` are included

## Guardrail or model changes only

See [GOVERNANCE.md](../GOVERNANCE.md).

- [ ] Every new false positive or false negative has a regression test in `tests/test_guardrails.py`
- [ ] Before and after numbers from the fixed example personas are pasted below (pass rate, judge totals, seconds, cost)
- [ ] The judge is still a different model family from the writer
- [ ] Entry added to the guardrail log or version log in `docs/PROCESS_LOG.md`

## Evidence

<!-- Paste test output, GIF links, or manifest numbers. -->
