from __future__ import annotations

import json
from pathlib import Path

from pawly.audit.events import AuditEvent


class AuditLedger:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else None
        self.events: list[dict] = []

    def append(self, event: AuditEvent) -> dict:
        payload = event.to_dict()
        self.events.append(payload)
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, sort_keys=True) + "\n")
        return payload

    def load_events(self) -> list[dict]:
        if self.path and self.path.exists():
            lines = self.path.read_text(encoding="utf-8").splitlines()
            return [json.loads(line) for line in lines if line.strip()]
        return list(self.events)

    def find_event(self, *, event_id: str | None = None, decision_id: str | None = None, event_type: str | None = None) -> dict | None:
        events = self.load_events()
        for event in reversed(events):
            if event_id is not None and event.get("event_id") != event_id:
                continue
            if decision_id is not None and event.get("decision_id") != decision_id:
                continue
            if event_type is not None and event.get("event_type") != event_type:
                continue
            return event
        return None
