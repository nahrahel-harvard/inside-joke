"""Concept stage: write 3 candidates, filter them with deterministic guardrails,
then have a different model family judge them. Generative output is not
deterministic, so we generate several and select (best-of-N) instead of trusting
one draw."""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor

from . import llm
from .config import MODELS
from .formats import FORMATS

WRITER_SYSTEM = """You write tiny, warm, specific comedy for B2B outreach. The reader is a busy professional receiving a personalized GIF from someone they have not met. Success: they smile within 3 seconds and think "this person looked at what I actually do."

Rules:
1. The joke's target is a shared enemy of the reader's job: a process, tool, meeting, metric, season, or industry habit. Never the reader themselves, their looks, age, gender, race, religion, health, family, politics, or their employer's failures, layoffs, lawsuits, or bad news.
2. Personalize only from the facts provided. List every specific detail you use in `grounding` with the exact input field it came from. Never invent achievements, funding, numbers, news, or quotes.
3. No product pitch inside the image. The image is a gift.
4. Obey every word limit exactly. Short wins.
5. Use the reader's first name at most once across on-image text, spelled exactly as given.
6. Mechanisms you may use: incongruity, exaggeration of a real job pain, callback to their own words, an object with feelings, understatement.
7. Original scenes only: no copyrighted characters, famous meme templates, celebrities, or real logos.
8. Art prompts describe an original illustrated scene with generic stylized characters or anthropomorphic objects. Never depict the real reader. No words, letters, or numbers in the art.
9. Make the 3 concepts genuinely different: different mechanism and different detail from the input."""

JUDGE_SYSTEM = """You are a strict comedy editor and a brand-safety reviewer for B2B outreach. Score each concept 1-10:
- funny: would a busy professional actually smile?
- specific: would this only make sense for this exact person? Generic = low.
- kind: is the reader in on the joke, never the butt of it? Anything that could embarrass, offend, or feel invasive scores low.
- glance: is it understood in 3 seconds without explanation?
Penalize anything that sounds like a sales pitch, a cliché, or invented facts not present in the input. Return JSON only."""


def _prospect_block(prospect: dict, context: str | None) -> str:
    facts = {k: v for k, v in prospect.items() if v not in (None, "", [], {})}
    out = "PROSPECT FACTS (cite these field names in grounding):\n" + json.dumps(facts, indent=2)
    if context:
        out += "\n\nCONVERSATION CONTEXT (field name: conversation):\n" + context.strip()
    return out


MECHANISMS = {
    "incongruity": "incongruity: set up the expected version of their day, then swap in a surprising but true-feeling outcome",
    "exaggeration": "exaggeration: blow one real pain from their facts up to absurd scale",
    "personification": "personification: a tool, meeting, or metric from their job has feelings and opinions",
    "callback": "callback: build the joke on their own words from the conversation context",
    "understatement": "understatement: describe a big job pain in a calm, tiny way",
}

GENERIC_BLOCK = """GENERIC MODE: write for any office worker. Use no name, no company, no industry, and no personal facts. The joke is about office life in general. `grounding` must be an empty list."""


def _mechanisms(context: str | None, generic: bool) -> list[str]:
    if generic:
        return ["incongruity", "exaggeration", "personification"]
    return ["callback", "incongruity", "personification"] if context else ["incongruity", "exaggeration", "personification"]


def _write_one(prospect: dict, fmt: str, context: str | None, mechanism: str, cid: str, *,
               model: str, generic: bool, ledger: llm.Ledger) -> dict | None:
    spec = FORMATS[fmt]
    fields = "\n".join(f'    "{k}": {v}' for k, v in spec["fields"].items())
    art_shape = ('"art_prompts": [3 strings, one per panel, each max 50 words]' if spec["panels"] > 1
                 else '"art_prompt": "one scene, max 60 words"')
    facts = GENERIC_BLOCK if generic else _prospect_block(prospect, context)
    user = f"""{facts}

FORMAT: {spec['name']}. {spec['pitch']}
ART NOTE: {spec['art_note']}
MECHANISM TO USE: {MECHANISMS[mechanism]}

Return ONE compact JSON object, no prose, no code fences:
{{
  "mechanism": "{mechanism}",
  "joke_target": "the shared enemy being teased, max 8 words",
  "grounding": [{{"fact": "detail used", "field": "exact input field name"}}],
  "text": {{
{fields}
  }},
  {art_shape},
  "alt_text": "one sentence describing the finished image",
  "email_line": "one casual sentence to send alongside the image, max 20 words, no pitch"
}}"""
    try:
        c = llm.chat_json(model, WRITER_SYSTEM, user, max_tokens=1600, temperature=1.0,
                          ledger=ledger, stage=f"{fmt}:write:{mechanism}")
    except Exception as e:
        ledger.add(stage=f"{fmt}:write:{mechanism}:fail", model=model, seconds=0, cost=0, error=str(e)[:200])
        return None
    if isinstance(c, dict) and "concepts" in c and isinstance(c["concepts"], list) and c["concepts"]:
        c = c["concepts"][0]
    if not isinstance(c, dict):
        return None
    c["id"] = cid
    c.setdefault("mechanism", mechanism)
    return c


def write_concepts(prospect: dict, fmt: str, context: str | None, *, fast: bool,
                   ledger: llm.Ledger, generic: bool = False, round_no: int = 1) -> list[dict]:
    """Fan out: one writer call per humor mechanism, in parallel. Each call is short
    (about 600 output tokens), so the stage takes as long as the slowest single call,
    and assigning mechanisms forces the 3 candidates to differ."""
    model = MODELS["writer_fast"] if fast else MODELS["writer"]
    mechs = _mechanisms(context, generic)
    with ThreadPoolExecutor(max_workers=len(mechs)) as ex:
        futs = [ex.submit(_write_one, prospect, fmt, context, m, f"r{round_no}c{i + 1}",
                          model=model, generic=generic, ledger=ledger) for i, m in enumerate(mechs)]
        return [c for c in (f.result() for f in futs) if c]


# ---------- deterministic guardrails ----------

# Words are matched whole. "old" and "fired" were removed after the first real
# run: "old spreadsheet" and "fired off the forecast" are harmless and the list
# rejected a good meme for "OLD". Age jokes are still caught by "elderly"/"boomer"
# and by the judge's kind score.
BANNED = re.compile(
    r"\b(fat|skinny|elderly|boomers?|bald|ugly|pregnan\w*|death|dead|funeral|cancer|layoffs?|laid off|"
    r"lawsuits?|sued|divorc\w*|religio\w*|racis\w*|politic\w*|democrats?|republicans?|"
    r"sexy|drunk|hungover|suicid\w*|therapy|diagnos\w*)\b",
    re.I,
)


def _all_text(c: dict) -> str:
    return json.dumps(c.get("text", {}), ensure_ascii=False) + " " + str(c.get("email_line", ""))


def _words(v) -> int:
    return len(str(v).split())


def check(c: dict, prospect: dict, fmt: str, context: str | None, generic: bool = False) -> list[str]:
    """Return a list of problems. Empty list = concept passes."""
    problems = []
    if generic:
        prospect, context = {}, None
    spec = FORMATS[fmt]
    text = c.get("text") or {}
    allowed = {k for k, v in prospect.items() if v not in (None, "", [], {})}
    if context:
        allowed.add("conversation")
    for f in spec["fields"]:
        if f not in text or text[f] in (None, "", []):
            problems.append(f"missing field {f}")
    for f, lim in spec["limits"].items():
        v = text.get(f)
        items = v if isinstance(v, list) else [v]
        for item in items:
            if item and _words(item) > lim * 1.3:
                problems.append(f"{f} too long ({_words(item)} > {lim})")
    if fmt == "comic":
        if len(text.get("captions") or []) != 3 or len(c.get("art_prompts") or []) != 3:
            problems.append("comic needs exactly 3 captions and 3 art_prompts")
    if fmt == "card":
        stats = text.get("stats") or []
        if len(stats) != 3 or not all(isinstance(s, dict) and "label" in s for s in stats):
            problems.append("card needs 3 stats")
    if fmt == "reply" and text.get("prop") not in ("calendar_flip", "progress_bar", "stamp"):
        problems.append("reply prop must be calendar_flip|progress_bar|stamp")
    m = BANNED.search(_all_text(c))
    if m:
        problems.append(f"banned topic word: {m.group(0)}")
    grounding = c.get("grounding") or []
    if generic:
        if grounding:
            problems.append("generic concept must not cite personal facts")
        return problems
    if not grounding:
        problems.append("no grounding: concept is not personalized")
    for g in grounding:
        if not isinstance(g, dict):
            problems.append(f"grounding entry must be an object with a field name, got {str(g)[:40]!r}")
        elif g.get("field") not in allowed:
            problems.append(f"grounding cites unknown field {g.get('field')!r}")
    first = (prospect.get("first_name") or "").strip()
    if first:
        uses = len(re.findall(rf"\b{re.escape(first)}\b", json.dumps(text, ensure_ascii=False), re.I))
        if uses > 1:
            problems.append(f"first name used {uses} times")
    return problems


def judge(prospect: dict, fmt: str, context: str | None, concepts: list[dict], *,
          ledger: llm.Ledger) -> dict:
    slim = [{"id": c["id"], "mechanism": c.get("mechanism"), "text": c.get("text"),
             "grounding": c.get("grounding")} for c in concepts]
    user = f"""{_prospect_block(prospect, context)}

FORMAT: {FORMATS[fmt]['name']}
CONCEPTS:
{json.dumps(slim, indent=2, ensure_ascii=False)}

Return JSON: {{"scores": [{{"id": "...", "funny": n, "specific": n, "kind": n, "glance": n, "note": "max 15 words"}}]}}"""
    return llm.chat_json(MODELS["judge"], JUDGE_SYSTEM, user, max_tokens=2000, temperature=0,
                         ledger=ledger, stage=f"{fmt}:judge")


WEIGHTS = {"funny": 0.35, "specific": 0.30, "glance": 0.20, "kind": 0.15}


def pick(prospect: dict, fmt: str, context: str | None, *, fast: bool, ledger: llm.Ledger,
         generic: bool = False, min_passing: int = 1) -> dict:
    """Full concept stage. Returns {chosen, ranked, candidates, rejected, scores}.
    min_passing=2 is for the study, which needs 2 different personalized jokes."""
    rejected = []
    passing = []
    for attempt in range(3 if min_passing > 1 else 2):
        cands = write_concepts(prospect, fmt, context, fast=fast, ledger=ledger, generic=generic,
                               round_no=attempt + 1)
        for c in cands:
            probs = check(c, prospect, fmt, context, generic=generic)
            (rejected if probs else passing).append({**c, "problems": probs} if probs else c)
        if len(passing) >= min_passing:
            break
    if not passing:
        raise RuntimeError(f"{fmt}: every concept failed guardrails: {[r['problems'] for r in rejected]}")
    scores = {}
    if not fast and len(passing) > 1:
        try:
            res = judge(prospect, fmt, context, passing, ledger=ledger)
            for s in res.get("scores", []):
                total = sum(float(s.get(k, 0)) * w for k, w in WEIGHTS.items())
                if float(s.get("kind", 0)) < 7:
                    total = -1  # a concept the judge thinks could sting never ships
                scores[s.get("id")] = {**s, "total": round(total, 2)}
        except Exception as e:  # judge is advisory; fall back to the first passing concept
            scores = {"_error": str(e)}
    judged = bool(scores) and "_error" not in scores
    # When the judge ran, a concept it did not score is treated as failing the
    # kindness bar (total -1). Before this, a missing id defaulted to 0 and beat
    # concepts the judge had scored below 7 on kind.
    default = -1 if judged else 0
    ranked = sorted(passing, key=lambda c: (scores.get(c["id"]) or {}).get("total", default), reverse=True)
    if judged and all((scores.get(c["id"]) or {}).get("total", -1) < 0 for c in ranked):
        raise RuntimeError(f"{fmt}: judge scored every concept below the kindness bar")
    return {"chosen": ranked[0], "ranked": ranked, "candidates": passing, "rejected": rejected, "scores": scores}
