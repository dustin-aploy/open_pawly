"""Shared contracts for Pawly approval notification platforms."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(slots=True)
class ApprovalNotificationMessage:
    """Normalized approval payload delivered to one or more platforms."""

    approval_id: str
    project_id: str = ""
    run_id: str = ""
    risk_level: str = "medium"
    summary: str = "Approval required"
    status: str = "pending"
    approve_url: str = ""
    reject_url: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def title(self) -> str:
        return f"Pawly approval ({self.risk_level}): {self.summary}".strip()

    def body(self) -> str:
        lines = [
            self.title(),
            f"Approval ID: {self.approval_id}",
        ]
        if self.project_id:
            lines.append(f"Project: {self.project_id}")
        if self.run_id:
            lines.append(f"Run: {self.run_id}")
        if self.approve_url:
            lines.append(f"Approve: {self.approve_url}")
        if self.reject_url:
            lines.append(f"Reject: {self.reject_url}")
        return "\n".join(lines)


@dataclass(slots=True)
class NotificationDeliveryResult:
    channel: str
    ok: bool
    detail: str = ""
    external_reference: dict[str, Any] = field(default_factory=dict)


class ApprovalNotificationPlatform(Protocol):
    """Platform adapter that delivers approval notifications through Pawly."""

    channel: str

    def send(
        self,
        message: ApprovalNotificationMessage,
        *,
        credentials: dict[str, Any] | None = None,
        recipient: dict[str, Any] | None = None,
    ) -> NotificationDeliveryResult:
        ...
