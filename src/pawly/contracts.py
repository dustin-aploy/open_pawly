from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DecisionState(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"
    SIMULATE = "simulate"


class DecisionSource(str, Enum):
    RULE = "rule"
    CLOUD = "cloud"


class IntentSource(str, Enum):
    TOOL_CALL = "tool_call"
    PLANNER_OUTPUT = "planner_output"
    EXECUTION_REQUEST = "execution_request"


@dataclass(slots=True)
class Action:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    target: str | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Action":
        return cls(
            name=str(payload["name"]),
            arguments=dict(payload.get("arguments", {})),
            target=None if payload.get("target") is None else str(payload["target"]),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {"name": self.name, "arguments": self.arguments}
        if self.target is not None:
            payload["target"] = self.target
        return payload


@dataclass(slots=True)
class Intent:
    intent_id: str
    source: IntentSource
    action: Action
    summary: str = ""
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Intent":
        context = payload.get("context", {})
        return cls(
            intent_id=str(payload["intent_id"]),
            source=IntentSource(payload["source"]),
            action=Action.from_dict(payload["action"]),
            summary=str(context.get("summary", "")),
            confidence=float(context.get("confidence", 0.0)),
            metadata=dict(payload.get("metadata", {})),
        )

    def text(self) -> str:
        return f"{self.summary} {self.action.name}".strip()

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "source": self.source.value,
            "action": self.action.to_dict(),
            "context": {
                "summary": self.summary,
                "confidence": self.confidence,
            },
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class PolicyScore:
    risk_score: float | None = None
    reason_codes: list[str] = field(default_factory=list)
    matched_rules: list[str] = field(default_factory=list)
    audit_tags: list[str] = field(default_factory=list)
    uncertainty: float | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.risk_score is not None:
            payload["risk_score"] = self.risk_score
        if self.reason_codes:
            payload["reason_codes"] = list(self.reason_codes)
        if self.matched_rules:
            payload["matched_rules"] = list(self.matched_rules)
        if self.audit_tags:
            payload["audit_tags"] = list(self.audit_tags)
        if self.uncertainty is not None:
            payload["uncertainty"] = self.uncertainty
        return payload


@dataclass(slots=True)
class Decision:
    type: DecisionState
    reason: str
    source: str | None = None
    reason_codes: list[str] = field(default_factory=list)
    matched_rules: list[str] = field(default_factory=list)
    risk_score: float | None = None
    rewritten_action: Action | None = None
    audit_tags: list[str] = field(default_factory=list)
    worker_id: str | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Decision":
        rewritten_action = payload.get("rewritten_action")
        return cls(
            type=DecisionState(payload["type"]),
            reason=str(payload["reason"]),
            source=None if payload.get("source") is None else str(payload["source"]),
            reason_codes=[str(item) for item in payload.get("reason_codes", [])],
            matched_rules=[str(item) for item in payload.get("matched_rules", [])],
            risk_score=None if payload.get("risk_score") is None else float(payload["risk_score"]),
            rewritten_action=Action.from_dict(rewritten_action) if isinstance(rewritten_action, dict) else None,
            audit_tags=[str(item) for item in payload.get("audit_tags", [])],
            worker_id=None if payload.get("worker_id") is None else str(payload["worker_id"]),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": self.type.value,
            "reason": self.reason,
        }
        if self.source is not None:
            payload["source"] = self.source
        if self.reason_codes:
            payload["reason_codes"] = list(self.reason_codes)
        if self.matched_rules:
            payload["matched_rules"] = list(self.matched_rules)
        if self.risk_score is not None:
            payload["risk_score"] = self.risk_score
        if self.rewritten_action is not None:
            payload["rewritten_action"] = self.rewritten_action.to_dict()
        if self.audit_tags:
            payload["audit_tags"] = list(self.audit_tags)
        if self.worker_id is not None:
            payload["worker_id"] = self.worker_id
        return payload
