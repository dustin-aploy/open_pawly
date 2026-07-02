from __future__ import annotations

import importlib
import os

from pawly.backends.reviewer import ReviewerPolicy, resolve_policy as resolve_reviewer_policy

from .base import Policy
from .heuristic import DefaultOssPolicy


def resolve_scoring_policy(policy: Policy | str | None = None) -> Policy:
    if isinstance(policy, Policy):
        return policy

    selected_policy = (policy or os.environ.get("PAWLY_SCORING_POLICY") or "heuristic").strip().lower()
    if selected_policy in {"heuristic", "default", "oss"}:
        return DefaultOssPolicy()
    if selected_policy == "cloud":
        return _resolve_external_cloud_policy()
    raise ValueError(f"unsupported scoring policy: {selected_policy}")


def resolve_action_routing_policies(policy: Policy | str | None = None) -> tuple[Policy, Policy | None, Policy]:
    resolved = resolve_scoring_policy(policy)
    local_policy = resolved.local_policy()
    fallback_policy = resolved.fallback_scoring_policy() or local_policy or DefaultOssPolicy()
    return local_policy, resolved, fallback_policy


def resolve_reviewer_selection(
    *,
    policy: str = "rules",
    policy_impl: ReviewerPolicy | None = None,
    reviewer: str | None = None,
    reviewer_backend: ReviewerPolicy | None = None,
) -> tuple[str, ReviewerPolicy | None]:
    return reviewer or policy, reviewer_backend or policy_impl


def _resolve_external_cloud_policy() -> Policy:
    try:
        module = importlib.import_module("pawly_cloud")
    except ModuleNotFoundError as exc:
        raise ValueError(
            "scoring policy 'cloud' requires the optional 'pawly-cloud' package. "
            "Install or add pawly-cloud, or pass an explicit Policy implementation."
        ) from exc
    cloud_policy_cls = getattr(module, "CloudPolicy", None)
    if cloud_policy_cls is None:
        raise ValueError("optional package 'pawly-cloud' does not export CloudPolicy")
    return cloud_policy_cls.from_env(fallback_policy=DefaultOssPolicy())


__all__ = [
    "resolve_action_routing_policies",
    "resolve_reviewer_policy",
    "resolve_reviewer_selection",
    "resolve_scoring_policy",
]
