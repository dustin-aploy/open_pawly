from __future__ import annotations

from dataclasses import replace
from dataclasses import dataclass, field
from typing import Any, Callable

from pawly.gateway import GatewayProtocol
from pawly.gateway.adapter_support import build_gateway, execute_adapter_action, metadata_from_intent
from pawly.runtime import PawlyRuntime


@dataclass(slots=True)
class OpenAIAgentAction:
    task: str
    tool_name: str
    confidence: float
    payload: dict[str, Any] = field(default_factory=dict)


ExecutorHook = Callable[[OpenAIAgentAction], Any]
AuditHook = Callable[[dict[str, Any]], None]


class OpenAIAgentsPawAdapter:
    """Minimal Pawly adapter for execution-boundary checks around an OpenAI agent action."""

    def __init__(
        self,
        runtime: PawlyRuntime,
        audit_hook: AuditHook | None = None,
        approval_handler=None,
        gateway: GatewayProtocol | None = None,
    ) -> None:
        self.gateway = build_gateway(runtime, approval_handler=approval_handler, gateway=gateway)
        self.audit_hook = audit_hook

    def execute_tool(self, action: OpenAIAgentAction, executor: ExecutorHook) -> dict[str, Any]:
        return execute_adapter_action(
            gateway=self.gateway,
            item=action,
            task=action.task,
            action=action.tool_name,
            confidence=action.confidence,
            metadata=action.payload,
            executor=executor,
            remap=lambda current, intent: replace(
                current,
                task=intent.summary,
                tool_name=intent.action.name,
                confidence=intent.confidence,
                payload=metadata_from_intent(intent),
            ),
            audit_hook=self.audit_hook,
            audit_payload=lambda outcome: {
                "framework": "openai-agents",
                "event": "tool-execution",
                "tool_name": action.tool_name,
                "decision_type": outcome["type"],
                "executed": outcome["execution"]["executed"],
            },
        )
