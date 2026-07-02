from __future__ import annotations

from dataclasses import dataclass

from pawly.contracts import Decision
from pawly.backends.reviewer import ReviewerPolicy, evaluate_reviewer_policy
from pawly.budget.checker import BudgetResult, check_budget
from pawly.budget.state import BudgetState
from pawly.pawprint_loader import PawprintConfig
from pawly.policy_engine.models import PolicyEvaluation
from pawly.policy_engine.runtime_overlay import apply_runtime_overlays
from pawly.types import Intent


@dataclass(slots=True)
class RuntimeDecisionState:
    policy_evaluation: PolicyEvaluation
    budget_result: BudgetResult
    decision: Decision
    runtime_overlays: dict[str, object]


def evaluate_core_policy(
    policy: ReviewerPolicy,
    *,
    intent: Intent,
    pawprint: PawprintConfig,
) -> PolicyEvaluation:
    return evaluate_reviewer_policy(policy, intent, pawprint)


def evaluate_runtime_decision(
    *,
    policy: ReviewerPolicy,
    intent: Intent,
    pawprint: PawprintConfig,
    raw_pawprint_config: dict,
    budget_state: BudgetState,
) -> RuntimeDecisionState:
    policy_evaluation = evaluate_core_policy(
        policy,
        intent=intent,
        pawprint=pawprint,
    )
    budget_result = check_budget(raw_pawprint_config, budget_state, intent)
    decision, runtime_overlays = apply_runtime_overlays(policy_evaluation, budget_result)
    return RuntimeDecisionState(
        policy_evaluation=policy_evaluation,
        budget_result=budget_result,
        decision=decision,
        runtime_overlays=runtime_overlays,
    )
