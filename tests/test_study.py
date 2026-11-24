"""Tests for the study toolkit. No network: the concept and art stages are faked.
Run:
    .venv/bin/python -m unittest tests.test_study -v
"""
from __future__ import annotations

import csv
import io
import json
import pathlib
import random
import sys
import tempfile
import unittest
from collections import Counter
from contextlib import redirect_stderr
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

from study import DISCLOSURE_LABEL, SCENARIO, analysis, assign, batch, pages, text_only  # noqa: E402

INTAKE_HEADER = ["code", "first_name", "role", "field", "goal", "annoyance", "tools", "is_persona", "email"]


def write_intake(path: pathlib.Path, n: int) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(INTAKE_HEADER)
        for i in range(n):
            w.writerow([f"P{i:03d}", f"Name{i}", "Analyst", "Economics", "finish thesis", "slow Wi-Fi",
                        "Excel, Slack", "yes" if i % 5 == 0 else "", f"p{i}@example.com"])


def fake_concept(cid, text, total=8.0):
    return {"id": cid, "mechanism": "incongruity", "joke_target": "slow Wi-Fi",
            "grounding": [{"fact": "slow Wi-Fi", "field": "notes"}], "text": text,
            "art_prompt": "a sad router", "alt_text": "a router", "email_line": "Thought of your Wi-Fi."}


def fake_pick_factory(fmt):
    text = ({"top": "WHEN THE WI-FI", "bottom": "takes a coffee break too"} if fmt == "meme" else
            {"publication": "Campus Ledger", "kicker": "Breaking", "headline": "Thesis done early", "dek": "Wi-Fi stunned."})
    c1, c2, c3 = fake_concept("r1c1", text), fake_concept("r1c2", text), fake_concept("r1c3", text)

    def pick(facts, f, context, *, fast, ledger, generic=False, min_passing=1):
        ledger.add(stage="write", model="fake", seconds=0, cost=0.01)
        scores = {"r1c1": {"funny": 8, "specific": 8, "kind": 9, "glance": 8, "total": 8.1},
                  "r1c2": {"funny": 6, "specific": 6, "kind": 9, "glance": 7, "total": 6.5},
                  "r1c3": {"funny": 5, "specific": 5, "kind": 5, "glance": 5, "total": -1}}
        return {"chosen": c1, "ranked": [c1, c2, c3], "candidates": [c1, c2, c3], "rejected": [], "scores": scores}
    return pick


def fake_art(backend):
    def make_art(prompts, size, aspect, mode, ledger, stage):
        return [Image.new("RGB", size, (200, 180, 150)) for _ in prompts], backend
    return make_art


class AssignTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = pathlib.Path(self.tmp.name)
        write_intake(self.d / "intake.csv", 37)

    def tearDown(self):
        self.tmp.cleanup()

    def test_same_seed_same_file(self):
        rows = assign.read_intake(self.d / "intake.csv")
        self.assertEqual(assign.to_csv(assign.assign(rows, 7)), assign.to_csv(assign.assign(rows, 7)))
        self.assertNotEqual(assign.to_csv(assign.assign(rows, 7)), assign.to_csv(assign.assign(rows, 8)))
        out = io.StringIO()
        with mock.patch("sys.stdout", out):
            self.assertEqual(assign.main(["--data-dir", str(self.d), "--seed", "11"]), 0)
        first = (self.d / "assignments.csv").read_bytes()
        with mock.patch("sys.stdout", out):
            self.assertEqual(assign.main(["--data-dir", str(self.d), "--seed", "11"]), 0)
        self.assertEqual(first, (self.d / "assignments.csv").read_bytes())
        with redirect_stderr(io.StringIO()):
            self.assertEqual(assign.main(["--data-dir", str(self.d), "--seed", "12"]), 2)  # refuses to overwrite
        self.assertEqual(first, (self.d / "assignments.csv").read_bytes())
        self.assertNotIn("example.com", first.decode())

    def test_balance(self):
        rows = assign.read_intake(self.d / "intake.csv")
        a = assign.assign(rows, 3)
        for start in range(0, 36, 4):  # every full block is 2 + 2
            self.assertEqual(Counter(x["arm"] for x in a[start:start + 4]), Counter({"label": 2, "no_label": 2}))
        for arm in ("label", "no_label"):
            mine = [x for x in a if x["arm"] == arm]
            fmts = [x["format"] for x in mine]
            self.assertTrue(all(fmts[i] != fmts[i + 1] for i in range(len(fmts) - 1)), "format alternates")
            orders = Counter(x["order"] for x in mine)
            self.assertEqual(len(orders), 6)
            self.assertLessEqual(max(orders.values()) - min(orders.values()), 2)
            for x in mine:
                self.assertEqual(sorted([x["pos_A"], x["pos_B"], x["pos_C"]]), [1, 2, 3])
        self.assertTrue({x["gif_rank"] for x in a} <= {0, 1})
        self.assertTrue({x["generic_item"] for x in a} <= set(range(6)))
        self.assertEqual(len({x["gif_rank"] for x in a}), 2)

    def test_prospect_mapping(self):
        p = assign.intake_to_prospect({"first_name": "Ana", "role": "TA", "field": "Physics", "goal": "g",
                                       "annoyance": "a", "tools": "t", "email": "x@y.z"})
        self.assertEqual(p["company"], "Physics")
        self.assertEqual(p["title"], "TA")
        self.assertEqual(p["industry"], "Physics")
        self.assertEqual(p["notes"], "Working toward: g. Recurring annoyance: a. Tools: t.")
        self.assertNotIn("x@y.z", json.dumps(p))


class TextOnlyTests(unittest.TestCase):
    def test_escaping(self):
        b = {"format": "meme", "text": {"top": "<script>alert(1)</script>", "bottom": "Tom & \"Jerry\""},
             "email_line": "<b>hi</b>"}
        h = text_only.render_html(b)
        self.assertNotIn("<script>", h)
        self.assertNotIn("<b>hi", h)
        self.assertIn("&lt;script&gt;", h)
        self.assertIn("&amp;", h)
        self.assertIn("Alex", h)

    def test_calm_caps_keeps_names(self):
        lines = text_only.message_lines("meme", {"top": "WHEN DANA OPENS EXCEL", "bottom": "IT OPENS HER BACK"},
                                        "", {"first_name": "Dana", "notes": "Tools: Excel."})
        self.assertIn("Dana", lines[0])
        self.assertIn("Excel", lines[0])
        self.assertFalse(lines[0].isupper())

    def test_headline_message(self):
        lines = text_only.message_lines("headline", {"publication": "Ledger", "kicker": "Big", "headline": "Win",
                                                     "dek": "Wow."}, "Hi there.")
        self.assertEqual(lines[0], "Hi there.")
        self.assertIn('"Win."', lines[1])


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = pathlib.Path(self.tmp.name)
        write_intake(self.d / "intake.csv", 3)
        with mock.patch("sys.stdout", io.StringIO()):
            assign.main(["--data-dir", str(self.d), "--seed", "5"])

    def tearDown(self):
        self.tmp.cleanup()

    def _patch(self, backend):
        def pick(facts, fmt, context, **kw):
            return fake_pick_factory(fmt)(facts, fmt, context, **kw)
        return mock.patch.multiple(batch, concept=mock.Mock(pick=pick), art_mod=mock.Mock(make_art=fake_art(backend)))

    def test_refuses_auto(self):
        with self.assertRaises(ValueError):
            batch.run_batch(data_dir=self.d, intake=self.d / "intake.csv", art="auto", log=lambda *_: None)
        with self.assertRaises(ValueError):
            batch.check_art("placeholder")
        with redirect_stderr(io.StringIO()):
            self.assertEqual(batch.main(["--data-dir", str(self.d), "--art", "auto"]), 2)
        self.assertFalse((self.d / "stimuli").exists())

    def test_placeholder_art_marks_failed(self):
        with self._patch("placeholder"):
            done = batch.run_batch(data_dir=self.d, intake=self.d / "intake.csv", art="image", limit=1,
                                   log=lambda *_: None)
        self.assertEqual(done[0]["status"], "failed_art")
        stim = self.d / "stimuli" / done[0]["code"]
        self.assertFalse((stim / "A.gif").exists())
        self.assertFalse((stim / "manifest.json").exists())
        log = batch.read_log(self.d / "screening_log.csv")
        self.assertEqual(log[done[0]["code"]]["status"], "failed_art")

    def test_success_and_idempotent(self):
        with self._patch("image"):
            done = batch.run_batch(data_dir=self.d, intake=self.d / "intake.csv", art="image", limit=2,
                                   log=lambda *_: None)
            self.assertEqual(len(done), 2)
            for m in done:
                self.assertEqual(m["status"], "ok")
                stim = self.d / "stimuli" / m["code"]
                for f in ("A.gif", "A.png", "B.json", "manifest.json"):
                    self.assertTrue((stim / f).exists(), f)
                self.assertNotEqual(m["A"]["id"], m["B"]["id"])
                self.assertEqual({m["A"]["id"], m["B"]["id"]}, {"r1c1", "r1c2"})  # top 2 that pass the kind bar
                self.assertEqual(m["A"]["rank"], int(m["assignment"]["gif_rank"]))
                self.assertFalse(m["settings"]["research"])
            log = batch.read_log(self.d / "screening_log.csv")
            self.assertEqual({r["status"] for r in log.values()}, {"pending_review"})
            again = batch.run_batch(data_dir=self.d, intake=self.d / "intake.csv", art="image", log=lambda *_: None)
            self.assertEqual(len(again), 1)  # only the 3rd participant is new


class PagesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = pathlib.Path(self.tmp.name)
        write_intake(self.d / "intake.csv", 8)
        with mock.patch("sys.stdout", io.StringIO()):
            assign.main(["--data-dir", str(self.d), "--seed", "9"])
        self.assignments = assign.read_assignments(self.d / "assignments.csv")
        for fmt in ("meme", "headline"):
            g = self.d / "generic" / fmt
            g.mkdir(parents=True)
            for i in range(6):
                Image.new("RGB", (8, 8)).save(g / f"{i}.gif")
        rows = {}
        for k, a in enumerate(self.assignments):
            stim = self.d / "stimuli" / a["code"]
            stim.mkdir(parents=True)
            Image.new("RGB", (8, 8)).save(stim / "A.gif")
            b = {"format": a["format"], "text": {"top": "x", "bottom": "y"}, "email_line": f"marker-{a['code']}"}
            b["html"] = text_only.render_html(b)
            (stim / "B.json").write_text(json.dumps(b))
            (stim / "manifest.json").write_text("{}")
            rows[a["code"]] = {"code": a["code"], "status": "approved" if k < 6 else "pending_review"}
        batch.write_log(self.d / "screening_log.csv", rows)

    def tearDown(self):
        self.tmp.cleanup()

    def test_label_only_in_label_arm_and_only_approved(self):
        built = pages.build_pages(data_dir=self.d, log=lambda *_: None)
        self.assertEqual(len(built), 6)
        approved = {a["code"] for a in self.assignments[:6]}
        self.assertEqual(set(built), approved)
        arms = set()
        for a in self.assignments:
            page = self.d / "pages" / a["code"] / "index.html"
            if a["code"] not in approved:
                self.assertFalse(page.exists())
                continue
            h = page.read_text()
            arms.add(a["arm"])
            self.assertIn(SCENARIO, h)
            for p in (1, 2, 3):
                self.assertIn(f"Item {p}", h)
            self.assertEqual(h.count(DISCLOSURE_LABEL), 3 if a["arm"] == "label" else 0)
            self.assertNotIn("A.gif", h)
            self.assertNotIn("generic", h)
            self.assertIn("Select 2 for this row.", h)
            self.assertIn("Download my answers", h)
            b_pos = a["order"].split("-").index("B") + 1
            self.assertIn(f"marker-{a['code']}", h)
            self.assertFalse((self.d / "pages" / a["code"] / f"item{b_pos}.gif").exists())
        self.assertEqual(arms, {"label", "no_label"})

    def test_form_url_mode(self):
        with self.assertRaises(ValueError):
            pages.build_pages(data_dir=self.d, form_url="https://example.com/form", log=lambda *_: None)
        pages.build_pages(data_dir=self.d, form_url="https://example.com/f?entry.1={code}", log=lambda *_: None)
        h = (self.d / "pages" / self.assignments[0]["code"] / "index.html").read_text()
        self.assertIn("Send my answers", h)
        self.assertIn("entry.1={code}", h)


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = pathlib.Path(self.tmp.name)
        self.n = 28
        write_intake(self.d / "intake.csv", self.n)
        with mock.patch("sys.stdout", io.StringIO()):
            assign.main(["--data-dir", str(self.d), "--seed", "21"])
        self.assignments = assign.read_assignments(self.d / "assignments.csv")
        rng = random.Random(0)
        self.answers_dir = self.d / "answers"
        self.answers_dir.mkdir()
        screen = {}
        for k, a in enumerate(self.assignments):
            screen[a["code"]] = {"code": a["code"], "status": "approved"}
            payload = {"code": a["code"], "seconds": 300, "submitted_at": f"2026-12-01T10:{k:02d}:00Z",
                       "mc_ai": 6 if a["arm"] == "label" else 4, "mc_minutes": 1 if a["arm"] == "label" else 10,
                       "facts_type": "real", "open_text": ""}
            letters = a["order"].split("-")
            for p, cond in enumerate(letters, 1):
                base = {"A": 5.5, "B": 4.0, "C": 2.5}[cond]
                for key in pages.ITEM_KEYS:
                    v = base + rng.choice([-1, 0, 0, 1])
                    if key.startswith("creepy"):
                        v = {"A": 4, "B": 4, "C": 2}[cond] + rng.choice([-1, 0, 1])
                    if key == "funny" and cond == "B":
                        v = 3 + rng.choice([-1, 0, 1])
                    payload[f"item{p}_{key}"] = int(max(1, min(7, v)))
                if p == 2:
                    payload["item2_attention"] = 2
            # planted exclusions
            if k == 0:
                payload["item2_attention"] = 5
            if k == 1:
                payload["seconds"] = 40
            if k == 2:
                for key in list(payload):
                    if key.startswith("item"):
                        payload[key] = 4
                payload["item2_attention"] = 2
                for key in pages.ITEM_KEYS:
                    payload[f"item2_{key}"] = 4
            (self.answers_dir / f"{a['code']}_answers.json").write_text(json.dumps(payload))
            if k == 3:  # a later second submission with reversed effect must be ignored
                dup = dict(payload, submitted_at="2026-12-02T10:00:00Z")
                (self.answers_dir / f"{a['code']}_answers_2.json").write_text(json.dumps(dup))
            # judge scores for M1
            stim = self.d / "stimuli" / a["code"]
            stim.mkdir(parents=True)
            (stim / "manifest.json").write_text(json.dumps({
                "A": {"id": "r1c1", "grounding_count": 2, "scores": {"funny": 8, "specific": 9, "kind": 9, "glance": 8}},
                "B": {"id": "r1c2", "grounding_count": 1, "scores": {"funny": rng.randint(4, 8), "specific": 7, "kind": 8, "glance": 7}}}))
        for fmt in ("meme", "headline"):
            g = self.d / "generic" / fmt
            g.mkdir(parents=True)
            for i in range(6):
                (g / f"{i}.json").write_text(json.dumps({"concept": {"id": "r1c1"},
                                                          "scores": {"r1c1": {"funny": 5 + i % 3, "specific": 2, "kind": 9, "glance": 9}}}))
        screen["P999"] = {"code": "P999", "status": "failed_concepts"}
        batch.write_log(self.d / "screening_log.csv", screen)

    def tearDown(self):
        self.tmp.cleanup()

    def test_planted_effect_and_exclusions(self):
        rows = analysis.collect(self.answers_dir, None)
        analysis.write_ratings(rows, self.d / "ratings.csv")
        out = self.d / "results"
        builder = self.assignments[4]["code"]
        res = analysis.run(ratings=self.d / "ratings.csv", data_dir=self.d, out_dir=out, builders={builder})
        fl = res["flow"]
        self.assertEqual(fl["attention_check"], 1)
        self.assertEqual(fl["under_90_seconds"], 1)
        self.assertEqual(fl["same_answer_all_30"], 1)
        self.assertEqual(fl["duplicate_submissions_dropped"], 1)
        self.assertEqual(fl["helped_build"], 1)
        self.assertEqual(fl["failed_concepts_before_rating"], 1)
        self.assertEqual(res["n"], self.n - 4)
        self.assertTrue(res["tests"])
        h = res["hyp"]
        self.assertGreater(h["H1"]["mean_diff"], 0)
        self.assertLess(h["H1"]["p_holm"], 0.05)
        self.assertGreater(h["H3"]["mean_diff"], 0)
        self.assertGreater(h["H4"]["mean_diff"], 0)
        self.assertGreater(h["H1"]["ci"][0], 0)
        self.assertGreaterEqual(h["H1"]["p_holm"], h["H1"]["p_t"])
        self.assertIn("g", h["H2"])
        self.assertGreater(res["manip"]["ai"]["mean_diff"], 0)
        self.assertIsNotNone(res["m1_all"])
        self.assertEqual(set(res["m1_all"]), {"funny", "specific", "kind", "glance"})
        summary = (out / "summary.md").read_text()
        self.assertIn("Valid participants: 24", summary)
        self.assertIn("H1 effort", summary)
        self.assertNotIn(chr(0x2014), summary)

    def test_descriptives_only_below_16(self):
        files = sorted(self.answers_dir.glob("*.json"))
        small = self.d / "small"
        small.mkdir()
        for f in files[:12]:
            (small / f.name).write_text(f.read_text())
        analysis.write_ratings(analysis.collect(small, None), self.d / "ratings_small.csv")
        res = analysis.run(ratings=self.d / "ratings_small.csv", data_dir=self.d, out_dir=self.d / "res_small")
        self.assertFalse(res["tests"])
        summary = (self.d / "res_small" / "summary.md").read_text()
        self.assertIn("descriptive statistics and plots only", summary)
        self.assertNotIn("## Confirmatory tests", summary)

    def test_holm(self):
        adj = analysis.holm({"a": 0.01, "b": 0.04, "c": 0.03})
        self.assertAlmostEqual(adj["a"], 0.03)
        self.assertAlmostEqual(adj["c"], 0.06)
        self.assertAlmostEqual(adj["b"], 0.06)


if __name__ == "__main__":
    unittest.main()
