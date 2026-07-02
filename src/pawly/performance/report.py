from __future__ import annotations

from datetime import datetime, timezone

from pawly.pawprint_loader import PawprintConfig
from pawly.performance.metrics import summarize_decisions, summarize_policy_evaluations, summarize_runtime_overlays


def build_daily_report(agent_config: PawprintConfig, decisions: list[dict]) -> dict:
    metrics = summarize_decisions(decisions)
    policy_metrics = summarize_policy_evaluations(decisions)
    overlay_metrics = summarize_runtime_overlays(decisions)
    report = {
        "worker_id": agent_config.id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "status": "failed" if metrics["deny"] else "needs-review" if (metrics["require_approval"] or metrics["simulate"]) else "ok",
            "notes": [
                f"total_decisions={metrics['total_decisions']}",
                f"allow={metrics['allow']}",
                f"require_approval={metrics['require_approval']}",
                f"deny={metrics['deny']}",
                f"simulate={metrics['simulate']}",
            ],
        },
        "policy_summary": {
            "status": "failed" if policy_metrics["deny"] else "needs-review" if (policy_metrics["require_approval"] or policy_metrics["simulate"]) else "ok",
            "notes": [
                f"total_policy_evaluations={policy_metrics['total_policy_evaluations']}",
                f"allow={policy_metrics['allow']}",
                f"require_approval={policy_metrics['require_approval']}",
                f"deny={policy_metrics['deny']}",
                f"simulate={policy_metrics['simulate']}",
            ],
        },
        "runtime_overlay_summary": {
            "notes": [
                f"overlay_decisions={overlay_metrics['overlay_decisions']}",
                f"budget_exhausted={overlay_metrics['budget_exhausted']}",
                f"budget_warning_decisions={overlay_metrics['budget_warning_decisions']}",
            ],
        },
    }
    return report
