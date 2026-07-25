from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, NotRequired, TypedDict

from pawly import AuditService, HeuristicPolicy, Pawly, PolicyService, SkillService


EXAMPLE_ROOT = Path(__file__).resolve().parent
AGENT_PAWPRINT = EXAMPLE_ROOT / "agents" / "goal_first_support_agent.yaml"


class AgentPlan(TypedDict):
    objective: str
    context: dict[str, Any]
    constraints: NotRequired[dict[str, Any]]


def lookup_order(args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    del args
    return {
        "order_id": context["order_id"],
        "status": "paid",
        "duplicate_charge": True,
    }


def safe_reply(args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    return {
        "message": "We checked the order and will follow up without changing the account automatically.",
        "objective": args["objective"],
        "order_id": context["order_id"],
    }


def issue_refund(args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "refund_requested",
        "objective": args["objective"],
        "order_id": context["order_id"],
    }


pawly = Pawly(
    str(AGENT_PAWPRINT),
    skills=SkillService.local(
        {
            "lookup_order": lookup_order,
            "safe_reply": safe_reply,
            "issue_refund": issue_refund,
        }
    ),
    policy=PolicyService.local(routing=HeuristicPolicy()),
    audit=AuditService.local(os.environ.get("PAWLY_AUDIT_PATH", str(EXAMPLE_ROOT / "goal-first-audit.jsonl"))),
)


class SupportAgentRuntime:
    """Minimal agent runtime boundary used by this example.

    In production this method is usually backed by your agent framework's
    structured-output mode. The contract is the same: return objective, context,
    and optional constraints; never call production skills directly.
    """

    def plan(self, user_message: str, *, order_id: str, customer_id: str) -> AgentPlan:
        normalized = user_message.lower()
        if "refund" in normalized or "charged" in normalized:
            objective = f"safe_reply about a billing question; do not issue_refund automatically: {user_message}"
            constraints = {"max_refund": 0}
        elif "order" in normalized:
            objective = f"lookup_order and safe_reply for this customer request: {user_message}"
            constraints = {}
        else:
            objective = f"safe_reply for this support request: {user_message}"
            constraints = {}
        return {
            "objective": objective,
            "context": {
                "order_id": order_id,
                "customer_id": customer_id,
                "channel": "chat",
            },
            "constraints": constraints,
        }


def agent_runtime_structured_output(user_message: str, *, order_id: str, customer_id: str) -> AgentPlan:
    """Compatibility helper for framework examples that expect a function."""
    return SupportAgentRuntime().plan(user_message, order_id=order_id, customer_id=customer_id)


def logic_plan_without_agent_runtime(user_message: str, *, order_id: str, customer_id: str) -> AgentPlan:
    """Use the same contract when a workflow is simple deterministic code."""
    normalized = user_message.lower()
    if "refund" in normalized or "charged" in normalized:
        objective = f"safe_reply about a billing question; do not issue_refund automatically: {user_message}"
        constraints = {"max_refund": 0}
    elif "order" in normalized:
        objective = f"lookup_order and safe_reply for this customer request: {user_message}"
        constraints = {}
    else:
        objective = f"safe_reply for this support request: {user_message}"
        constraints = {}
    return {
        "objective": objective,
        "context": {
            "order_id": order_id,
            "customer_id": customer_id,
            "channel": "chat",
        },
        "constraints": constraints,
    }


def handle_agent_message(user_message: str, *, order_id: str, customer_id: str) -> dict[str, Any]:
    agent_runtime = SupportAgentRuntime()
    plan = agent_runtime.plan(user_message, order_id=order_id, customer_id=customer_id)
    result = pawly.achieve(**plan)
    if result.status == "completed":
        return {"status": "completed", "result": result.result, "receipt": result.action_receipt}
    if result.status == "needs_review":
        return {"status": "needs_review", "receipt": result.action_receipt}
    return {"status": result.status, "reason": result.needs or result.error, "receipt": result.action_receipt}


if __name__ == "__main__":
    payload = handle_agent_message(
        "I was charged twice. Can you refund me?",
        order_id="ord_123",
        customer_id="cus_123",
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
