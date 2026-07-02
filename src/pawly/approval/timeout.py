from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pawly.approval.models import ApprovalRecord


def expiry_from_now(timeout_seconds: int | None) -> datetime | None:
    if timeout_seconds is None:
        return None
    return datetime.now(timezone.utc) + timedelta(seconds=timeout_seconds)


def is_expired(record: ApprovalRecord, *, now: datetime | None = None) -> bool:
    if record.expires_at is None:
        return False
    current = now or datetime.now(timezone.utc)
    return current >= datetime.fromisoformat(record.expires_at)
