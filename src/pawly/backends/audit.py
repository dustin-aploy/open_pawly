from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Protocol
from urllib import error, request

from pawly.audit.events import AuditEvent
from pawly.audit.ledger import AuditLedger
from pawly.loader.yaml_loader import load_yaml_file

DEFAULT_PAWLY_CLOUD_BASE_URL = "https://api.pawly.dev"
PAWLY_CLOUD_BASE_URL_ENV = "PAWLY_CLOUD_BASE_URL"
PAWLY_AUTH_PATH_ENV = "PAWLY_AUTH_PATH"


class AuditSink(Protocol):
    name: str

    def append(self, event: AuditEvent) -> dict[str, Any]:
        ...

    def load_events(self) -> list[dict[str, Any]]:
        ...

    def find_event(self, *, event_id: str | None = None, decision_id: str | None = None, event_type: str | None = None) -> dict[str, Any] | None:
        ...


class LocalAuditSink:
    name = "local-jsonl"

    def __init__(self, path: str | Path | None = None) -> None:
        self.ledger = AuditLedger(path)

    def append(self, event: AuditEvent) -> dict[str, Any]:
        return self.ledger.append(event)

    def load_events(self) -> list[dict[str, Any]]:
        return self.ledger.load_events()

    def find_event(self, *, event_id: str | None = None, decision_id: str | None = None, event_type: str | None = None) -> dict[str, Any] | None:
        return self.ledger.find_event(event_id=event_id, decision_id=decision_id, event_type=event_type)


class CompositeAuditSink:
    name = "composite-audit"

    def __init__(self, sinks: list[AuditSink]) -> None:
        if not sinks:
            raise ValueError("CompositeAuditSink requires at least one sink")
        self.sinks = sinks
        self.ledger = getattr(sinks[0], "ledger", sinks[0])

    def append(self, event: AuditEvent) -> dict[str, Any]:
        payload: dict[str, Any] | None = None
        for index, sink in enumerate(self.sinks):
            result = sink.append(event)
            if index == 0:
                payload = result
        return payload or event.to_dict()

    def load_events(self) -> list[dict[str, Any]]:
        return self.sinks[0].load_events()

    def find_event(self, *, event_id: str | None = None, decision_id: str | None = None, event_type: str | None = None) -> dict[str, Any] | None:
        return self.sinks[0].find_event(event_id=event_id, decision_id=decision_id, event_type=event_type)


class HostedActionSyncAuditSink:
    name = "cloud-action-sync"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout: float = 5.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def append(self, event: AuditEvent) -> dict[str, Any]:
        payload = event.to_dict()
        body = json.dumps(_action_ingest_payload(payload)).encode("utf-8")
        req = request.Request(
            f"{self.base_url}/v1/actions:ingest",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                response.read()
        except (OSError, error.URLError, error.HTTPError) as exc:
            raise RuntimeError(f"cloud action sync failed: {exc}") from exc
        return payload

    def load_events(self) -> list[dict[str, Any]]:
        raise NotImplementedError("Hosted action sync is write-only from the OSS runtime path.")

    def find_event(self, *, event_id: str | None = None, decision_id: str | None = None, event_type: str | None = None) -> dict[str, Any] | None:
        del event_id, decision_id, event_type
        raise NotImplementedError("Hosted action sync is write-only from the OSS runtime path.")


class CloudAuditSinkStub:
    name = "cloud-audit"

    def append(self, event: AuditEvent) -> dict[str, Any]:
        del event
        raise NotImplementedError("Cloud audit sinks are optional extensions and are not part of the OSS runtime path.")

    def load_events(self) -> list[dict[str, Any]]:
        raise NotImplementedError("Cloud audit sinks are optional extensions and are not part of the OSS runtime path.")

    def find_event(self, *, event_id: str | None = None, decision_id: str | None = None, event_type: str | None = None) -> dict[str, Any] | None:
        del event_id, decision_id, event_type
        raise NotImplementedError("Cloud audit sinks are optional extensions and are not part of the OSS runtime path.")


def build_default_audit_sink(audit_path: str | Path | None = None) -> AuditSink:
    local = LocalAuditSink(audit_path)
    hosted = _build_hosted_action_sync()
    if hosted is None:
        return local
    return CompositeAuditSink([local, hosted])


def _build_hosted_action_sync() -> HostedActionSyncAuditSink | None:
    auth = _load_pawly_auth()
    if auth is None:
        return None
    api_key = str(auth.get("api_key", "")).strip()
    if not api_key:
        return None
    return HostedActionSyncAuditSink(
        base_url=_resolve_pawly_cloud_base_url(),
        api_key=api_key,
    )


def _action_ingest_payload(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": event.get("event_id"),
        "decision_id": event.get("decision_id"),
        "timestamp": event.get("timestamp"),
        "event_type": event.get("event_type"),
        "outcome": event.get("outcome"),
        "agent_id": event.get("agent_id"),
        "action": dict(event.get("executed_action") or event.get("action") or {}),
        "executed_action": event.get("executed_action"),
        "risk_score": event.get("risk_score"),
        "request_id": event.get("request_id"),
        "metadata": {
            "reason_codes": event.get("reason_codes") or [],
            "policy_references": event.get("policy_references") or [],
            "execution_result_ref": event.get("execution_result_ref"),
        },
    }


def _load_pawly_auth() -> dict[str, Any] | None:
    path = _pawly_auth_path()
    if not path.exists() or not path.is_file():
        return None
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
    else:
        payload = load_yaml_file(path)
    if isinstance(payload, dict):
        return payload
    return None


def _pawly_auth_path() -> Path:
    explicit = os.environ.get(PAWLY_AUTH_PATH_ENV, "").strip()
    if explicit:
        return Path(explicit)
    return Path.home() / ".pawly" / "pawly_auth.yaml"


def _resolve_pawly_cloud_base_url() -> str:
    return os.environ.get(PAWLY_CLOUD_BASE_URL_ENV, "").strip() or DEFAULT_PAWLY_CLOUD_BASE_URL
