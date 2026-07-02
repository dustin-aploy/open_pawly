from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pawly.backends.audit import AuditSink, build_default_audit_sink
from pawly.backends.reviewer import ReviewerPolicy
from pawly.backends.risk import RiskProvider
from pawly.budget.state import BudgetState
from pawly.memory.store import MemoryStore
from pawly.middleware.hooks import HookRegistry
from pawly.pawprint_loader import PawprintConfig, load_pawprint_file
from pawly.policy import resolve_action_routing_policies, resolve_reviewer_policy, resolve_reviewer_selection
from pawly.policy.base import Policy
from pawly.protected_oss import ProtectedAuditRedactingSink, is_protected_skill
from pawly.runtime_ids import RuntimeIdSequence
from pawly.validator.validator import PawprintValidator

ScoringPolicyFallbackMode = Literal["review", "heuristic", "deny"]


@dataclass(slots=True)
class RuntimeConfig:
    agent_path: Path
    raw_pawprint_config: dict
    pawprint_config: PawprintConfig
    reviewer_name: str
    reviewer_policy: ReviewerPolicy
    local_scoring_policy: Policy
    scoring_policy: Policy
    fallback_scoring_policy: Policy
    scoring_policy_fallback_mode: ScoringPolicyFallbackMode


@dataclass(slots=True)
class RuntimeServices:
    audit_sink: AuditSink
    audit_ledger: object
    validator: PawprintValidator
    memory_store: MemoryStore
    hooks: HookRegistry
    budget_state: BudgetState = field(default_factory=BudgetState)
    ids: RuntimeIdSequence = field(default_factory=RuntimeIdSequence)
    decisions: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class RuntimeBootstrap:
    config: RuntimeConfig
    services: RuntimeServices


def bootstrap_runtime(
    *,
    agent_path: str | Path,
    audit_path: str | Path | None,
    policy: str,
    policy_impl: ReviewerPolicy | None,
    risk_provider: RiskProvider | None,
    audit_sink: AuditSink | None,
    scoring_policy_fallback_mode: ScoringPolicyFallbackMode,
    scoring_policy: Policy | str | None,
    reviewer: str | None,
    reviewer_backend: ReviewerPolicy | None,
) -> RuntimeBootstrap:
    resolved_agent_path = Path(agent_path)
    validator = PawprintValidator()
    loaded_pawprint = load_pawprint_file(resolved_agent_path, validator)

    selected_policy, selected_policy_impl = resolve_reviewer_selection(
        policy=policy,
        policy_impl=policy_impl,
        reviewer=reviewer,
        reviewer_backend=reviewer_backend,
    )
    local_scoring_policy, scoring_policy_impl, fallback_scoring_policy = resolve_action_routing_policies(scoring_policy)
    resolved_audit_sink = audit_sink or build_default_audit_sink(audit_path)
    if is_protected_skill(loaded_pawprint.config):
        resolved_audit_sink = ProtectedAuditRedactingSink(resolved_audit_sink, loaded_pawprint.config)
    return RuntimeBootstrap(
        config=RuntimeConfig(
            agent_path=resolved_agent_path,
            raw_pawprint_config=loaded_pawprint.raw_document,
            pawprint_config=loaded_pawprint.config,
            reviewer_name=selected_policy,
            reviewer_policy=resolve_reviewer_policy(
                selected_policy,
                policy_impl=selected_policy_impl,
                risk_provider=risk_provider,
            ),
            local_scoring_policy=local_scoring_policy,
            scoring_policy=scoring_policy_impl,
            fallback_scoring_policy=fallback_scoring_policy,
            scoring_policy_fallback_mode=scoring_policy_fallback_mode,
        ),
        services=RuntimeServices(
            audit_sink=resolved_audit_sink,
            audit_ledger=getattr(resolved_audit_sink, "ledger", resolved_audit_sink),
            validator=validator,
            memory_store=MemoryStore("none"),
            hooks=HookRegistry(),
        ),
    )
