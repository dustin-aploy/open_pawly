"""Telegram approval notification platform (Pawly official bot account)."""

from __future__ import annotations

from typing import Any

import httpx

from .base import ApprovalNotificationMessage, NotificationDeliveryResult


class TelegramApprovalNotificationPlatform:
    channel = "telegram"

    def send(
        self,
        message: ApprovalNotificationMessage,
        *,
        credentials: dict[str, Any] | None = None,
        recipient: dict[str, Any] | None = None,
    ) -> NotificationDeliveryResult:
        creds = dict(credentials or {})
        dest = dict(recipient or {})
        token = str(creds.get("bot_token") or creds.get("TELEGRAM_BOT_TOKEN") or "").strip()
        chat_id = str(dest.get("chat_id") or creds.get("chat_id") or creds.get("TELEGRAM_CHAT_ID") or "").strip()
        if not token:
            return NotificationDeliveryResult(channel=self.channel, ok=False, detail="telegram_bot_token_required")
        if not chat_id:
            return NotificationDeliveryResult(channel=self.channel, ok=False, detail="telegram_chat_id_required")

        inline_keyboard: list[list[dict[str, str]]] = []
        row: list[dict[str, str]] = []
        if message.approve_url:
            row.append({"text": "Approve", "url": message.approve_url})
        if message.reject_url:
            row.append({"text": "Reject", "url": message.reject_url})
        if not row:
            row = [
                {"text": "Approve", "callback_data": f"pawly.approval.approve:{message.approval_id}"},
                {"text": "Reject", "callback_data": f"pawly.approval.reject:{message.approval_id}"},
            ]
        inline_keyboard.append(row)

        payload = {
            "chat_id": chat_id,
            "text": message.body(),
            "reply_markup": {"inline_keyboard": inline_keyboard},
            "disable_web_page_preview": True,
        }
        try:
            response = httpx.post(f"https://api.telegram.org/bot{token}/sendMessage", json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:  # noqa: BLE001 - surface provider failure to caller
            return NotificationDeliveryResult(channel=self.channel, ok=False, detail=str(exc))
        if not data.get("ok"):
            return NotificationDeliveryResult(channel=self.channel, ok=False, detail=str(data))
        result = data.get("result") or {}
        return NotificationDeliveryResult(
            channel=self.channel,
            ok=True,
            detail="telegram_sent",
            external_reference={"message_id": result.get("message_id", ""), "chat_id": chat_id},
        )
