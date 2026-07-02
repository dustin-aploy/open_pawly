from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pawly.contracts import Action


SkillHandler = Callable[[dict[str, Any], dict[str, Any]], Any]


class MissingSkillRegistryError(RuntimeError):
    """Raised when run_actions is used before a skill registry is registered."""


class SkillRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, SkillHandler] = {}

    def register(self, action_name: str, handler: SkillHandler) -> None:
        normalized = str(action_name).strip()
        if not normalized:
            raise ValueError("action_name must not be empty")
        self._handlers[normalized] = handler

    def execute(self, action: Action, context: dict[str, Any] | None = None) -> Any:
        handler = self._handlers.get(action.name)
        if handler is None:
            raise KeyError(f"no skill registered for action: {action.name}")
        return handler(dict(action.arguments), dict(context or {}))

