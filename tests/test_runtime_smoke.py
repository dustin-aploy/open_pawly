import tempfile
import unittest
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

from pawly.contracts import Action, PolicyScore
from pawly.policy.base import Policy
from pawly.runtime import PawlyRuntime
from pawly.runtime_result import RuntimeDecisionResult
from pawly.types import Intent, IntentAction, IntentSource
from pawly.validator.validator import SchemaValidationError
from pawly.types import TaskRequest


class RuntimeSmokeTests(unittest.TestCase):
    def test_runtime_loads_basic_worker_and_evaluates(self):
        audit_file = Path(tempfile.gettempdir()) / "pawly-smoke.jsonl"
        if audit_file.exists():
            audit_file.unlink()
        runtime = PawlyRuntime(REPO_ROOT / "examples" / "agents" / "basic_worker.yaml", audit_path=audit_file)
        result = runtime.evaluate("Answer order status questions for a customer", "draft helpful reply", 0.92)
        self.assertEqual(result["type"], "allow")
        self.assertEqual(result["policy_evaluation"]["type"], "allow")
        self.assertTrue(audit_file.exists())

    def test_runtime_exposes_core_policy_separately_from_overlays(self):
        runtime = PawlyRuntime(REPO_ROOT / "examples" / "agents" / "basic_worker.yaml")
        intent = TaskRequest(
            task="Send an external status update to a partner",
            action="send_external_message",
            confidence=0.93,
        ).to_intent()
        policy = runtime._evaluate_core_policy(intent)
        self.assertEqual(policy.decision_type.value, "require_approval")
        self.assertEqual(policy.reason_codes, ["boundary_ask_first"])

    def test_runtime_exposes_typed_result_boundary(self):
        runtime = PawlyRuntime(REPO_ROOT / "examples" / "agents" / "basic_worker.yaml")
        result = runtime.evaluate_result("Answer order status questions for a customer", "draft helpful reply", 0.92)
        self.assertIsInstance(result, RuntimeDecisionResult)
        self.assertEqual(result.decision.type.value, "allow")
        self.assertEqual(result.to_dict()["type"], "allow")

    def test_runtime_scores_candidate_actions_with_default_worker_context(self):
        runtime = PawlyRuntime(REPO_ROOT / "examples" / "agents" / "basic_worker.yaml")
        scores = runtime.score_actions(
            [
                Action(name="draft helpful reply", arguments={}, target="inbox"),
                Action(name="delete account", arguments={}, target="customer-record"),
            ]
        )
        self.assertEqual(len(scores), 2)
        self.assertLess(scores[0].risk_score, scores[1].risk_score)
        self.assertIn("policy:heuristic", scores[0].audit_tags)

    def test_runtime_scoring_does_not_mutate_supplied_state(self):
        runtime = PawlyRuntime(REPO_ROOT / "examples" / "agents" / "basic_worker.yaml")
        state = {"preferred_targets": ["inbox"]}
        runtime.score_actions([Action(name="draft helpful reply", arguments={}, target="inbox")], state=state)
        self.assertEqual(state, {"preferred_targets": ["inbox"]})
        self.assertNotIn("worker", state)

    def test_runtime_validates_internal_intent_shape(self):
        runtime = PawlyRuntime(REPO_ROOT / "examples" / "agents" / "basic_worker.yaml")
        invalid_intent = Intent(
            intent_id="bad-intent",
            source=IntentSource.EXECUTION_REQUEST,
            action=IntentAction(name="", arguments={}),
            summary="short summary",
            confidence=0.9,
            metadata={},
        )
        with self.assertRaises(SchemaValidationError):
            runtime.evaluate_intent(invalid_intent)

    def test_cloud_policy_high_uncertainty_downgrades_allow_to_review(self):
        class _HighUncertaintyCloudPolicy(Policy):
            name = "test-cloud"
            source = "cloud"
            supports_scoring = True

            def evaluate(self, state: Any, actions):
                del state
                return [
                    PolicyScore(
                        risk_score=0.1,
                        reason_codes=["cloud_rank"],
                        audit_tags=["policy:cloud"],
                        uncertainty=0.91,
                    )
                    for _ in actions
                ]

        runtime = PawlyRuntime(
            REPO_ROOT / "examples" / "agents" / "basic_worker.yaml",
            scoring_policy=_HighUncertaintyCloudPolicy(),
        )
        decision = runtime.decide_actions({}, [Action(name="publish_post", arguments={"draft_id": "post-1"})])

        self.assertIsNotNone(decision.selected_action)
        self.assertEqual(decision.selected_action.name, "publish_post")
        self.assertTrue(decision.requires_review)
        self.assertEqual(decision.boundary_type, "review")
        self.assertEqual(decision.reason, "cloud_candidate_uncertainty_requires_review")

    def test_cloud_policy_escalation_recommendation_downgrades_allow_to_review(self):
        class _EscalatingCloudPolicy(Policy):
            name = "test-cloud"
            source = "cloud"
            supports_scoring = True

            def evaluate(self, state: Any, actions):
                del state
                return [
                    PolicyScore(
                        risk_score=0.08,
                        reason_codes=["cloud_rank"],
                        audit_tags=["policy:cloud", "escalation:human_handoff"],
                        uncertainty=0.21,
                    )
                    for _ in actions
                ]

        runtime = PawlyRuntime(
            REPO_ROOT / "examples" / "agents" / "basic_worker.yaml",
            scoring_policy=_EscalatingCloudPolicy(),
        )
        decision = runtime.decide_actions({}, [Action(name="publish_post", arguments={"draft_id": "post-1"})])

        self.assertIsNotNone(decision.selected_action)
        self.assertEqual(decision.selected_action.name, "publish_post")
        self.assertTrue(decision.requires_review)
        self.assertEqual(decision.boundary_type, "review")
        self.assertEqual(decision.reason, "cloud_candidate_handoff_recommended")


if __name__ == "__main__":
    unittest.main()
