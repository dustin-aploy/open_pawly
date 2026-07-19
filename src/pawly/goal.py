from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from pawly.contracts import Action
from pawly.pawprint_loader import PawprintConfig
from pawly.runtime import DecisionEngine
from pawly.services import DEFAULT_CLOUD_CONSOLE_URL, AuditService, PolicyService, SkillService
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
    """Goal-oriented Open Pawly facade."""

    def __init__(
        self,
        pawprint: str | None = None,
        *,
        skills: SkillService | SkillRegistry | Mapping[str, Callable[[dict[str, Any], dict[str, Any]], Any]] | None = None,
        policy: PolicyService | None = None,
        audit: AuditService | None = None,
    ) -> None:
        self.skills = _resolve_skill_service(skills)
        self.policy = policy or PolicyService.local()
        self.audit = audit or AuditService()
        self.engine: DecisionEngine | None = None
        if pawprint is not None:
            self.engine = DecisionEngine(pawprint, **self._engine_kwargs())
            if self.skills is not None:
                self.engine.register_skills(self.skills.to_registry())

    def register_skills(self, skills: SkillService | SkillRegistry | Mapping[str, Callable[[dict[str, Any], dict[str, Any]], Any]]) -> "Pawly":
        self.skills = _resolve_skill_service(skills)
        if self.engine is None:
            raise MissingSkillRegistryError("register_skills requires a Pawprint path such as Pawly('./worker.yaml').")
        self.engine.register_skills(self.skills.to_registry())
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
                status="configuration_required",
                objective=cleaned_objective,
                error="missing_pawprint",
                needs="Pass your Pawprint YAML path, for example Pawly('./worker.yaml').",
                action_receipt=self._receipt(
                    objective=cleaned_objective,
                    status="configuration_required",
                    selected_action=None,
                    context=context,
                    constraints=constraints,
                ),
            )
        if not self.policy.is_configured() or not self.audit.is_configured():
            missing = "policy" if not self.policy.is_configured() else "audit"
            return GoalExecutionResult(
                status="configuration_required",
                objective=cleaned_objective,
                error="missing_api_key",
                needs=f"Copy a hosted key at {DEFAULT_CLOUD_CONSOLE_URL}.",
                action_receipt=self._receipt(
                    objective=cleaned_objective,
                    status="configuration_required",
                    selected_action=None,
                    context=context,
                    constraints=constraints,
                    extra={"missing_service": missing},
                ),
            )
        if self.engine.skill_registry is None:
            raise MissingSkillRegistryError("achieve requires skills. Pass skills=... or call register_skills(...).")

        action = _resolve_objective_to_action(cleaned_objective, self.engine.skill_registry)
        if action is None:
            return GoalExecutionResult(
                status="unsupported_goal",
                objective=cleaned_objective,
                needs="Register a skill whose capability matches this objective.",
                action_receipt=self._receipt(
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
            action_receipt=self._receipt(
                objective=cleaned_objective,
                status=status,
                selected_action=action,
                context=context,
                constraints=constraints,
                run_result=run_result,
            ),
        )

    def _engine_kwargs(self) -> dict[str, Any]:
        payload = self.policy.to_engine_kwargs()
        payload.update(self.audit.to_engine_kwargs())
        return payload

    def _receipt(
        self,
        *,
        objective: str,
        status: str,
        selected_action: Action | None,
        context: Mapping[str, Any] | None,
        constraints: Mapping[str, Any] | None,
        run_result: Mapping[str, Any] | None = None,
        extra: Mapping[str, Any] | None = None,
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
            "skills": None if self.skills is None else self.skills.to_dict(),
            "policy": self.policy.to_dict(),
            "audit": self.audit.to_dict(),
        }
        if extra:
            payload.update(dict(extra))
        return payload


def achieve(
    pawprint: str,
    *,
    objective: str,
    context: Mapping[str, Any] | None = None,
    constraints: Mapping[str, Any] | None = None,
    skills: SkillService | SkillRegistry | Mapping[str, Callable[[dict[str, Any], dict[str, Any]], Any]] | None = None,
    policy: PolicyService | None = None,
    audit: AuditService | None = None,
) -> GoalExecutionResult:
    return Pawly(pawprint, skills=skills, policy=policy, audit=audit).achieve(
        objective=objective,
        context=context,
        constraints=constraints,
    )


def _resolve_skill_service(
    skills: SkillService | SkillRegistry | Mapping[str, Callable[[dict[str, Any], dict[str, Any]], Any]] | None,
) -> SkillService | None:
    if skills is None:
        return None
    if isinstance(skills, SkillService):
        return skills
    if isinstance(skills, SkillRegistry):
        return SkillService.from_registry(skills)
    return SkillService.local(skills)


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
