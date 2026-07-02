import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

from pawly.loader.yaml_loader import load_yaml_file
from pawly.policy_engine.engine import evaluate_pawprint
from pawly.types import TaskRequest


class PawprintPolicyEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_yaml_file(REPO_ROOT / "examples" / "agents" / "basic_worker.yaml")

    def test_allow_path_returns_low_risk_with_reason_codes(self):
        intent = TaskRequest(
            task="Answer order status questions for a customer",
            action="draft helpful reply",
            confidence=0.92,
        ).to_intent()
        result = evaluate_pawprint(intent, self.config)
        self.assertEqual(result.decision_type.value, "allow")
        self.assertIn("allow_within_boundaries", result.reason_codes)
        self.assertGreaterEqual(result.risk_score, 0.0)
        self.assertLess(result.risk_score, 0.3)

    def test_deny_path_returns_forbidden_boundary_match(self):
        intent = TaskRequest(
            task="Give legal advice to a customer",
            action="write legal answer",
            confidence=0.95,
        ).to_intent()
        result = evaluate_pawprint(intent, self.config)
        self.assertEqual(result.decision_type.value, "deny")
        self.assertEqual(result.reason_codes, ["boundary_never"])
        self.assertIn("give legal advice", result.matched_rules)
        self.assertGreaterEqual(result.risk_score, 0.95)

    def test_require_approval_for_ask_first_boundary(self):
        intent = TaskRequest(
            task="Send an external status update to a partner",
            action="send_external_message",
            confidence=0.95,
        ).to_intent()
        result = evaluate_pawprint(intent, self.config)
        self.assertEqual(result.decision_type.value, "require_approval")
        self.assertEqual(result.reason_codes, ["boundary_ask_first"])
        self.assertIn("send_external_message", result.matched_rules)

    def test_low_confidence_request_requires_approval(self):
        intent = TaskRequest(
            task="A customer asks for a vague status update",
            action="draft reply",
            confidence=0.55,
        ).to_intent()
        result = evaluate_pawprint(intent, self.config)
        self.assertEqual(result.decision_type.value, "require_approval")
        self.assertEqual(result.reason_codes, ["handoff_triggered"])
        self.assertIn("low-confidence-handoff", result.matched_rules)
        self.assertIsNone(result.handoff_target)

    def test_risk_score_increases_for_capability_mismatch(self):
        intent = TaskRequest(
            task="Create a quarterly pricing strategy",
            action="design pricing plan",
            confidence=0.85,
        ).to_intent()
        result = evaluate_pawprint(intent, self.config)
        self.assertEqual(result.decision_type.value, "require_approval")
        self.assertEqual(result.reason_codes, ["capability_mismatch"])
        self.assertGreaterEqual(result.risk_score, 0.45)

    def test_simulate_path_returns_simulate_when_requested(self):
        intent = TaskRequest(
            task="Preview an outbound support response",
            action="draft helpful reply",
            confidence=0.91,
            metadata={"simulate": True},
        ).to_intent()
        result = evaluate_pawprint(intent, self.config)
        self.assertEqual(result.decision_type.value, "simulate")
        self.assertEqual(result.reason_codes, ["simulate_requested"])


if __name__ == "__main__":
    unittest.main()
