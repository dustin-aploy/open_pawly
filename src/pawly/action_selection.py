from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pawly.contracts import Action, PolicyScore


BoundaryType = Literal["allow", "review", "blocked"]
DecisionSourceName = Literal["heuristic", "custom", "cloud", "fallback"]


@dataclass(slots=True)
class ActionCandidate:
    action: Action
    boundary_type: BoundaryType
    requires_review: bool
    decision_source: DecisionSourceName
    score: PolicyScore
    reason: str
    uncertainty: float | None

    def to_dict(self) -> dict[str, object]:
        return {
            "action": self.action.to_dict(),
            "boundary_type": self.boundary_type,
            "requires_review": self.requires_review,
            "decision_source": self.decision_source,
            "source": self.decision_source,
            "reason": self.reason,
            "uncertainty": self.uncertainty,
            "score": self.score.to_dict(),
        }


@dataclass(slots=True)
class ActionDecision:
    trace_id: str | None
    selected_action: Action | None
    requires_review: bool
    decision_source: DecisionSourceName | None
    boundary_type: Literal["allow", "review"] | None
    reason: str | None = None
    uncertainty: float | None = None
    protection: dict[str, object] | None = None
    allowed_actions: list[ActionCandidate] = field(default_factory=list)
    review_required_actions: list[ActionCandidate] = field(default_factory=list)
    blocked_actions: list[Action] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "trace_id": self.trace_id,
            "selected_action": None if self.selected_action is None else self.selected_action.to_dict(),
            "requires_review": self.requires_review,
            "decision_source": self.decision_source,
            "source": self.decision_source,
            "boundary_type": self.boundary_type,
            "reason": self.reason,
            "uncertainty": self.uncertainty,
            "protection": None if self.protection is None else dict(self.protection),
            "allowed_actions": [candidate.to_dict() for candidate in self.allowed_actions],
            "review_required_actions": [candidate.to_dict() for candidate in self.review_required_actions],
            "blocked_actions": [action.to_dict() for action in self.blocked_actions],
        }
