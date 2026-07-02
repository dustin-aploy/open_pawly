from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

from pawly import wrap_execute_fn


def send_support_reply(task: str, action: str, confidence: float, metadata: dict | None = None) -> dict:
    del confidence
    return {
        "sent": True,
        "task": task,
        "action": action,
        "metadata": metadata or {},
    }


def main() -> int:
    wrapped_send = wrap_execute_fn(
        send_support_reply,
        REPO_ROOT / "examples" / "agents" / "basic_worker.yaml",
    )

    allowed = wrapped_send(
        "Answer order status questions for a customer",
        "draft helpful reply",
        0.95,
        {"channel": "email"},
    )
    review_required = wrapped_send(
        "Send an external status update to a partner",
        "send_external_message",
        0.95,
        {"channel": "email"},
    )

    print(json.dumps({"allowed": allowed, "review_required": review_required}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
