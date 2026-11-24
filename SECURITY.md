# Security policy

## Supported versions

Only the latest commit on `main` gets fixes. This is a course project with 1 maintainer.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting: open the repository's **Security** tab and choose **Report a vulnerability**. That keeps the report private until a fix ships.

If that option is unavailable, open a regular issue titled "Security contact request" with no technical details, and the maintainer will reply with a private channel.

Please include the affected file, steps to reproduce, and what an attacker could do. Expect a first reply within 7 days.

## What counts

- A way to read files outside `out/` through `serve.py` (path traversal), or to write anywhere except `out/`.
- A way for model output to run code, load a remote resource, or reach the network during rendering (for example through the SVG backend).
- A way to leak `OPENROUTER_API_KEY` into logs, `manifest.json`, the web app, or a GIF.
- Prompt injection through prospect fields or `--research` page text that defeats the guardrails in `inside_joke/concept.py`.

A joke that is unkind, invasive, or factually invented is a guardrail problem. Report it with the [guardrail report template](.github/ISSUE_TEMPLATE/guardrail_report.md).

## How the code limits risk today

- `serve.py` binds to `127.0.0.1` only, caps request bodies at 64 KB and string fields at 4,000 characters, validates every field, and resolves `/out/` paths inside the output folder only. `tests/test_serve.py` covers traversal attempts.
- The SVG backend strips `<script>`, `<foreignObject>`, `<image>`, `<text>` and external `href` values before `resvg` rasterizes the drawing.
- Model output never becomes code. Animation is chosen from 3 named primitives and checked against that list.
- The API key is read from the environment or a local `.env`, which `.gitignore` excludes. CI runs with no key.
- `--research` fetches 1 public homepage with an 8-second timeout and reads at most 600,000 bytes.

## Secrets

Never commit `.env`, `out/`, or `docs/private/`. If a key is committed by mistake, revoke it at openrouter.ai first, then remove it from history.
