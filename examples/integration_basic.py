from __future__ import annotations

import json
from pathlib import Path

from pawly import Action, HeuristicPolicy, load_pawprint_file
from pawly.runtime import DecisionEngine

try:
    from pawly_cloud import CloudPolicy
except ImportError:
    CloudPolicy = None


REPO_ROOT = Path(__file__).resolve().parents[1]
PAWPRINT_PATH = REPO_ROOT / "examples" / "agents" / "basic_worker.yaml"


def _decision_payload(runtime: DecisionEngine, decision) -> dict[str, object]:
    payload = runtime.log_decision(decision)
    return {
        "selected_action": None if decision.selected_action is None else decision.selected_action.name,
        "decision": payload["decision"],
        "boundary_type": payload["boundary_type"],
        "decision_source": payload["decision_source"],
        "requires_review": payload["requires_review"],
        "reason": payload["reason"],
        "policy_fallback_used": payload["policy_fallback_used"],
    }


def main() -> int:
    loaded = load_pawprint_file(PAWPRINT_PATH)
    candidate_actions = [
        Action(name="safe_reply", arguments={"template": "status-update"}, target="helpdesk"),
        Action(name="publish_post", arguments={"draft_id": "post-42"}),
    ]
    state = {
        "preferred_targets": ["helpdesk"],
        "trace_id": "integration-basic",
    }

    local_runtime = DecisionEngine(
        PAWPRINT_PATH,
        scoring_policy=HeuristicPolicy(),
    )
    local_decision = local_runtime.decide_actions(state, candidate_actions, loaded.config)

    print("Loaded Pawprint contract:")
    print(json.dumps(loaded.config.to_dict(), indent=2, sort_keys=True))

    print("\nCandidate actions:")
    print(json.dumps([action.to_dict() for action in candidate_actions], indent=2, sort_keys=True))

    print("\nLocal Pawly decision without pawly-cloud:")
    print(json.dumps(_decision_payload(local_runtime, local_decision), indent=2, sort_keys=True))

    if CloudPolicy is None:
        print("\nOptional CloudPolicy integration:")
        print(json.dumps({"status": "pawly-cloud not installed; local Pawly path works offline"}, indent=2, sort_keys=True))
        return 0

    cloud_policy = CloudPolicy(api_key="", endpoint="", fallback_policy=HeuristicPolicy())
    if not cloud_policy.is_scoring_available():
        print("\nOptional CloudPolicy integration:")
        print(
            "CloudPolicy is installed but credentials are missing. "
            "Falling back to local heuristic behavior without crashing."
        )

    cloud_runtime = DecisionEngine(
        PAWPRINT_PATH,
        scoring_policy=cloud_policy,
    )
    cloud_decision = cloud_runtime.decide_actions(state, [Action(name="publish_post", arguments={"draft_id": "post-42"})], loaded.config)

    print(json.dumps(_decision_payload(cloud_runtime, cloud_decision), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
