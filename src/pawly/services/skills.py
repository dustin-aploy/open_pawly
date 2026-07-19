from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from pawly.skill_registry import SkillRegistry


@dataclass(slots=True)
class SkillService:
    """Skill wiring for Pawly goal execution."""

    registry: SkillRegistry = field(default_factory=SkillRegistry)
    source: str = "local"

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

    def to_registry(self) -> SkillRegistry:
        return self.registry

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "count": len(self.registry.action_names()),
            "capabilities": self.registry.action_names(),
        }


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
