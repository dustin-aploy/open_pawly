from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pawly.backends.audit import AuditSink, CompositeAuditSink, HostedActionSyncAuditSink, LocalAuditSink
from pawly.backends.reviewer import ReviewerPolicy
from pawly.contracts import Action
from pawly.pawprint_loader import PawprintConfig
from pawly.policy.base import Policy
from pawly.runtime import DecisionEngine
from pawly.skill_registry import MissingSkillRegistryError, SkillRegistry


DEFAULT_CLOUD_CONSOLE_URL = "https://developer.aploy.ai/pawly"
DEFAULT_CLOUD_API_URL = "https://api.aploy.ai"


@dataclass(slots=True)
class CloudConnection:
    """Project-scoped hosted connection for an otherwise local Pawly runtime.

    CloudConnection does not replace a Pawprint. The local Pawprint remains the
    source of capabilities and boundaries; the hosted project provides managed
    project identity, optional action sync, and console visibility.
    """

    project_id: str
    api_key: str | None = None
    api_url: str = DEFAULT_CLOUD_API_URL
    console_url: str = DEFAULT_CLOUD_CONSOLE_URL
    sync_actions: bool = True

    def is_configured(self) -> bool:
        return bool(str(self.api_key or "").strip())

    def to_dict(self, *, include_secret: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "mode": "hosted_project",
            "project_id": self.project_id,
            "api_url": self.api_url.rstrip("/"),
            "console_url": self.console_url.rstrip("/"),
            "sync_actions": self.sync_actions,
            "api_key_configured": self.is_configured(),
        }
        if include_secret and self.api_key:
            payload["api_key"] = self.api_key
        return payload

    def build_audit_sink(self) -> HostedActionSyncAuditSink | None:
        if not self.sync_actions or not self.is_configured():
            return None
        return HostedActionSyncAuditSink(
            base_url=self.api_url,
            api_key=str(self.api_key),
        )


@dataclass(slots=True)
class PawlyServices:
    """Runtime service wiring for policy and action records.

    Local and cloud modes use the same Pawprint and skill registry. The only
    difference is which service implementations evaluate policy and store action
    records.
    """

    mode: str = "local"
    policy: str | None = None
    scoring_policy: Policy | str | None = None
    reviewer_backend: ReviewerPolicy | None = None
    audit_path: str | Path | None = None
    audit_sink: AuditSink | None = None
    cloud_connection: CloudConnection | None = None

    @classmethod
    def local(
        cls,
        *,
        policy: str = "rules",
        scoring_policy: Policy | str | None = None,
        audit_path: str | Path | None = None,
        audit_sink: AuditSink | None = None,
        reviewer_backend: ReviewerPolicy | None = None,
    ) -> "PawlyServices":
        return cls(
            mode="local",
            policy=policy,
            scoring_policy=scoring_policy,
            reviewer_backend=reviewer_backend,
            audit_path=audit_path,
            audit_sink=audit_sink,
        )

    @classmethod
    def cloud(
        cls,
        *,
        project_id: str,
        api_key: str | None = None,
        api_url: str = DEFAULT_CLOUD_API_URL,
        console_url: str = DEFAULT_CLOUD_CONSOLE_URL,
        policy: str = "cloud",
        scoring_policy: Policy | str | None = None,
        local_audit_path: str | Path | None = None,
        audit_sink: AuditSink | None = None,
        reviewer_backend: ReviewerPolicy | None = None,
        sync_actions: bool = True,
    ) -> "PawlyServices":
        return cls(
            mode="cloud",
            policy=policy,
            scoring_policy=scoring_policy,
            reviewer_backend=reviewer_backend,
            audit_path=local_audit_path,
            audit_sink=audit_sink,
            cloud_connection=CloudConnection(
                project_id=project_id,
                api_key=api_key,
                api_url=api_url,
                console_url=console_url,
                sync_actions=sync_actions,
            ),
        )

    def is_configured(self) -> bool:
        return self.cloud_connection is None or self.cloud_connection.is_configured()

    def to_engine_kwargs(self, engine_kwargs: Mapping[str, Any]) -> dict[str, Any]:
        resolved = dict(engine_kwargs)
        if self.policy is not None and "policy" not in resolved and "reviewer" not in resolved:
            resolved["policy"] = self.policy
        if self.scoring_policy is not None and "scoring_policy" not in resolved:
            resolved["scoring_policy"] = self.scoring_policy
        if self.reviewer_backend is not None and "reviewer_backend" not in resolved and "policy_impl" not in resolved:
            resolved["reviewer_backend"] = self.reviewer_backend
        if "audit_path" not in resolved and self.audit_path is not None:
            resolved["audit_path"] = self.audit_path

        explicit_audit_sink = resolved.get("audit_sink") or self.audit_sink
        resolved["audit_sink"] = _merge_service_audit_sink(
            existing=explicit_audit_sink,
            audit_path=self.audit_path,
            cloud=self.cloud_connection,
        )
        if resolved["audit_sink"] is None:
            resolved.pop("audit_sink")
        return resolved

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "mode": self.mode,
            "policy_backend": self.policy or "rules",
            "action_records": {
                "local_file": None if self.audit_path is None else str(self.audit_path),
                "custom_sink": self.audit_sink is not None,
                "cloud_sync": bool(self.cloud_connection and self.cloud_connection.sync_actions),
            },
        }
        if self.scoring_policy is not None:
            payload["scoring_policy"] = getattr(self.scoring_policy, "name", self.scoring_policy)
        if self.cloud_connection is not None:
            payload["cloud"] = self.cloud_connection.to_dict()
        return payload


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
    """Goal-oriented Open Pawly facade.

    OSS resolves a delegated objective to one registered local capability using
    deterministic metadata matching, then reuses the existing control layer,
    execution gateway, audit, and policy path through DecisionEngine.run_actions.
    """

    def __init__(
        self,
        pawprint: str | None = None,
        *,
        services: PawlyServices | Mapping[str, Any] | None = None,
        cloud: CloudConnection | Mapping[str, Any] | None = None,
        api_key: str | None = None,
        project_id: str | None = None,
        skill_registry: SkillRegistry | None = None,
        **engine_kwargs: Any,
    ) -> None:
        self.services = _resolve_services(services=services, cloud=cloud, api_key=api_key, project_id=project_id)
        self.cloud = self.services.cloud_connection
        self.engine: DecisionEngine | None = None
        if pawprint is not None:
            self.engine = DecisionEngine(pawprint, **self.services.to_engine_kwargs(engine_kwargs))
        if skill_registry is not None:
            self.register_skills(skill_registry)

    def connect_cloud(
        self,
        *,
        project_id: str,
        api_key: str | None = None,
        api_url: str = DEFAULT_CLOUD_API_URL,
        console_url: str = DEFAULT_CLOUD_CONSOLE_URL,
        sync_actions: bool = True,
    ) -> "Pawly":
        self.services = PawlyServices.cloud(
            project_id=project_id,
            api_key=api_key,
            api_url=api_url,
            console_url=console_url,
            local_audit_path=self.services.audit_path,
            audit_sink=self.services.audit_sink,
            sync_actions=sync_actions,
        )
        self.cloud = self.services.cloud_connection
        if self.engine is not None:
            sink = self.cloud.build_audit_sink() if self.cloud is not None else None
            if sink is not None:
                self.engine.audit_sink = _combine_audit_sinks(self.engine.audit_sink, sink)
                self.engine.services.audit_sink = self.engine.audit_sink
                self.engine.audit_ledger = getattr(self.engine.audit_sink, "ledger", self.engine.audit_sink)
                self.engine.services.audit_ledger = self.engine.audit_ledger
        return self

    def register_skills(self, skill_registry: SkillRegistry) -> "Pawly":
        if self.engine is None:
            raise MissingSkillRegistryError("register_skills requires a Pawprint path such as Pawly('./worker.yaml').")
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
                status="configuration_required",
                objective=cleaned_objective,
                result=None,
                error="missing_pawprint",
                needs=(
                    "Pass your Pawprint YAML path, for example Pawly('./worker.yaml'). "
                    "A hosted project key connects receipts and review workflows, but it does not replace local capabilities and boundaries."
                ),
                action_receipt=_receipt(
                    objective=cleaned_objective,
                    status="configuration_required",
                    selected_action=None,
                    context=context,
                    constraints=constraints,
                    services=self.services,
                ),
            )
        if not self.services.is_configured():
            return GoalExecutionResult(
                status="configuration_required",
                objective=cleaned_objective,
                result=None,
                error="missing_api_key",
                needs=f"Copy the one-time project key for {self.cloud.project_id} at {self.cloud.console_url.rstrip('/')}.",
                action_receipt=_receipt(
                    objective=cleaned_objective,
                    status="configuration_required",
                    selected_action=None,
                    context=context,
                    constraints=constraints,
                    services=self.services,
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
                    services=self.services,
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
                services=self.services,
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
    services: PawlyServices | None = None,
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
    if services is not None:
        payload["services"] = services.to_dict()
        if services.cloud_connection is not None:
            payload["cloud"] = services.cloud_connection.to_dict()
            payload["project_id"] = services.cloud_connection.project_id
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


def _resolve_services(
    *,
    services: PawlyServices | Mapping[str, Any] | None,
    cloud: CloudConnection | Mapping[str, Any] | None,
    api_key: str | None,
    project_id: str | None,
) -> PawlyServices:
    if services is not None:
        if isinstance(services, PawlyServices):
            return services
        payload = dict(services)
        if "cloud" in payload and "cloud_connection" not in payload:
            payload["cloud_connection"] = payload.pop("cloud")
        if isinstance(payload.get("cloud_connection"), Mapping):
            payload["cloud_connection"] = CloudConnection(**dict(payload["cloud_connection"]))
        return PawlyServices(**payload)
    resolved_cloud = _resolve_cloud_connection(cloud=cloud, api_key=api_key, project_id=project_id)
    if resolved_cloud is not None:
        return PawlyServices(mode="cloud", policy="cloud", cloud_connection=resolved_cloud)
    return PawlyServices.local()


def _resolve_cloud_connection(
    *,
    cloud: CloudConnection | Mapping[str, Any] | None,
    api_key: str | None,
    project_id: str | None,
) -> CloudConnection | None:
    if cloud is not None:
        if isinstance(cloud, CloudConnection):
            return cloud
        return CloudConnection(**dict(cloud))
    if api_key is None and project_id is None:
        return None
    if not project_id:
        raise ValueError("project_id is required when api_key is provided. Use CloudConnection(project_id=..., api_key=...).")
    return CloudConnection(project_id=project_id, api_key=api_key)


def _merge_service_audit_sink(
    *,
    existing: AuditSink | None,
    audit_path: str | Path | None,
    cloud: CloudConnection | None,
) -> AuditSink | None:
    selected = existing
    if selected is None and audit_path is not None and cloud is not None:
        selected = LocalAuditSink(audit_path)
    hosted = None if cloud is None else cloud.build_audit_sink()
    if hosted is None:
        return selected
    if selected is None:
        return hosted
    return _combine_audit_sinks(selected, hosted)


def _combine_audit_sinks(existing: AuditSink, hosted: HostedActionSyncAuditSink) -> AuditSink:
    if isinstance(existing, CompositeAuditSink):
        return CompositeAuditSink([*existing.sinks, hosted])
    return CompositeAuditSink([existing, hosted])
