"""Dispatch approval notifications to one or more Pawly platforms."""

from __future__ import annotations

from typing import Any, Iterable

from pawly.approval.callback import CallbackApprovalNotifier
from pawly.approval.models import ApprovalRecord

from .base import ApprovalNotificationMessage, ApprovalNotificationPlatform, NotificationDeliveryResult
from .email import EmailApprovalNotificationPlatform
from .slack import SlackApprovalNotificationPlatform
from .telegram import TelegramApprovalNotificationPlatform


DEFAULT_PLATFORMS: dict[str, ApprovalNotificationPlatform] = {
    "telegram": TelegramApprovalNotificationPlatform(),
    "slack": SlackApprovalNotificationPlatform(),
    "email": EmailApprovalNotificationPlatform(),
}


class MultiChannelApprovalNotifier:
    """Send the same approval event to every configured platform channel."""

    def __init__(
        self,
        *,
        platforms: dict[str, ApprovalNotificationPlatform] | None = None,
    ) -> None:
        self.platforms = dict(platforms or DEFAULT_PLATFORMS)

    def notify_channels(
        self,
        message: ApprovalNotificationMessage,
        *,
        channels: Iterable[str],
        credentials_by_channel: dict[str, dict[str, Any]] | None = None,
        recipients_by_channel: dict[str, dict[str, Any]] | None = None,
    ) -> list[NotificationDeliveryResult]:
        creds_map = dict(credentials_by_channel or {})
        recipient_map = dict(recipients_by_channel or {})
        results: list[NotificationDeliveryResult] = []
        seen: set[str] = set()
        for raw in channels:
            channel = str(raw or "").strip().lower()
            if not channel or channel in seen:
                continue
            seen.add(channel)
            platform = self.platforms.get(channel)
            if platform is None:
                results.append(
                    NotificationDeliveryResult(channel=channel, ok=False, detail="unsupported_approval_channel")
                )
                continue
            results.append(
                platform.send(
                    message,
                    credentials=dict(creds_map.get(channel) or {}),
                    recipient=dict(recipient_map.get(channel) or {}),
                )
            )
        return results

    def as_record_callback(
        self,
        *,
        channels: Iterable[str],
        credentials_by_channel: dict[str, dict[str, Any]] | None = None,
        recipients_by_channel: dict[str, dict[str, Any]] | None = None,
        project_id: str = "",
    ) -> CallbackApprovalNotifier:
        channel_list = [str(item).strip().lower() for item in channels if str(item).strip()]

        def _callback(record: ApprovalRecord) -> None:
            message = ApprovalNotificationMessage(
                approval_id=record.record_id,
                project_id=project_id,
                risk_level=str((record.decision.to_dict() or {}).get("risk_level") or "medium"),
                summary=str(record.intent.summary or record.proposed_action.name or "Approval required"),
                status=record.status.value,
                metadata={"intent_id": record.intent.intent_id},
            )
            self.notify_channels(
                message,
                channels=channel_list,
                credentials_by_channel=credentials_by_channel,
                recipients_by_channel=recipients_by_channel,
            )

        return CallbackApprovalNotifier(_callback)
