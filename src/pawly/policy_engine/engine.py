from __future__ import annotations

import re

from pawly.backends.risk import LocalRiskProvider, RiskContext, RiskProvider
from pawly.escalation.patterns import text_matches_rule
from pawly.pawprint_loader import PawprintConfig, parse_pawprint_document
from pawly.types import DecisionSource, DecisionType, Intent, PolicyEvaluation

def evaluate_pawprint(
    intent: Intent,
    pawprint: PawprintConfig | dict,
    *,
    risk_provider: RiskProvider | None = None,
) -> PolicyEvaluation:
    pawprint = _coerce_worker(pawprint)
    text = intent.text()
    capabilities = pawprint.capabilities
    simulate_requested = bool(intent.metadata.get("simulate") or intent.action.arguments.get("simulate"))

    auto_matches = _match_rules(text, pawprint.allowed_actions, _matches_boundary_rule)
    ask_first_matches = _match_rules(text, pawprint.review_actions, _matches_boundary_rule)
    never_matches = _match_rules(text, pawprint.blocked_actions, _matches_boundary_rule)
    capability_matches = _match_rules(text, capabilities, text_matches_rule)
    handoff_matches: list[str] = []
    if intent.confidence < 0.7:
        handoff_matches.append("low-confidence-handoff")
    handoff_matches = list(dict.fromkeys(handoff_matches))

    capability_matched = not capabilities or bool(capability_matches)
    provider = risk_provider or LocalRiskProvider()
    risk_score = provider.score(
        RiskContext(
            intent=intent,
            ask_first_matches=ask_first_matches,
            never_matches=never_matches,
            capability_matched=capability_matched,
            handoff_matches=handoff_matches,
        )
    )

    if never_matches:
        return PolicyEvaluation(
            decision_type=DecisionType.DENY,
            reason=f"intent violates forbidden boundary: {never_matches[0]}",
            reason_codes=["boundary_never"],
            matched_rules=never_matches,
            risk_score=risk_score,
            audit_tags=["boundary:never", "risk:high"],
        )

    if ask_first_matches:
        return PolicyEvaluation(
            decision_type=DecisionType.REQUIRE_APPROVAL,
            reason=f"intent requires approval before proceeding: {ask_first_matches[0]}",
            source=DecisionSource.RULE,
            reason_codes=["boundary_ask_first"],
            matched_rules=ask_first_matches,
            risk_score=risk_score,
            audit_tags=["boundary:ask_first", "risk:elevated"],
        )

    if handoff_matches:
        return PolicyEvaluation(
            decision_type=DecisionType.REQUIRE_APPROVAL,
            reason=f"intent triggered handoff conditions: {handoff_matches[0]}",
            source=DecisionSource.RULE,
            reason_codes=["handoff_triggered"],
            matched_rules=handoff_matches,
            risk_score=risk_score,
            audit_tags=["handoff:triggered", "risk:elevated"],
        )

    if not capability_matched:
        return PolicyEvaluation(
            decision_type=DecisionType.REQUIRE_APPROVAL,
            reason="intent does not clearly match a declared capability",
            source=DecisionSource.RULE,
            reason_codes=["capability_mismatch"],
            matched_rules=capabilities,
            risk_score=risk_score,
            audit_tags=["capability:unclear", "risk:moderate"],
        )

    if simulate_requested:
        return PolicyEvaluation(
            decision_type=DecisionType.SIMULATE,
            reason="intent requested simulation instead of real execution",
            source=DecisionSource.RULE,
            reason_codes=["simulate_requested"],
            matched_rules=auto_matches or capability_matches,
            risk_score=risk_score,
            audit_tags=["execution:simulated", "risk:low"],
        )

    matched_rules = auto_matches or capability_matches
    return PolicyEvaluation(
        decision_type=DecisionType.ALLOW,
        reason="intent is within declared Pawprint boundaries",
        source=DecisionSource.RULE,
        reason_codes=["allow_within_boundaries"],
        matched_rules=matched_rules,
        risk_score=risk_score,
        audit_tags=["boundary:auto", "capability:match", "handoff:clear", "risk:low"],
    )


def _match_rules(text: str, rules: list[str], matcher) -> list[str]:
    matches: list[str] = []
    for rule in rules:
        if rule and matcher(text, rule):
            matches.append(rule)
    return list(dict.fromkeys(matches))


def _match_handoff(text: str, rules: list[str]) -> list[str]:
    matches: list[str] = []
    for rule in rules:
        if rule and _matches_handoff_rule(text, rule):
            matches.append(rule)
    return matches


def _coerce_worker(pawprint: PawprintConfig | dict) -> PawprintConfig:
    if isinstance(pawprint, PawprintConfig):
        return pawprint
    return parse_pawprint_document(dict(pawprint))


def _ensure_reason_prefix(reason: str, marker: str) -> str:
    if marker in reason:
        return reason
    return f"{marker}: {reason}"


def _matches_boundary_rule(text: str, rule: str) -> bool:
    if rule.lower() in text.lower():
        return True
    text_tokens = set(re.findall(r"[a-z0-9]+", text.lower()))
    rule_tokens = set(re.findall(r"[a-z0-9]+", rule.lower()))
    return len(text_tokens & rule_tokens) >= max(2, len(rule_tokens))


def _matches_handoff_rule(text: str, rule: str) -> bool:
    if rule.lower() in text.lower():
        return True
    text_tokens = set(re.findall(r"[a-z0-9]+", text.lower()))
    rule_tokens = set(re.findall(r"[a-z0-9]+", rule.lower()))
    overlap = text_tokens & rule_tokens
    if len(rule_tokens) >= 4:
        return len(overlap) >= 3
    return text_matches_rule(text, rule)
