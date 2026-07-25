from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, NotRequired, TypedDict

from pawly import AuditService, HeuristicPolicy, Pawly, PolicyService, SkillService


REPO_ROOT = Path(__file__).resolve().parents[1]
PAWPRINT_PATH = REPO_ROOT / "examples" / "agents" / "goal_first_support_agent.yaml"


class AgentPlan(TypedDict):
    objective: str
    context: dict[str, Any]
    constraints: NotRequired[dict[str, Any]]


def safe_reply(args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "reply",
        "message": "Handled safely without changing the customer's account.",
        "objective": args["objective"],
        "order_id": context.get("order_id"),
    }


def lookup_order(args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    del args
    return {
        "kind": "lookup",
        "order_id": context.get("order_id"),
        "status": "paid",
    }


def issue_refund(args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "refund",
        "objective": args["objective"],
        "order_id": context.get("order_id"),
    }


def plan_from_business_logic(user_message: str, *, order_id: str, customer_id: str) -> AgentPlan:
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


def main() -> int:
    api_key = os.getenv("PAWLY_API_KEY")
    pawly = Pawly(
        str(PAWPRINT_PATH),
        skills=SkillService.local(
            {
                "safe_reply": safe_reply,
                "lookup_order": lookup_order,
                "issue_refund": issue_refund,
            }
        ),
        policy=PolicyService.local(routing=HeuristicPolicy()) if not api_key else PolicyService.cloud(api_key=api_key),
        audit=AuditService.local("./pawly-audit.jsonl")
        if not api_key
        else AuditService.cloud(api_key=api_key, local_path="./pawly-audit.jsonl"),
    )
    plan = plan_from_business_logic(
        "I was charged twice. Can you refund me?",
        order_id="ord_123",
        customer_id="cus_123",
    )
    result = pawly.achieve(**plan)
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
