# Pawly (OSS)

`pawly` is the open-source local decision engine published from this `open_pawly` project.
Throughout this project, `pawly` means the OSS package; the full product (OSS plus the cloud
version) is the Pawly platform, and cloud-only behavior lives in `pawly-cloud`.

It depends on `pawprint` and works without `pawly-cloud`.

Contents:

- `src/pawly/`: core package
- `tests/`: runtime tests
- `test-suite/`: local conformance suite
- `examples/`: runnable examples
- `adapters/`: adapter stubs and docs
- `scripts/`: bootstrap and smoke scripts
- `docs/`: architecture and runtime notes
  - skill-protection compatibility notes live in `docs/protected_skills.md`

Public runtime surface:

- `decide(...)`
- `run(...)`
- `DecisionEngine.register_skills(...)`
- `DecisionEngine.run_actions(...)`
- `wrap_*` helpers for existing tool or skill executors

Dependency direction:

- `pawly` depends on `pawprint`
- `pawly-cloud` may depend on `pawly`
- `pawly` does not depend on `pawly-cloud`

`pawly` is an execution-boundary controller and decision engine. It is not a runtime replacement for host frameworks.

Skill protection note:

- `pawly` is compatible with skill-protection metadata declared in `pawprint`
- `pawly` does not guarantee anti-absorption
- `pawly` only avoids exposing obvious private fields to model-visible context
- full cloud skill-protection enforcement belongs in `pawly-cloud`
- `pawly` remains independent from `pawly-cloud`

## Install

From PyPI (after release):

```bash
pip install pawly
```

This pulls in `pawly-pawprint` automatically. Do **not** run `pip install pawprint` — that PyPI name belongs to an unrelated package.

From GitHub:

```bash
pip install "git+https://github.com/dustin-aploy/pawprint.git"
pip install "git+https://github.com/dustin-aploy/open_pawly.git" --no-deps
```

From a local checkout of this repository (with sibling `pawprint` checkout):

```bash
pip install -e ../pawprint
pip install --no-build-isolation --no-deps -e .
```

Or use `scripts/bootstrap.sh`, which installs sibling `pawprint` when present.

`pawly-cloud` is optional. `examples/basic_usage.py` runs without it and skips cloud-specific output when the package is not installed.

## Quick Start

1. Install `pawly` (PyPI) or follow the GitHub/local steps in [Install](#install):

```bash
pip install pawly
```

2. Write a Pawprint file such as `worker.yaml`:

```yaml
metadata:
  id: support-triage-worker
  name: Support Triage Worker
  description: Reviews inbound support requests.

capabilities:
  - name: safe_reply
    description: Send a low-risk reply.
  - name: publish_post
    description: Publish a prepared update.

boundaries:
  allow:
    - safe_reply
    - publish_post
  review:
    - send_external_message
  block:
    - issue_refund
```

3. Validate the contract:

```bash
python -m pawprint.validate ./worker.yaml
```

4. Register skills and let Pawly decide + execute in one call:

```python
from pawly import Action, DecisionEngine, HeuristicPolicy, SkillRegistry

runtime = DecisionEngine(
    "./worker.yaml",
    scoring_policy=HeuristicPolicy(),
)

skills = SkillRegistry()
skills.register("safe_reply", lambda args, context: {"kind": "reply", "args": args, "context": context})
skills.register("publish_post", lambda args, context: {"kind": "publish", "args": args, "context": context})
runtime.register_skills(skills)

result = runtime.run_actions(
    state={"preferred_targets": ["helpdesk"]},
    actions=[
        Action(name="safe_reply", arguments={}, target="helpdesk"),
        Action(name="publish_post", arguments={"draft_id": "post-42"}),
    ],
    context={"channel": "chat"},
)

print(result["status"])
print(result["decision"]["selected_action"])
print(result["result"])
```

`pawly` applies hard Pawprint boundaries first:

- `block`: removed completely
- `review`: may be selected, but still requires approval
- `allow`: scored normally

If you set the runtime `scoring_policy` to `cloud`, Pawly sends `allow` and `review` candidates to the configured cloud policy. Cloud may still recommend review, but runtime outputs remain aligned to Pawprint boundaries: `allow`, `review`, and `block`.

Manual `decide(...)` and `decide_actions(...)` flows are still available for advanced integrations, but `register_skills(...)` + `run_actions(...)` is now the recommended default path.

## Example 1: Local Heuristic Decision

This is the smallest offline decision-only path. It does not require `pawly-cloud`.

```python
from pawly import Action, decide

decision = decide(
    "./worker.yaml",
    state={"preferred_targets": ["helpdesk"]},
    actions=[
        Action(name="safe_reply", arguments={}, target="helpdesk"),
        Action(name="issue_refund", arguments={"order_id": "123"}),
    ],
)

print({
    "selected_action": None if decision.selected_action is None else decision.selected_action.name,
    "decision_source": decision.decision_source,
    "requires_review": decision.requires_review,
    "blocked_actions": [action.name for action in decision.blocked_actions],
})
```

Expected behavior:

- `safe_reply` remains a normal candidate
- `issue_refund` is removed by the Pawprint `block` boundary

## Example 2: One-Call Decision + Execution

This is the recommended developer path for new integrations.

```python
from pawly import Action, DecisionEngine, HeuristicPolicy, SkillRegistry

runtime = DecisionEngine("./worker.yaml", scoring_policy=HeuristicPolicy())
skills = SkillRegistry()
skills.register("safe_reply", lambda args, context: {"message": "safe reply", "args": args})
runtime.register_skills(skills)

result = runtime.run_actions(
    state={"trace_id": "support-1"},
    actions=[Action(name="safe_reply", arguments={"message": "hello"})],
    context={"channel": "chat"},
)

print(result["status"])
print(result["decision"]["requires_review"])
print(result["result"])
```

## Example 3: Wrap An Existing Tool Executor

If you already have an OpenAI-style tool call shape, use the built-in adapter wrapper instead of hand-writing `Action` conversion.

```python
from pawly import PawlyRuntime, wrap_openai_tool_executor

runtime = PawlyRuntime("./worker.yaml")

wrapped_tool = wrap_openai_tool_executor(
    runtime,
    lambda updated: {
        "tool_name": updated.tool_name,
        "payload": updated.payload,
    },
)

result = wrapped_tool(
    {
        "task": "Answer order status questions for a customer",
        "tool_name": "safe_reply",
        "confidence": 0.95,
        "payload": {"channel": "email"},
    }
)

print(result["type"])
print(result["execution"]["executed"])
```

Use the same pattern for Claude-style skills with `wrap_claude_skill_executor(...)`.

## Offline Operation

`HeuristicPolicy` is the default OSS path. Local decisions, examples, tests, and adapter wrappers work without cloud credentials and without `pawly-cloud` installed.
