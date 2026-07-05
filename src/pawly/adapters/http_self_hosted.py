from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(slots=True)
class SelfHostedWorkerConfig:
    invoke_url: str
    healthcheck_url: str
    auth_type: str = "bearer"
    auth_token: str | None = None


@dataclass(slots=True)
class InvokeRequest:
    task: str
    action: str
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)
    raw_item: Any = None

    @classmethod
    def from_value(
        cls,
        value: Any,
        *,
        task: str | None = None,
        action: str | None = None,
        confidence: float | None = None,
        metadata: Mapping[str, Any] | None = None,
        task_field: str = "task",
        action_field: str = "action",
        confidence_field: str = "confidence",
        metadata_field: str = "metadata",
    ) -> "InvokeRequest":
        resolved_task = task if task is not None else _extract_value(value, task_field)
        resolved_action = action if action is not None else _extract_value(value, action_field)
        resolved_confidence = confidence if confidence is not None else _extract_value(
            value,
            confidence_field,
            required=False,
            default=1.0,
        )
        resolved_metadata = dict(metadata) if metadata is not None else dict(
            _extract_value(value, metadata_field, required=False, default={}) or {}
        )
        return cls(
            task=str(resolved_task),
            action=str(resolved_action),
            confidence=float(resolved_confidence),
            metadata=resolved_metadata,
            raw_item=value,
        )


class SelfHostedHTTPAdapter:
    """Builds transport requests for a self-hosted worker boundary."""

    def __init__(self, config: SelfHostedWorkerConfig) -> None:
        self.config = config

    def build_invoke_request(self, request: InvokeRequest) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self.config.auth_type == "bearer" and self.config.auth_token:
            headers["Authorization"] = f"Bearer {self.config.auth_token}"
        return {
            "method": "POST",
            "url": self.config.invoke_url,
            "headers": headers,
            "body": {
                "task": request.task,
                "action": request.action,
                "confidence": request.confidence,
                "metadata": request.metadata,
            },
        }

    def build_native_invoke_request(
        self,
        value: Any,
        *,
        task: str | None = None,
        action: str | None = None,
        confidence: float | None = None,
        metadata: Mapping[str, Any] | None = None,
        task_field: str = "task",
        action_field: str = "action",
        confidence_field: str = "confidence",
        metadata_field: str = "metadata",
    ) -> dict[str, Any]:
        return self.build_invoke_request(
            InvokeRequest.from_value(
                value,
                task=task,
                action=action,
                confidence=confidence,
                metadata=metadata,
                task_field=task_field,
                action_field=action_field,
                confidence_field=confidence_field,
                metadata_field=metadata_field,
            )
        )

    def build_healthcheck_request(self) -> dict[str, Any]:
        headers: dict[str, str] = {}
        if self.config.auth_type == "bearer" and self.config.auth_token:
            headers["Authorization"] = f"Bearer {self.config.auth_token}"
        return {
            "method": "GET",
            "url": self.config.healthcheck_url,
            "headers": headers,
        }


def _extract_value(value: Any, field: str, *, required: bool = True, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        if field in value:
            return value[field]
    elif hasattr(value, field):
        return getattr(value, field)
    if required:
        raise ValueError(f"unable to extract required field '{field}'")
    return default
