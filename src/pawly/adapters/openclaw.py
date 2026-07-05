from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Callable, Iterable, Mapping

from pawly.gateway import GatewayProtocol
from pawly.gateway.adapter_support import build_gateway, execute_adapter_action, metadata_from_intent
from pawly.runtime import PawlyRuntime


@dataclass(slots=True)
class OpenClawActionContext:
    task: str
    action: str
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)
    raw_item: Any = None

    @classmethod
    def from_value(
        cls,
        value: Any,
        *,
        task: str | None = None,
        confidence: float | None = None,
        metadata: Mapping[str, Any] | None = None,
        action_field: str = "action",
        task_field: str = "task",
        confidence_field: str = "confidence",
        metadata_field: str = "metadata",
    ) -> "OpenClawActionContext":
        action = _extract_value(value, action_field)
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
            task=str(resolved_task),
            action=str(action),
            confidence=float(resolved_confidence),
            metadata=resolved_metadata,
            raw_item=value,
        )


ToolExecutor = Callable[[OpenClawActionContext], Any]
AuditHook = Callable[[dict[str, Any]], None]


class OpenClawPawAdapter:
    """Gateway-backed adapter for OpenClaw-style tool boundaries."""

    def __init__(
        self,
        runtime: PawlyRuntime,
        audit_hook: AuditHook | None = None,
        approval_handler=None,
        gateway: GatewayProtocol | None = None,
    ) -> None:
        self.gateway = build_gateway(runtime, approval_handler=approval_handler, gateway=gateway)
        self.audit_hook = audit_hook

    def execute_tool(self, context: OpenClawActionContext, executor: ToolExecutor) -> dict[str, Any]:
        return execute_adapter_action(
            gateway=self.gateway,
            item=context,
            task=context.task,
            action=context.action,
            confidence=context.confidence,
            metadata=context.metadata,
            executor=executor,
            remap=lambda current, intent: replace(
                current,
                task=intent.summary,
                action=intent.action.name,
                confidence=intent.confidence,
                metadata=metadata_from_intent(intent),
            ),
            audit_hook=self.audit_hook,
            audit_payload=lambda outcome: {
                "framework": "openclaw",
                "event": "pre-tool-execution",
                "task": context.task,
                "action": context.action,
                "decision_type": outcome["type"],
                "executed": outcome["execution"]["executed"],
            },
        )

    def execute_native_tool(
        self,
        value: Any,
        executor: ToolExecutor,
        *,
        task: str | None = None,
        confidence: float | None = None,
        metadata: Mapping[str, Any] | None = None,
        action_field: str = "action",
        task_field: str = "task",
        confidence_field: str = "confidence",
        metadata_field: str = "metadata",
    ) -> dict[str, Any]:
        return self.execute_tool(
            OpenClawActionContext.from_value(
                value,
                task=task,
                confidence=confidence,
                metadata=metadata,
                action_field=action_field,
                task_field=task_field,
                confidence_field=confidence_field,
                metadata_field=metadata_field,
            ),
            executor,
        )


def wrap_openclaw_tool_executor(
    runtime: PawlyRuntime,
    executor: ToolExecutor,
    *,
    audit_hook: AuditHook | None = None,
    approval_handler=None,
    gateway: GatewayProtocol | None = None,
    task: str | None = None,
    confidence: float | None = None,
    metadata: Mapping[str, Any] | None = None,
    action_field: str = "action",
    task_field: str = "task",
    confidence_field: str = "confidence",
    metadata_field: str = "metadata",
) -> Callable[[Any], dict[str, Any]]:
    adapter = OpenClawPawAdapter(runtime, audit_hook=audit_hook, approval_handler=approval_handler, gateway=gateway)

    def wrapped(value: Any) -> dict[str, Any]:
        return adapter.execute_native_tool(
            value,
            executor,
            task=task,
            confidence=confidence,
            metadata=metadata,
            action_field=action_field,
            task_field=task_field,
            confidence_field=confidence_field,
            metadata_field=metadata_field,
        )

    return wrapped


def wrap_openclaw_tools(
    runtime: PawlyRuntime,
    tools: Iterable[Any],
    *,
    audit_hook: AuditHook | None = None,
    approval_handler=None,
    gateway: GatewayProtocol | None = None,
    executor_field: str = "executor",
    action_field: str = "action",
    task: str | None = None,
    confidence: float | None = None,
    metadata: Mapping[str, Any] | None = None,
    task_field: str = "task",
    confidence_field: str = "confidence",
    metadata_field: str = "metadata",
) -> dict[str, Callable[[Any], dict[str, Any]]]:
    wrapped: dict[str, Callable[[Any], dict[str, Any]]] = {}
    for tool in tools:
        action_name = str(_extract_value(tool, action_field))
        executor = _extract_value(tool, executor_field)
        if not callable(executor):
            raise TypeError(f"executor for tool '{action_name}' must be callable")
        wrapped[action_name] = wrap_openclaw_tool_executor(
            runtime,
            executor,
            audit_hook=audit_hook,
            approval_handler=approval_handler,
            gateway=gateway,
            task=task,
            confidence=confidence,
            metadata=metadata,
            action_field=action_field,
            task_field=task_field,
            confidence_field=confidence_field,
            metadata_field=metadata_field,
        )
    return wrapped


def _extract_value(value: Any, field: str, *, required: bool = True, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        if field in value:
            return value[field]
    elif hasattr(value, field):
        return getattr(value, field)
    if required:
        raise ValueError(f"unable to extract required field '{field}'")
    return default
