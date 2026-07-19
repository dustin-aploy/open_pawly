from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pawly.action_selection import ActionDecision
from pawly.contracts import Action
from pawly.pawprint_loader import PawprintConfig
from pawly.runtime import DecisionEngine
from pawly.goal import GoalExecutionResult, Pawly
from pawly.services import AuditService, PolicyService, SkillService
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
    skills: SkillService | SkillRegistry | Mapping[str, Any] | None = None,
    skill_registry: SkillRegistry | None = None,
    pawprint_config: PawprintConfig | None = None,
    **engine_kwargs: Any,
) -> dict[str, Any]:
    engine = DecisionEngine(pawprint, **engine_kwargs)
    if isinstance(skills, SkillService):
        engine.register_skills(skills.to_registry())
    elif isinstance(skills, SkillRegistry):
        engine.register_skills(skills)
    elif skills is not None:
        engine.register_skills(SkillService.local(skills).to_registry())
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
    skills: SkillService | SkillRegistry | Mapping[str, Any] | None = None,
    policy: PolicyService | None = None,
    audit: AuditService | None = None,
) -> GoalExecutionResult:
    return Pawly(str(pawprint), skills=skills, policy=policy, audit=audit).achieve(
        objective=objective,
        context=context,
        constraints=constraints,
    )
