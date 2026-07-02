from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from pawly.escalation.patterns import text_matches_rule
from pawly.types import Intent


EXTERNAL_SIDE_EFFECT_RULES = (
    "issue refund",
    "change account details",
    "delete customer records",
    "approve exception",
    "send external message",
    "publish update",
    "modify billing",
    "legal advice",
)


@dataclass(slots=True)
class RiskContext:
    intent: Intent
    ask_first_matches: list[str]
    never_matches: list[str]
    capability_matched: bool
    handoff_matches: list[str]


class RiskProvider(Protocol):
    name: str

    def score(self, context: RiskContext) -> float:
        ...


class LocalRiskProvider:
    name = "local-rules"

    def score(self, context: RiskContext) -> float:
        if context.never_matches:
            return 0.98

        score = 0.1
        if context.ask_first_matches:
            score += 0.35
        if context.handoff_matches:
            score += 0.2
        if not context.capability_matched:
            score += 0.35
        if _has_external_side_effect(context.intent):
            score += 0.15
        if context.intent.confidence < 0.7:
            score += 0.15
        return round(min(score, 0.95), 2)


class AdvancedRiskProviderStub:
    name = "cloud-risk"

    def score(self, context: RiskContext) -> float:
        del context
        raise NotImplementedError("Cloud risk providers are optional extensions and are not part of the OSS runtime path.")


def _has_external_side_effect(intent: Intent) -> bool:
    text = " ".join(
        part for part in [intent.summary, intent.action.name, intent.action.target or ""] if part
    )
    return any(text_matches_rule(text, rule) for rule in EXTERNAL_SIDE_EFFECT_RULES)
