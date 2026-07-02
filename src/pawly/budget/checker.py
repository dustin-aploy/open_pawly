from __future__ import annotations

from dataclasses import dataclass, field

from pawly.budget.state import BudgetState
from pawly.types import Intent


@dataclass(slots=True)
class BudgetResult:
    exhausted: bool
    warnings: list[str] = field(default_factory=list)
    consumed: dict[str, float] = field(default_factory=dict)


def check_budget(agent_config: dict, state: BudgetState, intent: Intent) -> BudgetResult:
    warnings: list[str] = []
    consumed: dict[str, float] = {}
    exhausted = False
    for limit in agent_config.get("budget", {}).get("limits", []):
        name = limit.get("name", "unnamed-limit")
        amount = float(limit.get("amount", 0))
        unit = limit.get("unit", "count")
        increment = float(intent.metadata.get(name, 1 if unit == "count" else 0))
        current = state.consume(name, increment)
        consumed[name] = current
        if amount and current >= amount:
            if limit.get("enforcement") == "hard":
                exhausted = True
            warnings.append(f"budget limit reached for {name}: {current:g}/{amount:g}")
        else:
            for threshold in agent_config.get("budget", {}).get("warning_thresholds", []):
                if threshold.get("limit") == name:
                    percent = float(threshold.get("percent", 0))
                    if amount and current >= amount * (percent / 100.0):
                        warnings.append(f"budget warning for {name}: {current:g}/{amount:g}")
    return BudgetResult(exhausted=exhausted, warnings=list(dict.fromkeys(warnings)), consumed=consumed)
