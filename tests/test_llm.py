"""OpenRouter client with the network call replaced by a fake. No API key needed.

    .venv/bin/python -m unittest tests.test_llm -v
"""
from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent), str(HERE)]

from inside_joke import config, llm  # noqa: E402


def response(content, finish="stop", cost=0.0012, tokens_in=310, tokens_out=95):
    return {"choices": [{"message": {"content": content}, "finish_reason": finish}],
            "usage": {"cost": cost, "prompt_tokens": tokens_in, "completion_tokens": tokens_out}}


class FakePost:
    """Stands in for llm._post: records payloads and returns queued responses."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.payloads = []

    def __call__(self, payload, timeout=120):
        self.payloads.append(payload)
        return self.responses.pop(0)


class ParseJsonTest(unittest.TestCase):
    def test_strips_code_fences(self):
        self.assertEqual(llm.parse_json('```json\n{"a": 1, "b": [2, 3]}\n```'), {"a": 1, "b": [2, 3]})

    def test_strips_prose(self):
        raw = 'Sure! Here is the concept:\n{"top": "HI", "nested": {"x": "y"}}\nHope that helps.'
        self.assertEqual(llm.parse_json(raw), {"top": "HI", "nested": {"x": "y"}})

    def test_no_object_raises(self):
        with self.assertRaises(ValueError):
            llm.parse_json('{"')
        with self.assertRaises(ValueError):
            llm.parse_json("no json here")


class ChatTest(unittest.TestCase):
    def test_reasoning_budget_for_anthropic_and_gemini(self):
        for model in ("anthropic/claude-sonnet-5.5", "google/gemini-3.6-flash"):
            fake = FakePost(response("ok"))
            with mock.patch.object(llm, "_post", fake):
                self.assertEqual(llm.chat(model, "sys", "user", max_tokens=800), "ok")
            p = fake.payloads[0]
            self.assertEqual(p["reasoning"], {"max_tokens": llm.REASONING_BUDGET}, model)
            self.assertEqual(p["max_tokens"], 800 + llm.REASONING_BUDGET + 200, model)

    def test_no_reasoning_budget_for_other_models(self):
        fake = FakePost(response("ok"))
        with mock.patch.object(llm, "_post", fake):
            llm.chat("openai/gpt-x", "sys", "user", max_tokens=800)
        self.assertNotIn("reasoning", fake.payloads[0])
        self.assertEqual(fake.payloads[0]["max_tokens"], 800)

    def test_finish_length_raises(self):
        ledger = llm.Ledger()
        fake = FakePost(response('{"', finish="length"))
        with mock.patch.object(llm, "_post", fake), self.assertRaises(llm.LLMError) as cm:
            llm.chat("anthropic/claude-sonnet-5.5", "sys", "user", ledger=ledger, stage="meme:write")
        self.assertIn("max_tokens", str(cm.exception))
        self.assertEqual(ledger.rows[0]["finish"], "length")

    def test_ledger_records_tokens_and_finish(self):
        ledger = llm.Ledger()
        fake = FakePost(response("a", cost=0.002, tokens_in=100, tokens_out=40),
                        response("b", cost=None, tokens_in=50, tokens_out=10))
        with mock.patch.object(llm, "_post", fake):
            llm.chat("google/gemini-3.6-flash", "s", "u", ledger=ledger, stage="meme:judge")
            llm.chat("anthropic/claude-sonnet-5.5", "s", "u", ledger=ledger, stage="meme:write")
        r = ledger.rows[0]
        self.assertEqual((r["stage"], r["model"]), ("meme:judge", "google/gemini-3.6-flash"))
        self.assertEqual((r["tokens_in"], r["tokens_out"], r["finish"]), (100, 40, "stop"))
        self.assertIn("seconds", r)
        self.assertEqual(ledger.cost, 0.002)  # a None cost counts as 0

    def test_chat_json_repairs_once(self):
        ledger = llm.Ledger()
        fake = FakePost(response("I could not format that."), response('{"fixed": true}'))
        with mock.patch.object(llm, "_post", fake):
            out = llm.chat_json("anthropic/claude-sonnet-5.5", "s", "u", ledger=ledger, stage="meme:write")
        self.assertEqual(out, {"fixed": True})
        self.assertEqual([r["stage"] for r in ledger.rows], ["meme:write", "meme:write:repair"])


class ConfigKeyTest(unittest.TestCase):
    def test_env_var_wins(self):
        with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "  sk-test  "}):
            self.assertEqual(config.openrouter_key(), "sk-test")

    def test_dotenv_then_config_error(self):
        env = {k: v for k, v in os.environ.items() if k != "OPENROUTER_API_KEY"}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(config, "ROOT", pathlib.Path(tmp)):
            with self.assertRaises(config.ConfigError):
                config.openrouter_key()
            (pathlib.Path(tmp) / ".env").write_text('# comment\nOPENROUTER_API_KEY="sk-from-file"\n')
            self.assertEqual(config.openrouter_key(), "sk-from-file")

    def test_config_error_is_runtime_error(self):
        self.assertTrue(issubclass(config.ConfigError, RuntimeError))


if __name__ == "__main__":
    unittest.main()
