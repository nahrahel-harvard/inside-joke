"""Thin OpenRouter client (stdlib only). Tracks latency + cost per call so the
write-up can report real numbers."""
from __future__ import annotations

import base64
import json
import re
import socket
import time
import urllib.error
import urllib.request

from .config import openrouter_key

URL = "https://openrouter.ai/api/v1/chat/completions"
REASONING_BUDGET = 1024


class LLMError(RuntimeError):
    def __init__(self, msg: str, code: int | None = None):
        super().__init__(msg)
        self.code = code


class Ledger:
    """Collects one row per model call: stage, model, seconds, cost."""

    def __init__(self):
        self.rows: list[dict] = []

    def add(self, **row):
        self.rows.append(row)

    @property
    def cost(self) -> float:
        return round(sum(r.get("cost") or 0 for r in self.rows), 5)


def _post(payload: dict, timeout: int = 120, *, paid_once: bool = False) -> dict:
    """paid_once=True (image calls): never retry after the request may have been
    processed and billed (timeouts, HTTP 500). Retry only when the provider
    clearly did no work (429, 502, 503) or the connection never opened."""
    body = json.dumps(payload).encode()
    retry_codes = (429, 502, 503) if paid_once else (429, 500, 502, 503)
    last = None
    for attempt in range(3):
        req = urllib.request.Request(
            URL,
            data=body,
            headers={
                "Authorization": f"Bearer {openrouter_key()}",
                "Content-Type": "application/json",
                "X-Title": "Inside Joke",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read())
        except urllib.error.HTTPError as e:
            raw = e.read().decode(errors="replace")
            try:
                msg = json.loads(raw).get("error", {}).get("message", raw)
            except Exception:
                msg = raw
            last = LLMError(f"HTTP {e.code}: {msg[:300]}", e.code)
            if e.code in retry_codes and attempt < 2:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise last
        except (urllib.error.URLError, TimeoutError) as e:
            last = LLMError(f"network: {e}")
            never_sent = isinstance(e, urllib.error.URLError) and isinstance(
                getattr(e, "reason", None), (ConnectionRefusedError, socket.gaierror))
            if attempt < 2 and (never_sent or not paid_once):
                time.sleep(1.5 * (attempt + 1))
                continue
            raise last
        if "error" in data:
            err = data["error"]
            raise LLMError(f"{err.get('code')}: {err.get('message')}", err.get("code"))
        return data
    raise last  # pragma: no cover


def chat(model: str, system: str, user: str, *, max_tokens: int = 2000,
         temperature: float = 0.9, ledger: Ledger | None = None, stage: str = "") -> str:
    t0 = time.time()
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "usage": {"include": True},
    }
    if model.startswith(("anthropic/", "google/gemini")):
        # Claude 5.x on OpenRouter makes reasoning mandatory, and reasoning tokens
        # count against max_tokens. Without a separate budget the first real run
        # returned just '{"' (689 of 800 tokens went to reasoning).
        payload["reasoning"] = {"max_tokens": REASONING_BUDGET}
        payload["max_tokens"] = max_tokens + REASONING_BUDGET + 200
    data = _post(payload)
    choice = data["choices"][0]
    text = choice["message"].get("content") or ""
    usage = data.get("usage") or {}
    if ledger is not None:
        ledger.add(stage=stage, model=model, seconds=round(time.time() - t0, 2),
                   cost=usage.get("cost"), tokens_in=usage.get("prompt_tokens"),
                   tokens_out=usage.get("completion_tokens"), finish=choice.get("finish_reason"))
    if choice.get("finish_reason") == "length":
        raise LLMError(f"{model} hit max_tokens ({len(text)} chars of output); output is truncated")
    return text


def parse_json(text: str):
    """Models sometimes wrap JSON in fences or add a sentence. Take the outermost object."""
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON object in model output: {text[:200]}")
    return json.loads(text[start:end + 1])


def chat_json(model: str, system: str, user: str, **kw):
    raw = chat(model, system, user, **kw)
    try:
        return parse_json(raw)
    except (ValueError, json.JSONDecodeError):
        # One repair attempt: ask the same model to return only valid JSON.
        fixed = chat(model, "Return only valid JSON. No prose.",
                     f"Fix this into valid JSON with the same content:\n{raw[:12000]}",
                     max_tokens=kw.get("max_tokens", 2000), temperature=0,
                     ledger=kw.get("ledger"), stage=(kw.get("stage") or "") + ":repair")
        return parse_json(fixed)


def image(model: str, prompt: str, aspect: str = "1:1", *, ledger: Ledger | None = None,
          stage: str = "") -> bytes:
    t0 = time.time()
    data = _post({
        "model": model,
        "modalities": ["image", "text"],
        "image_config": {"aspect_ratio": aspect},
        "messages": [{"role": "user", "content": prompt}],
        "usage": {"include": True},
    }, timeout=90, paid_once=True)
    msg = data["choices"][0]["message"]
    imgs = msg.get("images") or []
    if not imgs:
        raise LLMError(f"{model} returned no image")
    url = imgs[0]["image_url"]["url"]
    if ledger is not None:
        usage = data.get("usage") or {}
        ledger.add(stage=stage, model=model, seconds=round(time.time() - t0, 2),
                   cost=usage.get("cost"), tokens_in=usage.get("prompt_tokens"),
                   tokens_out=usage.get("completion_tokens"))
    return base64.b64decode(url.split(",", 1)[1])
