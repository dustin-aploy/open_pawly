# `run_actions(...)`

In this document `pawly` means the open-source package published from `open_pawly`.

Pawly now supports a one-call candidate-action path that keeps decision and selected-action execution inside `DecisionEngine`.

## Recommended usage

```python
from pawly import DecisionEngine, HeuristicPolicy, SkillRegistry, load_pawprint_file


class SupportAgent:
    def __init__(self):
        self.pawprint_path = "./agents/support_worker.yaml"
        self.pawprint = load_pawprint_file(self.pawprint_path).config

        self.pawly = DecisionEngine(
            self.pawprint_path,
            scoring_policy=HeuristicPolicy(),
        )

        self.skills = SkillRegistry()
        self.skills.register("safe_reply", self.safe_reply)
        self.skills.register("send_external_message", self.send_external_message)
        self.skills.register("lookup_order", self.lookup_order)

        self.pawly.register_skills(self.skills)

    def handle_request(self, user_message, context):
        candidate_actions = self.plan(user_message, context)

        state = {
            "trace_id": context.get("trace_id"),
            "actor": {
                "tenant_id": context.get("tenant_id"),
                "agent_id": "support-agent-v1",
                "user_id": context.get("user_id"),
            },
            "conversation": {
                "current_text": user_message,
            },
        }

        return self.pawly.run_actions(
            state=state,
            actions=candidate_actions,
            context=context,
            pawprint_config=self.pawprint,
        )
```

## What `run_actions(...)` does

`DecisionEngine.run_actions(...)` now:

1. calls `decide_actions(...)`
2. blocks or returns `needs_review` when required
3. executes the selected action through a registered `SkillRegistry`
4. applies deterministic boundary Shield inspection
5. writes audit metadata through the existing audit sink
6. returns a unified payload

Return shape:

```python
{
  "status": "completed" | "blocked" | "needs_review" | "failed",
  "decision": decision.to_dict(),
  "result": skill_result | None,
}
```

## Skill registration

Register your skills once:

```python
self.skills = SkillRegistry()
self.skills.register("safe_reply", self.safe_reply)
self.skills.register("send_external_message", self.send_external_message)
self.pawly.register_skills(self.skills)
```

`decide_actions(...)` still works for advanced or backward-compatible manual flows, but `run_actions(...)` is now the recommended path.

## Shield configuration

Shield is a Pawly policy strategy, not a separate product/runtime.

Developer-facing config is intentionally small:

```yaml
protection:
  level: protected
  assets:
    - customer_data
    - external_write
  handling: cautious
```

Supported fields:

- `level`: `open | standard | protected | confidential`
- `assets`:
  - `customer_data`
  - `private_knowledge`
  - `internal_workflow`
  - `paid_api`
  - `external_write`
- `handling`: `auto | cautious | strict`

If omitted, Pawly uses:

```yaml
protection:
  level: standard
  assets: []
  handling: auto
```

## Boundary-only v1 scope

This version protects the boundary around selected-action execution inside Pawly:

- candidate action decision protection
- action argument inspection/sanitization before execution
- internal execution through `SkillRegistry`
- output inspection/redaction after execution
- audit metadata

This version does not protect:

- skill-internal model calls
- skill-internal RAG calls
- skill-internal external API calls
- internal skill traces
- tool calls that bypass the registered `SkillRegistry`

This version does not implement:

- `pawly.model.generate(...)`
- `pawly.rag.retrieve(...)`
- `pawly.tool.call(...)`
- step-aware routing
- phase-aware protection
- model-purpose routing

## Manual flow remains valid

The older manual pattern still works:

```python
decision = pawly.decide_actions(...)
result = skills.execute(decision.selected_action, context)
```

That remains useful for advanced control, but it is no longer the recommended default integration.

## Future path

- V1: decision + internal selected-action execution + boundary Shield
- V2: optional gateway protection for internal model/RAG/tool calls
- V3: phase-aware native protection for official or high-value skills
