import unittest

from core import (
    assess_overreliance,
    build_reflection_prompt,
    revision_delta,
    should_trigger,
)


class ReflectAITests(unittest.TestCase):
    def test_fast_unchanged_acceptance_is_high_risk(self):
        a = assess_overreliance(
            latency_seconds=4,
            ai_answer="Use evidence and compare alternatives.",
            edited_answer="Use evidence and compare alternatives.",
            action="Accept",
        )
        self.assertEqual(a.level, "High")
        self.assertGreaterEqual(a.score, 0.65)

    def test_slow_substantial_revision_is_low_risk(self):
        a = assess_overreliance(
            latency_seconds=45,
            ai_answer="Accept the offer.",
            edited_answer="I would first compare funding, supervision, and long-term fit.",
            action="Revise",
        )
        self.assertEqual(a.level, "Low")

    def test_adaptive_condition_uses_risk(self):
        high = assess_overreliance(3, "x", "x", "Accept")
        low = assess_overreliance(60, "x", "a different independent answer", "Revise")
        self.assertTrue(should_trigger("Adaptive Reflection", high))
        self.assertFalse(should_trigger("Adaptive Reflection", low))
        self.assertTrue(should_trigger("Static Reflection", low))
        self.assertFalse(should_trigger("Baseline", high))

    def test_revision_delta(self):
        self.assertEqual(revision_delta("same", "same"), 0.0)
        self.assertGreater(revision_delta("yes", "completely different reasoning"), 0.5)

    def test_prompt_contains_rationale(self):
        p = build_reflection_prompt(["very fast acceptance"])
        self.assertIn("very fast acceptance", p)


if __name__ == "__main__":
    unittest.main()
