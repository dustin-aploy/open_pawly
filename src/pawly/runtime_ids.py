from __future__ import annotations

from dataclasses import dataclass, field
from itertools import count


@dataclass(slots=True)
class RuntimeIdSequence:
    _decision_counter: count = field(default_factory=lambda: count(1))
    _event_counter: count = field(default_factory=lambda: count(1))

    def next_intent_id(self) -> str:
        return f"intent-{next(self._decision_counter)}"

    def next_decision_id(self) -> str:
        return f"decision-{next(self._decision_counter)}"

    def next_event_id(self) -> str:
        return f"event-{next(self._event_counter)}"
