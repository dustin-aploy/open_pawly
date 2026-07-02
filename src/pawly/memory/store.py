from __future__ import annotations

from collections import defaultdict
from typing import Any

from pawly.memory.tiers import MemoryTier


class MemoryStore:
    def __init__(self, mode: str = MemoryTier.NONE.value) -> None:
        self.mode = MemoryTier(mode)
        self._store: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def remember(self, category: str, payload: dict[str, Any]) -> None:
        if self.mode == MemoryTier.NONE:
            return
        self._store[category].append(payload)

    def recall(self, category: str) -> list[dict[str, Any]]:
        return list(self._store.get(category, []))

    def clear(self) -> None:
        self._store.clear()
