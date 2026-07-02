from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]

from pawly.contracts import Action, PolicyScore
from pawly.pawprint_loader import load_pawprint_file
from pawly.policy import Policy
from pawly.runtime import DecisionEngine
from pawly.skill_registry import SkillRegistry
try:
    from pawly_cloud import CloudPolicy
except ImportError:
    CloudPolicy = None


class CustomCloudPolicy(Policy):
    name = "custom"
    source = "custom"
    supports_scoring = True

    def evaluate(self, state, actions):
        del state
        scores: list[PolicyScore] = []
        for action in actions:
            if action.name == "publish_post":
                scores.append(
                    PolicyScore(
                        risk_score=0.08,
                        reason_codes=["custom_quality_gate"],
                        audit_tags=["policy:custom", "source:custom"],
                        uncertainty=0.12,
                    )
                )
            else:
                scores.append(
                    PolicyScore(
                        risk_score=0.35,
                        reason_codes=["custom_default_rank"],
                        audit_tags=["policy:custom", "source:custom"],
                    )
                )
        return scores


def _summarize(runtime: DecisionEngine, decision) -> dict[str, object]:
    payload = runtime.log_decision(decision)
    return {
        "trace_id": payload["trace_id"],
        "selected_action": decision.selected_action.name if decision.selected_action is not None else None,
        "decision": payload["decision"],
        "requires_review": payload["requires_review"],
        "boundary_type": payload["boundary_type"],
        "decision_source": payload["decision_source"],
        "reason": payload["reason"],
        "policy_name": payload["policy_name"],
        "policy_fallback_used": payload["policy_fallback_used"],
        "scores": payload.get("scores", []),
    }


def main() -> int:
    pawprint_path = REPO_ROOT / "examples" / "agents" / "basic_worker.yaml"
    loaded = load_pawprint_file(pawprint_path)

    print("Loaded Pawprint YAML:")
    print(json.dumps(loaded.config.to_dict(), indent=2, sort_keys=True))

    heuristic_runtime = DecisionEngine(
        pawprint_path,
        scoring_policy="heuristic",
    )
    skill_registry = SkillRegistry()
    skill_registry.register("safe_reply", lambda args, context: {"kind": "reply", "args": args, "context": context})
    skill_registry.register("publish_post", lambda args, context: {"kind": "publish", "args": args, "context": context})
    heuristic_runtime.register_skills(skill_registry)
    custom_runtime = DecisionEngine(
        pawprint_path,
        scoring_policy=CustomCloudPolicy(),
    )
    cloud_runtime = None
    cloud_fallback_runtime = None
    if CloudPolicy is not None:
        cloud_runtime = DecisionEngine(
            pawprint_path,
            scoring_policy=CloudPolicy(api_key="demo-key", endpoint="https://example.com/policy"),
        )
        cloud_fallback_runtime = DecisionEngine(
            pawprint_path,
            scoring_policy=CloudPolicy(api_key="", endpoint=""),
        )

    local_allow = heuristic_runtime.decide_actions(
        {"preferred_targets": ["helpdesk"]},
        [Action(name="safe_reply", arguments={}, target="helpdesk")],
        loaded.config,
    )
    local_review = heuristic_runtime.decide_actions(
        {},
        [Action(name="send_external_message", arguments={"channel": "email"})],
        loaded.config,
    )
    local_block = heuristic_runtime.decide_actions(
        {},
        [Action(name="issue_refund", arguments={"amount": 25})],
        loaded.config,
    )
    local_publish = heuristic_runtime.decide_actions(
        {},
        [Action(name="publish_post", arguments={"draft_id": "post-42"})],
        loaded.config,
    )

    custom_cloud = custom_runtime.decide_actions(
        {},
        [Action(name="publish_post", arguments={"draft_id": "post-42"})],
        loaded.config,
    )
    executed_local = heuristic_runtime.run_actions(
        state={"preferred_targets": ["helpdesk"], "trace_id": "basic-usage-local"},
        actions=[Action(name="safe_reply", arguments={"template": "status-update"}, target="helpdesk")],
        context={"channel": "chat"},
        pawprint_config=loaded.config,
    )

    cloud_publish = None
    cloud_missing_creds = None
    cloud_api_failure = None
    if cloud_runtime is not None and cloud_fallback_runtime is not None:
        with mock.patch("pawly_cloud.client.request.urlopen") as mocked:
            mocked.return_value.__enter__.return_value.read.return_value = (
                b'{"scores":[{"action_name":"publish_post","score":0.06,"uncertainty":0.08,"reason":"cloud_rank","metadata":{"audit_tags":["policy:cloud"]}}]}'
            )
            cloud_publish = cloud_runtime.decide_actions(
                {},
                [Action(name="publish_post", arguments={"draft_id": "post-42"})],
                loaded.config,
            )

        cloud_missing_creds = cloud_fallback_runtime.decide_actions(
            {},
            [Action(name="publish_post", arguments={"draft_id": "post-42"})],
            loaded.config,
        )

        with mock.patch("pawly_cloud.client.request.urlopen", side_effect=OSError("timeout")):
            cloud_api_failure = cloud_runtime.decide_actions(
                {},
                [Action(name="publish_post", arguments={"draft_id": "post-42"})],
                loaded.config,
            )

    print("\nLocal heuristic mode:")
    print(
        json.dumps(
            {
                "allow_action": _summarize(heuristic_runtime, local_allow),
                "review_action": _summarize(heuristic_runtime, local_review),
                "block_action": _summarize(heuristic_runtime, local_block),
                "publish_action": _summarize(heuristic_runtime, local_publish),
                "run_actions": executed_local,
            },
            indent=2,
            sort_keys=True,
        )
    )

    print("\nCustom cloud policy mode:")
    print(json.dumps(_summarize(custom_runtime, custom_cloud), indent=2, sort_keys=True))

    if cloud_runtime is not None and cloud_publish is not None and cloud_fallback_runtime is not None:
        print("\nCloudPolicy mode:")
        print(json.dumps(_summarize(cloud_runtime, cloud_publish), indent=2, sort_keys=True))

        print("\nCloud fallback behavior:")
        print(
            json.dumps(
                {
                    "missing_credentials": _summarize(cloud_fallback_runtime, cloud_missing_creds),
                    "api_failure": _summarize(cloud_runtime, cloud_api_failure),
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print("\nCloudPolicy mode:")
        print(json.dumps({"skipped": "install pawly-cloud to run the optional cloud example path"}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
