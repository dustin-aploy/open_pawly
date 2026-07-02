from __future__ import annotations

from pawly.contracts import Intent
from pawly.loader.schema_loader import load_pawprint_version
from pawly.protected_oss import apply_extraction_guardrail
from pawly.runtime_decision import evaluate_runtime_decision
from pawly.runtime_bootstrap import RuntimeConfig, RuntimeServices
from pawly.runtime_flow import (
    build_before_hook_payload,
    finalize_runtime_artifacts,
    remember_allowed_decision,
    validate_intent_or_raise,
)
from pawly.runtime_result import RuntimeDecisionResult, build_runtime_decision_artifacts


def evaluate_runtime_intent(
    *,
    config: RuntimeConfig,
    services: RuntimeServices,
    intent: Intent,
) -> RuntimeDecisionResult:
    validate_intent_or_raise(services.validator, intent)
    services.hooks.run_before(build_before_hook_payload(intent, config.pawprint_config.id))

    decision_state = evaluate_runtime_decision(
        policy=config.reviewer_policy,
        intent=intent,
        pawprint=config.pawprint_config,
        raw_pawprint_config=config.raw_pawprint_config,
        budget_state=services.budget_state,
    )
    guarded_decision, guarded_runtime_overlays = apply_extraction_guardrail(
        pawprint=config.pawprint_config,
        policy_evaluation=decision_state.policy_evaluation,
        decision=decision_state.decision,
        runtime_overlays=decision_state.runtime_overlays,
        intent=intent,
    )
    remember_allowed_decision(services.memory_store, intent, guarded_decision)

    artifacts = build_runtime_decision_artifacts(
        event_id=services.ids.next_event_id(),
        decision_id=services.ids.next_decision_id(),
        agent_id=config.pawprint_config.id,
        pawprint_version=load_pawprint_version(),
        intent=intent,
        policy_evaluation=decision_state.policy_evaluation,
        runtime_overlays=guarded_runtime_overlays,
        decision=guarded_decision,
        budget_result=decision_state.budget_result,
    )
    return finalize_runtime_artifacts(
        validator=services.validator,
        audit_sink=services.audit_sink,
        hooks=services.hooks,
        decisions=services.decisions,
        artifacts=artifacts,
    )
