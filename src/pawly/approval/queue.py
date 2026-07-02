from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from pawly.contracts import Action, Decision, Intent, IntentSource
from pawly.approval.models import ApprovalRecord, ApprovalStatus
from pawly.approval.timeout import is_expired
from pawly.types import IntentAction


class ApprovalQueue(Protocol):
    def create(self, record: ApprovalRecord) -> ApprovalRecord: ...
    def get(self, record_id: str) -> ApprovalRecord | None: ...
    def update(self, record: ApprovalRecord) -> ApprovalRecord: ...
    def list_pending(self) -> list[ApprovalRecord]: ...
    def expire_due(self) -> list[ApprovalRecord]: ...


class InMemoryApprovalQueue:
    def __init__(self) -> None:
        self._records: dict[str, ApprovalRecord] = {}

    def create(self, record: ApprovalRecord) -> ApprovalRecord:
        self._records[record.record_id] = record
        return record

    def get(self, record_id: str) -> ApprovalRecord | None:
        return self._records.get(record_id)

    def update(self, record: ApprovalRecord) -> ApprovalRecord:
        self._records[record.record_id] = record
        return record

    def list_pending(self) -> list[ApprovalRecord]:
        return [record for record in self._records.values() if record.status == ApprovalStatus.PENDING]

    def expire_due(self) -> list[ApprovalRecord]:
        expired: list[ApprovalRecord] = []
        for record in self.list_pending():
            if is_expired(record):
                record.mark_expired()
                self.update(record)
                expired.append(record)
        return expired


class FileApprovalQueue:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def create(self, record: ApprovalRecord) -> ApprovalRecord:
        records = self._load()
        records[record.record_id] = record
        self._save(records)
        return record

    def get(self, record_id: str) -> ApprovalRecord | None:
        return self._load().get(record_id)

    def update(self, record: ApprovalRecord) -> ApprovalRecord:
        records = self._load()
        records[record.record_id] = record
        self._save(records)
        return record

    def list_pending(self) -> list[ApprovalRecord]:
        return [record for record in self._load().values() if record.status == ApprovalStatus.PENDING]

    def expire_due(self) -> list[ApprovalRecord]:
        records = self._load()
        expired: list[ApprovalRecord] = []
        for record in records.values():
            if record.status == ApprovalStatus.PENDING and is_expired(record):
                record.mark_expired()
                expired.append(record)
        self._save(records)
        return expired

    def _load(self) -> dict[str, ApprovalRecord]:
        if not self.path.exists():
            return {}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return {record_id: _record_from_dict(item) for record_id, item in payload.items()}

    def _save(self, records: dict[str, ApprovalRecord]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {record_id: record.to_dict() for record_id, record in records.items()}
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _record_from_dict(value: dict) -> ApprovalRecord:
    intent = Intent.from_dict(value["intent"])
    proposed = value["proposed_action"]
    edited = value.get("edited_action")
    return ApprovalRecord(
        record_id=value["record_id"],
        intent=intent,
        proposed_action=Action.from_dict(proposed),
        edited_action=Action.from_dict(edited) if edited is not None else None,
        status=ApprovalStatus(value["status"]),
        created_at=value["created_at"],
        updated_at=value["updated_at"],
        expires_at=value.get("expires_at"),
        decision=Decision.from_dict(value["decision"]),
        reviewer=value.get("reviewer"),
        notes=value.get("notes", []),
    )
