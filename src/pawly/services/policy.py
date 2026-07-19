from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pawly.backends.reviewer import ReviewerPolicy
from pawly.policy.base import Policy
from pawly.services.cloud import DEFAULT_CLOUD_API_URL, DEFAULT_CLOUD_CONSOLE_URL, CloudConnection


@dataclass(slots=True)
class PolicyService:
    """Policy wiring for boundary review and action routing.

    The public concept is one policy service. Internally, Open Pawly bridges it
    to the existing reviewer and action-routing hooks used by DecisionEngine.
    """

    reviewer: str = "rules"
    routing: Policy | str | None = None
    reviewer_backend: ReviewerPolicy | None = None
    cloud_connection: CloudConnection | None = None

    @classmethod
    def local(
        cls,
        routing: Policy | str | None = None,
        *,
        reviewer_backend: ReviewerPolicy | None = None,
    ) -> "PolicyService":
        return cls(reviewer="rules", routing=routing, reviewer_backend=reviewer_backend)

    @classmethod
    def cloud(
        cls,
        *,
        api_key: str | None = None,
        routing: Policy | str | None = None,
        api_url: str = DEFAULT_CLOUD_API_URL,
        console_url: str = DEFAULT_CLOUD_CONSOLE_URL,
    ) -> "PolicyService":
        return cls(
            reviewer="cloud",
            routing=routing,
            cloud_connection=CloudConnection(api_key=api_key, api_url=api_url, console_url=console_url),
        )

    def is_configured(self) -> bool:
        return self.cloud_connection is None or self.cloud_connection.is_configured()

    def to_engine_kwargs(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"policy": self.reviewer}
        if self.routing is not None:
            payload["scoring_policy"] = self.routing
        if self.reviewer_backend is not None:
            payload["reviewer_backend"] = self.reviewer_backend
        return payload

    def alerts(self) -> list[dict[str, str]]:
        if self.cloud_connection is None:
            return []
        dashboard_url = self.cloud_connection.console_url.rstrip("/")
        alerts = [
            {
                "level": "info",
                "code": "cloud_policy_selected",
                "message": "Cloud policy is selected when available; local rules remain available during development.",
                "action": f"Open {dashboard_url} to review policy configuration.",
            }
        ]
        if not self.cloud_connection.is_configured():
            alerts.insert(
                0,
                {
                    "level": "warning",
                    "code": "missing_api_key",
                    "message": "Cloud policy is selected but no PAWLY_API_KEY is configured.",
                    "action": f"Create or copy a cloud key at {dashboard_url}.",
                },
            )
        return alerts

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "mode": "cloud" if self.cloud_connection is not None else "local",
            "reviewer": self.reviewer,
        }
        if self.routing is not None:
            payload["routing"] = getattr(self.routing, "name", self.routing)
        if self.cloud_connection is not None:
            payload["cloud"] = self.cloud_connection.to_dict()
            payload["dashboard_url"] = self.cloud_connection.console_url.rstrip("/")
        alerts = self.alerts()
        if alerts:
            payload["alerts"] = alerts
        return payload
