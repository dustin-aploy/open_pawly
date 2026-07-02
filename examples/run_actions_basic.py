from __future__ import annotations

import json
from pathlib import Path

from pawly import Action, HeuristicPolicy, SkillRegistry, run_actions


REPO_ROOT = Path(__file__).resolve().parents[1]
PAWPRINT_PATH = REPO_ROOT / "examples" / "agents" / "basic_worker.yaml"


def main() -> int:
    skills = SkillRegistry()
    skills.register(
        "safe_reply",
        lambda args, context: {
            "kind": "reply",
            "message": f"safe:{args.get('message', '')}",
            "channel": context.get("channel"),
        },
    )
    skills.register(
        "publish_post",
        lambda args, context: {
            "kind": "publish",
            "draft_id": args.get("draft_id"),
            "channel": context.get("channel"),
        },
    )

    allowed = run_actions(
        PAWPRINT_PATH,
        state={
            "preferred_targets": ["helpdesk"],
            "trace_id": "run-actions-basic-allow",
        },
        actions=[Action(name="safe_reply", arguments={"message": "hello"}, target="helpdesk")],
        context={"channel": "chat"},
        skill_registry=skills,
        scoring_policy=HeuristicPolicy(),
    )
    review_required = run_actions(
        PAWPRINT_PATH,
        state={"trace_id": "run-actions-basic-review"},
        actions=[Action(name="send_external_message", arguments={"channel": "email"})],
        context={"channel": "email"},
        skill_registry=skills,
        scoring_policy=HeuristicPolicy(),
    )
    blocked = run_actions(
        PAWPRINT_PATH,
        state={"trace_id": "run-actions-basic-block"},
        actions=[Action(name="issue_refund", arguments={"amount": 25})],
        context={"channel": "chat"},
        skill_registry=skills,
        scoring_policy=HeuristicPolicy(),
    )

    print(
        json.dumps(
            {
                "allowed": allowed,
                "review_required": review_required,
                "blocked": blocked,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
