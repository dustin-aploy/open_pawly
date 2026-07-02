from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from pawly import (
    Action,
    DecisionEngine,
    HeuristicPolicy,
    LocalApprovalBackend,
    MissingSkillRegistryError,
    SkillRegistry,
    StaticApprovalHandler,
    load_pawprint_file,
)


BASIC_WORKER = """
metadata:
  id: support-worker
  name: Support Worker
  description: Support worker for run_actions tests.

capabilities:
  - name: safe_reply
    description: Reply safely.
  - name: send_external_message
    description: Send an external message.
  - name: issue_refund
    description: Refund a customer.

boundaries:
  allow:
    - safe_reply
    - send_external_message
  review: []
  block:
    - issue_refund
"""


PROTECTED_WORKER = """
metadata:
  id: protected-support-worker
  name: Protected Support Worker
  description: Protected worker for Shield tests.

capabilities:
  - name: safe_reply
    description: Reply safely.
  - name: send_external_message
    description: Send an external message.

boundaries:
  allow:
    - safe_reply
    - send_external_message
  review: []
  block: []

protection:
  level: protected
  assets:
    - customer_data
    - external_write
  handling: cautious
"""


CONFIDENTIAL_WORKER = """
metadata:
  id: confidential-support-worker
  name: Confidential Support Worker
  description: Confidential worker for Shield tests.

capabilities:
  - name: safe_reply
    description: Reply safely.
  - name: send_external_message
    description: Send an external message.

boundaries:
  allow:
    - safe_reply
    - send_external_message
  review: []
  block: []

protection:
  level: confidential
  assets:
    - customer_data
    - external_write
  handling: strict
"""


CONFIDENTIAL_LOCAL_WORKER = """
metadata:
  id: confidential-local-worker
  name: Confidential Local Worker
  description: Confidential local-only worker for Shield tests.

capabilities:
  - name: safe_reply
    description: Reply safely.

boundaries:
  allow:
    - safe_reply
  review: []
  block: []

protection:
  level: confidential
  assets:
    - customer_data
  handling: strict
"""


class RunActionsTests(unittest.TestCase):
    def _make_runtime(self, worker_text: str) -> tuple[DecisionEngine, Path]:
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        worker_path = Path(tempdir.name) / "worker.yaml"
        audit_path = Path(tempdir.name) / "audit.jsonl"
        worker_path.write_text(worker_text, encoding="utf-8")
        runtime = DecisionEngine(worker_path, audit_path=audit_path, scoring_policy=HeuristicPolicy())
        return runtime, audit_path

    def test_existing_worker_without_new_protection_still_loads(self) -> None:
        runtime, _ = self._make_runtime(BASIC_WORKER)
        loaded = load_pawprint_file(runtime.agent_path)
        self.assertIsNone(loaded.config.protection)
        decision = runtime.decide_actions({}, [Action(name="safe_reply", arguments={"message": "hello"})])
        self.assertIsNotNone(decision.selected_action)
        self.assertEqual(decision.selected_action.name, "safe_reply")

    def test_register_skills_stores_registry(self) -> None:
        runtime, _ = self._make_runtime(BASIC_WORKER)
        registry = SkillRegistry()
        self.assertIs(runtime.register_skills(registry), runtime)
        self.assertIs(runtime.skill_registry, registry)

    def test_run_actions_executes_selected_action_when_allowed(self) -> None:
        runtime, _ = self._make_runtime(BASIC_WORKER)
        registry = SkillRegistry()
        registry.register("safe_reply", lambda args, context: {"reply": f"{args['message']}::{context['channel']}"})
        runtime.register_skills(registry)

        result = runtime.run_actions(
            state={"trace_id": "run-1"},
            actions=[Action(name="safe_reply", arguments={"message": "ok"})],
            context={"channel": "chat"},
        )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["result"]["reply"], "ok::chat")

    def test_run_actions_returns_blocked_when_no_action_is_safe(self) -> None:
        runtime, _ = self._make_runtime(BASIC_WORKER)
        registry = SkillRegistry()
        registry.register("issue_refund", lambda args, context: {"ok": True})
        runtime.register_skills(registry)

        result = runtime.run_actions(
            state={"trace_id": "run-2"},
            actions=[Action(name="issue_refund", arguments={"order_id": "ord-1"})],
            context={},
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIsNone(result["result"])

    def test_run_actions_returns_needs_review_when_decision_requires_review(self) -> None:
        runtime, _ = self._make_runtime(PROTECTED_WORKER)
        registry = SkillRegistry()
        registry.register("send_external_message", lambda args, context: {"sent": True})
        runtime.register_skills(registry)

        result = runtime.run_actions(
            state={"trace_id": "run-3"},
            actions=[Action(name="send_external_message", arguments={"to": "user@example.com"})],
            context={},
        )

        self.assertEqual(result["status"], "needs_review")
        self.assertIsNone(result["result"])

    def test_run_actions_raises_when_skill_registry_is_missing(self) -> None:
        runtime, _ = self._make_runtime(BASIC_WORKER)
        with self.assertRaises(MissingSkillRegistryError):
            runtime.run_actions(
                state={"trace_id": "run-4"},
                actions=[Action(name="safe_reply", arguments={"message": "hello"})],
                context={},
            )

    def test_run_actions_sanitizes_action_arguments_before_execution(self) -> None:
        runtime, _ = self._make_runtime(CONFIDENTIAL_LOCAL_WORKER)
        seen: list[dict[str, str]] = []
        registry = SkillRegistry()
        registry.register("safe_reply", lambda args, context: seen.append(args) or {"ok": True})
        runtime.register_skills(registry)

        result = runtime.run_actions(
            state={"trace_id": "run-5"},
            actions=[
                Action(
                    name="safe_reply",
                    arguments={
                        "email": "user@example.com",
                    },
                )
            ],
            context={},
        )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(seen[0]["email"], "[redacted-email]")

    def test_output_secret_redaction_happens_automatically(self) -> None:
        runtime, _ = self._make_runtime(BASIC_WORKER)
        registry = SkillRegistry()
        registry.register("safe_reply", lambda args, context: {"body": "token=sk-abcdefghijklmnopqrstuvwxyz123456"})
        runtime.register_skills(registry)

        result = runtime.run_actions(
            state={"trace_id": "run-6"},
            actions=[Action(name="safe_reply", arguments={"message": "hello"})],
            context={},
        )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["result"]["body"], "token=[redacted-secret]")

    def test_confidential_output_secret_blocks_result(self) -> None:
        runtime, _ = self._make_runtime(CONFIDENTIAL_LOCAL_WORKER)
        registry = SkillRegistry()
        registry.register("safe_reply", lambda args, context: {"body": "token=sk-abcdefghijklmnopqrstuvwxyz123456"})
        runtime.register_skills(registry)

        result = runtime.run_actions(
            state={"trace_id": "run-7"},
            actions=[Action(name="safe_reply", arguments={"message": "hello"})],
            context={},
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIsNone(result["result"])

    def test_confidential_external_write_strict_requires_review_before_execution(self) -> None:
        runtime, _ = self._make_runtime(CONFIDENTIAL_WORKER)
        registry = SkillRegistry()
        registry.register("safe_reply", lambda args, context: {"body": "ok"})
        runtime.register_skills(registry)

        result = runtime.run_actions(
            state={"trace_id": "run-7b"},
            actions=[Action(name="safe_reply", arguments={"message": "hello"})],
            context={},
        )

        self.assertEqual(result["status"], "needs_review")
        self.assertIn("always_requires_review", result["decision"]["protection"]["reasons"])

    def test_failed_skill_execution_returns_safe_error(self) -> None:
        runtime, _ = self._make_runtime(BASIC_WORKER)
        registry = SkillRegistry()

        def _raise(args, context):
            raise RuntimeError("authorization token secret leak")

        registry.register("safe_reply", _raise)
        runtime.register_skills(registry)

        result = runtime.run_actions(
            state={"trace_id": "run-8"},
            actions=[Action(name="safe_reply", arguments={"message": "hello"})],
            context={},
        )

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error"], "skill_execution_failed")

    def test_decision_to_dict_includes_protection_metadata(self) -> None:
        runtime, _ = self._make_runtime(PROTECTED_WORKER)
        decision = runtime.decide_actions({}, [Action(name="send_external_message", arguments={"to": "user@example.com"})])
        payload = decision.to_dict()
        self.assertIn("protection", payload)
        self.assertEqual(payload["protection"]["level"], "protected")
        self.assertIn("external_write", payload["protection"]["assets"])

    def test_run_actions_audit_redacts_chain_of_thought_and_sensitive_output(self) -> None:
        runtime, audit_path = self._make_runtime(CONFIDENTIAL_WORKER)
        registry = SkillRegistry()
        registry.register(
            "safe_reply",
            lambda args, context: {
                "body": "normal reply",
                "chain_of_thought": "secret reasoning steps",
                "system_prompt": "hidden instructions",
            },
        )
        runtime.register_skills(registry)

        runtime.run_actions(
            state={"trace_id": "run-9", "actor": {"tenant_id": "tenant-1", "agent_id": "agent-1", "user_id": "user-1"}},
            actions=[Action(name="safe_reply", arguments={"message": "hello"})],
            context={"customer_email": "user@example.com"},
        )

        events = runtime.audit_sink.load_events()
        self.assertTrue(audit_path.exists())
        self.assertEqual(len(events), 1)
        event_text = str(events[0])
        self.assertNotIn("secret reasoning steps", event_text)
        self.assertNotIn("hidden instructions", event_text)
        self.assertNotIn("user@example.com", event_text)
        self.assertEqual(events[0]["original_intent"]["selected_action"]["arguments"]["message"], "hello")
        self.assertEqual(events[0]["executed_action"]["arguments"]["message"], "hello")
        self.assertEqual(events[0]["execution"]["result_summary"], None)
        self.assertEqual(events[0]["tenant_id"], "tenant-1")
        self.assertEqual(events[0]["user_id"], "user-1")
        self.assertEqual(events[0]["protection_level"], "confidential")
        self.assertEqual(events[0]["protection_handling"], "strict")
        self.assertEqual(events[0]["protection_assets"], ["customer_data", "external_write"])
        self.assertEqual(events[0]["action_argument_summary"]["message"], "hello")
        self.assertNotIn("output_summary", events[0])

    def test_run_actions_without_protection_keeps_normal_action_payload_in_audit(self) -> None:
        runtime, _ = self._make_runtime(BASIC_WORKER)
        registry = SkillRegistry()
        registry.register("safe_reply", lambda args, context: {"body": "normal reply"})
        runtime.register_skills(registry)

        runtime.run_actions(
            state={"trace_id": "run-10"},
            actions=[Action(name="safe_reply", arguments={"message": "hello"})],
            context={"channel": "chat"},
        )

        events = runtime.audit_sink.load_events()
        self.assertEqual(events[0]["original_intent"]["selected_action"]["arguments"]["message"], "hello")

    def test_protected_external_write_without_actor_context_requires_review(self) -> None:
        runtime, _ = self._make_runtime(PROTECTED_WORKER)
        decision = runtime.decide_actions(
            {},
            [Action(name="send_external_message", arguments={"to": "user@example.com"})],
        )
        self.assertTrue(decision.requires_review)
        self.assertIn("missing_actor_context_requires_review", decision.to_dict()["protection"]["reasons"])

    def test_run_actions_with_approval_backend_returns_review_payload(self) -> None:
        runtime, _ = self._make_runtime(PROTECTED_WORKER)
        registry = SkillRegistry()
        registry.register("send_external_message", lambda args, context: {"sent": True})
        runtime.register_skills(registry)
        runtime.register_approval_backend(LocalApprovalBackend())

        result = runtime.run_actions(
            state={"trace_id": "run-11", "actor": {"tenant_id": "tenant-1"}},
            actions=[Action(name="send_external_message", arguments={"to": "user@example.com"})],
            context={},
        )

        self.assertEqual(result["status"], "needs_review")
        self.assertIn("approval", result)
        self.assertEqual(result["approval"]["status"], "pending")
        self.assertEqual(result["approval"]["proposed_action"]["name"], "send_external_message")

    def test_run_actions_with_auto_approved_backend_executes_reviewed_action(self) -> None:
        runtime, _ = self._make_runtime(PROTECTED_WORKER)
        registry = SkillRegistry()
        registry.register("send_external_message", lambda args, context: {"sent": True, "to": args["to"]})
        runtime.register_skills(registry)
        runtime.register_approval_backend(
            LocalApprovalBackend(
                handler=StaticApprovalHandler(
                    approved=True,
                    reviewer="local-approver",
                    notes=["approved in test"],
                )
            )
        )

        result = runtime.run_actions(
            state={"trace_id": "run-12", "actor": {"tenant_id": "tenant-1"}},
            actions=[Action(name="send_external_message", arguments={"to": "user@example.com"})],
            context={},
        )

        self.assertEqual(result["status"], "completed")
        self.assertIn("approval", result)
        self.assertEqual(result["approval"]["status"], "approved")
        self.assertTrue(result["result"]["sent"])


if __name__ == "__main__":
    unittest.main()
