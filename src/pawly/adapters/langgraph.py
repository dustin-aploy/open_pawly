from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Callable, Iterable, Mapping

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
    raw_item: Any = None

    @classmethod
    def from_value(
        cls,
        value: Any,
        *,
        task: str | None = None,
        confidence: float | None = None,
        metadata: Mapping[str, Any] | None = None,
        from_node_field: str = "from_node",
        to_node_field: str = "to_node",
        task_field: str = "task",
        confidence_field: str = "confidence",
        metadata_field: str = "metadata",
    ) -> "GraphTransition":
        from_node = _extract_value(value, from_node_field)
        to_node = _extract_value(value, to_node_field)
        resolved_task = task if task is not None else _extract_value(value, task_field, required=False, default="")
        resolved_confidence = confidence if confidence is not None else _extract_value(
            value,
            confidence_field,
            required=False,
            default=1.0,
        )
        resolved_metadata = dict(metadata) if metadata is not None else dict(
            _extract_value(value, metadata_field, required=False, default={}) or {}
        )
        return cls(
            from_node=str(from_node),
            to_node=str(to_node),
            task=str(resolved_task),
            confidence=float(resolved_confidence),
            metadata=resolved_metadata,
            raw_item=value,
        )


TransitionExecutor = Callable[[GraphTransition], Any]
AuditHook = Callable[[dict[str, Any]], None]


class LangGraphPawAdapter:
    """Gateway-backed adapter for LangGraph-style transition execution."""

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

    def execute_native_transition(
        self,
        value: Any,
        executor: TransitionExecutor,
        *,
        task: str | None = None,
        confidence: float | None = None,
        metadata: Mapping[str, Any] | None = None,
        from_node_field: str = "from_node",
        to_node_field: str = "to_node",
        task_field: str = "task",
        confidence_field: str = "confidence",
        metadata_field: str = "metadata",
    ) -> dict[str, Any]:
        return self.execute_transition(
            GraphTransition.from_value(
                value,
                task=task,
                confidence=confidence,
                metadata=metadata,
                from_node_field=from_node_field,
                to_node_field=to_node_field,
                task_field=task_field,
                confidence_field=confidence_field,
                metadata_field=metadata_field,
            ),
            executor,
        )


def wrap_langgraph_transition_executor(
    runtime: PawlyRuntime,
    executor: TransitionExecutor,
    *,
    audit_hook: AuditHook | None = None,
    approval_handler=None,
    gateway: GatewayProtocol | None = None,
    task: str | None = None,
    confidence: float | None = None,
    metadata: Mapping[str, Any] | None = None,
    from_node_field: str = "from_node",
    to_node_field: str = "to_node",
    task_field: str = "task",
    confidence_field: str = "confidence",
    metadata_field: str = "metadata",
) -> Callable[[Any], dict[str, Any]]:
    adapter = LangGraphPawAdapter(runtime, audit_hook=audit_hook, approval_handler=approval_handler, gateway=gateway)

    def wrapped(value: Any) -> dict[str, Any]:
        return adapter.execute_native_transition(
            value,
            executor,
            task=task,
            confidence=confidence,
            metadata=metadata,
            from_node_field=from_node_field,
            to_node_field=to_node_field,
            task_field=task_field,
            confidence_field=confidence_field,
            metadata_field=metadata_field,
        )

    return wrapped


def wrap_langgraph_transitions(
    runtime: PawlyRuntime,
    transitions: Iterable[Any],
    *,
    audit_hook: AuditHook | None = None,
    approval_handler=None,
    gateway: GatewayProtocol | None = None,
    executor_field: str = "executor",
    transition_name_field: str = "name",
    task: str | None = None,
    confidence: float | None = None,
    metadata: Mapping[str, Any] | None = None,
    from_node_field: str = "from_node",
    to_node_field: str = "to_node",
    task_field: str = "task",
    confidence_field: str = "confidence",
    metadata_field: str = "metadata",
) -> dict[str, Callable[[Any], dict[str, Any]]]:
    wrapped: dict[str, Callable[[Any], dict[str, Any]]] = {}
    for transition in transitions:
        transition_name = str(_extract_value(transition, transition_name_field, required=False, default=""))
        if not transition_name:
          from_node = _extract_value(transition, from_node_field)
          to_node = _extract_value(transition, to_node_field)
          transition_name = f"{from_node}->{to_node}"
        executor = _extract_value(transition, executor_field)
        if not callable(executor):
            raise TypeError(f"executor for transition '{transition_name}' must be callable")
        wrapped[transition_name] = wrap_langgraph_transition_executor(
            runtime,
            executor,
            audit_hook=audit_hook,
            approval_handler=approval_handler,
            gateway=gateway,
            task=task,
            confidence=confidence,
            metadata=metadata,
            from_node_field=from_node_field,
            to_node_field=to_node_field,
            task_field=task_field,
            confidence_field=confidence_field,
            metadata_field=metadata_field,
        )
    return wrapped


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


def _extract_value(value: Any, field: str, *, required: bool = True, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        if field in value:
            return value[field]
    elif hasattr(value, field):
        return getattr(value, field)
    if required:
        raise ValueError(f"unable to extract required field '{field}'")
    return default
