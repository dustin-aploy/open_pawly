from __future__ import annotations

import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any

from pawly.action_selection import ActionCandidate, ActionDecision
from pawly.approval.models import ApprovalStatus
from pawly.backends.approval import ApprovalBackend
from pawly.audit.events import AuditEvent
from pawly.contracts import Action, Decision, DecisionState, PolicyScore
from pawly.backends.audit import AuditSink
from pawly.backends.reviewer import ReviewerPolicy
from pawly.backends.risk import RiskProvider
from pawly.budget.state import BudgetState
from pawly.loader.schema_loader import load_pawprint_version
from pawly.pawprint_loader import PawprintConfig
from pawly.policy.base import Policy, score_source as policy_score_source
from pawly.runtime_bootstrap import RuntimeConfig, RuntimeServices, ScoringPolicyFallbackMode, bootstrap_runtime
from pawly.runtime_decision import evaluate_core_policy
from pawly.runtime_execute import evaluate_runtime_intent
from pawly.runtime_request import build_task_request_intent
from pawly.runtime_report import build_validated_runtime_report
from pawly.runtime_result import RuntimeDecisionResult
from pawly.runtime_scoring import score_actions as score_runtime_actions
from pawly.shield import OutputProtectionResult, ShieldEnvelope, ShieldPolicy
from pawly.skill_registry import MissingSkillRegistryError, SkillRegistry
from pawly.types import Intent, IntentSource, PolicyEvaluation

LOGGER = logging.getLogger(__name__)
_SUMMARY_EMAIL_PATTERN = r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"
_SUMMARY_PHONE_PATTERN = r"\b(?:\+?\d[\d .-]{7,}\d)\b"


class DecisionEngine:
    def __init__(
        self,
        agent_path: str | Path,
        audit_path: str | Path | None = None,
        *,
        policy: str = "rules",
        policy_impl: ReviewerPolicy | None = None,
        risk_provider: RiskProvider | None = None,
        audit_sink: AuditSink | None = None,
        scoring_policy_fallback_mode: ScoringPolicyFallbackMode = "review",
        scoring_policy: Policy | str | None = None,
        reviewer: str | None = None,
        reviewer_backend: ReviewerPolicy | None = None,
        approval_backend: ApprovalBackend | None = None,
    ) -> None:
        if scoring_policy_fallback_mode not in {"review", "heuristic", "deny"}:
            raise ValueError("scoring_policy_fallback_mode must be 'review', 'heuristic', or 'deny'")
        bootstrap = bootstrap_runtime(
            agent_path=agent_path,
            audit_path=audit_path,
            policy=policy,
            policy_impl=policy_impl,
            risk_provider=risk_provider,
            audit_sink=audit_sink,
            scoring_policy_fallback_mode=scoring_policy_fallback_mode,
            scoring_policy=scoring_policy,
            reviewer=reviewer,
            reviewer_backend=reviewer_backend,
        )
        self.config: RuntimeConfig = bootstrap.config
        self.services: RuntimeServices = bootstrap.services

        self.agent_path = self.config.agent_path
        self.validator = self.services.validator
        self.raw_pawprint_config = self.config.raw_pawprint_config
        self.pawprint_config = self.config.pawprint_config
        self.raw_agent_config = self.raw_pawprint_config
        self.agent_config = self.pawprint_config
        self.reviewer = self.config.reviewer_name
        self.policy = self.config.reviewer_policy
        self.reviewer_backend = self.policy
        self.local_scoring_policy = self.config.local_scoring_policy
        self.scoring_policy = self.config.scoring_policy
        self.fallback_scoring_policy = self.config.fallback_scoring_policy
        self.audit_sink = self.services.audit_sink
        self.audit_ledger = self.services.audit_ledger
        self.budget_state = self.services.budget_state
        self.memory_store = self.services.memory_store
        self.hooks = self.services.hooks
        self.ids = self.services.ids
        self._decisions = self.services.decisions
        self.skill_registry: SkillRegistry | None = None
        self.shield_policy = ShieldPolicy()
        self.approval_backend = approval_backend

    def evaluate(self, task: str, action: str, confidence: float, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.evaluate_result(task, action, confidence, metadata).to_dict()

    def evaluate_result(
        self,
        task: str,
        action: str,
        confidence: float,
        metadata: dict[str, Any] | None = None,
    ) -> RuntimeDecisionResult:
        intent = build_task_request_intent(
            task=task,
            action=action,
            confidence=confidence,
            metadata=metadata,
            intent_id=self.ids.next_intent_id(),
        )
        return self.evaluate_intent_result(intent)

    def evaluate_intent(self, intent: Intent) -> dict[str, Any]:
        return self.evaluate_intent_result(intent).to_dict()

    def evaluate_intent_result(self, intent: Intent) -> RuntimeDecisionResult:
        return evaluate_runtime_intent(
            config=self.config,
            services=self.services,
            intent=intent,
        )

    def next_event_id(self) -> str:
        return self.ids.next_event_id()

    def score_actions(
        self,
        actions: Sequence[Action],
        state: Mapping[str, Any] | None = None,
    ) -> list[PolicyScore]:
        return score_runtime_actions(
            policy=self.local_scoring_policy,
            actions=actions,
            state=state,
        )

    def decide_actions(
        self,
        state: Mapping[str, Any] | None,
        actions: Sequence[Action],
        pawprint_config: PawprintConfig | None = None,
    ) -> ActionDecision:
        pawprint = pawprint_config or self.pawprint_config
        classified = _classify_actions(actions, pawprint)
        scoring_resolution = _resolve_scoring_policy(self)

        allowed_candidates = _build_candidates(
            actions=classified["allow"],
            boundary_type="allow",
            requires_review=False,
            scores=score_runtime_actions(
                policy=scoring_resolution["policy"],
                actions=classified["allow"],
                state=state,
            ),
            default_source=str(scoring_resolution["default_source"]),
        )
        review_candidates = _build_candidates(
            actions=classified["review"],
            boundary_type="review",
            requires_review=True,
            scores=score_runtime_actions(
                policy=scoring_resolution["policy"],
                actions=classified["review"],
                state=state,
            ),
            default_source=str(scoring_resolution["default_source"]),
        )
        promoted_review_candidates, retained_allow_candidates = _apply_cloud_review_guardrails(
            state=state,
            candidates=allowed_candidates,
        )
        allowed_candidates = retained_allow_candidates
        review_candidates = [*review_candidates, *promoted_review_candidates]
        allowed_candidates, review_candidates, blocked_actions, protection_metadata = _apply_shield_policy(
            engine=self,
            state=state,
            pawprint=pawprint,
            allowed_candidates=allowed_candidates,
            review_candidates=review_candidates,
            blocked_actions=classified["blocked"],
        )

        ranked = sorted(
            [*allowed_candidates, *review_candidates],
            key=_candidate_rank_key,
        )
        best = ranked[0] if ranked else None
        decision = ActionDecision(
            trace_id=self.ids.next_event_id(),
            selected_action=None if best is None else best.action,
            requires_review=False if best is None else best.requires_review,
            decision_source=None if best is None else best.decision_source,
            boundary_type=None if best is None else best.boundary_type,
            reason=None if best is None else best.reason,
            uncertainty=None if best is None else best.uncertainty,
            protection=protection_metadata,
            allowed_actions=allowed_candidates,
            review_required_actions=review_candidates,
            blocked_actions=blocked_actions,
        )
        self.log_decision(decision)
        return decision

    def register_skills(self, skill_registry: SkillRegistry) -> "DecisionEngine":
        self.skill_registry = skill_registry
        return self

    def bind_skills(self, skill_registry: SkillRegistry) -> "DecisionEngine":
        return self.register_skills(skill_registry)

    def register_approval_backend(self, approval_backend: ApprovalBackend) -> "DecisionEngine":
        self.approval_backend = approval_backend
        return self

    def run_actions(
        self,
        *,
        state: Mapping[str, Any] | None,
        actions: Sequence[Action],
        context: Mapping[str, Any] | None = None,
        pawprint_config: PawprintConfig | None = None,
    ) -> dict[str, Any]:
        decision = self.decide_actions(
            state=state,
            actions=actions,
            pawprint_config=pawprint_config,
        )
        if decision.selected_action is None:
            payload = {
                "status": "blocked",
                "decision": decision.to_dict(),
                "result": None,
            }
            self._append_run_actions_audit(
                state=state,
                context=context,
                decision=decision,
                execution_status="blocked",
                executed_action=None,
                result=None,
                error=None,
                redactions=[],
                envelope=self.shield_policy.envelope_for(pawprint_config or self.pawprint_config),
                protection_enabled=(pawprint_config or self.pawprint_config).protection is not None,
            )
            return payload
        if decision.requires_review:
            approval_payload = None
            approved_action = None
            if self.approval_backend is not None and decision.selected_action is not None:
                approval_record = self.approval_backend.submit(
                    _build_review_intent(self, decision.selected_action, state, context),
                    _build_review_decision(decision),
                )
                approval_payload = self.approval_backend.status_payload(approval_record)
                if approval_record.status == ApprovalStatus.APPROVED:
                    approved_action = approval_record.approved_action()
            if approved_action is not None:
                decision = _replace_selected_action(decision, approved_action)
            else:
                payload = {
                    "status": "needs_review",
                    "decision": decision.to_dict(),
                    "result": None,
                }
                if approval_payload is not None:
                    payload["approval"] = approval_payload
                self._append_run_actions_audit(
                    state=state,
                    context=context,
                    decision=decision,
                    execution_status="needs_review",
                    executed_action=decision.selected_action,
                    result=None,
                    error=None,
                    redactions=[],
                    envelope=self.shield_policy.envelope_for(pawprint_config or self.pawprint_config),
                    protection_enabled=(pawprint_config or self.pawprint_config).protection is not None,
                    approval_payload=approval_payload,
                )
                return payload
        else:
            approval_payload = None
        if self.skill_registry is None:
            raise MissingSkillRegistryError("run_actions requires a registered SkillRegistry. Call register_skills(...) first.")

        pawprint = pawprint_config or self.pawprint_config
        envelope = self.shield_policy.envelope_for(pawprint)
        sanitized_action, redactions = self.shield_policy.sanitize_action(decision.selected_action, envelope)

        try:
            raw_result = self.skill_registry.execute(sanitized_action, dict(context or {}))
        except Exception as exc:
            safe_error = _sanitize_error(exc)
            self._append_run_actions_audit(
                state=state,
                context=context,
                decision=decision,
                execution_status="failed",
                executed_action=sanitized_action,
                result=None,
                error=safe_error,
                redactions=redactions,
                envelope=envelope,
                protection_enabled=pawprint.protection is not None,
                approval_payload=approval_payload,
            )
            payload = {
                "status": "failed",
                "decision": decision.to_dict(),
                "error": safe_error,
                "result": None,
            }
            if approval_payload is not None:
                payload["approval"] = approval_payload
            return payload

        reviewed_result = self.apply_output_protection(
            raw_result,
            decision=decision,
            state=state,
            context=context or {},
            envelope=envelope,
        )
        combined_redactions = [*redactions, *reviewed_result.redactions]

        if reviewed_result.status == "needs_review":
            self._append_run_actions_audit(
                state=state,
                context=context,
                decision=decision,
                execution_status="needs_review",
                executed_action=sanitized_action,
                result=reviewed_result.result,
                error=None,
                redactions=combined_redactions,
                protection_reasons=reviewed_result.reasons,
                envelope=envelope,
                protection_enabled=pawprint.protection is not None,
                approval_payload=approval_payload,
            )
            payload = {
                "status": "needs_review",
                "decision": decision.to_dict(),
                "result": reviewed_result.result,
            }
            if approval_payload is not None:
                payload["approval"] = approval_payload
            return payload
        if reviewed_result.status == "blocked":
            self._append_run_actions_audit(
                state=state,
                context=context,
                decision=decision,
                execution_status="blocked",
                executed_action=sanitized_action,
                result=None,
                error=None,
                redactions=combined_redactions,
                protection_reasons=reviewed_result.reasons,
                envelope=envelope,
                protection_enabled=pawprint.protection is not None,
                approval_payload=approval_payload,
            )
            payload = {
                "status": "blocked",
                "decision": decision.to_dict(),
                "result": None,
            }
            if approval_payload is not None:
                payload["approval"] = approval_payload
            return payload

        self._append_run_actions_audit(
            state=state,
            context=context,
            decision=decision,
            execution_status="completed",
            executed_action=sanitized_action,
            result=reviewed_result.result,
            error=None,
            redactions=combined_redactions,
            protection_reasons=reviewed_result.reasons,
            envelope=envelope,
            protection_enabled=pawprint.protection is not None,
            approval_payload=approval_payload,
        )
        payload = {
            "status": "completed",
            "decision": decision.to_dict(),
            "result": reviewed_result.result,
        }
        if approval_payload is not None:
            payload["approval"] = approval_payload
        return payload

    def apply_output_protection(
        self,
        result: Any,
        *,
        decision: ActionDecision,
        state: Mapping[str, Any] | None,
        context: Mapping[str, Any] | None,
        envelope: ShieldEnvelope | None = None,
    ) -> OutputProtectionResult:
        del state, context, decision
        selected_envelope = envelope or self.shield_policy.envelope_for(self.pawprint_config)
        return self.shield_policy.protect_output(result, selected_envelope)

    def _append_run_actions_audit(
        self,
        *,
        state: Mapping[str, Any] | None,
        context: Mapping[str, Any] | None,
        decision: ActionDecision,
        execution_status: str,
        executed_action: Action | None,
        result: Any,
        error: str | None,
        redactions: list[str],
        protection_reasons: list[str] | None = None,
        envelope: ShieldEnvelope | None = None,
        protection_enabled: bool = False,
        approval_payload: dict[str, Any] | None = None,
    ) -> None:
        selected_action = decision.selected_action
        action_name = None if selected_action is None else selected_action.name
        selected_action_payload = _audit_action_payload(
            selected_action,
            envelope=envelope,
            protection_enabled=protection_enabled,
        )
        executed_action_payload = _audit_action_payload(
            executed_action,
            envelope=envelope,
            protection_enabled=protection_enabled,
        )
        event = AuditEvent.from_governed_execution(
            event_id=self.ids.next_event_id(),
            decision_id=decision.trace_id or self.ids.next_decision_id(),
            agent_id=self.pawprint_config.id,
            pawprint_version=load_pawprint_version(),
            outcome=execution_status,
            original_intent=_build_run_actions_request_payload(state, context, selected_action_payload),
            normalized_intent=_build_run_actions_request_payload(state, context, selected_action_payload),
            action={"name": action_name},
            policy_evaluation={},
            runtime_overlays={
                "run_actions": True,
                "protection": None if decision.protection is None else dict(decision.protection),
            },
            policy_references=[],
            final_decision=decision.to_dict(),
            reason_codes=list(protection_reasons or []),
            approval=approval_payload,
            executed_action=executed_action_payload,
            action_diff=None,
            execution={
                "attempted": executed_action is not None,
                "executed": execution_status == "completed",
                "blocked_by": None if execution_status == "completed" else execution_status,
                "result_summary": _audit_result_summary(
                    result,
                    envelope=envelope,
                    protection_enabled=protection_enabled,
                ),
                "error": error,
            },
            execution_result_ref=None,
            risk_score=_selected_risk_score(decision),
            escalated_to=None,
            tenant_id=_actor_value(state, "tenant_id"),
            user_id=_actor_value(state, "user_id"),
            protection_level=None if decision.protection is None else str(decision.protection.get("level", "")) or None,
            protection_handling=None if decision.protection is None else str(decision.protection.get("handling", "")) or None,
            protection_assets=None if decision.protection is None else [str(item) for item in decision.protection.get("assets", [])],
            action_argument_summary=_action_argument_summary(selected_action_payload),
            output_summary=_audit_result_summary(
                result,
                envelope=envelope,
                protection_enabled=protection_enabled,
            ),
            error_summary=error,
        )
        if redactions:
            event.redactions_applied = list(dict.fromkeys(redactions))
        self.audit_sink.append(event)

    def _evaluate_core_policy(self, intent: Intent) -> PolicyEvaluation:
        return evaluate_core_policy(
            self.policy,
            intent=intent,
            pawprint=self.pawprint_config,
        )

    def build_report(self) -> dict[str, Any]:
        return build_validated_runtime_report(
            validator=self.validator,
            pawprint=self.pawprint_config,
            decisions=self._decisions,
        )

    def log_decision(self, decision: ActionDecision) -> dict[str, object]:
        payload = _build_action_decision_log(self, decision)
        LOGGER.info("action_decision=%s", payload)
        return payload


PawlyRuntime = DecisionEngine


def _classify_actions(actions: Sequence[Action], pawprint: PawprintConfig) -> dict[str, list[Action]]:
    blocked = {_normalize_name(name) for name in pawprint.blocked_actions}
    review = {_normalize_name(name) for name in pawprint.review_actions}
    allowed = {_normalize_name(name) for name in pawprint.allowed_actions}

    buckets: dict[str, list[Action]] = {
        "allow": [],
        "review": [],
        "blocked": [],
    }
    for action in actions:
        normalized = _normalize_name(action.name)
        if normalized in blocked:
            buckets["blocked"].append(action)
        elif normalized in review:
            buckets["review"].append(action)
        elif normalized in allowed:
            buckets["allow"].append(action)
    return buckets


def _build_candidates(
    *,
    actions: Sequence[Action],
    boundary_type: str,
    requires_review: bool,
    scores: Sequence[PolicyScore],
    default_source: str,
) -> list[ActionCandidate]:
    return [
        ActionCandidate(
            action=action,
            boundary_type=boundary_type,
            requires_review=requires_review,
            decision_source=policy_score_source(score, default_source),
            score=score,
            reason=_candidate_reason(boundary_type, requires_review, score),
            uncertainty=score.uncertainty,
        )
        for action, score in zip(actions, scores, strict=False)
    ]


def _candidate_rank_key(candidate: ActionCandidate) -> tuple[float, int]:
    risk_score = 1.0 if candidate.score.risk_score is None else float(candidate.score.risk_score)
    review_penalty = 1 if candidate.requires_review else 0
    return (risk_score, review_penalty)


def _apply_cloud_review_guardrails(
    *,
    state: Mapping[str, Any] | None,
    candidates: Sequence[ActionCandidate],
) -> tuple[list[ActionCandidate], list[ActionCandidate]]:
    threshold = _uncertainty_review_threshold(state)
    promoted_review: list[ActionCandidate] = []
    retained_allow: list[ActionCandidate] = []
    for candidate in candidates:
        escalation = _escalation_recommendation(candidate)
        if escalation == "human_handoff":
            promoted_review.append(
                replace(
                    candidate,
                    boundary_type="review",
                    requires_review=True,
                    reason="cloud_candidate_handoff_recommended",
                )
            )
            continue
        if escalation == "require_review":
            promoted_review.append(
                replace(
                    candidate,
                    boundary_type="review",
                    requires_review=True,
                    reason="cloud_candidate_requires_review",
                )
            )
            continue
        if candidate.uncertainty is not None and candidate.uncertainty >= threshold:
            promoted_review.append(
                replace(
                    candidate,
                    boundary_type="review",
                    requires_review=True,
                    reason="cloud_candidate_uncertainty_requires_review",
                )
            )
            continue
        retained_allow.append(candidate)
    return promoted_review, retained_allow


def _uncertainty_review_threshold(state: Mapping[str, Any] | None) -> float:
    default_threshold = 0.6
    if not isinstance(state, Mapping):
        return default_threshold
    raw_value = state.get("uncertainty_review_threshold")
    if raw_value is None:
        cloud_policy = state.get("cloud_policy")
        if isinstance(cloud_policy, Mapping):
            raw_value = cloud_policy.get("uncertainty_review_threshold")
    try:
        if raw_value is None:
            return default_threshold
        return float(raw_value)
    except (TypeError, ValueError):
        return default_threshold


def _escalation_recommendation(candidate: ActionCandidate) -> str | None:
    for tag in candidate.score.audit_tags:
        if tag.startswith("escalation:"):
            value = tag.split(":", 1)[1].strip()
            return value or None
    return None


def _normalize_name(value: str) -> str:
    return value.strip().lower()


def _resolve_scoring_policy(engine: DecisionEngine) -> dict[str, object]:
    policy = engine.scoring_policy
    if policy.is_scoring_available():
        return {
            "policy": policy,
            "default_source": policy.source_name(),
            "fallback_used": False,
        }

    reason = policy.scoring_unavailable_reason()
    if policy.source_name() == "cloud":
        LOGGER.warning(
            "CloudPolicy is configured but Pawly Cloud credentials are missing. Falling back to local Pawprint boundary preferences."
        )
    else:
        LOGGER.warning(
            "Scoring policy '%s' is unavailable. Falling back to the local scoring policy. %s",
            getattr(policy, "name", policy.source_name()),
            reason or "No additional details provided.",
        )
    return {
        "policy": engine.fallback_scoring_policy,
        "default_source": "fallback",
        "fallback_used": True,
    }


def _candidate_reason(boundary_type: str, requires_review: bool, score: PolicyScore) -> str:
    if score.reason_codes:
        return score.reason_codes[0]
    if requires_review:
        return f"{boundary_type}_candidate_requires_review"
    return f"{boundary_type}_candidate_selected"


def _build_action_decision_log(engine: DecisionEngine, decision: ActionDecision) -> dict[str, object]:
    selected_candidate = _selected_candidate(decision)
    blocked_action = decision.blocked_actions[0] if decision.blocked_actions else None
    fallback_used = _policy_fallback_used(decision)
    policy = _logged_policy(engine, fallback_used)

    action_name: str | None
    if selected_candidate is not None:
        action_name = selected_candidate.action.name
    elif blocked_action is not None:
        action_name = blocked_action.name
    else:
        action_name = None

    boundary_type = decision.boundary_type
    if boundary_type is None and blocked_action is not None:
        boundary_type = "block"

    decision_name = "deny"
    if decision.selected_action is not None:
        decision_name = "require_review" if decision.requires_review else "allow"

    scores = _scores_payload(decision)
    uncertainty = None if selected_candidate is None else selected_candidate.uncertainty
    reason = decision.reason
    if reason is None and blocked_action is not None:
        reason = "blocked_by_pawprint_boundary"

    payload: dict[str, object] = {
        "trace_id": decision.trace_id or engine.ids.next_event_id(),
        "action": action_name,
        "decision": decision_name,
        "boundary_type": boundary_type,
        "requires_review": decision.requires_review,
        "decision_source": _decision_source(engine, decision, selected_candidate, fallback_used),
        "policy_name": getattr(policy, "name", policy.source_name()),
        "policy_supports_scoring": policy.is_scoring_capable(),
        "policy_fallback_used": fallback_used,
        "reason": reason,
    }
    if uncertainty is not None:
        payload["uncertainty"] = uncertainty
    if scores:
        payload["scores"] = scores
    return payload


def _selected_candidate(decision: ActionDecision) -> ActionCandidate | None:
    if decision.selected_action is None:
        return None
    for candidate in [*decision.allowed_actions, *decision.review_required_actions]:
        if candidate.action == decision.selected_action:
            return candidate
    return None


def _policy_fallback_used(decision: ActionDecision) -> bool:
    return decision.decision_source == "fallback"


def _logged_policy(
    engine: DecisionEngine,
    fallback_used: bool,
) -> Policy:
    return engine.fallback_scoring_policy if fallback_used else engine.scoring_policy


def _decision_source(
    engine: DecisionEngine,
    decision: ActionDecision,
    selected_candidate: ActionCandidate | None,
    fallback_used: bool,
) -> str:
    if decision.decision_source is not None:
        return decision.decision_source
    if selected_candidate is not None:
        return selected_candidate.decision_source
    return engine.fallback_scoring_policy.source_name() if fallback_used else engine.scoring_policy.source_name()


def _scores_payload(decision: ActionDecision) -> list[dict[str, object]]:
    candidates = [*decision.allowed_actions, *decision.review_required_actions]
    payload: list[dict[str, object]] = []
    for candidate in candidates:
        score_payload = candidate.score.to_dict()
        payload.append(
            {
                "action": candidate.action.name,
                "boundary_type": candidate.boundary_type,
                "decision_source": candidate.decision_source,
                "score": score_payload,
            }
        )
    return payload


def _apply_shield_policy(
    *,
    engine: DecisionEngine,
    state: Mapping[str, Any] | None,
    pawprint: PawprintConfig,
    allowed_candidates: list[ActionCandidate],
    review_candidates: list[ActionCandidate],
    blocked_actions: list[Action],
) -> tuple[list[ActionCandidate], list[ActionCandidate], list[Action], dict[str, object]]:
    protection_reasons: list[str] = []
    next_allowed: list[ActionCandidate] = []
    next_review: list[ActionCandidate] = []
    next_blocked: list[Action] = list(blocked_actions)

    for candidate in allowed_candidates:
        outcome, updated, reasons = engine.shield_policy.apply_to_candidate(candidate, pawprint=pawprint, state=dict(state or {}))
        protection_reasons.extend(reasons)
        if outcome == "block":
            next_blocked.append(updated.action)
        elif outcome == "review":
            next_review.append(updated)
        else:
            next_allowed.append(updated)

    for candidate in review_candidates:
        outcome, updated, reasons = engine.shield_policy.apply_to_candidate(candidate, pawprint=pawprint, state=dict(state or {}))
        protection_reasons.extend(reasons)
        if outcome == "block":
            next_blocked.append(updated.action)
        else:
            next_review.append(updated)

    envelope = engine.shield_policy.envelope_for(pawprint)
    protection = {
        "level": envelope.level,
        "handling": envelope.handling,
        "assets": list(envelope.assets),
        "mode": envelope.mode,
        "reasons": list(dict.fromkeys(protection_reasons)),
    }
    deduped_review = _dedupe_candidates(next_review)
    deduped_allowed = _dedupe_candidates(next_allowed)
    deduped_blocked = _dedupe_actions(next_blocked)
    return deduped_allowed, deduped_review, deduped_blocked, protection


def _dedupe_candidates(candidates: list[ActionCandidate]) -> list[ActionCandidate]:
    seen: set[tuple[str, tuple[tuple[str, str], ...], str | None]] = set()
    deduped: list[ActionCandidate] = []
    for candidate in candidates:
        key = (
            candidate.action.name,
            tuple(sorted((str(k), repr(v)) for k, v in candidate.action.arguments.items())),
            candidate.action.target,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def _dedupe_actions(actions: list[Action]) -> list[Action]:
    seen: set[tuple[str, tuple[tuple[str, str], ...], str | None]] = set()
    deduped: list[Action] = []
    for action in actions:
        key = (
            action.name,
            tuple(sorted((str(k), repr(v)) for k, v in action.arguments.items())),
            action.target,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(action)
    return deduped


def _selected_risk_score(decision: ActionDecision) -> float | None:
    candidate = _selected_candidate(decision)
    if candidate is None:
        return None
    return candidate.score.risk_score


def _build_run_actions_request_payload(
    state: Mapping[str, Any] | None,
    context: Mapping[str, Any] | None,
    selected_action: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "state": dict(state or {}),
        "context": _safe_summary(dict(context or {})),
        "selected_action": selected_action,
    }


def _audit_action_payload(
    action: Action | None,
    *,
    envelope: ShieldEnvelope | None,
    protection_enabled: bool,
) -> dict[str, Any] | None:
    if action is None:
        return None
    if not protection_enabled or envelope is None:
        return action.to_dict()
    if envelope.trace.input_storage == "none":
        return {"name": action.name}
    if envelope.trace.input_storage == "summary":
        return {
            "name": action.name,
            "arguments": _safe_summary(action.arguments),
            **({"target": action.target} if action.target is not None else {}),
        }
    redacted_arguments = {key: "[redacted]" for key in action.arguments}
    payload: dict[str, Any] = {"name": action.name, "arguments": redacted_arguments}
    if action.target is not None:
        payload["target"] = action.target
    return payload


def _audit_result_summary(
    result: Any,
    *,
    envelope: ShieldEnvelope | None,
    protection_enabled: bool,
) -> Any:
    if not protection_enabled or envelope is None:
        return _safe_summary(result)
    if envelope.trace.output_storage == "none":
        return None
    if envelope.trace.output_storage == "summary":
        return _safe_summary(result)
    return "[redacted-output]"


def _safe_summary(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, dict):
        summary: dict[str, Any] = {}
        for key, item in value.items():
            normalized = str(key).strip().lower()
            if normalized in {"chain_of_thought", "cot", "reasoning", "internal_prompt", "system_prompt"}:
                summary[str(key)] = "[redacted]"
                continue
            summary[str(key)] = _safe_summary(item)
        return summary
    if isinstance(value, list):
        return [_safe_summary(item) for item in value[:10]]
    if isinstance(value, str):
        lowered = value.lower()
        if any(token in lowered for token in ("api key", "authorization", "private key", "system prompt", "hidden instructions")):
            return "[redacted]"
        trimmed = value[:200]
        trimmed = re.sub(_SUMMARY_EMAIL_PATTERN, "[redacted-email]", trimmed, flags=re.IGNORECASE)
        trimmed = re.sub(_SUMMARY_PHONE_PATTERN, "[redacted-phone]", trimmed, flags=re.IGNORECASE)
        return trimmed
    if isinstance(value, (int, float, bool)):
        return value
    return str(value)[:200]


def _actor_value(state: Mapping[str, Any] | None, field: str) -> str | None:
    if not isinstance(state, Mapping):
        return None
    actor = state.get("actor")
    if not isinstance(actor, Mapping):
        return None
    value = str(actor.get(field, "")).strip()
    return value or None


def _action_argument_summary(action_payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(action_payload, dict):
        return None
    arguments = action_payload.get("arguments")
    if not isinstance(arguments, dict):
        return None
    return dict(arguments)


def _sanitize_error(exc: Exception) -> str:
    text = str(exc).strip() or exc.__class__.__name__
    lowered = text.lower()
    if any(token in lowered for token in ("secret", "token", "api key", "private key", "authorization")):
        return "skill_execution_failed"
    return text[:200]


def _build_review_decision(decision: ActionDecision) -> Decision:
    return Decision(
        type=DecisionState.REQUIRE_APPROVAL,
        reason=decision.reason or "candidate_action_requires_review",
        source=decision.decision_source,
        reason_codes=[] if decision.protection is None else [str(item) for item in decision.protection.get("reasons", [])],
        matched_rules=[],
        risk_score=_selected_risk_score(decision),
        audit_tags=["candidate-action:review"],
    )


def _build_review_intent(
    engine: DecisionEngine,
    action: Action,
    state: Mapping[str, Any] | None,
    context: Mapping[str, Any] | None,
) -> Intent:
    summary = ""
    confidence = 0.0
    if isinstance(state, Mapping):
        conversation = state.get("conversation")
        if isinstance(conversation, Mapping):
            summary = str(conversation.get("current_text", "")).strip()
        request = state.get("request")
        if isinstance(request, Mapping):
            raw_confidence = request.get("confidence")
            try:
                if raw_confidence is not None:
                    confidence = float(raw_confidence)
            except (TypeError, ValueError):
                confidence = 0.0
    metadata: dict[str, Any] = {}
    if isinstance(state, Mapping):
        metadata["state"] = dict(state)
    if isinstance(context, Mapping):
        metadata["context"] = dict(context)
    return Intent(
        intent_id=engine.ids.next_intent_id(),
        source=IntentSource.EXECUTION_REQUEST,
        action=action,
        summary=summary,
        confidence=confidence,
        metadata=metadata,
    )


def _replace_selected_action(decision: ActionDecision, action: Action) -> ActionDecision:
    return replace(decision, selected_action=action)
