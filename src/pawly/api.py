from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pawly.action_selection import ActionDecision
from pawly.contracts import Action
from pawly.pawprint_loader import PawprintConfig
from pawly.runtime import DecisionEngine
from pawly.goal import GoalExecutionResult, Pawly
from pawly.skill_registry import SkillRegistry


def decide(
    pawprint: str | Path,
    *,
    state: Mapping[str, Any] | None,
    actions: Sequence[Action],
    pawprint_config: PawprintConfig | None = None,
    **engine_kwargs: Any,
) -> ActionDecision:
    engine = DecisionEngine(pawprint, **engine_kwargs)
    return engine.decide_actions(state, actions, pawprint_config)


def run(
    pawprint: str | Path,
    *,
    task: str,
    action: str,
    confidence: float,
    metadata: dict[str, Any] | None = None,
    **engine_kwargs: Any,
) -> dict[str, Any]:
    engine = DecisionEngine(pawprint, **engine_kwargs)
    return engine.evaluate(task, action, confidence, metadata)


def run_actions(
    pawprint: str | Path,
    *,
    state: Mapping[str, Any] | None,
    actions: Sequence[Action],
    context: Mapping[str, Any] | None = None,
    skill_registry: SkillRegistry | None = None,
    pawprint_config: PawprintConfig | None = None,
    **engine_kwargs: Any,
) -> dict[str, Any]:
    engine = DecisionEngine(pawprint, **engine_kwargs)
    if skill_registry is not None:
        engine.register_skills(skill_registry)
    return engine.run_actions(
        state=state,
        actions=actions,
        context=context,
        pawprint_config=pawprint_config,
    )


def achieve(
    pawprint: str | Path,
    *,
    objective: str,
    context: Mapping[str, Any] | None = None,
    constraints: Mapping[str, Any] | None = None,
    skill_registry: SkillRegistry | None = None,
    **engine_kwargs: Any,
) -> GoalExecutionResult:
    return Pawly(str(pawprint), skill_registry=skill_registry, **engine_kwargs).achieve(
        objective=objective,
        context=context,
        constraints=constraints,
    )
