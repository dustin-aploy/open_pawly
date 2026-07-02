from __future__ import annotations

from pawly.contracts import Decision
from pawly.approval.handler import ApprovalHandler
from pawly.approval.models import ApprovalRecord, ApprovalRequest, ApprovalResponse, ApprovalStatus
from pawly.approval.queue import ApprovalQueue, InMemoryApprovalQueue
from pawly.approval.timeout import expiry_from_now
from pawly.types import Intent


class ApprovalRouter:
    def __init__(
        self,
        *,
        queue: ApprovalQueue | None = None,
        handler: ApprovalHandler | None = None,
        timeout_seconds: int | None = 300,
    ) -> None:
        self.queue = queue or InMemoryApprovalQueue()
        self.handler = handler
        self.timeout_seconds = timeout_seconds

    def submit(self, intent: Intent, decision: Decision) -> ApprovalRecord:
        record = ApprovalRecord.create(
            intent=intent,
            decision=decision,
            expires_at=expiry_from_now(self.timeout_seconds),
        )
        self.queue.create(record)
        if self.handler is not None:
            response = self.handler.review(ApprovalRequest(intent=intent, decision=decision, record=record))
            return self.apply_response(record.record_id, response)
        self.queue.expire_due()
        return self.get(record.record_id)

    def get(self, record_id: str) -> ApprovalRecord:
        self.queue.expire_due()
        record = self.queue.get(record_id)
        if record is None:
            raise KeyError(record_id)
        return record

    def apply_response(self, record_id: str, response: ApprovalResponse) -> ApprovalRecord:
        record = self.get(record_id)
        record.apply_response(response)
        self.queue.update(record)
        self.queue.expire_due()
        return self.get(record_id)

    def expire_due(self) -> list[ApprovalRecord]:
        return self.queue.expire_due()

    def status_payload(self, record: ApprovalRecord) -> dict:
        return {
            "record_id": record.record_id,
            "status": record.status.value,
            "approved": record.status == ApprovalStatus.APPROVED,
            "reviewer": record.reviewer,
            "notes": record.notes,
            "proposed_action": record.proposed_action.to_dict(),
            "edited_action": record.edited_action.to_dict() if record.edited_action is not None else None,
            "decision": record.decision.to_dict(),
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "expires_at": record.expires_at,
        }
