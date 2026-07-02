from __future__ import annotations

from pawly.contracts import Decision, DecisionSource, DecisionState
from pawly.budget.checker import BudgetResult
from pawly.policy_engine.decision import merge_decisions
from pawly.policy_engine.models import PolicyEvaluation


def apply_runtime_overlays(policy_evaluation: PolicyEvaluation, budget_result: BudgetResult) -> tuple[Decision, dict[str, object]]:
    policy_decision = policy_evaluation.to_decision()
    budget_decision = Decision(
        type=DecisionState.DENY if budget_result.exhausted else DecisionState.ALLOW,
        reason="budget exhaustion policy triggered" if budget_result.exhausted else "budget remains within limits",
        source=DecisionSource.RULE.value,
        reason_codes=["budget_exhausted"] if budget_result.exhausted else ["budget_ok"],
        risk_score=0.9 if budget_result.exhausted else 0.1,
        audit_tags=["budget:exhausted"] if budget_result.exhausted else ["budget:ok"],
    )
    decision = merge_decisions(policy_decision, budget_decision)
    return decision, build_runtime_overlays(policy_evaluation, budget_result, decision)


def build_runtime_overlays(
    policy_evaluation: PolicyEvaluation,
    budget_result: BudgetResult,
    decision: Decision,
) -> dict[str, object]:
    overlay_applied = policy_evaluation.decision_type != decision.type or budget_result.exhausted or bool(budget_result.warnings)
    return {
        "overlay_applied": overlay_applied,
        "budget": {
            "exhausted": budget_result.exhausted,
            "warnings": budget_result.warnings,
            "consumed": budget_result.consumed,
        },
        "merged_decision_type": decision.type.value,
    }
