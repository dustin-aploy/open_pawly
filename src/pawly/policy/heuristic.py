from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pawly.contracts import Action, PolicyScore

from .base import Policy, tag_scores


_HIGH_IMPACT_TERMS = frozenset({"approve", "delete", "deploy", "publish", "refund", "remove", "send"})
_LOW_IMPACT_TERMS = frozenset({"answer", "draft", "fetch", "list", "preview", "read", "summarize", "view"})


class HeuristicPolicy(Policy):
    """Deterministic OSS baseline for ranking already-allowed actions."""

    name = "heuristic"
    source = "heuristic"
    policy_source = "heuristic"
    supports_scoring = "fallback"
    supports_scoring_decision = False

    def evaluate(self, state: Any, actions: Sequence[Action]) -> list[PolicyScore]:
        preferred_targets = _preferred_targets(state)
        recent_failures = _recent_failures(state)
        return tag_scores(
            [
                _score_action(
                    action,
                    preferred_targets=preferred_targets,
                    recent_failures=recent_failures,
                )
                for action in actions
            ],
            self.source_name(),
        )


DefaultOssPolicy = HeuristicPolicy


def _score_action(
    action: Action,
    *,
    preferred_targets: set[str],
    recent_failures: set[str],
) -> PolicyScore:
    score = 0.5
    reason_codes: list[str] = []
    matched_rules: list[str] = []
    audit_tags: list[str] = ["policy:heuristic"]

    if action.target:
        normalized_target = action.target.strip().lower()
        if normalized_target in preferred_targets:
            score -= 0.1
            reason_codes.append("preferred_target")
            audit_tags.append(f"target:{normalized_target}")
        else:
            score += 0.05
            reason_codes.append("unrecognized_target")
    else:
        score += 0.03
        reason_codes.append("missing_target")

    normalized_name = action.name.strip().lower()
    if normalized_name in recent_failures:
        score += 0.2
        reason_codes.append("recent_failure")
        audit_tags.append("history:retry")

    action_terms = _tokenize(action.name)
    if action_terms & _LOW_IMPACT_TERMS:
        score -= 0.05
        reason_codes.append("low_friction_action")

    complexity_penalty = _complexity_penalty(action)
    if complexity_penalty:
        score += complexity_penalty
        reason_codes.append("action_complexity")

    impact_adjustment, impact_code = _impact_adjustment(action.name)
    score += impact_adjustment
    if impact_code is not None:
        reason_codes.append(impact_code)

    return PolicyScore(
        risk_score=_clamp(score),
        reason_codes=reason_codes,
        matched_rules=matched_rules,
        audit_tags=audit_tags,
    )


def _preferred_targets(state: Any) -> set[str]:
    if not isinstance(state, Mapping):
        return set()
    raw_targets = state.get("preferred_targets", [])
    if not isinstance(raw_targets, Sequence) or isinstance(raw_targets, (str, bytes)):
        return set()
    return {str(item).strip().lower() for item in raw_targets if str(item).strip()}


def _recent_failures(state: Any) -> set[str]:
    if not isinstance(state, Mapping):
        return set()
    raw_failures = state.get("recent_failures", [])
    if not isinstance(raw_failures, Sequence) or isinstance(raw_failures, (str, bytes)):
        return set()
    return {str(item).strip().lower() for item in raw_failures if str(item).strip()}


def _complexity_penalty(action: Action) -> float:
    penalty = 0.0
    if len(action.arguments) > 4:
        penalty += 0.05
    for value in action.arguments.values():
        if isinstance(value, Mapping):
            penalty += 0.05
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            penalty += 0.03
    return min(penalty, 0.15)


def _impact_adjustment(action_name: str) -> tuple[float, str | None]:
    terms = _tokenize(action_name)
    if terms & _HIGH_IMPACT_TERMS:
        return 0.2, "high_impact_action"
    if terms & _LOW_IMPACT_TERMS:
        return -0.1, "low_impact_action"
    return 0.0, None


def _tokenize(value: str) -> set[str]:
    normalized = value.replace("-", " ").replace("_", " ").lower()
    return {token for token in normalized.split() if token}


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, round(value, 4)))
