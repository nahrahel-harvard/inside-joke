---
name: Guardrail report
about: Report a joke that crossed a line, or a good joke the guardrails blocked
title: "[guardrail] "
labels: guardrail
assignees: ""
---

<!--
Do not paste real names, companies, or private details. Replace them with
placeholders such as [FIRST_NAME] and [COMPANY]. If the output involves a real
person, describe it in words instead of attaching the GIF.
-->

## Kind of report

- [ ] The joke crossed a line and the guardrails let it through (false negative)
- [ ] A harmless joke was blocked (false positive)

## The concept

- Format (meme, headline, comic, card, reply):
- On-image text (with placeholders):
- `email_line`:
- `grounding` entries (field names only):

## Why it crossed the line, or why the block was wrong

<!-- Which part: the topic, the target of the joke, an invented fact, the art, the tone? -->

## Guardrail output

- Rule that fired, if any (from `rejected[].problems` in manifest.json):
- Judge scores (funny, specific, kind, glance):

## Did it reach a person?

- [ ] No, caught during human review
- [ ] Yes (please describe what happened next)

## Suggested fix

<!-- A banned word, a prompt rule, a judge rubric change, or a new deterministic check. -->
