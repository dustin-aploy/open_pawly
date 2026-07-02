from __future__ import annotations

from typing import Any


def diff_actions(original: dict[str, Any] | None, executed: dict[str, Any] | None) -> dict[str, Any]:
    original = original or {}
    executed = executed or {}
    changed_fields: list[dict[str, Any]] = []
    for key in sorted(set(original) | set(executed)):
        if original.get(key) != executed.get(key):
            changed_fields.append(
                {
                    "field": key,
                    "original": original.get(key),
                    "executed": executed.get(key),
                }
            )
    return {
        "changed": bool(changed_fields),
        "changed_fields": changed_fields,
        "original_action": original,
        "executed_action": executed,
    }
