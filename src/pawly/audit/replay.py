from __future__ import annotations

from pathlib import Path
from typing import Any

from pawly.audit.diff import diff_actions
from pawly.audit.ledger import AuditLedger


def load_audit_record(
    path: str | Path,
    *,
    event_id: str | None = None,
    decision_id: str | None = None,
    event_type: str = "governed-execution",
) -> dict[str, Any]:
    ledger = AuditLedger(path)
    record = ledger.find_event(event_id=event_id, decision_id=decision_id, event_type=event_type)
    if record is None:
        raise KeyError(event_id or decision_id or event_type)
    return record


def replay_governed_path(record: dict[str, Any]) -> dict[str, Any]:
    original_action = record.get("action", {})
    executed_action = record.get("executed_action")
    action_diff = record.get("action_diff") or diff_actions(original_action, executed_action)
    return {
        "event_id": record.get("event_id"),
        "decision_id": record.get("decision_id"),
        "agent_id": record.get("agent_id"),
        "original_intent": record.get("original_intent"),
        "normalized_intent": record.get("normalized_intent"),
        "policy": {
            "matched_rules": record.get("matched_policy_rules", record.get("policy_references", [])),
            "risk_score": record.get("risk_score"),
            "policy_evaluation": record.get("policy_evaluation"),
            "final_decision": record.get("final_decision"),
        },
        "approval": record.get("approval"),
        "execution": record.get("execution"),
        "original_action": original_action,
        "executed_action": executed_action,
        "action_diff": action_diff,
    }
