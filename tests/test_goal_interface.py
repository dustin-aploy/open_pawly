from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pawly import CloudConnection, GoalExecutionResult, HeuristicPolicy, Pawly, PawlyServices, SkillRegistry, achieve
from pawly.loader.schema_loader import load_schema


LEGACY_WORKER = """
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


CURRENT_WORKER = """
id: goal-worker
name: Goal Worker
role: Support action runner
summary: Worker for goal interface tests with safe replies and refund handoff.
capabilities:
  - safe_reply
  - issue_refund
boundaries:
  auto:
    - safe_reply
  ask_first: []
  never:
    - issue_refund
handoff:
  to: support-lead
  when:
    - refund requested
style:
  tone: clear and practical
  format: concise support update
"""


def _basic_worker() -> str:
    required = load_schema("pawprint.schema.json").get("required", [])
    return CURRENT_WORKER if "metadata" not in required else LEGACY_WORKER


class GoalInterfaceTests(unittest.TestCase):
    def _worker_path(self, tempdir: str) -> Path:
        path = Path(tempdir) / "worker.yaml"
        path.write_text(_basic_worker(), encoding="utf-8")
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

    def test_cloud_connection_requires_local_pawprint(self) -> None:
        pawly = Pawly(api_key="test-key")

        result = pawly.achieve(objective="Resolve a customer issue safely", context={"source": "first_connection"})

        self.assertEqual(result.status, "configuration_required")
        self.assertEqual(result.error, "missing_pawprint")
        self.assertEqual(result.action_receipt["interface"], "pawly.achieve")
        self.assertEqual(result.action_receipt["services"]["mode"], "cloud")
        self.assertEqual(result.action_receipt["services"]["policy_backend"], "rules")
        self.assertEqual(result.action_receipt["cloud"]["mode"], "hosted")
        self.assertEqual(result.action_receipt["execution_envelope"]["resource_scope"], {"source": "first_connection"})

    def test_hosted_project_without_api_key_points_to_developer_console(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            registry = SkillRegistry()
            registry.register("safe_reply", lambda args, context: {"reply": "handled"})
            services = PawlyServices.cloud()
            pawly = Pawly(str(self._worker_path(tempdir)), services=services, skill_registry=registry)

            result = pawly.achieve(objective="safe reply to the duplicate charge question")

        self.assertEqual(result.status, "configuration_required")
        self.assertEqual(result.error, "missing_api_key")
        self.assertIn("https://developer.aploy.ai/pawly", result.needs or "")
        self.assertEqual(result.action_receipt["services"]["mode"], "cloud")
        self.assertEqual(result.action_receipt["services"]["alerts"][0]["code"], "missing_api_key")
        self.assertFalse(result.action_receipt["cloud"]["api_key_configured"])

    def test_cloud_connection_keeps_local_pawprint_execution_path(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            registry = SkillRegistry()
            registry.register("safe_reply", lambda args, context: {"reply": "handled"})
            services = PawlyServices.cloud(
                api_key="test-key",
                scoring_policy=HeuristicPolicy(),
                sync_actions=False,
            )
            pawly = Pawly(str(self._worker_path(tempdir)), services=services, skill_registry=registry)

            result = pawly.achieve(objective="safe reply to the duplicate charge question")

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.action_receipt["selected_capability"], "safe_reply")
        self.assertEqual(result.action_receipt["services"]["mode"], "cloud")
        self.assertNotIn("project_id", result.action_receipt)
        self.assertTrue(result.action_receipt["cloud"]["api_key_configured"])

    def test_cloud_policy_is_explicit_service_choice(self) -> None:
        services = PawlyServices.cloud_policy(api_key="test-key", scoring_policy=HeuristicPolicy())

        self.assertEqual(services.policy, "cloud")
        self.assertTrue(services.cloud_connection and services.cloud_connection.sync_policy)
        self.assertIn("cloud_policy_selected", {alert["code"] for alert in services.alerts()})

    def test_local_services_can_write_action_records_to_file(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            audit_path = Path(tempdir) / "audit.jsonl"
            registry = SkillRegistry()
            registry.register("safe_reply", lambda args, context: {"reply": "handled"})
            services = PawlyServices.local(scoring_policy=HeuristicPolicy(), audit_path=audit_path)
            pawly = Pawly(str(self._worker_path(tempdir)), services=services, skill_registry=registry)

            result = pawly.achieve(objective="safe reply to the duplicate charge question")

            self.assertEqual(result.status, "completed")
            self.assertTrue(audit_path.exists())
            self.assertEqual(result.action_receipt["services"]["mode"], "local")
            self.assertEqual(result.action_receipt["services"]["action_records"]["local_file"], str(audit_path))

    def test_cloud_audit_can_keep_optional_local_audit_file(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            audit_path = Path(tempdir) / "audit.jsonl"
            registry = SkillRegistry()
            registry.register("safe_reply", lambda args, context: {"reply": "handled"})
            services = PawlyServices.cloud_audit(
                api_key="test-key",
                local_audit_path=audit_path,
                scoring_policy=HeuristicPolicy(),
            )
            pawly = Pawly(str(self._worker_path(tempdir)), services=services, skill_registry=registry)

            result = pawly.achieve(objective="safe reply to the duplicate charge question")

            alert_codes = {alert["code"] for alert in result.action_receipt["services"]["alerts"]}
            self.assertEqual(result.status, "completed")
            self.assertTrue(audit_path.exists())
            self.assertIn("cloud_audit_enabled", alert_codes)
            self.assertIn("local_audit_enabled", alert_codes)


if __name__ == "__main__":
    unittest.main()
