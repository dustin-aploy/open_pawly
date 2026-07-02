from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pawly.contracts import Action, Decision, DecisionSource, DecisionState


@dataclass(slots=True)
class PolicyEvaluation:
    decision_type: DecisionState
    reason: str
    source: DecisionSource = DecisionSource.RULE
    reason_codes: list[str] = field(default_factory=list)
    matched_rules: list[str] = field(default_factory=list)
    risk_score: float = 0.0
    audit_tags: list[str] = field(default_factory=list)
    handoff_target: str | None = None
    rewritten_action: Action | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PolicyEvaluation":
        rewritten_action = payload.get("rewritten_action")
        return cls(
            decision_type=DecisionState(payload["type"]),
            reason=str(payload["reason"]),
            source=DecisionSource(payload.get("source", DecisionSource.RULE.value)),
            reason_codes=[str(item) for item in payload.get("reason_codes", [])],
            matched_rules=[str(item) for item in payload.get("matched_rules", [])],
            risk_score=float(payload.get("risk_score", 0.0)),
            audit_tags=[str(item) for item in payload.get("audit_tags", [])],
            handoff_target=None if payload.get("handoff_target") is None else str(payload["handoff_target"]),
            rewritten_action=Action.from_dict(rewritten_action) if isinstance(rewritten_action, dict) else None,
        )

    def to_decision(self) -> Decision:
        return Decision(
            type=self.decision_type,
            reason=self.reason,
            source=self.source.value,
            reason_codes=self.reason_codes,
            matched_rules=self.matched_rules,
            risk_score=self.risk_score,
            rewritten_action=self.rewritten_action,
            audit_tags=self.audit_tags,
        )

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "type": self.decision_type.value,
            "reason": self.reason,
            "source": self.source.value,
            "reason_codes": self.reason_codes,
            "matched_rules": self.matched_rules,
            "risk_score": self.risk_score,
            "audit_tags": self.audit_tags,
        }
        if self.handoff_target is not None:
            payload["handoff_target"] = self.handoff_target
        if self.rewritten_action is not None:
            payload["rewritten_action"] = self.rewritten_action.to_dict()
        return payload
