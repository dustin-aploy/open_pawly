from __future__ import annotations

from pawly.types import Decision, DecisionType


STATUS_ORDER = {
    DecisionType.ALLOW: 0,
    DecisionType.SIMULATE: 1,
    DecisionType.REQUIRE_APPROVAL: 2,
    DecisionType.DENY: 3,
}


def merge_decisions(*decisions: Decision) -> Decision:
    chosen = max(decisions, key=lambda item: STATUS_ORDER[item.type])
    reasons: list[str] = []
    reason_codes: list[str] = []
    matched: list[str] = []
    audit_tags: list[str] = []
    risk_scores: list[float] = []
    rewritten_action = None
    for decision in decisions:
        reasons.append(decision.reason)
        reason_codes.extend(decision.reason_codes)
        matched.extend(decision.matched_rules)
        audit_tags.extend(decision.audit_tags)
        if decision.risk_score is not None:
            risk_scores.append(decision.risk_score)
        if rewritten_action is None and decision.rewritten_action is not None:
            rewritten_action = decision.rewritten_action
    return Decision(
        type=chosen.type,
        reason="; ".join(list(dict.fromkeys(reasons))),
        source=chosen.source,
        reason_codes=list(dict.fromkeys(reason_codes)),
        matched_rules=list(dict.fromkeys(matched)),
        risk_score=max(risk_scores) if risk_scores else None,
        rewritten_action=rewritten_action,
        audit_tags=list(dict.fromkeys(audit_tags)),
    )
