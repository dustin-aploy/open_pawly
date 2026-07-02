from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pawly.contracts import Action, PolicyScore
from pawly.policy.base import Policy


def build_scoring_state(
    *,
    state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if state is None:
        return {}
    return dict(state)


def score_actions(
    *,
    policy: Policy,
    actions: Sequence[Action],
    state: Mapping[str, Any] | None = None,
) -> list[PolicyScore]:
    return policy.evaluate(build_scoring_state(state=state), actions)
