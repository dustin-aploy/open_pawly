from __future__ import annotations

from typing import Any, Callable, TypeVar

from pawly.gateway import ExecutionGateway, GatewayProtocol
from pawly.runtime import PawlyRuntime


T = TypeVar("T")

AdapterExecutor = Callable[[T], Any]
AdapterRemap = Callable[[T, Any], T]
AuditHook = Callable[[dict[str, Any]], None]
AuditPayloadBuilder = Callable[[dict[str, Any]], dict[str, Any]]


def build_gateway(
    runtime: PawlyRuntime,
    *,
    approval_handler: object | None = None,
    gateway: GatewayProtocol | None = None,
) -> GatewayProtocol:
    return gateway or ExecutionGateway(runtime, approval_handler=approval_handler)


def metadata_from_intent(intent: Any) -> dict[str, Any]:
    metadata = dict(intent.metadata)
    for key, value in intent.action.arguments.items():
        if key != "task":
            metadata[key] = value
    return metadata


def execute_adapter_action(
    *,
    gateway: GatewayProtocol,
    item: T,
    task: str,
    action: str,
    confidence: float,
    metadata: dict[str, Any],
    executor: AdapterExecutor[T],
    remap: AdapterRemap[T],
    audit_hook: AuditHook | None = None,
    audit_payload: AuditPayloadBuilder | None = None,
) -> dict[str, Any]:
    outcome = gateway.execute(
        task=task,
        action=action,
        confidence=confidence,
        metadata=metadata,
        executor=lambda intent: executor(remap(item, intent)),
    )
    if audit_hook is not None and audit_payload is not None:
        audit_hook(audit_payload(outcome))
    return outcome
