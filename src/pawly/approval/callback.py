from __future__ import annotations

from typing import Callable

from pawly.approval.models import ApprovalRecord


CallbackHook = Callable[[ApprovalRecord], None]


class CallbackApprovalNotifier:
    def __init__(self, callback: CallbackHook) -> None:
        self.callback = callback

    def notify(self, record: ApprovalRecord) -> None:
        self.callback(record)
