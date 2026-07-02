import unittest
from pathlib import Path

from pawly.contracts import Action
from pawly.policy import HeuristicPolicy


class HeuristicPolicyTests(unittest.TestCase):
    def test_returns_one_score_per_action_in_order(self):
        policy = HeuristicPolicy()
        scores = policy.evaluate(
            {},
            [
                Action(name="draft reply", arguments={}),
                Action(name="publish report", arguments={}),
            ],
        )
        self.assertEqual(len(scores), 2)
        self.assertLess(scores[0].risk_score, scores[1].risk_score)

    def test_prefers_worker_capability_matches_and_low_impact_actions(self):
        policy = HeuristicPolicy()
        safe = Action(name="draft reply", arguments={}, target="inbox")
        risky = Action(name="publish report", arguments={"channels": ["email", "web"]}, target="public-web")
        scores = policy.evaluate({"preferred_targets": ["inbox"]}, [safe, risky])
        self.assertLess(scores[0].risk_score, scores[1].risk_score)
        self.assertIn("low_friction_action", scores[0].reason_codes)
        self.assertIn("preferred_target", scores[0].reason_codes)

    def test_is_deterministic_for_same_inputs(self):
        policy = HeuristicPolicy()
        state = {
            "preferred_targets": ["inbox"],
            "recent_failures": ["send email"],
        }
        actions = [
            Action(name="draft reply", arguments={"tone": "neutral"}, target="inbox"),
            Action(name="send email", arguments={"recipient": "user@example.com"}, target="outbound"),
        ]
        first = [score.to_dict() for score in policy.evaluate(state, actions)]
        second = [score.to_dict() for score in policy.evaluate(state, actions)]
        self.assertEqual(first, second)

    def test_penalizes_recent_failures_deterministically(self):
        policy = HeuristicPolicy()
        action = Action(name="send email", arguments={"recipient": "user@example.com"})
        score = policy.evaluate({"recent_failures": ["send email"]}, [action])[0]
        self.assertIn("recent_failure", score.reason_codes)
        self.assertGreaterEqual(score.risk_score, 0.7)


if __name__ == "__main__":
    unittest.main()
