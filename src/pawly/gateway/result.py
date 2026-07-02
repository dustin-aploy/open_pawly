from __future__ import annotations

from typing import Any
from uuid import uuid4

from pawly.contracts import Decision, Intent
from pawly.audit.diff import diff_actions
from pawly.audit.events import AuditEvent
from pawly.loader.schema_loader import load_pawprint_version
from pawly.runtime_result import RuntimeDecisionResult


def build_gateway_payload(
    decision_result: RuntimeDecisionResult,
    *,
    execution: dict[str, Any],
    approval: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        **decision_result.to_dict(),
        "execution": execution,
    }
    if approval is not None:
        payload["approval"] = approval
    return payload


def build_governed_execution_event(
    *,
    event_id: str | None,
    original_intent: Intent,
    decision_result: RuntimeDecisionResult,
    payload: dict[str, Any],
) -> AuditEvent:
    executed_action = payload.get("execution", {}).get("used_action")
    action = original_intent.action.to_dict()
    return AuditEvent.from_governed_execution(
        event_id=event_id or f"event-{uuid4().hex}",
        decision_id=decision_result.decision_id,
        agent_id=decision_result.agent_id,
        pawprint_version=decision_result.pawprint_version or load_pawprint_version(),
        outcome=decision_result.decision.type.value,
        original_intent=original_intent.to_dict(),
        normalized_intent=decision_result.intent.to_dict(),
        action=action,
        policy_evaluation=decision_result.policy_evaluation.to_dict(),
        runtime_overlays=decision_result.runtime_overlays,
        policy_references=decision_result.decision.matched_rules,
        final_decision=decision_result.decision.to_dict(),
        reason_codes=decision_result.decision.reason_codes,
        approval=payload.get("approval"),
        executed_action=executed_action,
        action_diff=diff_actions(action, executed_action),
        execution=payload.get("execution"),
        execution_result_ref=_execution_result_ref(payload.get("execution", {}).get("result")),
        risk_score=decision_result.decision.risk_score,
        escalated_to=decision_result.policy_evaluation.handoff_target,
    )


def _execution_result_ref(result: Any) -> str | None:
    if isinstance(result, dict):
        for key in ("result_ref", "artifact_ref", "reference", "uri", "path"):
            value = result.get(key)
            if isinstance(value, str) and value:
                return value
    return None
