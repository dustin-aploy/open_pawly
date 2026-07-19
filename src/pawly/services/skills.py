from __future__ import annotations

import inspect
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any
from urllib import error, request

from pawly.services.cloud import DEFAULT_CLOUD_API_URL, DEFAULT_CLOUD_CONSOLE_URL, CloudConnection
from pawly.skill_registry import SkillRegistry


@dataclass(slots=True)
class SkillService:
    """Skill wiring for Pawly goal execution."""

    registry: SkillRegistry = field(default_factory=SkillRegistry)
    source: str = "local"
    cloud_connection: CloudConnection | None = None

    @classmethod
    def local(cls, skills: Mapping[str, Callable[[dict[str, Any], dict[str, Any]], Any]] | None = None) -> "SkillService":
        registry = SkillRegistry()
        for name, handler in dict(skills or {}).items():
            registry.register(name, handler)
        return cls(registry=registry, source="local")

    @classmethod
    def from_registry(cls, registry: SkillRegistry) -> "SkillService":
        return cls(registry=registry, source="registry")

    @classmethod
    def cloud(
        cls,
        *,
        api_key: str | None = None,
        skill_ids: Sequence[str] | None = None,
        api_url: str = DEFAULT_CLOUD_API_URL,
        console_url: str = DEFAULT_CLOUD_CONSOLE_URL,
    ) -> "SkillService":
        connection = CloudConnection(api_key=api_key, api_url=api_url, console_url=console_url)
        client = HostedSkillClient(connection)
        registry = SkillRegistry()
        for skill_id in skill_ids or []:
            registry.register(str(skill_id), client.handler(str(skill_id)))
        return cls(registry=registry, source="cloud-skills", cloud_connection=connection)

    @classmethod
    def from_openai_tools(
        cls,
        tools: Sequence[Any],
        *,
        name_field: str = "tool_name",
        executor_field: str = "executor",
        fallback_name_field: str = "name",
    ) -> "SkillService":
        registry = SkillRegistry()
        for tool in tools:
            name = _extract_tool_value(tool, name_field, required=False)
            if name is None:
                name = _extract_tool_value(tool, fallback_name_field)
            executor = _extract_tool_value(tool, executor_field, required=False)
            if executor is None and callable(tool):
                executor = tool
            if not callable(executor):
                raise TypeError(f"OpenAI tool '{name}' must provide a callable executor")
            registry.register(str(name), _openai_tool_handler(str(name), executor))
        return cls(registry=registry, source="openai-tools")

    def is_configured(self) -> bool:
        return self.cloud_connection is None or self.cloud_connection.is_configured()

    def to_registry(self) -> SkillRegistry:
        return self.registry

    def alerts(self) -> list[dict[str, str]]:
        if self.cloud_connection is None:
            return []
        dashboard_url = self.cloud_connection.console_url.rstrip("/")
        alerts = [
            {
                "level": "info",
                "code": "cloud_skills_enabled",
                "message": "Hosted skills selected in the dashboard can be called from this project.",
                "action": f"Open {dashboard_url} to search, test, and add skills.",
            }
        ]
        if not self.cloud_connection.is_configured():
            alerts.insert(
                0,
                {
                    "level": "warning",
                    "code": "missing_api_key",
                    "message": "Hosted skills are selected but no PAWLY_API_KEY is configured.",
                    "action": f"Create or copy a hosted key at {dashboard_url}.",
                },
            )
        if not self.registry.action_names():
            alerts.append(
                {
                    "level": "info",
                    "code": "no_cloud_skills_selected",
                    "message": "No hosted skills are selected locally yet.",
                    "action": f"Add marketplace skills to the project at {dashboard_url}.",
                }
            )
        return alerts

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "source": self.source,
            "count": len(self.registry.action_names()),
            "capabilities": self.registry.action_names(),
        }
        if self.cloud_connection is not None:
            payload["mode"] = "cloud"
            payload["cloud"] = self.cloud_connection.to_dict()
            payload["dashboard_url"] = self.cloud_connection.console_url.rstrip("/")
        alerts = self.alerts()
        if alerts:
            payload["alerts"] = alerts
        return payload


@dataclass(slots=True)
class HostedSkillClient:
    connection: CloudConnection

    def handler(self, skill_id: str) -> Callable[[dict[str, Any], dict[str, Any]], Any]:
        def _call(args: dict[str, Any], context: dict[str, Any]) -> Any:
            if not self.connection.is_configured():
                raise RuntimeError(
                    "Hosted skill calls require PAWLY_API_KEY. Add the skill in the dashboard, copy the project key, then retry."
                )
            return self.call(skill_id=skill_id, args=args, context=context)

        return _call

    def call(self, *, skill_id: str, args: Mapping[str, Any], context: Mapping[str, Any]) -> dict[str, Any]:
        payload = json.dumps({"skill_id": skill_id, "input": dict(args), "context": dict(context)}).encode("utf-8")
        req = request.Request(
            f"{self.connection.api_url.rstrip('/')}/v1/skills/{request.pathname2url(skill_id)}:call",
            data=payload,
            headers={
                "Authorization": f"Bearer {self.connection.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=15.0) as response:
                body = response.read().decode("utf-8")
        except (OSError, error.URLError, error.HTTPError) as exc:
            raise RuntimeError(f"hosted skill call failed for {skill_id}: {exc}") from exc
        if not body:
            return {"status": "completed", "skill_id": skill_id}
        parsed = json.loads(body)
        return parsed if isinstance(parsed, dict) else {"result": parsed, "skill_id": skill_id}


def _extract_tool_value(value: Any, field_name: str, *, required: bool = True) -> Any:
    if isinstance(value, Mapping) and field_name in value:
        return value[field_name]
    if hasattr(value, field_name):
        return getattr(value, field_name)
    function_payload = _extract_tool_value(value, "function", required=False) if field_name != "function" else None
    if isinstance(function_payload, Mapping) and field_name in function_payload:
        return function_payload[field_name]
    if function_payload is not None and hasattr(function_payload, field_name):
        return getattr(function_payload, field_name)
    if required:
        raise ValueError(f"unable to extract required field '{field_name}'")
    return None


def _openai_tool_handler(name: str, executor: Callable[..., Any]) -> Callable[[dict[str, Any], dict[str, Any]], Any]:
    def handler(args: dict[str, Any], context: dict[str, Any]) -> Any:
        payload = {**context, **args}
        action_payload = {
            "tool_name": name,
            "name": name,
            "task": str(args.get("objective") or context.get("objective") or name),
            "payload": payload,
        }
        parameters = inspect.signature(executor).parameters
        if len(parameters) == 0:
            return executor()
        return executor(action_payload)

    return handler
