from __future__ import annotations

from typing import Any

from pawly.contracts import Intent
from pawly.task_request import TaskRequest


def build_task_request_intent(
    *,
    task: str,
    action: str,
    confidence: float,
    metadata: dict[str, Any] | None = None,
    intent_id: str = "intent-from-task-request",
) -> Intent:
    request = TaskRequest(
        task=task,
        action=action,
        confidence=confidence,
        metadata=metadata or {},
    )
    return request.to_intent(intent_id=intent_id)
