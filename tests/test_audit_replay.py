import json
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

from pawly.approval.handler import StaticApprovalHandler
from pawly.audit.diff import diff_actions
from pawly.audit.replay import load_audit_record, replay_governed_path
from pawly.gateway.wrapper import ExecutionGateway
from pawly.runtime import PawlyRuntime
from pawly.types import IntentAction


class AuditReplayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.audit_file = Path(tempfile.gettempdir()) / "pawly-audit-replay.jsonl"
        if self.audit_file.exists():
            self.audit_file.unlink()
        self.runtime = PawlyRuntime(REPO_ROOT / "examples" / "agents" / "basic_worker.yaml", audit_path=self.audit_file)

    def test_diff_output_reports_edited_action(self):
        diff = diff_actions(
            {"name": "send_external_message", "arguments": {"channel": "email"}},
            {"name": "draft refund response", "arguments": {"mode": "manual-review"}},
        )
        self.assertTrue(diff["changed"])
        self.assertEqual(diff["changed_fields"][0]["field"], "arguments")
        self.assertEqual(diff["changed_fields"][1]["field"], "name")

    def test_replay_loads_governed_execution_event(self):
        gateway = ExecutionGateway(self.runtime)
        gateway.execute(
            task="Answer order status questions for a customer",
            action="draft helpful reply",
            confidence=0.95,
            executor=lambda intent: {"ok": True, "path": "/tmp/result.json"},
        )
        record = load_audit_record(self.audit_file)
        replay = replay_governed_path(record)
        self.assertEqual(record["event_type"], "governed-execution")
        self.assertEqual(replay["original_action"]["name"], "draft helpful reply")
        self.assertEqual(replay["executed_action"]["name"], "draft helpful reply")
        self.assertEqual(replay["execution"]["result"]["path"], "/tmp/result.json")

    def test_approval_edited_execution_trace_is_replayable(self):
        gateway = ExecutionGateway(
            self.runtime,
            approval_handler=StaticApprovalHandler(
                approved=True,
                reviewer="human-approver",
                notes=["edited"],
                edited_action=IntentAction(name="draft refund response", arguments={"mode": "manual-review"}),
            ),
        )
        gateway.execute(
            task="Send an external status update to a partner",
            action="send_external_message",
            confidence=0.95,
            executor=lambda intent: {"ok": True, "action": intent.action.name},
        )
        record = load_audit_record(self.audit_file)
        replay = replay_governed_path(record)
        self.assertEqual(record["approval"]["status"], "approved")
        self.assertEqual(record["executed_action"]["name"], "draft refund response")
        self.assertTrue(record["action_diff"]["changed"])
        self.assertEqual(replay["action_diff"]["executed_action"]["name"], "draft refund response")
        self.assertEqual(replay["approval"]["reviewer"], "human-approver")


if __name__ == "__main__":
    unittest.main()
