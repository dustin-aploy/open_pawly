from __future__ import annotations

from pawly.backends.risk import LocalRiskProvider, RiskContext
from pawly.types import Intent


def score_policy_risk(
    *,
    intent: Intent,
    ask_first_matches: list[str],
    never_matches: list[str],
    capability_matched: bool,
    handoff_matches: list[str],
) -> float:
    provider = LocalRiskProvider()
    return provider.score(
        RiskContext(
            intent=intent,
            ask_first_matches=ask_first_matches,
            never_matches=never_matches,
            capability_matched=capability_matched,
            handoff_matches=handoff_matches,
        )
    )
