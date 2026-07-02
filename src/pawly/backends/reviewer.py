from __future__ import annotations

import inspect
import importlib
import logging
from typing import Any
from typing import Protocol

from pawly.backends.risk import LocalRiskProvider, RiskProvider
from pawly.pawprint_loader import PawprintConfig
from pawly.policy_engine.engine import evaluate_pawprint
from pawly.types import Intent, PolicyEvaluation


LOGGER = logging.getLogger(__name__)
_CONFIG_WARNING = "Pawly Cloud not configured. Falling back to rule-based decision."


class ReviewerPolicy(Protocol):
    name: str

    def evaluate(self, intent: Intent, pawprint: PawprintConfig, context: dict[str, Any] | None = None) -> PolicyEvaluation:
        ...


class RulePolicy:
    name = "rules"
    reviewer_mode = "rule"

    def __init__(self, risk_provider: RiskProvider | None = None) -> None:
        self.risk_provider = risk_provider or LocalRiskProvider()

    def evaluate(self, intent: Intent, pawprint: PawprintConfig, context: dict[str, Any] | None = None) -> PolicyEvaluation:
        del context
        return evaluate_pawprint(
            intent,
            pawprint,
            risk_provider=self.risk_provider,
        )

    def review(self, intent: Intent, pawprint: PawprintConfig, context: dict[str, Any] | None = None) -> PolicyEvaluation:
        return self.evaluate(intent, pawprint, context)


class CloudReviewerStub:
    name = "cloud-review"

    def evaluate(self, intent: Intent, pawprint: PawprintConfig, context: dict[str, Any] | None = None) -> PolicyEvaluation:
        del context
        del intent, pawprint
        raise NotImplementedError("Cloud reviewer backends are optional extensions and are not part of the OSS runtime path.")

    def review(self, intent: Intent, pawprint: PawprintConfig, context: dict[str, Any] | None = None) -> PolicyEvaluation:
        return self.evaluate(intent, pawprint, context)


class CloudReviewer(CloudReviewerStub):
    @classmethod
    def from_env(cls) -> "CloudReviewer | None":
        cloud_reviewer_cls = _load_external_cloud_reviewer()
        if cloud_reviewer_cls is None:
            return None
        return cloud_reviewer_cls.from_env()


def resolve_policy(
    policy: str = "rules",
    *,
    policy_impl: ReviewerPolicy | None = None,
    risk_provider: RiskProvider | None = None,
) -> ReviewerPolicy:
    if policy_impl is not None:
        return policy_impl
    if policy == "rules":
        return RulePolicy(risk_provider=risk_provider)
    if policy == "cloud":
        cloud_reviewer = CloudReviewer.from_env()
        if cloud_reviewer is not None:
            return cloud_reviewer
        LOGGER.warning(_CONFIG_WARNING)
        return RulePolicy(risk_provider=risk_provider)
    raise ValueError(f"unsupported policy: {policy}")


def evaluate_reviewer_policy(
    policy: ReviewerPolicy,
    intent: Intent,
    pawprint: PawprintConfig,
    context: dict[str, Any] | None = None,
) -> PolicyEvaluation:
    evaluate = getattr(policy, "evaluate", None)
    if callable(evaluate):
        return evaluate(intent, pawprint, context)

    review = getattr(policy, "review", None)
    if not callable(review):
        raise TypeError("reviewer policy must provide evaluate(...) or review(...)")

    parameters = inspect.signature(review).parameters
    if "context" in parameters or len(parameters) >= 3:
        return review(intent, pawprint, context)
    return review(intent, pawprint)


ReviewerBackend = ReviewerPolicy
RuleReviewer = RulePolicy


def resolve_reviewer_backend(
    reviewer: str = "rules",
    *,
    reviewer_backend: ReviewerBackend | None = None,
    risk_provider: RiskProvider | None = None,
) -> ReviewerBackend:
    return resolve_policy(
        policy=reviewer,
        policy_impl=reviewer_backend,
        risk_provider=risk_provider,
    )


def _load_external_cloud_reviewer():
    try:
        module = importlib.import_module("pawly_cloud")
    except ModuleNotFoundError:
        return None
    return getattr(module, "CloudReviewer", None)
