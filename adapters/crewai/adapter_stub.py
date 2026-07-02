from __future__ import annotations

from dataclasses import replace
from dataclasses import dataclass, field
from typing import Any, Callable

from pawly.gateway import GatewayProtocol
from pawly.gateway.adapter_support import build_gateway, execute_adapter_action, metadata_from_intent
from pawly.runtime import PawlyRuntime


@dataclass(slots=True)
class CrewTaskAction:
    task: str
    action: str
    confidence: float
    payload: dict[str, Any] = field(default_factory=dict)


TaskExecutor = Callable[[CrewTaskAction], Any]
AuditHook = Callable[[dict[str, Any]], None]


class CrewAIPawAdapter:
    """Thin Pawly wrapper for crew-style task execution boundaries."""

    def __init__(
        self,
        runtime: PawlyRuntime,
        audit_hook: AuditHook | None = None,
        approval_handler=None,
        gateway: GatewayProtocol | None = None,
    ) -> None:
        self.gateway = build_gateway(runtime, approval_handler=approval_handler, gateway=gateway)
        self.audit_hook = audit_hook

    def execute_task(self, action: CrewTaskAction, executor: TaskExecutor) -> dict[str, Any]:
        return execute_adapter_action(
            gateway=self.gateway,
            item=action,
            task=action.task,
            action=action.action,
            confidence=action.confidence,
            metadata=action.payload,
            executor=executor,
            remap=lambda current, intent: replace(
                current,
                task=intent.summary,
                action=intent.action.name,
                confidence=intent.confidence,
                payload=metadata_from_intent(intent),
            ),
            audit_hook=self.audit_hook,
            audit_payload=lambda outcome: {
                "framework": "crewai",
                "event": "task-execution",
                "action": action.action,
                "decision_type": outcome["type"],
                "executed": outcome["execution"]["executed"],
            },
        )
