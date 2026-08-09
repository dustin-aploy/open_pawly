from __future__ import annotations

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
    user_id: str | None = None
    session_id: str | None = None

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
        if self.user_id:
            payload["user_id"] = self.user_id
        if self.session_id:
            payload["session_id"] = self.session_id
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
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> GoalExecutionResult:
        cleaned_objective = str(objective).strip()
        if not cleaned_objective:
            raise ValueError("objective must not be empty")
        runtime_context = _with_user_context(context, user_id=user_id, session_id=session_id)
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
                    context=runtime_context,
                    constraints=constraints,
                ),
                user_id=user_id,
                session_id=session_id,
            )
        if (self.skills is not None and not self.skills.is_configured()) or not self.policy.is_configured() or not self.audit.is_configured():
            missing = "skills" if self.skills is not None and not self.skills.is_configured() else "policy" if not self.policy.is_configured() else "audit"
            return GoalExecutionResult(
                status="configuration_required",
                objective=cleaned_objective,
                error="missing_api_key",
                needs=f"Copy a cloud key at {DEFAULT_CLOUD_CONSOLE_URL}.",
                action_receipt=self._receipt(
                    objective=cleaned_objective,
                    status="configuration_required",
                    selected_action=None,
                    context=runtime_context,
                    constraints=constraints,
                    extra={"missing_service": missing},
                ),
                user_id=user_id,
                session_id=session_id,
            )
        if self.engine.skill_registry is None:
            raise MissingSkillRegistryError("achieve requires skills. Pass skills=... or call register_skills(...).")

        actions = [
            Action(name=name, arguments={"objective": cleaned_objective})
            for name in self.engine.skill_registry.action_names()
        ]
        if not actions:
            return GoalExecutionResult(
                status="unsupported_goal",
                objective=cleaned_objective,
                needs="Register at least one local skill before calling pawly.achieve(...).",
                action_receipt=self._receipt(
                    objective=cleaned_objective,
                    status="unsupported_goal",
                    selected_action=None,
                    context=runtime_context,
                    constraints=constraints,
                    extra={"available_capabilities": []},
                ),
                user_id=user_id,
                session_id=session_id,
            )

        run_result = self._run_goal_candidate_actions(
            state={
                "objective": cleaned_objective,
                "goal_interface": "achieve",
                "constraints": dict(constraints or {}),
                **dict(constraints or {}),
            },
            actions=actions,
            context={
                **dict(runtime_context or {}),
                "objective": cleaned_objective,
                "constraints": dict(constraints or {}),
            },
            pawprint_config=pawprint_config,
        )
        status = str(run_result.get("status", "failed"))
        selected_action = _selected_action_from_run_result(run_result)
        return GoalExecutionResult(
            status=status,
            objective=cleaned_objective,
            result=run_result.get("result"),
            decision=run_result.get("decision"),
            error=run_result.get("error"),
            action_receipt=self._receipt(
                objective=cleaned_objective,
                status=status,
                selected_action=selected_action,
                context=runtime_context,
                constraints=constraints,
                run_result=run_result,
                extra={"candidate_capabilities": [action.name for action in actions]},
            ),
            user_id=user_id,
            session_id=session_id,
        )

    def _run_goal_candidate_actions(
        self,
        *,
        state: Mapping[str, Any] | None,
        actions: list[Action],
        context: Mapping[str, Any] | None = None,
        pawprint_config: PawprintConfig | None = None,
    ) -> dict[str, Any]:
        if self.engine is None:
            raise MissingSkillRegistryError("achieve requires a Pawprint path such as Pawly('./worker.yaml').")
        if self.engine.skill_registry is None:
            raise MissingSkillRegistryError("achieve requires skills. Pass skills=... or call register_skills(...).")
        return self.engine.run_actions(
            state=state,
            actions=actions,
            context=context,
            pawprint_config=pawprint_config,
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
    user_id: str | None = None,
    session_id: str | None = None,
) -> GoalExecutionResult:
    return Pawly(pawprint, skills=skills, policy=policy, audit=audit).achieve(
        objective=objective,
        context=context,
        constraints=constraints,
        user_id=user_id,
        session_id=session_id,
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


def _selected_action_from_run_result(run_result: Mapping[str, Any]) -> Action | None:
    decision = run_result.get("decision")
    if not isinstance(decision, Mapping):
        return None
    selected = decision.get("selected_action")
    if not isinstance(selected, Mapping):
        return None
    return Action.from_dict(dict(selected))


def _with_user_context(
    context: Mapping[str, Any] | None,
    *,
    user_id: str | None,
    session_id: str | None,
) -> dict[str, Any]:
    payload = dict(context or {})
    if user_id:
        payload.setdefault("user_id", user_id)
    if session_id:
        payload.setdefault("session_id", session_id)
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
