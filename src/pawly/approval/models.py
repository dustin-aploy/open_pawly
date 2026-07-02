from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pawly.contracts import Decision
from pawly.types import Intent, IntentAction


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass(slots=True)
class ApprovalRequest:
    intent: Intent
    decision: Decision
    record: "ApprovalRecord | None" = None


@dataclass(slots=True)
class ApprovalResponse:
    status: ApprovalStatus
    reviewer: str | None = "local-reviewer"
    notes: list[str] = field(default_factory=list)
    edited_action: IntentAction | None = None


@dataclass(slots=True)
class ApprovalRecord:
    record_id: str
    intent: Intent
    proposed_action: IntentAction
    edited_action: IntentAction | None
    status: ApprovalStatus
    created_at: str
    updated_at: str
    expires_at: str | None
    decision: Decision
    reviewer: str | None = None
    notes: list[str] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        *,
        intent: Intent,
        decision: Decision,
        expires_at: datetime | None,
    ) -> "ApprovalRecord":
        now = utc_now().isoformat()
        return cls(
            record_id=f"approval-{uuid4().hex}",
            intent=intent,
            proposed_action=intent.action,
            edited_action=None,
            status=ApprovalStatus.PENDING,
            created_at=now,
            updated_at=now,
            expires_at=expires_at.isoformat() if expires_at is not None else None,
            decision=decision,
        )

    def apply_response(self, response: ApprovalResponse) -> None:
        self.status = response.status
        self.reviewer = response.reviewer
        self.notes = list(response.notes)
        self.edited_action = response.edited_action
        self.updated_at = utc_now().isoformat()

    def mark_expired(self) -> None:
        self.status = ApprovalStatus.EXPIRED
        self.updated_at = utc_now().isoformat()
        if "approval request expired" not in self.notes:
            self.notes.append("approval request expired")

    def approved_action(self) -> IntentAction:
        return self.edited_action or self.proposed_action

    def approved_intent(self) -> Intent:
        action = self.approved_action()
        return Intent(
            intent_id=self.intent.intent_id,
            source=self.intent.source,
            action=action,
            summary=self.intent.summary,
            confidence=self.intent.confidence,
            metadata=self.intent.metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "record_id": self.record_id,
            "intent": self.intent.to_dict(),
            "proposed_action": self.proposed_action.to_dict(),
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "decision": self.decision.to_dict(),
        }
        if self.edited_action is not None:
            payload["edited_action"] = self.edited_action.to_dict()
        if self.expires_at is not None:
            payload["expires_at"] = self.expires_at
        if self.reviewer is not None:
            payload["reviewer"] = self.reviewer
        if self.notes:
            payload["notes"] = self.notes
        return payload
