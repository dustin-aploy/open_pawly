from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pawly.backends.audit import AuditSink, CompositeAuditSink, HostedActionSyncAuditSink, LocalAuditSink
from pawly.services.cloud import DEFAULT_CLOUD_API_URL, DEFAULT_CLOUD_CONSOLE_URL, CloudConnection


class BestEffortAuditSink:
    name = "best-effort-cloud-action-sync"

    def __init__(self, sink: HostedActionSyncAuditSink) -> None:
        self.sink = sink
        self.last_error: str | None = None

    def append(self, event: Any) -> dict[str, Any]:
        payload = event.to_dict()
        try:
            return self.sink.append(event)
        except Exception as exc:
            self.last_error = str(exc)
            return payload

    def load_events(self) -> list[dict[str, Any]]:
        return []

    def find_event(self, *, event_id: str | None = None, decision_id: str | None = None, event_type: str | None = None) -> dict[str, Any] | None:
        del event_id, decision_id, event_type
        return None


@dataclass(slots=True)
class AuditService:
    """Action-record wiring for local files, custom sinks, and cloud dashboard sync."""

    audit_path: str | Path | None = None
    sink: AuditSink | None = None
    cloud_connection: CloudConnection | None = None

    @classmethod
    def local(cls, path: str | Path = "./pawly-audit.jsonl") -> "AuditService":
        return cls(audit_path=path)

    @classmethod
    def custom(cls, sink: AuditSink) -> "AuditService":
        return cls(sink=sink)

    @classmethod
    def cloud(
        cls,
        *,
        api_key: str | None = None,
        local_path: str | Path | None = None,
        api_url: str = DEFAULT_CLOUD_API_URL,
        console_url: str = DEFAULT_CLOUD_CONSOLE_URL,
    ) -> "AuditService":
        return cls(
            audit_path=local_path,
            cloud_connection=CloudConnection(api_key=api_key, api_url=api_url, console_url=console_url),
        )

    def is_configured(self) -> bool:
        return self.cloud_connection is None or self.cloud_connection.is_configured()

    def to_engine_kwargs(self) -> dict[str, Any]:
        sink = self._build_sink()
        if sink is not None:
            return {"audit_sink": sink}
        if self.audit_path is not None:
            return {"audit_path": self.audit_path}
        return {}

    def alerts(self) -> list[dict[str, str]]:
        alerts: list[dict[str, str]] = []
        if self.cloud_connection is not None:
            dashboard_url = self.cloud_connection.console_url.rstrip("/")
            if not self.cloud_connection.is_configured():
                alerts.append(
                    {
                        "level": "warning",
                        "code": "missing_api_key",
                        "message": "Cloud audit is selected but no PAWLY_API_KEY is configured.",
                        "action": f"Create or copy a cloud key at {dashboard_url}.",
                    }
                )
            alerts.append(
                {
                    "level": "info",
                    "code": "cloud_audit_enabled",
                    "message": "Action records can appear in the Cloud dashboard.",
                    "action": f"Open {dashboard_url} to review runs and handoffs.",
                }
            )
        if self.audit_path is not None:
            alerts.append(
                {
                    "level": "info",
                    "code": "local_audit_enabled",
                    "message": f"Action records are written to {self.audit_path}.",
                    "action": "Open the local audit file when debugging a run.",
                }
            )
        if self.sink is not None:
            alerts.append(
                {
                    "level": "info",
                    "code": "custom_audit_enabled",
                    "message": "Action records are written through a custom audit sink.",
                    "action": "Inspect the configured sink for run records.",
                }
            )
        return alerts

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "mode": "cloud" if self.cloud_connection is not None else "local" if self.audit_path is not None else "custom" if self.sink is not None else "default",
            "local_file": None if self.audit_path is None else str(self.audit_path),
            "custom_sink": self.sink is not None,
        }
        if self.cloud_connection is not None:
            payload["cloud"] = self.cloud_connection.to_dict()
            payload["dashboard_url"] = self.cloud_connection.console_url.rstrip("/")
        alerts = self.alerts()
        if alerts:
            payload["alerts"] = alerts
        return payload

    def _build_sink(self) -> AuditSink | None:
        selected = self.sink
        if selected is None and self.audit_path is not None and self.cloud_connection is not None:
            selected = LocalAuditSink(self.audit_path)
        hosted = self._build_hosted_sink()
        if hosted is None:
            return selected
        if selected is None:
            return hosted
        if isinstance(selected, CompositeAuditSink):
            return CompositeAuditSink([*selected.sinks, hosted])
        return CompositeAuditSink([selected, hosted])

    def _build_hosted_sink(self) -> AuditSink | None:
        if self.cloud_connection is None or not self.cloud_connection.is_configured():
            return None
        return BestEffortAuditSink(
            HostedActionSyncAuditSink(
                base_url=self.cloud_connection.api_url,
                api_key=str(self.cloud_connection.api_key),
            )
        )
