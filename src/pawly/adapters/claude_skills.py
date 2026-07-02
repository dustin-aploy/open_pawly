from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Callable, Iterable, Mapping

from pawly.gateway import GatewayProtocol
from pawly.gateway.adapter_support import build_gateway, execute_adapter_action, metadata_from_intent
from pawly.runtime import PawlyRuntime


@dataclass(slots=True)
class ClaudeSkillInvocation:
    skill_name: str
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
        skill_name_field: str = "skill_name",
        task_field: str = "task",
        confidence_field: str = "confidence",
        metadata_field: str = "metadata",
    ) -> "ClaudeSkillInvocation":
        skill_name = _extract_value(value, skill_name_field)
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
            skill_name=str(skill_name),
            task=str(resolved_task),
            confidence=float(resolved_confidence),
            metadata=resolved_metadata,
            raw_item=value,
        )


SkillExecutor = Callable[[ClaudeSkillInvocation], Any]
AuditHook = Callable[[dict[str, Any]], None]


class ClaudeSkillsPawAdapter:
    """Gateway-backed adapter for Claude-style skill invocations."""

    def __init__(
        self,
        runtime: PawlyRuntime,
        audit_hook: AuditHook | None = None,
        approval_handler=None,
        gateway: GatewayProtocol | None = None,
    ) -> None:
        self.gateway = build_gateway(runtime, approval_handler=approval_handler, gateway=gateway)
        self.audit_hook = audit_hook

    def execute_skill(self, invocation: ClaudeSkillInvocation, executor: SkillExecutor) -> dict[str, Any]:
        return execute_adapter_action(
            gateway=self.gateway,
            item=invocation,
            task=invocation.task,
            action=invocation.skill_name,
            confidence=invocation.confidence,
            metadata=invocation.metadata,
            executor=executor,
            remap=lambda current, intent: replace(
                current,
                task=intent.summary,
                skill_name=intent.action.name,
                confidence=intent.confidence,
                metadata=metadata_from_intent(intent),
                approved_action_name=intent.action.name,
            ),
            audit_hook=self.audit_hook,
            audit_payload=lambda outcome: {
                "framework": "claude-skills",
                "event": "skill-execution",
                "skill_name": invocation.skill_name,
                "decision_type": outcome["type"],
                "executed": outcome["execution"]["executed"],
            },
        )

    def execute_native_skill(
        self,
        value: Any,
        executor: SkillExecutor,
        *,
        task: str | None = None,
        confidence: float | None = None,
        metadata: Mapping[str, Any] | None = None,
        skill_name_field: str = "skill_name",
        task_field: str = "task",
        confidence_field: str = "confidence",
        metadata_field: str = "metadata",
    ) -> dict[str, Any]:
        return self.execute_skill(
            ClaudeSkillInvocation.from_value(
                value,
                task=task,
                confidence=confidence,
                metadata=metadata,
                skill_name_field=skill_name_field,
                task_field=task_field,
                confidence_field=confidence_field,
                metadata_field=metadata_field,
            ),
            executor,
        )


def wrap_claude_skill_executor(
    runtime: PawlyRuntime,
    executor: SkillExecutor,
    *,
    audit_hook: AuditHook | None = None,
    approval_handler=None,
    gateway: GatewayProtocol | None = None,
    task: str | None = None,
    confidence: float | None = None,
    metadata: Mapping[str, Any] | None = None,
    skill_name_field: str = "skill_name",
    task_field: str = "task",
    confidence_field: str = "confidence",
    metadata_field: str = "metadata",
) -> Callable[[Any], dict[str, Any]]:
    adapter = ClaudeSkillsPawAdapter(
        runtime,
        audit_hook=audit_hook,
        approval_handler=approval_handler,
        gateway=gateway,
    )

    def wrapped(value: Any) -> dict[str, Any]:
        return adapter.execute_native_skill(
            value,
            executor,
            task=task,
            confidence=confidence,
            metadata=metadata,
            skill_name_field=skill_name_field,
            task_field=task_field,
            confidence_field=confidence_field,
            metadata_field=metadata_field,
        )

    return wrapped


def wrap_claude_skills(
    runtime: PawlyRuntime,
    skills: Iterable[Any],
    *,
    audit_hook: AuditHook | None = None,
    approval_handler=None,
    gateway: GatewayProtocol | None = None,
    executor_field: str = "executor",
    skill_name_field: str = "skill_name",
    task: str | None = None,
    confidence: float | None = None,
    metadata: Mapping[str, Any] | None = None,
    task_field: str = "task",
    confidence_field: str = "confidence",
    metadata_field: str = "metadata",
) -> dict[str, Callable[[Any], dict[str, Any]]]:
    wrapped_skills: dict[str, Callable[[Any], dict[str, Any]]] = {}
    for skill in skills:
        skill_name = str(_extract_value(skill, skill_name_field))
        executor = _extract_value(skill, executor_field)
        if not callable(executor):
            raise TypeError(f"executor for skill '{skill_name}' must be callable")
        wrapped_skills[skill_name] = wrap_claude_skill_executor(
            runtime,
            executor,
            audit_hook=audit_hook,
            approval_handler=approval_handler,
            gateway=gateway,
            task=task,
            confidence=confidence,
            metadata=metadata,
            skill_name_field=skill_name_field,
            task_field=task_field,
            confidence_field=confidence_field,
            metadata_field=metadata_field,
        )
    return wrapped_skills


def _extract_value(value: Any, field: str, *, required: bool = True, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        if field in value:
            return value[field]
    elif hasattr(value, field):
        return getattr(value, field)
    if required:
        raise ValueError(f"unable to extract required field '{field}'")
    return default
