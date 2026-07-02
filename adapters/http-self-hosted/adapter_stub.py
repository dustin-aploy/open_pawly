from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class SelfHostedWorkerConfig:
    invoke_url: str
    healthcheck_url: str
    auth_type: str = "bearer"


@dataclass(slots=True)
class InvokeRequest:
    task: str
    action: str
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)


class SelfHostedHTTPAdapter:
    """Minimal stub for calling a self-hosted worker over HTTP-like boundaries."""

    def __init__(self, config: SelfHostedWorkerConfig) -> None:
        self.config = config

    def build_invoke_request(self, request: InvokeRequest) -> dict[str, Any]:
        return {
            "method": "POST",
            "url": self.config.invoke_url,
            "headers": {
                "Content-Type": "application/json",
            },
            "body": {
                "task": request.task,
                "action": request.action,
                "confidence": request.confidence,
                "metadata": request.metadata,
            },
        }

    def build_healthcheck_request(self) -> dict[str, Any]:
        return {
            "method": "GET",
            "url": self.config.healthcheck_url,
        }
