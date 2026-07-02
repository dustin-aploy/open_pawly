from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from pawly.approval.handler import ApprovalHandler
from pawly.approval.models import ApprovalStatus
from pawly.approval.router import ApprovalRouter
from pawly.backends.approval import ApprovalBackend, LocalApprovalBackend
from pawly.backends.audit import AuditSink
from pawly.backends.reviewer import ReviewerPolicy
from pawly.backends.risk import RiskProvider
from pawly.decision_engine import DecisionEngine
from pawly.gateway.protocol import ExecutorFunc
from pawly.gateway.result import build_gateway_payload, build_governed_execution_event
from pawly.policy import resolve_reviewer_selection
from pawly.runtime_request import build_task_request_intent
from pawly.runtime_result import RuntimeDecisionResult
from pawly.types import Intent

ExecuteFn = Callable[[str, str, float, dict[str, Any] | None], Any]


class ExecutionGateway:
    def __init__(
        self,
        decision_engine: DecisionEngine,
        approval_handler: ApprovalHandler | None = None,
        policy: str = "rules",
        approval_router: ApprovalRouter | None = None,
        approval_backend: ApprovalBackend | None = None,
        runtime: DecisionEngine | None = None,
        reviewer: str | None = None,
    ) -> None:
        self.runtime = runtime or decision_engine
        self.policy = reviewer or policy
        self.reviewer = self.policy
        self.approval_backend = approval_backend or LocalApprovalBackend(
            handler=approval_handler,
            router=approval_router,
        )

    def execute(
        self,
        *,
        task: str,
        action: str,
        confidence: float,
        executor: ExecutorFunc,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.execute_intent(
            build_task_request_intent(
                task=task,
                action=action,
                confidence=confidence,
                metadata=metadata,
            ),
            executor,
        )

    def execute_intent(self, intent: Intent, executor: ExecutorFunc) -> dict[str, Any]:
        decision_result = (
            self.runtime.evaluate_intent_result(intent)
            if hasattr(self.runtime, "evaluate_intent_result")
            else None
        )
        if decision_result is None:
            from pawly.runtime_result import RuntimeDecisionResult

            decision_result = RuntimeDecisionResult.from_dict(self.runtime.evaluate_intent(intent))
        if decision_result.decision.type.value == "require_approval":
            record = self.approval_backend.submit(intent, decision_result.decision)
            approval = self.approval_backend.status_payload(record)
            if record.status == ApprovalStatus.APPROVED:
                approved_intent = record.approved_intent()
                result = executor(approved_intent)
                payload = build_gateway_payload(
                    decision_result,
                    approval=approval,
                    execution={
                        "attempted": True,
                        "executed": True,
                        "blocked_by": None,
                        "result": result,
                        "used_action": approved_intent.action.to_dict(),
                    },
                )
                self._append_governed_execution_event(intent, decision_result, payload)
                return payload
            blocked_by = "expired" if record.status == ApprovalStatus.EXPIRED else "require_approval"
            payload = build_gateway_payload(
                decision_result,
                approval=approval,
                execution={
                    "attempted": False,
                    "executed": False,
                    "blocked_by": blocked_by,
                    "reviewer": self.policy,
                },
            )
            self._append_governed_execution_event(intent, decision_result, payload)
            return payload
        if decision_result.decision.type.value == "simulate":
            payload = build_gateway_payload(
                decision_result,
                execution={
                    "attempted": False,
                    "executed": False,
                    "blocked_by": "simulate",
                    "reviewer": self.policy,
                },
            )
            self._append_governed_execution_event(intent, decision_result, payload)
            return payload
        if decision_result.decision.type.value != "allow":
            payload = build_gateway_payload(
                decision_result,
                execution={
                    "attempted": False,
                    "executed": False,
                    "blocked_by": decision_result.decision.type.value,
                    "reviewer": self.policy,
                },
            )
            self._append_governed_execution_event(intent, decision_result, payload)
            return payload

        result = executor(intent)
        payload = build_gateway_payload(
            decision_result,
            execution={
                "attempted": True,
                "executed": True,
                "blocked_by": None,
                "reviewer": self.policy,
                "result": result,
                "used_action": intent.action.to_dict(),
            },
        )
        self._append_governed_execution_event(intent, decision_result, payload)
        return payload

    def _append_governed_execution_event(
        self,
        original_intent: Intent,
        decision_result: RuntimeDecisionResult,
        payload: dict[str, Any],
    ) -> None:
        event = build_governed_execution_event(
            event_id=self.runtime.next_event_id() if hasattr(self.runtime, "next_event_id") else None,
            original_intent=original_intent,
            decision_result=decision_result,
            payload=payload,
        )
        if hasattr(self.runtime, "audit_sink"):
            self.runtime.audit_sink.append(event)


def wrap_executor(
    executor: ExecutorFunc,
    pawprint: str | Path,
    policy: str = "rules",
    *,
    approval_handler: ApprovalHandler | None = None,
    approval_router: ApprovalRouter | None = None,
    approval_backend: ApprovalBackend | None = None,
    policy_impl: ReviewerPolicy | None = None,
    risk_provider: RiskProvider | None = None,
    audit_sink: AuditSink | None = None,
    audit_path: str | Path | None = None,
    reviewer: str | None = None,
    reviewer_backend: ReviewerPolicy | None = None,
) -> ExecutorFunc:
    selected_policy, selected_policy_impl = resolve_reviewer_selection(
        policy=policy,
        policy_impl=policy_impl,
        reviewer=reviewer,
        reviewer_backend=reviewer_backend,
    )
    decision_engine = DecisionEngine(
        pawprint,
        audit_path=audit_path,
        policy=selected_policy,
        policy_impl=selected_policy_impl,
        risk_provider=risk_provider,
        audit_sink=audit_sink,
    )
    gateway = ExecutionGateway(
        decision_engine,
        approval_handler=approval_handler,
        policy=selected_policy,
        approval_router=approval_router,
        approval_backend=approval_backend,
    )

    def wrapped(intent: Intent) -> dict[str, Any]:
        return gateway.execute_intent(intent, executor)

    return wrapped


def wrap_execute_fn(
    fn: ExecuteFn,
    pawprint: str | Path,
    policy: str = "rules",
    *,
    approval_handler: ApprovalHandler | None = None,
    approval_router: ApprovalRouter | None = None,
    approval_backend: ApprovalBackend | None = None,
    policy_impl: ReviewerPolicy | None = None,
    risk_provider: RiskProvider | None = None,
    audit_sink: AuditSink | None = None,
    audit_path: str | Path | None = None,
    reviewer: str | None = None,
    reviewer_backend: ReviewerPolicy | None = None,
) -> ExecuteFn:
    selected_policy, selected_policy_impl = resolve_reviewer_selection(
        policy=policy,
        policy_impl=policy_impl,
        reviewer=reviewer,
        reviewer_backend=reviewer_backend,
    )
    decision_engine = DecisionEngine(
        pawprint,
        audit_path=audit_path,
        policy=selected_policy,
        policy_impl=selected_policy_impl,
        risk_provider=risk_provider,
        audit_sink=audit_sink,
    )
    gateway = ExecutionGateway(
        decision_engine,
        approval_handler=approval_handler,
        policy=selected_policy,
        approval_router=approval_router,
        approval_backend=approval_backend,
    )

    def wrapped(task: str, action: str, confidence: float, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        return gateway.execute(
            task=task,
            action=action,
            confidence=confidence,
            metadata=metadata,
            executor=lambda intent: _call_execute_fn_from_intent(fn, intent),
        )

    return wrapped


def wrap_framework_adapter(
    decision_engine: DecisionEngine,
    framework: str = "generic",
    *,
    approval_handler: ApprovalHandler | None = None,
    approval_router: ApprovalRouter | None = None,
    approval_backend: ApprovalBackend | None = None,
) -> ExecutionGateway:
    del framework
    return ExecutionGateway(
        decision_engine,
        approval_handler=approval_handler,
        policy="rules",
        approval_router=approval_router,
        approval_backend=approval_backend,
    )
def _call_execute_fn_from_intent(fn: ExecuteFn, intent: Intent) -> Any:
    metadata = dict(intent.metadata)
    for key, value in intent.action.arguments.items():
        if key != "task":
            metadata[key] = value
    return fn(intent.summary, intent.action.name, intent.confidence, metadata)
