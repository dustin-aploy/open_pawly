"""Slack approval notification platform (Pawly official webhook/bot)."""

from __future__ import annotations

from typing import Any

import httpx

from .base import ApprovalNotificationMessage, NotificationDeliveryResult


class SlackApprovalNotificationPlatform:
    channel = "slack"

    def send(
        self,
        message: ApprovalNotificationMessage,
        *,
        credentials: dict[str, Any] | None = None,
        recipient: dict[str, Any] | None = None,
    ) -> NotificationDeliveryResult:
        creds = dict(credentials or {})
        dest = dict(recipient or {})
        webhook_url = str(
            dest.get("webhook_url")
            or creds.get("webhook_url")
            or creds.get("SLACK_WEBHOOK_URL")
            or ""
        ).strip()
        bot_token = str(creds.get("bot_token") or creds.get("SLACK_BOT_TOKEN") or "").strip()
        channel = str(dest.get("channel") or creds.get("channel") or creds.get("SLACK_CHANNEL") or "").strip()

        actions = []
        if message.approve_url:
            actions.append(
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Approve"},
                    "style": "primary",
                    "url": message.approve_url,
                }
            )
        if message.reject_url:
            actions.append(
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Reject"},
                    "style": "danger",
                    "url": message.reject_url,
                }
            )
        blocks: list[dict[str, Any]] = [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*{message.title()}*\n{message.summary}"}},
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Approval `{message.approval_id}` · risk `{message.risk_level}`",
                    }
                ],
            },
        ]
        if actions:
            blocks.append({"type": "actions", "elements": actions})

        try:
            if webhook_url:
                response = httpx.post(
                    webhook_url,
                    json={"text": message.body(), "blocks": blocks},
                    timeout=30,
                )
                response.raise_for_status()
                return NotificationDeliveryResult(
                    channel=self.channel,
                    ok=True,
                    detail="slack_webhook_sent",
                    external_reference={"mode": "webhook"},
                )
            if not bot_token or not channel:
                return NotificationDeliveryResult(
                    channel=self.channel,
                    ok=False,
                    detail="slack_webhook_or_bot_credentials_required",
                )
            response = httpx.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {bot_token}"},
                json={"channel": channel, "text": message.body(), "blocks": blocks},
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:  # noqa: BLE001
            return NotificationDeliveryResult(channel=self.channel, ok=False, detail=str(exc))
        if not data.get("ok"):
            return NotificationDeliveryResult(channel=self.channel, ok=False, detail=str(data.get("error") or data))
        return NotificationDeliveryResult(
            channel=self.channel,
            ok=True,
            detail="slack_bot_sent",
            external_reference={"ts": data.get("ts", ""), "channel": data.get("channel", channel)},
        )
