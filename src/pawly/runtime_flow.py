from __future__ import annotations

from typing import Any

from pawly.contracts import Decision, Intent
from pawly.memory.store import MemoryStore
from pawly.middleware.hooks import HookRegistry
from pawly.runtime_result import RuntimeDecisionArtifacts, RuntimeDecisionResult
from pawly.validator.validator import PawprintValidator, SchemaValidationError


def validate_intent_or_raise(validator: PawprintValidator, intent: Intent) -> None:
    intent_validation = validator.validate_intent(intent.to_dict())
    if not intent_validation.valid:
        raise SchemaValidationError("; ".join(intent_validation.errors))


def build_before_hook_payload(intent: Intent, agent_id: str) -> dict[str, object]:
    return {
        "intent": intent.to_dict(),
        "agent_id": agent_id,
    }


def remember_allowed_decision(memory_store: MemoryStore, intent: Intent, decision: Decision) -> None:
    if decision.type.value != "allow":
        return
    memory_store.remember(
        "default",
        {"intent": intent.to_dict(), "decision_type": decision.type.value},
    )


def finalize_runtime_artifacts(
    *,
    validator: PawprintValidator,
    audit_sink: Any,
    hooks: HookRegistry,
    decisions: list[dict[str, Any]],
    artifacts: RuntimeDecisionArtifacts,
) -> RuntimeDecisionResult:
    audit_sink.append(artifacts.event)
    decision_validation = validator.validate_decision(artifacts.result.decision.to_dict())
    if not decision_validation.valid:
        raise SchemaValidationError("; ".join(decision_validation.errors))

    result_payload = artifacts.result.to_dict()
    decisions.append(result_payload)
    hooks.run_after(result_payload)
    return artifacts.result
