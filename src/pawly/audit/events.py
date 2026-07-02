from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class AuditEvent:
    event_id: str
    event_type: str
    timestamp: str
    agent_id: str
    pawprint_version: str
    decision_id: str
    outcome: str
    action: dict[str, Any]
    original_intent: dict[str, Any]
    normalized_intent: dict[str, Any]
    policy_evaluation: dict[str, Any]
    runtime_overlays: dict[str, Any]
    policy_references: list[str]
    matched_policy_rules: list[str]
    final_decision: dict[str, Any]
    reason_codes: list[str]
    approval: dict[str, Any] | None = None
    executed_action: dict[str, Any] | None = None
    action_diff: dict[str, Any] | None = None
    execution: dict[str, Any] | None = None
    execution_result_ref: str | None = None
    risk_score: float | None = None
    request_id: str | None = None
    escalated_to: str | None = None
    tenant_id: str | None = None
    user_id: str | None = None
    protection_level: str | None = None
    protection_handling: str | None = None
    protection_assets: list[str] | None = None
    action_argument_summary: dict[str, Any] | None = None
    output_summary: Any | None = None
    error_summary: str | None = None
    redactions_applied: list[str] | None = None

    @classmethod
    def from_decision(
        cls,
        *,
        event_id: str,
        decision_id: str,
        agent_id: str,
        pawprint_version: str,
        outcome: str,
        original_intent: dict[str, Any],
        normalized_intent: dict[str, Any],
        action_name: str,
        policy_evaluation: dict[str, Any],
        runtime_overlays: dict[str, Any],
        policy_references: list[str],
        final_decision: dict[str, Any],
        reason_codes: list[str],
        risk_score: float | None,
        escalated_to: str | None,
    ) -> "AuditEvent":
        return cls(
            event_id=event_id,
            event_type="action-proposed",
            timestamp=datetime.now(timezone.utc).isoformat(),
            agent_id=agent_id,
            pawprint_version=pawprint_version,
            decision_id=decision_id,
            outcome=outcome,
            action={"name": action_name, "approved": outcome == "allow"},
            original_intent=original_intent,
            normalized_intent=normalized_intent,
            policy_evaluation=policy_evaluation,
            runtime_overlays=runtime_overlays,
            policy_references=policy_references,
            matched_policy_rules=list(policy_references),
            final_decision=final_decision,
            reason_codes=reason_codes,
            risk_score=risk_score,
            escalated_to=escalated_to,
            redactions_applied=[],
        )

    @classmethod
    def from_governed_execution(
        cls,
        *,
        event_id: str,
        decision_id: str,
        agent_id: str,
        pawprint_version: str,
        outcome: str,
        original_intent: dict[str, Any],
        normalized_intent: dict[str, Any],
        action: dict[str, Any],
        policy_evaluation: dict[str, Any],
        runtime_overlays: dict[str, Any],
        policy_references: list[str],
        final_decision: dict[str, Any],
        reason_codes: list[str],
        approval: dict[str, Any] | None,
        executed_action: dict[str, Any] | None,
        action_diff: dict[str, Any] | None,
        execution: dict[str, Any],
        execution_result_ref: str | None,
        risk_score: float | None,
        escalated_to: str | None,
        tenant_id: str | None = None,
        user_id: str | None = None,
        protection_level: str | None = None,
        protection_handling: str | None = None,
        protection_assets: list[str] | None = None,
        action_argument_summary: dict[str, Any] | None = None,
        output_summary: Any | None = None,
        error_summary: str | None = None,
    ) -> "AuditEvent":
        return cls(
            event_id=event_id,
            event_type="governed-execution",
            timestamp=datetime.now(timezone.utc).isoformat(),
            agent_id=agent_id,
            pawprint_version=pawprint_version,
            decision_id=decision_id,
            outcome=outcome,
            action=action,
            original_intent=original_intent,
            normalized_intent=normalized_intent,
            policy_evaluation=policy_evaluation,
            runtime_overlays=runtime_overlays,
            policy_references=policy_references,
            matched_policy_rules=list(policy_references),
            final_decision=final_decision,
            reason_codes=reason_codes,
            approval=approval,
            executed_action=executed_action,
            action_diff=action_diff,
            execution=execution,
            execution_result_ref=execution_result_ref,
            risk_score=risk_score,
            escalated_to=escalated_to,
            tenant_id=tenant_id,
            user_id=user_id,
            protection_level=protection_level,
            protection_handling=protection_handling,
            protection_assets=protection_assets,
            action_argument_summary=action_argument_summary,
            output_summary=output_summary,
            error_summary=error_summary,
            redactions_applied=[],
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return {key: value for key, value in payload.items() if value is not None}
