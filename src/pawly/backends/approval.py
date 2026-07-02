from __future__ import annotations

from typing import Any, Protocol

from pawly.contracts import Decision
from pawly.approval.handler import ApprovalHandler
from pawly.approval.models import ApprovalRecord, ApprovalResponse
from pawly.approval.queue import ApprovalQueue, InMemoryApprovalQueue
from pawly.approval.router import ApprovalRouter
from pawly.types import Intent


class ApprovalBackend(Protocol):
    name: str

    def submit(self, intent: Intent, decision: Decision) -> ApprovalRecord:
        ...

    def get(self, record_id: str) -> ApprovalRecord:
        ...

    def apply_response(self, record_id: str, response: ApprovalResponse) -> ApprovalRecord:
        ...

    def expire_due(self) -> list[ApprovalRecord]:
        ...

    def status_payload(self, record: ApprovalRecord) -> dict[str, Any]:
        ...


class LocalApprovalBackend:
    name = "local-approval"

    def __init__(
        self,
        *,
        queue: ApprovalQueue | None = None,
        handler: ApprovalHandler | None = None,
        timeout_seconds: int | None = 300,
        router: ApprovalRouter | None = None,
    ) -> None:
        self.router = router or ApprovalRouter(
            queue=queue or InMemoryApprovalQueue(),
            handler=handler,
            timeout_seconds=timeout_seconds,
        )

    def submit(self, intent: Intent, decision: Decision) -> ApprovalRecord:
        return self.router.submit(intent, decision)

    def get(self, record_id: str) -> ApprovalRecord:
        return self.router.get(record_id)

    def apply_response(self, record_id: str, response: ApprovalResponse) -> ApprovalRecord:
        return self.router.apply_response(record_id, response)

    def expire_due(self) -> list[ApprovalRecord]:
        return self.router.expire_due()

    def status_payload(self, record: ApprovalRecord) -> dict[str, Any]:
        return self.router.status_payload(record)


class CloudApprovalBackendStub:
    name = "cloud-approval"

    def submit(self, intent: Intent, decision: Decision) -> ApprovalRecord:
        del intent, decision
        raise NotImplementedError("Cloud approval backends are optional extensions and are not part of the OSS runtime path.")

    def get(self, record_id: str) -> ApprovalRecord:
        del record_id
        raise NotImplementedError("Cloud approval backends are optional extensions and are not part of the OSS runtime path.")

    def apply_response(self, record_id: str, response: ApprovalResponse) -> ApprovalRecord:
        del record_id, response
        raise NotImplementedError("Cloud approval backends are optional extensions and are not part of the OSS runtime path.")

    def expire_due(self) -> list[ApprovalRecord]:
        raise NotImplementedError("Cloud approval backends are optional extensions and are not part of the OSS runtime path.")

    def status_payload(self, record: ApprovalRecord) -> dict[str, Any]:
        del record
        raise NotImplementedError("Cloud approval backends are optional extensions and are not part of the OSS runtime path.")
