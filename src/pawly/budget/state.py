from __future__ import annotations

from collections import defaultdict


class BudgetState:
    def __init__(self) -> None:
        self._usage = defaultdict(float)

    def consume(self, name: str, amount: float) -> float:
        self._usage[name] += amount
        return self._usage[name]

    def snapshot(self) -> dict[str, float]:
        return dict(self._usage)
