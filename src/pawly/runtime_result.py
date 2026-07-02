from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pawly.contracts import Decision, Intent
from pawly.audit.events import AuditEvent
from pawly.budget.checker import BudgetResult
from pawly.policy_engine.models import PolicyEvaluation


@dataclass(slots=True)
class RuntimeDecisionArtifacts:
    event: AuditEvent
    result: RuntimeDecisionResult


@dataclass(slots=True)
class RuntimeDecisionResult:
    agent_id: str
    pawprint_version: str
    intent: Intent
    policy_evaluation: PolicyEvaluation
    runtime_overlays: dict[str, object]
    decision_id: str
    decision: Decision
    budget_consumed: dict[str, float]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RuntimeDecisionResult":
        return cls(
            agent_id=str(payload["agent_id"]),
            pawprint_version=str(payload["pawprint_version"]),
            intent=Intent.from_dict(payload["intent"]),
            policy_evaluation=PolicyEvaluation.from_dict(payload["policy_evaluation"]),
            runtime_overlays=dict(payload["runtime_overlays"]),
            decision_id=str(payload["decision_id"]),
            decision=Decision.from_dict(payload),
            budget_consumed=dict(payload.get("budget_consumed", {})),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "agent_id": self.agent_id,
            "pawprint_version": self.pawprint_version,
            "intent": self.intent.to_dict(),
            "policy_evaluation": self.policy_evaluation.to_dict(),
            "runtime_overlays": self.runtime_overlays,
            "decision_id": self.decision_id,
            **self.decision.to_dict(),
            "budget_consumed": self.budget_consumed,
        }


def build_decision_audit_event(
    *,
    event_id: str,
    decision_id: str,
    agent_id: str,
    pawprint_version: str,
    intent: Intent,
    policy_evaluation: PolicyEvaluation,
    runtime_overlays: dict[str, object],
    decision: Decision,
) -> AuditEvent:
    intent_payload = intent.to_dict()
    return AuditEvent.from_decision(
        event_id=event_id,
        decision_id=decision_id,
        agent_id=agent_id,
        pawprint_version=pawprint_version,
        outcome=decision.type.value,
        original_intent=intent_payload,
        normalized_intent=intent_payload,
        action_name=intent.action.name,
        policy_evaluation=policy_evaluation.to_dict(),
        runtime_overlays=runtime_overlays,
        policy_references=decision.matched_rules,
        final_decision=decision.to_dict(),
        reason_codes=decision.reason_codes,
        risk_score=decision.risk_score,
        escalated_to=policy_evaluation.handoff_target if decision.type.value == "require_approval" else None,
    )


def build_decision_result(
    *,
    agent_id: str,
    pawprint_version: str,
    intent: Intent,
    policy_evaluation: PolicyEvaluation,
    runtime_overlays: dict[str, object],
    decision_id: str,
    decision: Decision,
    budget_result: BudgetResult,
) -> RuntimeDecisionResult:
    return RuntimeDecisionResult(
        agent_id=agent_id,
        pawprint_version=pawprint_version,
        intent=intent,
        policy_evaluation=policy_evaluation,
        runtime_overlays=runtime_overlays,
        decision_id=decision_id,
        decision=decision,
        budget_consumed=budget_result.consumed,
    )


def build_runtime_decision_artifacts(
    *,
    event_id: str,
    decision_id: str,
    agent_id: str,
    pawprint_version: str,
    intent: Intent,
    policy_evaluation: PolicyEvaluation,
    runtime_overlays: dict[str, object],
    decision: Decision,
    budget_result: BudgetResult,
) -> RuntimeDecisionArtifacts:
    return RuntimeDecisionArtifacts(
        event=build_decision_audit_event(
            event_id=event_id,
            decision_id=decision_id,
            agent_id=agent_id,
            pawprint_version=pawprint_version,
            intent=intent,
            policy_evaluation=policy_evaluation,
            runtime_overlays=runtime_overlays,
            decision=decision,
        ),
        result=build_decision_result(
            agent_id=agent_id,
            pawprint_version=pawprint_version,
            intent=intent,
            policy_evaluation=policy_evaluation,
            runtime_overlays=runtime_overlays,
            decision_id=decision_id,
            decision=decision,
            budget_result=budget_result,
        ),
    )
