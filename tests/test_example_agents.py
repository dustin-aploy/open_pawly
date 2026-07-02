import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

from pawly.loader.yaml_loader import load_yaml_file
from pawly.runtime import PawlyRuntime
from pawly.validator.validator import PawprintValidator


class ExampleWorkerRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = PawprintValidator()
        self.worker_path = REPO_ROOT / "examples" / "agents" / "basic_worker.yaml"

    def _audit_path(self, name: str) -> Path:
        return Path(tempfile.gettempdir()) / f"{name}.jsonl"

    def test_basic_worker_card_validates(self):
        validation = self.validator.validate_agent_config(load_yaml_file(self.worker_path))
        self.assertTrue(validation.valid, validation.errors)

    def test_smart_boundary_is_rejected_by_schema(self):
        worker = load_yaml_file(self.worker_path)
        worker["boundaries"]["smart"] = [
            {
                "action": "approve_campaign",
                "description": "Decide whether this campaign should go live.",
            }
        ]
        validation = self.validator.validate_agent_config(worker)
        self.assertFalse(validation.valid)
        self.assertIn("$.boundaries.smart is not allowed by the Pawprint schema", validation.errors)

    def test_smart_boundary_entries_are_not_part_of_the_contract(self):
        worker = load_yaml_file(self.worker_path)
        worker["boundaries"]["smart"] = [
            {
                "action": "publish_post",
                "description": "",
            }
        ]
        validation = self.validator.validate_agent_config(worker)
        self.assertFalse(validation.valid)
        self.assertIn("$.boundaries.smart is not allowed by the Pawprint schema", validation.errors)

    def test_basic_worker_completes_safe_request(self):
        audit_path = self._audit_path("basic-worker-complete")
        if audit_path.exists():
            audit_path.unlink()
        runtime = PawlyRuntime(self.worker_path, audit_path=audit_path)
        result = runtime.evaluate("Answer order status questions for a customer", "draft helpful reply", 0.93)
        self.assertEqual(result["type"], "allow")
        self.assertEqual(result["policy_evaluation"]["type"], "allow")
        self.assertEqual(result["policy_evaluation"]["reason_codes"], ["allow_within_boundaries"])
        self.assertFalse(result["runtime_overlays"]["overlay_applied"])
        self.assertEqual(result["runtime_overlays"]["merged_decision_type"], "allow")
        self.assertTrue(audit_path.exists())

    def test_basic_worker_escalates_ask_first_request(self):
        runtime = PawlyRuntime(self.worker_path)
        result = runtime.evaluate("Send an external status update to a partner", "send_external_message", 0.93)
        self.assertEqual(result["type"], "require_approval")
        self.assertEqual(result["policy_evaluation"]["type"], "require_approval")
        self.assertEqual(result["policy_evaluation"]["reason_codes"], ["boundary_ask_first"])
        self.assertFalse(result["runtime_overlays"]["overlay_applied"])
        self.assertTrue(result["matched_rules"])

    def test_basic_worker_blocks_never_request(self):
        runtime = PawlyRuntime(self.worker_path)
        result = runtime.evaluate("Give legal advice about a dispute", "write legal answer", 0.96)
        self.assertEqual(result["type"], "deny")
        self.assertTrue(result["matched_rules"])


if __name__ == "__main__":
    unittest.main()
