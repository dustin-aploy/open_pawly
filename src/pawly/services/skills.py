from __future__ import annotations

import importlib.util
import inspect
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
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
    def single(cls, name: str, handler: Callable[[dict[str, Any], dict[str, Any]], Any]) -> "SkillService":
        return cls.local({name: handler})

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
        directory: str | Path | None = None,
        adapter: str = "python",
        skills: Mapping[str, Callable[[dict[str, Any], dict[str, Any]], Any]] | Sequence[Any] | None = None,
        api_url: str = DEFAULT_CLOUD_API_URL,
        console_url: str = DEFAULT_CLOUD_CONSOLE_URL,
    ) -> "SkillService":
        connection = CloudConnection(api_key=api_key, api_url=api_url, console_url=console_url)
        client = CloudSkillClient(connection)
        registry = SkillRegistry()
        for name in _skill_names(directory=directory, adapter=adapter, skills=skills):
            registry.register(name, client.handler(name))
        return cls(registry=registry, source="cloud-skills", cloud_connection=connection)

    @classmethod
    def from_directory(
        cls,
        directory: str | Path,
        *,
        adapter: str = "python",
        recursive: bool = True,
    ) -> "SkillService":
        return cls(
            registry=_registry_from_definitions(_load_skill_definitions(directory, adapter=adapter, recursive=recursive)),
            source=f"{adapter}-directory" if adapter != "python" else "directory",
        )

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
                "message": "Cloud skills for this project can be called through Pawly.",
                "action": f"Open {dashboard_url} to search, test, and manage skills.",
            }
        ]
        if not self.cloud_connection.is_configured():
            alerts.insert(
                0,
                {
                    "level": "warning",
                    "code": "missing_api_key",
                    "message": "Cloud skills are selected but no PAWLY_API_KEY is configured.",
                    "action": f"Create or copy a cloud key at {dashboard_url}.",
                },
            )
        if not self.registry.action_names():
            alerts.append(
                {
                    "level": "info",
                    "code": "no_cloud_skills_selected",
                    "message": "No local skill source was provided for cloud registration.",
                    "action": f"Add marketplace skills or connect a local skills directory at {dashboard_url}.",
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
class CloudSkillClient:
    connection: CloudConnection

    def handler(self, skill_id: str) -> Callable[[dict[str, Any], dict[str, Any]], Any]:
        def _call(args: dict[str, Any], context: dict[str, Any]) -> Any:
            if not self.connection.is_configured():
                raise RuntimeError(
                    "Cloud skill calls require PAWLY_API_KEY. Add or sync the skill in the dashboard, copy the project key, then retry."
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
            raise RuntimeError(f"cloud skill call failed for {skill_id}: {exc}") from exc
        if not body:
            return {"status": "completed", "skill_id": skill_id}
        parsed = json.loads(body)
        return parsed if isinstance(parsed, dict) else {"result": parsed, "skill_id": skill_id}


def _skill_names(
    *,
    directory: str | Path | None,
    adapter: str,
    skills: Mapping[str, Callable[[dict[str, Any], dict[str, Any]], Any]] | Sequence[Any] | None,
) -> list[str]:
    names: list[str] = []
    if directory is not None:
        names.extend(_registry_from_definitions(_load_skill_definitions(directory, adapter=adapter)).action_names())
    if isinstance(skills, Mapping):
        names.extend(str(name).strip() for name in skills)
    elif skills is not None:
        names.extend(_registry_from_definitions(skills).action_names())
    return sorted({name for name in names if name})


def _load_skill_definitions(directory: str | Path, *, adapter: str = "python", recursive: bool = True) -> list[Any]:
    adapter = str(adapter or "python").strip().lower()
    if adapter not in {"python", "openai", "claude"}:
        raise ValueError("adapter must be one of: python, openai, claude")
    root = Path(directory)
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"skills directory not found: {root}")
    pattern = "**/*.py" if recursive else "*.py"
    definitions: list[Any] = []
    for path in sorted(root.glob(pattern)):
        if path.name.startswith("_"):
            continue
        module = _load_python_module(path)
        for field_name in ("skills", "tools"):
            value = getattr(module, field_name, None)
            if value is not None:
                if isinstance(value, Mapping):
                    definitions.extend(
                        {"name": name, "executor": handler} if callable(handler) else handler
                        for name, handler in value.items()
                    )
                else:
                    definitions.extend(list(value))
        for field_name in ("skill", "tool"):
            value = getattr(module, field_name, None)
            if value is not None:
                definitions.append(value)
        if adapter == "openai":
            for field_name in ("openai_tool", "openai_tools"):
                value = getattr(module, field_name, None)
                if value is not None:
                    definitions.extend(list(value) if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) else [value])
        if adapter == "claude":
            for field_name in ("claude_skill", "claude_skills"):
                value = getattr(module, field_name, None)
                if value is not None:
                    definitions.extend(list(value) if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) else [value])
        for field_name in ("handler", "executor", "run", "call"):
            value = getattr(module, field_name, None)
            if callable(value):
                definitions.append({"name": path.stem, "executor": value})
                break
    return definitions


def _load_python_module(path: Path) -> Any:
    module_name = f"_pawly_skill_{path.stem}_{abs(hash(path))}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"unable to import skill module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _registry_from_definitions(definitions: Sequence[Any]) -> SkillRegistry:
    registry = SkillRegistry()
    for definition in definitions:
        name, executor = _skill_definition(definition)
        registry.register(name, executor)
    return registry


def _skill_definition(definition: Any) -> tuple[str, Callable[[dict[str, Any], dict[str, Any]], Any]]:
    if callable(definition) and not isinstance(definition, Mapping):
        name = getattr(definition, "tool_name", None) or getattr(definition, "skill_name", None) or getattr(definition, "name", None) or definition.__name__
        return str(name), _local_skill_handler(definition)
    name = _extract_tool_value(definition, "tool_name", required=False)
    if name is None:
        name = _extract_tool_value(definition, "skill_name", required=False)
    if name is None:
        name = _extract_tool_value(definition, "name", required=False)
    executor = _extract_tool_value(definition, "executor", required=False)
    if executor is None:
        executor = _extract_tool_value(definition, "handler", required=False)
    if executor is None:
        executor = _extract_tool_value(definition, "run", required=False)
    if executor is None:
        executor = _extract_tool_value(definition, "call", required=False)
    if not name:
        raise ValueError("skill definition must provide name or tool_name")
    if not callable(executor):
        raise TypeError(f"skill '{name}' must provide a callable executor, handler, run, or call")
    return str(name), _local_skill_handler(executor)


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


def _local_skill_handler(executor: Callable[..., Any]) -> Callable[[dict[str, Any], dict[str, Any]], Any]:
    def handler(args: dict[str, Any], context: dict[str, Any]) -> Any:
        parameters = inspect.signature(executor).parameters
        if len(parameters) == 0:
            return executor()
        if len(parameters) == 1:
            return executor({**context, **args})
        return executor(args, context)

    return handler
