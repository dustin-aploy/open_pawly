from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

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
        preferred_actions = _preferred_actions(state)
        recent_failures = _recent_failures(state)
        return tag_scores(
            [
                _score_action(
                    action,
                    preferred_targets=preferred_targets,
                    preferred_actions=preferred_actions,
                    recent_failures=recent_failures,
                )
                for action in actions
            ],
            self.source_name(),
        )


DefaultOssPolicy = HeuristicPolicy


@dataclass(frozen=True, slots=True)
class SmartPolicyDecision:
    decision: Literal["block", "review", "allow"]
    reason_code: str
    confidence: float
    source: str = "local_heuristic"


class HeuristicSmartPolicy:
    """Fast, deterministic local triage for Pawprint actions marked ``smart``."""

    def decide(self, state: Any, actions: Sequence[Action]) -> list[SmartPolicyDecision]:
        return [self._decide_one(state, action) for action in actions]

    def _decide_one(self, state: Any, action: Action) -> SmartPolicyDecision:
        name_terms = _tokenize(action.name)
        if not isinstance(state, Mapping):
            return SmartPolicyDecision("review", "smart_context_missing", 0.25)
        if state.get("policy_block") is True or state.get("account_restricted") is True:
            return SmartPolicyDecision("block", "smart_rule_blocked", 0.98)
        if state.get("requires_review") is True or state.get("risk_score", 0) >= 0.6:
            return SmartPolicyDecision("review", "smart_rule_review", 0.9)
        amount = action.arguments.get("amount", action.arguments.get("refund_amount"))
        if isinstance(amount, (int, float)) and amount > 50:
            return SmartPolicyDecision("review", "smart_amount_review", 0.9)
        if name_terms & _HIGH_IMPACT_TERMS and not state.get("verified", False):
            return SmartPolicyDecision("review", "smart_verification_required", 0.75)
        if state.get("context_complete") is False:
            return SmartPolicyDecision("review", "smart_context_incomplete", 0.75)
        return SmartPolicyDecision("allow", "smart_low_risk_allow", 0.7)


def _score_action(
    action: Action,
    *,
    preferred_targets: set[str],
    preferred_actions: set[str],
    recent_failures: set[str],
) -> PolicyScore:
    delivery_score = _score_known_message_delivery(action, recent_failures=recent_failures)
    if delivery_score is not None:
        return delivery_score

    score = 0.5
    reason_codes: list[str] = []
    matched_rules: list[str] = []
    audit_tags: list[str] = ["policy:heuristic", "risk:operational"]

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
    if normalized_name in preferred_actions:
        score -= 0.18
        reason_codes.append("preferred_action")
        audit_tags.append(f"action:{normalized_name}")

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


def _score_known_message_delivery(action: Action, *, recent_failures: set[str]) -> PolicyScore | None:
    """Score a reply to a known chat independently from generic action complexity.

    Inline callback buttons are handled by the same agent in a later request, so
    their nested JSON is not additional outbound risk. Links and embedded apps
    do change where a user can be sent and receive explicit adjustments instead.
    """
    normalized_name = action.name.strip().lower()
    if not normalized_name.endswith((".send_message", ".send_interactive_card", ".present_card")):
        return None
    arguments = action.arguments
    recipient = arguments.get("chat_id") or arguments.get("user_id") or arguments.get("to_user")
    if not str(recipient or "").strip():
        return None

    score = 0.18
    reason_codes = ["known_message_recipient"]
    audit_tags = ["policy:heuristic", "risk:operational", "action:known_message_delivery"]
    markup = arguments.get("reply_markup")
    buttons = _message_buttons(markup)
    if buttons:
        reason_codes.append("interactive_reply")
    if any(any(key in button for key in ("url", "login_url")) for button in buttons):
        score += 0.2
        reason_codes.append("external_link_in_reply")
    if any(any(key in button for key in ("web_app", "login_url")) for button in buttons):
        score += 0.22
        reason_codes.append("embedded_app_or_login")
    if normalized_name in recent_failures:
        score += 0.2
        reason_codes.append("recent_failure")
        audit_tags.append("history:retry")
    return PolicyScore(
        risk_score=_clamp(score),
        reason_codes=reason_codes,
        matched_rules=[],
        audit_tags=audit_tags,
    )


def _message_buttons(markup: Any) -> list[Mapping[str, Any]]:
    if not isinstance(markup, Mapping):
        return []
    rows = markup.get("inline_keyboard") or markup.get("buttons") or []
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        return []
    buttons: list[Mapping[str, Any]] = []
    for row in rows:
        values = row if isinstance(row, Sequence) and not isinstance(row, (str, bytes)) else [row]
        for button in values:
            if isinstance(button, Mapping):
                buttons.append(button)
    return buttons


def _preferred_targets(state: Any) -> set[str]:
    if not isinstance(state, Mapping):
        return set()
    raw_targets = state.get("preferred_targets", [])
    if not isinstance(raw_targets, Sequence) or isinstance(raw_targets, (str, bytes)):
        return set()
    return {str(item).strip().lower() for item in raw_targets if str(item).strip()}


def _preferred_actions(state: Any) -> set[str]:
    if not isinstance(state, Mapping):
        return set()
    raw_actions = state.get("preferred_actions", [])
    if not isinstance(raw_actions, Sequence) or isinstance(raw_actions, (str, bytes)):
        return set()
    return {str(item).strip().lower() for item in raw_actions if str(item).strip()}


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
