from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pawly import GoalExecutionResult, HeuristicPolicy, Pawly, SkillRegistry, achieve


BASIC_WORKER = """
metadata:
  id: goal-worker
  name: Goal Worker
  description: Worker for goal interface tests.

capabilities:
  - name: safe_reply
    description: Reply safely.
  - name: issue_refund
    description: Refund a customer.

boundaries:
  allow:
    - safe_reply
  review: []
  block:
    - issue_refund
"""


class GoalInterfaceTests(unittest.TestCase):
    def _worker_path(self, tempdir: str) -> Path:
        path = Path(tempdir) / "worker.yaml"
        path.write_text(BASIC_WORKER, encoding="utf-8")
        return path

    def test_achieve_resolves_goal_to_registered_skill_and_returns_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            registry = SkillRegistry()
            registry.register("safe_reply", lambda args, context: {"reply": "handled", "objective": args["objective"], "order": context["order_id"]})
            pawly = Pawly(str(self._worker_path(tempdir)), skill_registry=registry, scoring_policy=HeuristicPolicy())

            result = pawly.achieve(
                objective="safe reply to the duplicate charge question",
                context={"order_id": "123"},
                constraints={"max_cost": 2},
            )

        self.assertIsInstance(result, GoalExecutionResult)
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.result["reply"], "handled")
        self.assertEqual(result.action_receipt["interface"], "pawly.achieve")
        self.assertEqual(result.action_receipt["selected_capability"], "safe_reply")
        self.assertEqual(result.action_receipt["constraints"], {"max_cost": 2})
        self.assertEqual(result.action_receipt["execution_envelope"]["objective"], "safe reply to the duplicate charge question")
        self.assertEqual(result.action_receipt["execution_envelope"]["allowed_capabilities"], ["safe_reply"])
        self.assertEqual(result.action_receipt["execution_envelope"]["financial_limits"], {"max_cost": 2})

    def test_top_level_achieve_returns_unsupported_goal_when_no_skill_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            registry = SkillRegistry()
            registry.register("safe_reply", lambda args, context: {"reply": "handled"})
            result = achieve(
                str(self._worker_path(tempdir)),
                objective="book a flight to Tokyo",
                skill_registry=registry,
                scoring_policy=HeuristicPolicy(),
            )

        self.assertEqual(result.status, "unsupported_goal")
        self.assertEqual(result.needs, "Register a skill whose capability matches this objective.")
        self.assertIsNone(result.action_receipt["selected_capability"])
        self.assertEqual(result.action_receipt["execution_envelope"]["allowed_capabilities"], [])

    def test_cloud_style_constructor_accepts_goal_without_local_pawprint(self) -> None:
        pawly = Pawly(api_key="test-key", project_id="proj_123")

        result = pawly.achieve(objective="Resolve a customer issue safely", context={"source": "first_connection"})

        self.assertEqual(result.status, "accepted")
        self.assertEqual(result.action_receipt["interface"], "pawly.achieve")
        self.assertEqual(result.action_receipt["project_id"], "proj_123")
        self.assertEqual(result.action_receipt["execution_envelope"]["resource_scope"], {"source": "first_connection"})


if __name__ == "__main__":
    unittest.main()
