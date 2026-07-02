from __future__ import annotations

from collections import Counter


def summarize_decisions(decisions: list[dict]) -> dict:
    counts = Counter(item.get("type", "unknown") for item in decisions)
    total = sum(counts.values())
    return {
        "total_decisions": total,
        "allow": counts.get("allow", 0),
        "deny": counts.get("deny", 0),
        "require_approval": counts.get("require_approval", 0),
        "simulate": counts.get("simulate", 0),
    }


def summarize_policy_evaluations(decisions: list[dict]) -> dict:
    counts = Counter(item.get("policy_evaluation", {}).get("type", "unknown") for item in decisions)
    total = sum(counts.values())
    return {
        "total_policy_evaluations": total,
        "allow": counts.get("allow", 0),
        "deny": counts.get("deny", 0),
        "require_approval": counts.get("require_approval", 0),
        "simulate": counts.get("simulate", 0),
    }


def summarize_runtime_overlays(decisions: list[dict]) -> dict:
    overlay_decisions = 0
    budget_exhausted = 0
    budget_warning_decisions = 0
    for item in decisions:
        overlays = item.get("runtime_overlays", {})
        budget = overlays.get("budget", {})
        has_overlay = bool(overlays.get("overlay_applied"))
        if budget.get("exhausted"):
            budget_exhausted += 1
        if budget.get("warnings"):
            budget_warning_decisions += 1
        if has_overlay:
            overlay_decisions += 1
    return {
        "overlay_decisions": overlay_decisions,
        "budget_exhausted": budget_exhausted,
        "budget_warning_decisions": budget_warning_decisions,
    }
