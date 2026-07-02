from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pawly.contracts import Action, Intent, IntentSource


@dataclass(slots=True)
class TaskRequest:
    task: str
    action: str
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_intent(self, *, intent_id: str = "intent-from-task-request") -> Intent:
        return Intent(
            intent_id=intent_id,
            source=IntentSource.EXECUTION_REQUEST,
            action=Action(
                name=self.action,
                arguments={"task": self.task, **self.metadata},
            ),
            summary=self.task,
            confidence=self.confidence,
            metadata=self.metadata,
        )
