import json
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

from pawly.approval.handler import StaticApprovalHandler
from pawly.gateway.wrapper import ExecutionGateway
from pawly.runtime import PawlyRuntime


class AuditTests(unittest.TestCase):
    def test_audit_ledger_writes_jsonl(self):
        audit_file = Path(tempfile.gettempdir()) / "pawly-audit.jsonl"
        if audit_file.exists():
            audit_file.unlink()
        runtime = PawlyRuntime(REPO_ROOT / "examples" / "agents" / "basic_worker.yaml", audit_path=audit_file)
        runtime.evaluate("Answer order status questions for a customer", "draft helpful reply", 0.9)
        self.assertTrue(audit_file.exists())
        first_line = audit_file.read_text(encoding="utf-8").strip().splitlines()[0]
        payload = json.loads(first_line)
        self.assertEqual(payload["event_type"], "action-proposed")
        self.assertEqual(payload["policy_evaluation"]["type"], "allow")
        self.assertEqual(payload["policy_evaluation"]["reason_codes"], ["allow_within_boundaries"])
        self.assertFalse(payload["runtime_overlays"]["overlay_applied"])
        self.assertEqual(payload["runtime_overlays"]["merged_decision_type"], "allow")
        self.assertEqual(payload["reason_codes"], ["allow_within_boundaries", "budget_ok"])
        self.assertIn("risk_score", payload)
        self.assertIn("original_intent", payload)
        self.assertIn("normalized_intent", payload)
        self.assertIn("final_decision", payload)

    def test_governed_execution_event_captures_approval_and_execution(self):
        audit_file = Path(tempfile.gettempdir()) / "pawly-governed-execution.jsonl"
        if audit_file.exists():
            audit_file.unlink()
        runtime = PawlyRuntime(REPO_ROOT / "examples" / "agents" / "basic_worker.yaml", audit_path=audit_file)
        gateway = ExecutionGateway(
            runtime,
            approval_handler=StaticApprovalHandler(
                approved=True,
                reviewer="human-approver",
                notes=["edited"],
            ),
        )
        gateway.execute(
            task="Send an external status update to a partner",
            action="send_external_message",
            confidence=0.95,
            executor=lambda intent: {"ok": True, "action": intent.action.name},
        )
        last_line = audit_file.read_text(encoding="utf-8").strip().splitlines()[-1]
        payload = json.loads(last_line)
        self.assertEqual(payload["event_type"], "governed-execution")
        self.assertIn("approval", payload)
        self.assertIn("execution", payload)
        self.assertIn("action_diff", payload)
        self.assertIn("executed_action", payload)


if __name__ == "__main__":
    unittest.main()
