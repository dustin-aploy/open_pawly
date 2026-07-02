from __future__ import annotations

from typing import Protocol

from pawly.approval.models import ApprovalRequest, ApprovalResponse, ApprovalStatus
from pawly.types import IntentAction


class ApprovalHandler(Protocol):
    def review(self, request: ApprovalRequest) -> ApprovalResponse: ...


class StaticApprovalHandler:
    def __init__(
        self,
        *,
        approved: bool,
        reviewer: str = "local-reviewer",
        notes: list[str] | None = None,
        edited_action: IntentAction | None = None,
    ) -> None:
        self.approved = approved
        self.reviewer = reviewer
        self.notes = notes or []
        self.edited_action = edited_action

    def review(self, request: ApprovalRequest) -> ApprovalResponse:
        del request
        return ApprovalResponse(
            status=ApprovalStatus.APPROVED if self.approved else ApprovalStatus.REJECTED,
            reviewer=self.reviewer,
            notes=list(self.notes),
            edited_action=self.edited_action,
        )
