"""Deterministic guardrails in concept.check. No network.

    .venv/bin/python -m unittest tests.test_guardrails -v
"""
from __future__ import annotations

import copy
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent), str(HERE)]

from fixtures import CONTEXT, PROSPECT, sample_concept  # noqa: E402

from inside_joke import concept  # noqa: E402
from inside_joke.formats import ORDER  # noqa: E402


def meme(top="WHEN THE S&OP MEETING HITS HOUR THREE", bottom="AND THE FORECAST STARTS FORECASTING YOU",
         grounding=None, email_line="Made you something."):
    c = sample_concept("meme")
    c["text"] = {"top": top, "bottom": bottom}
    if grounding is not None:
        c["grounding"] = grounding
    c["email_line"] = email_line
    return c


class GuardrailTest(unittest.TestCase):
    def check(self, c, fmt="meme", context=None, generic=False):
        return concept.check(c, PROSPECT, fmt, context, generic=generic)

    def test_good_concept_passes_every_format(self):
        for fmt in ORDER:
            ctx = CONTEXT if fmt == "reply" else None
            self.assertEqual(self.check(sample_concept(fmt), fmt, ctx), [], fmt)

    def test_banned_word_rejected(self):
        probs = self.check(meme(bottom="AT LEAST THE LAYOFFS ARE ON TIME"))
        self.assertTrue(any("banned topic word" in p for p in probs), probs)

    def test_banned_word_in_email_line_rejected(self):
        probs = self.check(meme(email_line="Sorry about the lawsuit."))
        self.assertTrue(any("banned topic word" in p for p in probs), probs)

    def test_regression_old_and_fired_are_allowed(self):
        # Run 1 rejected a good meme for "OLD". These phrases are harmless.
        c = meme(top="THE OLD SPREADSHEET STILL WORKS", bottom="I FIRED OFF THE FORECAST AT 5")
        self.assertEqual(self.check(c), [])
        self.assertEqual(self.check(meme(email_line="Fired off a quick one about that old spreadsheet.")), [])

    def test_ungrounded_rejected(self):
        probs = self.check(meme(grounding=[]))
        self.assertIn("no grounding: concept is not personalized", probs)

    def test_unknown_grounding_field_rejected(self):
        probs = self.check(meme(grounding=[{"fact": "salary", "field": "salary"}]))
        self.assertTrue(any("unknown field 'salary'" in p for p in probs), probs)

    def test_conversation_field_needs_context(self):
        g = [{"fact": "ERP migration", "field": "conversation"}]
        self.assertTrue(any("unknown field" in p for p in self.check(meme(grounding=g))))
        self.assertEqual(self.check(meme(grounding=g), context=CONTEXT), [])

    def test_first_name_twice_rejected(self):
        probs = self.check(meme(top="Dana VERSUS THE FORECAST", bottom="Dana WINS IN ROUND 3"))
        self.assertIn("first name used 2 times", probs)
        self.assertEqual(self.check(meme(top="Dana VERSUS THE FORECAST", bottom="THE FORECAST BLINKS")), [])

    def test_over_limit_field_rejected(self):
        long_top = " ".join(["WORD"] * 13)  # limit 9, tolerance 1.3x
        probs = self.check(meme(top=long_top))
        self.assertTrue(any(p.startswith("top too long") for p in probs), probs)

    def test_missing_field_rejected(self):
        c = sample_concept("headline")
        del c["text"]["dek"]
        self.assertIn("missing field dek", self.check(c, "headline"))

    def test_format_shape_rules(self):
        comic = sample_concept("comic")
        comic["art_prompts"] = comic["art_prompts"][:2]
        self.assertIn("comic needs exactly 3 captions and 3 art_prompts", self.check(comic, "comic"))
        card = sample_concept("card")
        card["text"]["stats"] = card["text"]["stats"][:2]
        self.assertIn("card needs 3 stats", self.check(card, "card"))
        reply = sample_concept("reply")
        reply["text"]["prop"] = "confetti_cannon"
        self.assertIn("reply prop must be calendar_flip|progress_bar|stamp",
                      self.check(reply, "reply", CONTEXT))

    def test_generic_mode_rejects_grounding(self):
        probs = self.check(meme(), generic=True)
        self.assertIn("generic concept must not cite personal facts", probs)

    def test_generic_mode_passes_without_grounding(self):
        self.assertEqual(self.check(meme(grounding=[]), generic=True), [])

    def test_check_does_not_mutate_concept(self):
        c = meme()
        before = copy.deepcopy(c)
        self.check(c)
        self.assertEqual(c, before)


if __name__ == "__main__":
    unittest.main()
