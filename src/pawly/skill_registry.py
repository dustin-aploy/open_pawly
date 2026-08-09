from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from pawly.contracts import Action


SkillHandler = Callable[[dict[str, Any], dict[str, Any]], Any]


@dataclass(slots=True)
class SkillMetadata:
    name: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    category: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    available: bool = True
    allowed: bool = True

    def compact_schema(self) -> dict[str, Any]:
        schema = self.metadata.get("schema")
        if not isinstance(schema, Mapping):
            schema = self.metadata.get("input_schema")
        return dict(schema) if isinstance(schema, Mapping) else {}

    def compact_card(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "tags": list(self.tags),
            "category": self.category,
            "schema": self.compact_schema(),
        }


def skill_metadata_from_mapping(name: str, value: Mapping[str, Any] | None) -> SkillMetadata:
    payload = dict(value or {})
    tags = payload.get("tags") or payload.get("labels") or []
    if isinstance(tags, str):
        tags = [tags]
    return SkillMetadata(
        name=str(payload.get("name") or name),
        description=str(payload.get("description") or payload.get("summary") or ""),
        tags=[str(item) for item in tags],
        category=str(payload.get("category") or ""),
        metadata=dict(payload.get("metadata") or payload),
        available=bool(payload.get("available", True)),
        allowed=bool(payload.get("allowed", True)),
    )


class MissingSkillRegistryError(RuntimeError):
    """Raised when run_actions is used before a skill registry is registered."""


class SkillRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, SkillHandler] = {}
        self._metadata: dict[str, SkillMetadata] = {}

    def register(self, action_name: str, handler: SkillHandler, *, metadata: Mapping[str, Any] | SkillMetadata | None = None) -> None:
        normalized = str(action_name).strip()
        if not normalized:
            raise ValueError("action_name must not be empty")
        self._handlers[normalized] = handler
        if isinstance(metadata, SkillMetadata):
            self._metadata[normalized] = metadata
        elif metadata is not None:
            self._metadata[normalized] = skill_metadata_from_mapping(normalized, metadata)

    def action_names(self) -> list[str]:
        return sorted(self._handlers)

    def metadata(self, action_name: str) -> SkillMetadata | None:
        return self._metadata.get(action_name)

    def metadata_by_name(self) -> dict[str, SkillMetadata]:
        return dict(self._metadata)

    def execute(self, action: Action, context: dict[str, Any] | None = None) -> Any:
        handler = self._handlers.get(action.name)
        if handler is None:
            raise KeyError(f"no skill registered for action: {action.name}")
        return handler(dict(action.arguments), dict(context or {}))
