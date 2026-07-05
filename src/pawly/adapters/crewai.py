from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Callable, Iterable, Mapping

from pawly.gateway import GatewayProtocol
from pawly.gateway.adapter_support import build_gateway, execute_adapter_action, metadata_from_intent
from pawly.runtime import PawlyRuntime


@dataclass(slots=True)
class CrewTaskAction:
    task: str
    action: str
    confidence: float
    payload: dict[str, Any] = field(default_factory=dict)
    raw_item: Any = None

    @classmethod
    def from_value(
        cls,
        value: Any,
        *,
        task: str | None = None,
        confidence: float | None = None,
        payload: Mapping[str, Any] | None = None,
        action_field: str = "action",
        task_field: str = "task",
        confidence_field: str = "confidence",
        payload_field: str = "payload",
    ) -> "CrewTaskAction":
        action = _extract_value(value, action_field)
        resolved_task = task if task is not None else _extract_value(value, task_field, required=False, default="")
        resolved_confidence = confidence if confidence is not None else _extract_value(
            value,
            confidence_field,
            required=False,
            default=1.0,
        )
        resolved_payload = dict(payload) if payload is not None else dict(
            _extract_value(value, payload_field, required=False, default={}) or {}
        )
        return cls(
            task=str(resolved_task),
            action=str(action),
            confidence=float(resolved_confidence),
            payload=resolved_payload,
            raw_item=value,
        )


TaskExecutor = Callable[[CrewTaskAction], Any]
AuditHook = Callable[[dict[str, Any]], None]


class CrewAIPawAdapter:
    """Gateway-backed adapter for CrewAI-style task execution boundaries."""

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

    def execute_native_task(
        self,
        value: Any,
        executor: TaskExecutor,
        *,
        task: str | None = None,
        confidence: float | None = None,
        payload: Mapping[str, Any] | None = None,
        action_field: str = "action",
        task_field: str = "task",
        confidence_field: str = "confidence",
        payload_field: str = "payload",
    ) -> dict[str, Any]:
        return self.execute_task(
            CrewTaskAction.from_value(
                value,
                task=task,
                confidence=confidence,
                payload=payload,
                action_field=action_field,
                task_field=task_field,
                confidence_field=confidence_field,
                payload_field=payload_field,
            ),
            executor,
        )


def wrap_crewai_task_executor(
    runtime: PawlyRuntime,
    executor: TaskExecutor,
    *,
    audit_hook: AuditHook | None = None,
    approval_handler=None,
    gateway: GatewayProtocol | None = None,
    task: str | None = None,
    confidence: float | None = None,
    payload: Mapping[str, Any] | None = None,
    action_field: str = "action",
    task_field: str = "task",
    confidence_field: str = "confidence",
    payload_field: str = "payload",
) -> Callable[[Any], dict[str, Any]]:
    adapter = CrewAIPawAdapter(runtime, audit_hook=audit_hook, approval_handler=approval_handler, gateway=gateway)

    def wrapped(value: Any) -> dict[str, Any]:
        return adapter.execute_native_task(
            value,
            executor,
            task=task,
            confidence=confidence,
            payload=payload,
            action_field=action_field,
            task_field=task_field,
            confidence_field=confidence_field,
            payload_field=payload_field,
        )

    return wrapped


def wrap_crewai_tasks(
    runtime: PawlyRuntime,
    tasks: Iterable[Any],
    *,
    audit_hook: AuditHook | None = None,
    approval_handler=None,
    gateway: GatewayProtocol | None = None,
    executor_field: str = "executor",
    action_field: str = "action",
    task: str | None = None,
    confidence: float | None = None,
    payload: Mapping[str, Any] | None = None,
    task_field: str = "task",
    confidence_field: str = "confidence",
    payload_field: str = "payload",
) -> dict[str, Callable[[Any], dict[str, Any]]]:
    wrapped_tasks: dict[str, Callable[[Any], dict[str, Any]]] = {}
    for task_def in tasks:
        action_name = str(_extract_value(task_def, action_field))
        executor = _extract_value(task_def, executor_field)
        if not callable(executor):
            raise TypeError(f"executor for task '{action_name}' must be callable")
        wrapped_tasks[action_name] = wrap_crewai_task_executor(
            runtime,
            executor,
            audit_hook=audit_hook,
            approval_handler=approval_handler,
            gateway=gateway,
            task=task,
            confidence=confidence,
            payload=payload,
            action_field=action_field,
            task_field=task_field,
            confidence_field=confidence_field,
            payload_field=payload_field,
        )
    return wrapped_tasks


def _extract_value(value: Any, field: str, *, required: bool = True, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        if field in value:
            return value[field]
    elif hasattr(value, field):
        return getattr(value, field)
    if required:
        raise ValueError(f"unable to extract required field '{field}'")
    return default
