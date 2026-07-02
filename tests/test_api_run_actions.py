from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from pawly import Action, SkillRegistry, run_actions


WORKER = """
metadata:
  id: api-run-actions-worker
  name: API Run Actions Worker
  description: Example worker for top-level API helper tests.

capabilities:
  - name: safe_reply
    description: Reply safely.

boundaries:
  allow:
    - safe_reply
  review: []
  block: []
"""


class ApiRunActionsTests(unittest.TestCase):
    def test_top_level_run_actions_helper_executes_selected_action(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            worker_path = Path(tempdir) / "worker.yaml"
            worker_path.write_text(WORKER, encoding="utf-8")

            registry = SkillRegistry()
            registry.register("safe_reply", lambda args, context: {"message": args["message"], "channel": context["channel"]})

            result = run_actions(
                worker_path,
                state={"trace_id": "api-run-actions"},
                actions=[Action(name="safe_reply", arguments={"message": "hello"})],
                context={"channel": "chat"},
                skill_registry=registry,
            )

            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["result"]["message"], "hello")
            self.assertEqual(result["result"]["channel"], "chat")


if __name__ == "__main__":
    unittest.main()
