from __future__ import annotations

from dataclasses import replace
from dataclasses import dataclass, field
from typing import Any, Callable

from pawly.gateway import GatewayProtocol
from pawly.gateway.adapter_support import build_gateway, execute_adapter_action, metadata_from_intent
from pawly.runtime import PawlyRuntime


@dataclass(slots=True)
class SkillInvocation:
    skill_name: str
    task: str
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)
    approved_action_name: str | None = None


SkillExecutor = Callable[[SkillInvocation], Any]
AuditHook = Callable[[dict[str, Any]], None]


class ClaudeSkillsPawAdapter:
    """Small Pawly adapter stub for wrapping skill invocations with execution-boundary checks."""

    def __init__(
        self,
        runtime: PawlyRuntime,
        audit_hook: AuditHook | None = None,
        approval_handler=None,
        gateway: GatewayProtocol | None = None,
    ) -> None:
        self.gateway = build_gateway(runtime, approval_handler=approval_handler, gateway=gateway)
        self.audit_hook = audit_hook

    def execute_skill(self, invocation: SkillInvocation, executor: SkillExecutor) -> dict[str, Any]:
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
