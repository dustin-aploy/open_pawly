from __future__ import annotations

from dataclasses import replace
from dataclasses import dataclass, field
from typing import Any, Callable

from pawly.gateway import GatewayProtocol
from pawly.gateway.adapter_support import build_gateway, execute_adapter_action, metadata_from_intent
from pawly.runtime import PawlyRuntime


@dataclass(slots=True)
class GraphTransition:
    from_node: str
    to_node: str
    task: str
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)
    approved_action_name: str | None = None


TransitionExecutor = Callable[[GraphTransition], Any]
AuditHook = Callable[[dict[str, Any]], None]


class LangGraphPawAdapter:
    """Thin Pawly wrapper for execution-boundary checks in graph workflows."""

    def __init__(
        self,
        runtime: PawlyRuntime,
        audit_hook: AuditHook | None = None,
        approval_handler=None,
        gateway: GatewayProtocol | None = None,
    ) -> None:
        self.gateway = build_gateway(runtime, approval_handler=approval_handler, gateway=gateway)
        self.audit_hook = audit_hook

    def execute_transition(self, transition: GraphTransition, executor: TransitionExecutor) -> dict[str, Any]:
        return execute_adapter_action(
            gateway=self.gateway,
            item=transition,
            task=transition.task,
            action=f"{transition.from_node}->{transition.to_node}",
            confidence=transition.confidence,
            metadata=transition.metadata,
            executor=executor,
            remap=_transition_from_intent,
            audit_hook=self.audit_hook,
            audit_payload=lambda outcome: {
                "framework": "langgraph",
                "event": "transition-execution",
                "from_node": transition.from_node,
                "to_node": transition.to_node,
                "decision_type": outcome["type"],
                "executed": outcome["execution"]["executed"],
            },
        )


def _transition_from_intent(transition: GraphTransition, intent) -> GraphTransition:
    from_node, to_node = transition.from_node, transition.to_node
    if "->" in intent.action.name:
        left, right = intent.action.name.split("->", 1)
        if left and right:
            from_node, to_node = left, right
    return replace(
        transition,
        from_node=from_node,
        to_node=to_node,
        task=intent.summary,
        confidence=intent.confidence,
        metadata=metadata_from_intent(intent),
        approved_action_name=intent.action.name,
    )
