from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any

from pawly.contracts import Action, PolicyScore


class ScoringPolicyUnavailableError(RuntimeError):
    """Raised when a scoring policy is configured but cannot be used."""


class Policy(ABC):
    """Scores already-filtered candidate actions without executing or constraining them."""

    name = "custom"
    source = "custom"
    policy_source = "custom"
    supports_scoring = None
    supports_scoring_decision = False

    def source_name(self) -> str:
        return str(getattr(self, "source", getattr(self, "policy_source", "custom")))

    def is_scoring_capable(self) -> bool:
        support_mode = getattr(self, "supports_scoring", getattr(self, "supports_scoring_decision", False))
        if support_mode is None:
            support_mode = getattr(self, "supports_scoring_decision", False)
        return bool(support_mode is True)

    def scoring_support_mode(self) -> str:
        support_mode = getattr(self, "supports_scoring", getattr(self, "supports_scoring_decision", False))
        if support_mode is None:
            support_mode = getattr(self, "supports_scoring_decision", False)
        if support_mode is True:
            return "native"
        if support_mode == "fallback":
            return "fallback"
        return "none"

    def is_scoring_available(self) -> bool:
        return self.is_scoring_capable()

    def scoring_unavailable_reason(self) -> str | None:
        return None

    def local_policy(self) -> "Policy":
        return self

    def fallback_scoring_policy(self) -> "Policy | None":
        return None

    @abstractmethod
    def evaluate(self, state: Any, actions: Sequence[Action]) -> list[PolicyScore]:
        """Return one score per action in the same order as the input sequence."""


_SOURCE_PREFIX = "source:"


def score_source(score: PolicyScore, default_source: str = "custom") -> str:
    for tag in score.audit_tags:
        if tag.startswith(_SOURCE_PREFIX):
            return tag.split(":", 1)[1]
    return default_source


def tag_scores(scores: Sequence[PolicyScore], source: str) -> list[PolicyScore]:
    tagged_scores: list[PolicyScore] = []
    source_tag = f"{_SOURCE_PREFIX}{source}"
    for score in scores:
        audit_tags = [tag for tag in score.audit_tags if not tag.startswith(_SOURCE_PREFIX)]
        audit_tags.append(source_tag)
        tagged_scores.append(
            PolicyScore(
                risk_score=score.risk_score,
                reason_codes=list(score.reason_codes),
                matched_rules=list(score.matched_rules),
                audit_tags=audit_tags,
                uncertainty=score.uncertainty,
            )
        )
    return tagged_scores
