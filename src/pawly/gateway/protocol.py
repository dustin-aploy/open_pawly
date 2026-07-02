from __future__ import annotations

from typing import Any, Callable, Protocol

from pawly.contracts import Intent


ExecutorFunc = Callable[[Intent], Any]


class GatewayProtocol(Protocol):
    def execute(
        self,
        *,
        task: str,
        action: str,
        confidence: float,
        executor: ExecutorFunc,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ...

    def execute_intent(self, intent: Intent, executor: ExecutorFunc) -> dict[str, Any]:
        ...
