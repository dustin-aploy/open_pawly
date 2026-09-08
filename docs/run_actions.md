# Advanced Candidate-Action Policy Control

In this document `pawly` means the open-source package published from `open_pawly`.

Pawly supports a lower-level path that applies local Policy to candidate actions
already supplied by an adapter or application. This is not Open Pawly Skill
Discovery or Skill Selection as a product capability.

Most application developers should use `Pawly(...).achieve(...)`, where Pawly
applies local Policy across registered Skill actions before calling this
lower-level path.

## Adapter usage

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

`decide_actions(...)` still works for advanced or backward-compatible manual flows. For application code, prefer `Pawly(...).achieve(...)`.

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
  - `business_workflow`
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
- execution through `SkillRegistry`
- output inspection/redaction after execution
- audit metadata

This version does not protect:

- model calls made inside a Skill
- retrieval calls made inside a Skill
- external API calls made inside a Skill
- traces produced inside a Skill
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

That remains useful for advanced control, but it is not the recommended default integration.
