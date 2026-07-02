from __future__ import annotations

from typing import Callable


Hook = Callable[[dict], None]


class HookRegistry:
    def __init__(self) -> None:
        self.before_decision: list[Hook] = []
        self.after_decision: list[Hook] = []

    def run_before(self, payload: dict) -> None:
        for hook in self.before_decision:
            hook(payload)

    def run_after(self, payload: dict) -> None:
        for hook in self.after_decision:
            hook(payload)
