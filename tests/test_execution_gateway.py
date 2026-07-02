import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

from pawly.gateway.wrapper import ExecutionGateway
from pawly.gateway.wrapper import wrap_execute_fn, wrap_executor
from pawly.gateway.wrapper import wrap_framework_adapter
from pawly.approval import ApprovalResponse, ApprovalRouter, ApprovalStatus, InMemoryApprovalQueue
from pawly.runtime import PawlyRuntime
from pawly.approval.handler import StaticApprovalHandler
from pawly.types import IntentAction, TaskRequest


class ExecutionGatewayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = PawlyRuntime(REPO_ROOT / "examples" / "agents" / "basic_worker.yaml")
        self.gateway = ExecutionGateway(self.runtime)

    def test_gateway_executes_allowed_intent(self):
        calls: list[str] = []

        def executor(intent):
            calls.append(intent.action.name)
            return {"ok": True, "tool": intent.action.name}

        result = self.gateway.execute(
            task="Answer order status questions for a customer",
            action="draft helpful reply",
            confidence=0.95,
            executor=executor,
        )

        self.assertEqual(result["type"], "allow")
        self.assertTrue(result["execution"]["executed"])
        self.assertEqual(result["execution"]["result"]["tool"], "draft helpful reply")
        self.assertEqual(calls, ["draft helpful reply"])

    def test_gateway_blocks_non_allowed_intent(self):
        calls: list[str] = []

        def executor(intent):
            calls.append(intent.action.name)
            return {"ok": True}

        intent = TaskRequest(
            task="Send an external status update to a partner",
            action="send_external_message",
            confidence=0.95,
        ).to_intent()
        result = self.gateway.execute_intent(intent, executor)

        self.assertEqual(result["type"], "require_approval")
        self.assertEqual(result["approval"]["status"], "pending")
        self.assertEqual(result["approval"]["proposed_action"]["name"], "send_external_message")
        self.assertFalse(result["execution"]["executed"])
        self.assertEqual(result["execution"]["blocked_by"], "require_approval")
        self.assertEqual(calls, [])

    def test_gateway_executes_after_local_approval(self):
        calls: list[str] = []

        def executor(intent):
            calls.append(intent.action.name)
            return {"ok": True}

        gateway = ExecutionGateway(
            self.runtime,
            approval_handler=StaticApprovalHandler(approved=True, reviewer="local-approver", notes=["approved locally"]),
        )
        result = gateway.execute(
            task="Send an external status update to a partner",
            action="send_external_message",
            confidence=0.95,
            executor=executor,
        )

        self.assertEqual(result["type"], "require_approval")
        self.assertTrue(result["approval"]["approved"])
        self.assertEqual(result["approval"]["status"], "approved")
        self.assertTrue(result["execution"]["executed"])
        self.assertEqual(result["execution"]["used_action"]["name"], "send_external_message")
        self.assertEqual(calls, ["send_external_message"])

    def test_gateway_executes_edited_action_after_approval(self):
        calls: list[str] = []

        def executor(intent):
            calls.append(intent.action.name)
            return {"ok": True, "action": intent.action.name}

        gateway = ExecutionGateway(
            self.runtime,
            approval_handler=StaticApprovalHandler(
                approved=True,
                reviewer="local-approver",
                notes=["edited before approval"],
                edited_action=IntentAction(name="draft refund response", arguments={"mode": "manual-review"}),
            ),
        )
        result = gateway.execute(
            task="Send an external status update to a partner",
            action="send_external_message",
            confidence=0.95,
            executor=executor,
        )

        self.assertEqual(result["approval"]["edited_action"]["name"], "draft refund response")
        self.assertEqual(result["execution"]["used_action"]["name"], "draft refund response")
        self.assertEqual(result["execution"]["result"]["action"], "draft refund response")
        self.assertEqual(calls, ["draft refund response"])

    def test_gateway_can_deny_local_approval(self):
        calls: list[str] = []

        def executor(intent):
            calls.append(intent.action.name)
            return {"ok": True}

        gateway = ExecutionGateway(
            self.runtime,
            approval_handler=StaticApprovalHandler(approved=False, reviewer="local-approver", notes=["denied locally"]),
        )
        result = gateway.execute(
            task="Send an external status update to a partner",
            action="send_external_message",
            confidence=0.95,
            executor=executor,
        )

        self.assertEqual(result["approval"]["status"], "rejected")
        self.assertFalse(result["execution"]["executed"])
        self.assertEqual(calls, [])

    def test_gateway_expires_when_timeout_elapsed(self):
        calls: list[str] = []

        def executor(intent):
            calls.append(intent.action.name)
            return {"ok": True}

        gateway = ExecutionGateway(
            self.runtime,
            approval_router=ApprovalRouter(queue=InMemoryApprovalQueue(), timeout_seconds=0),
        )
        result = gateway.execute(
            task="Send an external status update to a partner",
            action="send_external_message",
            confidence=0.95,
            executor=executor,
        )

        self.assertEqual(result["approval"]["status"], "expired")
        self.assertEqual(result["execution"]["blocked_by"], "expired")
        self.assertFalse(result["execution"]["executed"])
        self.assertEqual(calls, [])

    def test_wrap_executor_hides_branching_from_executor_callsite(self):
        calls: list[str] = []

        def executor(intent):
            calls.append(intent.action.name)
            return {"ok": True}

        wrapped = wrap_executor(executor, REPO_ROOT / "examples" / "agents" / "basic_worker.yaml")
        result = wrapped(
            TaskRequest(
                task="Answer order status questions for a customer",
                action="draft helpful reply",
                confidence=0.95,
            ).to_intent()
        )

        self.assertEqual(result["type"], "allow")
        self.assertTrue(result["execution"]["executed"])
        self.assertEqual(calls, ["draft helpful reply"])

    def test_wrap_execute_fn_hides_branching_from_execute_function(self):
        calls: list[tuple[str, str, float]] = []

        def execute_fn(task, action, confidence, metadata=None):
            del metadata
            calls.append((task, action, confidence))
            return {"ok": True, "action": action}

        wrapped = wrap_execute_fn(execute_fn, REPO_ROOT / "examples" / "agents" / "basic_worker.yaml")
        result = wrapped("Answer order status questions for a customer", "draft helpful reply", 0.95)

        self.assertEqual(result["type"], "allow")
        self.assertTrue(result["execution"]["executed"])
        self.assertEqual(result["execution"]["result"]["action"], "draft helpful reply")
        self.assertEqual(calls, [("Answer order status questions for a customer", "draft helpful reply", 0.95)])

    def test_wrap_execute_fn_uses_approved_edited_action(self):
        calls: list[tuple[str, str, float, dict | None]] = []

        def execute_fn(task, action, confidence, metadata=None):
            calls.append((task, action, confidence, metadata))
            return {"ok": True, "action": action, "metadata": metadata}

        wrapped = wrap_execute_fn(
            execute_fn,
            REPO_ROOT / "examples" / "agents" / "basic_worker.yaml",
            approval_handler=StaticApprovalHandler(
                approved=True,
                reviewer="local-approver",
                edited_action=IntentAction(name="draft refund response", arguments={"mode": "manual-review"}),
            ),
        )
        result = wrapped("Send an external status update to a partner", "send_external_message", 0.95, {"channel": "email"})

        self.assertEqual(result["approval"]["status"], "approved")
        self.assertEqual(result["execution"]["used_action"]["name"], "draft refund response")
        self.assertEqual(result["execution"]["result"]["action"], "draft refund response")
        self.assertEqual(
            calls,
            [("Send an external status update to a partner", "draft refund response", 0.95, {"channel": "email", "mode": "manual-review"})],
        )

    def test_gateway_supports_simulate_without_executing(self):
        class SimulateRuntime:
            def evaluate_intent(self, intent):
                return {
                    "agent_id": "simulate-worker",
                    "pawprint_version": "test",
                    "intent": intent.to_dict(),
                    "policy_evaluation": {
                        "type": "simulate",
                        "reason": "simulation only",
                        "reason_codes": ["simulate_only"],
                        "matched_rules": [],
                        "risk_score": 0.2,
                        "audit_tags": ["simulate"],
                    },
                    "runtime_overlays": {
                        "overlay_applied": False,
                        "budget": {"exhausted": False, "warnings": [], "consumed": {}},
                        "merged_decision_type": "simulate",
                    },
                    "decision_id": "simulate-decision",
                    "type": "simulate",
                    "reason": "simulation only",
                    "reason_codes": ["simulate_only"],
                    "matched_rules": [],
                    "risk_score": 0.2,
                    "audit_tags": ["simulate"],
                    "budget_consumed": {},
                }

        calls: list[str] = []

        def executor(intent):
            calls.append(intent.action.name)
            return {"ok": True}

        gateway = ExecutionGateway(SimulateRuntime())
        result = gateway.execute(
            task="Preview an outbound message",
            action="simulate send",
            confidence=0.95,
            executor=executor,
        )

        self.assertEqual(result["type"], "simulate")
        self.assertFalse(result["execution"]["executed"])
        self.assertEqual(result["execution"]["blocked_by"], "simulate")
        self.assertEqual(calls, [])

    def test_wrap_framework_adapter_returns_gateway(self):
        gateway = wrap_framework_adapter(self.runtime, framework="openai-agents")
        self.assertIsInstance(gateway, ExecutionGateway)
        self.assertEqual(gateway.reviewer, "rules")


class ApprovalRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = PawlyRuntime(REPO_ROOT / "examples" / "agents" / "basic_worker.yaml")

    def test_router_creates_pending_record_in_queue(self):
        router = ApprovalRouter(queue=InMemoryApprovalQueue(), timeout_seconds=300)
        intent = TaskRequest(
            task="Send an external status update to a partner",
            action="send_external_message",
            confidence=0.95,
        ).to_intent()
        decision = self.runtime.evaluate_intent(intent)
        record = router.submit(intent, decision)

        self.assertEqual(record.status, ApprovalStatus.PENDING)
        self.assertEqual(router.get(record.record_id).proposed_action.name, "send_external_message")

    def test_router_updates_record_from_response(self):
        router = ApprovalRouter(queue=InMemoryApprovalQueue(), timeout_seconds=300)
        intent = TaskRequest(
            task="Send an external status update to a partner",
            action="send_external_message",
            confidence=0.95,
        ).to_intent()
        decision = self.runtime.evaluate_intent(intent)
        record = router.submit(intent, decision)
        updated = router.apply_response(
            record.record_id,
            ApprovalResponse(
                status=ApprovalStatus.APPROVED,
                reviewer="human-1",
                notes=["approved with edit"],
                edited_action=IntentAction(name="draft refund response"),
            ),
        )

        self.assertEqual(updated.status, ApprovalStatus.APPROVED)
        self.assertEqual(updated.edited_action.name, "draft refund response")
        self.assertEqual(updated.reviewer, "human-1")


if __name__ == "__main__":
    unittest.main()
