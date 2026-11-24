"""pipeline.run end to end with the two model stages faked. Rendering and encoding
are real. No network, no API key.

    .venv/bin/python -m unittest tests.test_pipeline_offline -v
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import threading
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent), str(HERE)]

from fixtures import CONTEXT, PROSPECT, sample_concept  # noqa: E402

from inside_joke import art, concept, pipeline  # noqa: E402
from inside_joke.formats import ORDER  # noqa: E402

MANIFEST_KEYS = {"slug", "out_dir", "created", "prospect", "context", "settings", "total_seconds",
                 "cost_usd", "results", "ledger"}
OK_KEYS = {"ok", "error", "gif", "png", "gif_kb", "seconds", "art_backend", "concept", "scores",
           "ranked_ids", "candidates", "rejected", "email_line", "alt_text"}


class Fakes:
    def __init__(self, fail: set[str] | None = None):
        self.fail = fail or set()
        self.facts_seen = []
        self.art_calls = []
        self.lock = threading.Lock()

    def pick(self, facts, fmt, context, *, fast, ledger, generic=False, min_passing=1):
        with self.lock:
            self.facts_seen.append(dict(facts))
        if fmt in self.fail:
            raise RuntimeError(f"{fmt}: every concept failed guardrails")
        ledger.add(stage=f"{fmt}:write:fake", model="fake/writer", seconds=0, cost=0.01,
                   tokens_in=1, tokens_out=1, finish="stop")
        a, b = sample_concept(fmt, "r1c1"), sample_concept(fmt, "r1c2")
        scores = {"r1c1": {"id": "r1c1", "funny": 8, "specific": 8, "kind": 9, "glance": 8, "total": 8.15},
                  "r1c2": {"id": "r1c2", "funny": 6, "specific": 6, "kind": 9, "glance": 7, "total": 6.5}}
        return {"chosen": a, "ranked": [a, b], "candidates": [a, b], "rejected": [], "scores": scores}

    def make_art(self, prompts, size, aspect, mode, ledger, stage):
        with self.lock:
            self.art_calls.append((stage, list(prompts), mode))
        return [art.placeholder(size, i) for i in range(len(prompts))], "placeholder"


class PipelineOfflineTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.out = pathlib.Path(self._tmp.name) / "run"

    def tearDown(self):
        self._tmp.cleanup()

    def run_pipeline(self, formats, fakes=None, **kw):
        fakes = fakes or Fakes()
        events = []
        with mock.patch.object(concept, "pick", fakes.pick), \
                mock.patch.object(art, "make_art", fakes.make_art):
            m = pipeline.run(PROSPECT, formats, out_dir=self.out, on_event=events.append, **kw)
        return m, fakes, events

    def test_manifest_shape_all_formats(self):
        m, fakes, events = self.run_pipeline(ORDER, context=CONTEXT, art="placeholder")
        self.assertEqual(set(m), MANIFEST_KEYS)
        self.assertEqual(m["slug"], "run")
        self.assertEqual(m["context"], CONTEXT)
        self.assertEqual(set(m["settings"]), {"art", "fast", "research", "generic", "models"})
        self.assertEqual(m["settings"]["art"], "placeholder")
        self.assertIsInstance(m["total_seconds"], float)
        self.assertAlmostEqual(m["cost_usd"], 0.05)
        self.assertEqual(len(m["ledger"]), 5)
        self.assertEqual(list(m["results"]), ORDER)
        for fmt, r in m["results"].items():
            self.assertTrue(OK_KEYS <= set(r), (fmt, OK_KEYS - set(r)))
            self.assertTrue(r["ok"], (fmt, r["error"]))
            self.assertIsNone(r["error"])
            self.assertEqual((r["gif"], r["png"]), (f"{fmt}.gif", f"{fmt}.png"))
            self.assertTrue((self.out / r["gif"]).exists())
            self.assertLess(r["gif_kb"], 1024)
            self.assertEqual(r["art_backend"], "placeholder")
            self.assertEqual(r["concept"]["id"], "r1c1")
            self.assertEqual(r["ranked_ids"], ["r1c1", "r1c2"])
            self.assertEqual(len(r["candidates"]), 2)
            self.assertEqual(r["rejected"], [])
            self.assertTrue(r["email_line"] and r["alt_text"])
        self.assertIn(("meme", "done"), {(e["format"], e["stage"]) for e in events})
        comic = next(c for c in fakes.art_calls if c[0] == "comic")
        self.assertEqual(len(comic[1]), 3)
        self.assertTrue(all(p.startswith("Recurring character:") for p in comic[1]))

    def test_manifest_json_written(self):
        m, _, _ = self.run_pipeline(["meme"])
        on_disk = json.loads((self.out / "manifest.json").read_text())
        self.assertEqual(set(on_disk), MANIFEST_KEYS)
        self.assertEqual(on_disk["results"]["meme"]["gif_kb"], m["results"]["meme"]["gif_kb"])
        self.assertEqual(on_disk["prospect"]["first_name"], "Dana")

    def test_reply_without_context_is_skipped(self):
        m, fakes, _ = self.run_pipeline(["reply"])
        r = m["results"]["reply"]
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], "needs conversation context")
        self.assertEqual(fakes.facts_seen, [])

    def test_generic_allows_reply_without_context(self):
        m, _, _ = self.run_pipeline(["reply"], generic=True)
        self.assertTrue(m["results"]["reply"]["ok"], m["results"]["reply"]["error"])
        self.assertTrue(m["settings"]["generic"])

    def test_brand_color_never_reaches_concept_stage(self):
        m, fakes, _ = self.run_pipeline(["meme", "card"])
        self.assertEqual(len(fakes.facts_seen), 2)
        for facts in fakes.facts_seen:
            self.assertNotIn("brand_color", facts)
            self.assertEqual(facts["first_name"], "Dana")
        self.assertEqual(m["prospect"]["brand_color"], "#0f8b8d")  # still used for styling

    def test_one_format_failing_does_not_sink_the_rest(self):
        m, _, events = self.run_pipeline(["meme", "headline"], fakes=Fakes(fail={"headline"}))
        self.assertTrue(m["results"]["meme"]["ok"])
        h = m["results"]["headline"]
        self.assertFalse(h["ok"])
        self.assertTrue(h["error"].startswith("RuntimeError:"))
        self.assertIn(("headline", "error"), {(e["format"], e["stage"]) for e in events})

    def test_unknown_formats_are_dropped_and_order_is_canonical(self):
        m, _, _ = self.run_pipeline(["card", "sonnet", "meme"])
        self.assertEqual(list(m["results"]), ["meme", "card"])


if __name__ == "__main__":
    unittest.main()
