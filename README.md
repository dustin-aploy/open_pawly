# Pawly OSS

<p align="center">
  <img src="docs/assets/icon.png" alt="Pawly icon" width="128">
</p>

Pawly OSS is the local runtime for safely completing delegated agent goals.

Use it when your agent already knows what it wants to accomplish, but you need a
clear boundary for what it may execute, which local skill should run, and what
receipt should be recorded after the attempt.

The main interface is:

```python
pawly.achieve(objective=..., context=..., constraints=...)
```

Pawly OSS runs locally and does not require `pawly-cloud`. Cloud-only planning,
credential brokering, hosted approvals, and marketplace governance live outside
this repository.

## What You Get

- Goal delegation through `Pawly(...).achieve(...)`
- Local Pawprint policy boundaries: `allow`, `review`, and `block`
- Local skill registration and execution
- Deterministic goal-to-skill matching
- Action receipts with an execution envelope
- Offline tests, examples, and adapter utilities

## Install

From PyPI, after release:

```bash
pip install pawly
```

From GitHub:

```bash
pip install "git+https://github.com/dustin-aploy/pawprint.git"
pip install "git+https://github.com/dustin-aploy/open_pawly.git" --no-deps
```

From a local checkout with sibling `pawprint`:

```bash
pip install -e ../pawprint
pip install --no-build-isolation --no-deps -e .
```

`pawly` depends on `pawly-pawprint`. Do not install the unrelated PyPI package
named `pawprint`.

## Quick Start

1. Create a Pawprint file, for example `worker.yaml`:

```yaml
metadata:
  id: support-triage-worker
  name: Support Triage Worker
  description: Handles safe support actions.

capabilities:
  - name: safe_reply
    description: Send a low-risk support reply.
  - name: issue_refund
    description: Refund a customer order.

boundaries:
  allow:
    - safe_reply
  review: []
  block:
    - issue_refund
```

2. Validate it:

```bash
python -m pawprint.validate ./worker.yaml
```

3. Register a local skill and delegate a goal:

```python
from pawly import HeuristicPolicy, Pawly, SkillRegistry

pawly = Pawly("./worker.yaml", scoring_policy=HeuristicPolicy())

skills = SkillRegistry()
skills.register(
    "safe_reply",
    lambda args, context: {
        "reply": "We checked your order and will follow up safely.",
        "objective": args["objective"],
        "order_id": context.get("order_id"),
    },
)
pawly.register_skills(skills)

result = pawly.achieve(
    objective="safe reply to the duplicate charge question",
    context={"order_id": "123", "channel": "chat"},
    constraints={"max_cost": 2},
)

print(result.status)
print(result.result)
print(result.action_receipt)
```

Expected outcome:

- Pawly matches the goal to the registered `safe_reply` capability.
- `issue_refund` is blocked by the Pawprint boundary.
- The result includes an action receipt with the selected capability and an
  execution envelope.

## Action Receipt

`achieve(...)` returns a `GoalExecutionResult`. The receipt is available at
`result.action_receipt` and includes:

```python
{
    "interface": "pawly.achieve",
    "objective": "safe reply to the duplicate charge question",
    "selected_capability": "safe_reply",
    "execution_envelope": {
        "objective": "safe reply to the duplicate charge question",
        "resource_scope": {"order_id": "123", "channel": "chat"},
        "allowed_capabilities": ["safe_reply"],
        "financial_limits": {"max_cost": 2},
        "execution_limits": {},
        "approval_policy": {},
    },
}
```

The execution envelope is the local runtime boundary for a delegated goal. It
captures the goal, resource scope, allowed capabilities, cost limits, execution
limits, and approval policy that applied to the attempt.

## Common Results

- `completed`: a matching local skill ran successfully.
- `unsupported_goal`: no registered skill matched the objective.
- `accepted`: cloud-style constructor input was accepted for handoff, but no
  local Pawprint was provided.
- `failed`: the selected local skill failed or the runtime blocked execution.

## Cloud-Style Project Setup

Developer platform projects can initialize Pawly with a project API key:

```python
from pawly import Pawly

pawly = Pawly(api_key="PAWLY_API_KEY", project_id="PAWLY_PROJECT_ID")
result = pawly.achieve(
    objective="resolve a customer issue safely",
    context={"source": "first_connection"},
    constraints={"max_cost": 2},
)
```

In OSS this returns an accepted receipt without performing hosted cloud planning.
Use the hosted Pawly platform for dynamic multi-skill planning, credential
brokering, human approval flows, and full cloud governance.

## Advanced APIs

Most new integrations should start with `Pawly(...).achieve(...)`.

These lower-level APIs still exist for framework adapters, tests, and migration
work:

- `achieve(...)`: top-level helper around `Pawly(...).achieve(...)`
- `DecisionEngine.run_actions(...)`: execute explicit `Action` objects
- `run_actions(...)`: top-level helper for explicit actions
- `decide(...)`: decision-only action selection
- `run(...)`: legacy task/action evaluation helper
- `wrap_openai_tool_executor(...)`, `wrap_claude_skill_executor(...)`, and other
  adapter wrappers for existing framework executors

If you are building a new agent integration, treat these as advanced escape
hatches rather than the first path.

## Repository Layout

- `src/pawly/`: core runtime package
- `examples/`: runnable local examples
- `docs/`: architecture and runtime notes
- `tests/`: package tests
- `test-suite/`: local conformance suite
- `adapters/`: adapter docs and stubs
- `scripts/`: bootstrap and smoke-test helpers

## OSS vs Cloud

Pawly OSS provides a local, deterministic execution boundary. It is useful for
development, local policy checks, and self-hosted agent runtimes.

The hosted Pawly platform adds the cloud-only product capabilities:

- dynamic multi-skill planning
- credential-scoped execution
- hosted human approval
- organization governance
- audit export
- marketplace skill access and settlement

Pawly OSS stays independent from `pawly-cloud`.
