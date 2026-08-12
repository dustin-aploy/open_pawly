"""Pawly approval notification platforms (Telegram, Slack, Email, ...)."""

from .base import ApprovalNotificationMessage, ApprovalNotificationPlatform, NotificationDeliveryResult
from .dispatcher import DEFAULT_PLATFORMS, MultiChannelApprovalNotifier
from .email import EmailApprovalNotificationPlatform
from .slack import SlackApprovalNotificationPlatform
from .telegram import TelegramApprovalNotificationPlatform

__all__ = [
    "ApprovalNotificationMessage",
    "ApprovalNotificationPlatform",
    "DEFAULT_PLATFORMS",
    "EmailApprovalNotificationPlatform",
    "MultiChannelApprovalNotifier",
    "NotificationDeliveryResult",
    "SlackApprovalNotificationPlatform",
    "TelegramApprovalNotificationPlatform",
]
