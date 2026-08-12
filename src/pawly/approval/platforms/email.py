"""Email approval notification platform (Pawly official SMTP account)."""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from typing import Any

from .base import ApprovalNotificationMessage, NotificationDeliveryResult


class EmailApprovalNotificationPlatform:
    channel = "email"

    def send(
        self,
        message: ApprovalNotificationMessage,
        *,
        credentials: dict[str, Any] | None = None,
        recipient: dict[str, Any] | None = None,
    ) -> NotificationDeliveryResult:
        creds = dict(credentials or {})
        dest = dict(recipient or {})
        to_addr = str(dest.get("to") or dest.get("email") or creds.get("to") or creds.get("EMAIL_TO") or "").strip()
        from_addr = str(creds.get("from") or creds.get("EMAIL_FROM") or "").strip()
        host = str(creds.get("smtp_host") or creds.get("SMTP_HOST") or "").strip()
        port = int(creds.get("smtp_port") or creds.get("SMTP_PORT") or 587)
        username = str(creds.get("smtp_username") or creds.get("SMTP_USERNAME") or "").strip()
        password = str(creds.get("smtp_password") or creds.get("SMTP_PASSWORD") or "").strip()
        use_tls = str(creds.get("smtp_tls") or creds.get("SMTP_TLS") or "1").strip().lower() not in {"0", "false", "no"}

        if not to_addr:
            return NotificationDeliveryResult(channel=self.channel, ok=False, detail="email_recipient_required")
        if not from_addr:
            return NotificationDeliveryResult(channel=self.channel, ok=False, detail="email_from_required")
        if not host:
            return NotificationDeliveryResult(channel=self.channel, ok=False, detail="smtp_host_required")

        email = EmailMessage()
        email["Subject"] = message.title()
        email["From"] = from_addr
        email["To"] = to_addr
        email.set_content(message.body())

        try:
            if use_tls:
                context = ssl.create_default_context()
                with smtplib.SMTP(host, port, timeout=30) as smtp:
                    smtp.starttls(context=context)
                    if username:
                        smtp.login(username, password)
                    smtp.send_message(email)
            else:
                with smtplib.SMTP(host, port, timeout=30) as smtp:
                    if username:
                        smtp.login(username, password)
                    smtp.send_message(email)
        except Exception as exc:  # noqa: BLE001
            return NotificationDeliveryResult(channel=self.channel, ok=False, detail=str(exc))
        return NotificationDeliveryResult(
            channel=self.channel,
            ok=True,
            detail="email_sent",
            external_reference={"to": to_addr, "from": from_addr},
        )
