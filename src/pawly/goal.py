from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pawly.contracts import Action
from pawly.pawprint_loader import PawprintConfig
from pawly.runtime import DecisionEngine
from pawly.skill_registry import MissingSkillRegistryError, SkillRegistry


@dataclass(slots=True)
class GoalExecutionResult:
    status: str
    objective: str
    result: Any = None
    action_receipt: dict[str, Any] = field(default_factory=dict)
    decision: dict[str, Any] | None = None
    error: str | None = None
    needs: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": self.status,
            "objective": self.objective,
            "result": self.result,
            "action_receipt": dict(self.action_receipt),
        }
        if self.decision is not None:
            payload["decision"] = dict(self.decision)
        if self.error is not None:
            payload["error"] = self.error
        if self.needs is not None:
            payload["needs"] = self.needs
        return payload


class Pawly:
    """Goal-oriented Pawly OSS facade.

    OSS resolves a delegated objective to one registered local capability using
    deterministic metadata matching, then reuses the existing control layer,
    execution gateway, audit, and policy path through DecisionEngine.run_actions.
    """

    def __init__(
        self,
        pawprint: str | None = None,
        *,
        api_key: str | None = None,
        project_id: str | None = None,
        skill_registry: SkillRegistry | None = None,
        **engine_kwargs: Any,
    ) -> None:
        self.api_key = api_key
        self.project_id = project_id
        self.engine: DecisionEngine | None = None
        if pawprint is not None:
            self.engine = DecisionEngine(pawprint, **engine_kwargs)
        if skill_registry is not None:
            self.register_skills(skill_registry)

    def register_skills(self, skill_registry: SkillRegistry) -> "Pawly":
        if self.engine is None:
            raise MissingSkillRegistryError("register_skills requires a local pawprint path.")
        self.engine.register_skills(skill_registry)
        return self

    def achieve(
        self,
        *,
        objective: str,
        context: Mapping[str, Any] | None = None,
        constraints: Mapping[str, Any] | None = None,
        pawprint_config: PawprintConfig | None = None,
    ) -> GoalExecutionResult:
        cleaned_objective = str(objective).strip()
        if not cleaned_objective:
            raise ValueError("objective must not be empty")
        if self.engine is None:
            return GoalExecutionResult(
                status="accepted",
                objective=cleaned_objective,
                result=None,
                action_receipt=_receipt(
                    objective=cleaned_objective,
                    status="accepted",
                    selected_action=None,
                    context=context,
                    constraints=constraints,
                    project_id=self.project_id,
                ),
            )
        if self.engine.skill_registry is None:
            raise MissingSkillRegistryError("achieve requires a registered SkillRegistry. Call register_skills(...) first.")

        action = _resolve_objective_to_action(cleaned_objective, self.engine.skill_registry)
        if action is None:
            return GoalExecutionResult(
                status="unsupported_goal",
                objective=cleaned_objective,
                result=None,
                needs="Register a skill whose capability matches this objective.",
                action_receipt=_receipt(
                    objective=cleaned_objective,
                    status="unsupported_goal",
                    selected_action=None,
                    context=context,
                    constraints=constraints,
                ),
            )

        run_result = self.engine.run_actions(
            state={
                "objective": cleaned_objective,
                "goal_interface": "achieve",
                "constraints": dict(constraints or {}),
            },
            actions=[action],
            context={
                **dict(context or {}),
                "objective": cleaned_objective,
                "constraints": dict(constraints or {}),
            },
            pawprint_config=pawprint_config,
        )
        status = str(run_result.get("status", "failed"))
        return GoalExecutionResult(
            status=status,
            objective=cleaned_objective,
            result=run_result.get("result"),
            decision=run_result.get("decision"),
            error=run_result.get("error"),
            action_receipt=_receipt(
                objective=cleaned_objective,
                status=status,
                selected_action=action,
                context=context,
                constraints=constraints,
                run_result=run_result,
            ),
        )


def achieve(
    pawprint: str,
    *,
    objective: str,
    context: Mapping[str, Any] | None = None,
    constraints: Mapping[str, Any] | None = None,
    skill_registry: SkillRegistry | None = None,
    **engine_kwargs: Any,
) -> GoalExecutionResult:
    return Pawly(pawprint, skill_registry=skill_registry, **engine_kwargs).achieve(
        objective=objective,
        context=context,
        constraints=constraints,
    )


def _resolve_objective_to_action(objective: str, skill_registry: SkillRegistry) -> Action | None:
    names = skill_registry.action_names()
    if not names:
        return None
    objective_tokens = _tokens(objective)
    ranked = sorted(
        names,
        key=lambda name: (_overlap_score(objective_tokens, _tokens(name)), -len(name)),
        reverse=True,
    )
    selected = ranked[0]
    selected_score = _overlap_score(objective_tokens, _tokens(selected))
    if selected_score == 0:
        return None
    return Action(name=selected, arguments={"objective": objective})


def _tokens(value: str) -> set[str]:
    return {token for token in re.split(r"[^a-zA-Z0-9]+", value.lower()) if token}


def _overlap_score(left: set[str], right: set[str]) -> int:
    return len(left & right)


def _receipt(
    *,
    objective: str,
    status: str,
    selected_action: Action | None,
    context: Mapping[str, Any] | None,
    constraints: Mapping[str, Any] | None,
    run_result: Mapping[str, Any] | None = None,
    project_id: str | None = None,
) -> dict[str, Any]:
    payload = {
        "objective": objective,
        "status": status,
        "interface": "pawly.achieve",
        "selected_capability": None if selected_action is None else selected_action.name,
        "execution_envelope": _execution_envelope(
            objective=objective,
            context=context,
            constraints=constraints,
            selected_action=selected_action,
        ),
        "context_keys": sorted(dict(context or {}).keys()),
        "constraints": dict(constraints or {}),
        "execution": None if run_result is None else dict(run_result).get("status"),
    }
    if project_id:
        payload["project_id"] = project_id
    return payload


def _execution_envelope(
    *,
    objective: str,
    context: Mapping[str, Any] | None,
    constraints: Mapping[str, Any] | None,
    selected_action: Action | None,
) -> dict[str, Any]:
    constraint_payload = dict(constraints or {})
    return {
        "objective": objective,
        "resource_scope": dict(context or {}),
        "allowed_capabilities": [] if selected_action is None else [selected_action.name],
        "financial_limits": _pick_limits(
            constraint_payload,
            {"max_cost", "max_refund", "max_refund_amount", "max_total_cost", "budget"},
        ),
        "execution_limits": _pick_limits(
            constraint_payload,
            {"deadline_seconds", "max_skill_calls", "max_duration_seconds", "timeout_seconds"},
        ),
        "approval_policy": {
            key: value
            for key, value in constraint_payload.items()
            if key.startswith("approval_") or key.endswith("_above") or key in {"requires_approval", "approval_required"}
        },
    }


def _pick_limits(payload: Mapping[str, Any], keys: set[str]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key in keys}
