# Pawly

<p align="center">
  <img src="docs/assets/icon.png" alt="Pawly icon" width="128">
</p>

<p align="center">
  <strong>Managed, safe execution for AI agent actions.</strong>
</p>

Pawly takes over the messy part of agent execution: deciding which capability
should run, checking whether it is allowed, wrapping the call in a policy-aware
execution path, and returning a receipt you can debug or audit later. It is built
for the moment an agent is about to touch the outside world: send an email,
publish content, issue a refund, update a record, call an API, or trigger a
payment.

Instead of wiring every tool call, permission rule, fallback, and audit record by
hand, your agent delegates a goal to Pawly. Pawly manages the execution path so
your agent can act without quietly doing something unsafe, unauthorized, or
impossible to reconstruct later.

```python
from pawly import Pawly

# Register skills before executing a goal. See Quickstart for a complete example.
pawly = Pawly("./worker.yaml")
result = pawly.achieve(
    objective="safe reply to the duplicate charge question",
    context={"order_id": "123"},
    constraints={"max_cost": 2},
)
```

Pawly is not another agent framework. It is the safety and execution layer you
put behind one: your agent decides what it wants, Pawly manages how that action
is allowed to run.

This repository contains Open Pawly, the local runtime for defining action
boundaries, registering skills, running policy checks, and collecting receipts
before your agent touches external systems.

## Status

Pawly is in alpha. The goal interface, Pawprint boundary model, and local
execution receipts are the primary stable surfaces. Lower-level adapter and
gateway APIs may continue to evolve.

## Why Pawly

Building agent products gets painful and risky right after the demo works. You
start with tool calls, then quickly need routing, permission checks, blocked
actions, review paths, audit logs, reproducible receipts, and framework adapters.
The hardest bugs are not syntax errors; they are agents calling the wrong tool,
acting outside their scope, or leaving no useful trace when something goes wrong.

Pawly packages that execution work into a small runtime:

- **Stop hand-rolling tool routing.** Delegate an objective and let Pawly map it
  to a registered capability.
- **Make external actions safer.** Put policy checks before calls that can email,
  publish, refund, delete, pay, or modify user data.
- **Keep permissions out of prompt glue.** Declare allowed, review-only, and
  blocked capabilities in Pawprint instead of relying on model instructions.
- **Make execution inspectable.** Every goal attempt can return an action receipt
  with the selected capability and execution envelope.
- **Keep your existing framework.** Insert Pawly before the tool or skill
  executor instead of rebuilding your agent loop.
- **Run locally first.** Use deterministic Open Pawly policy checks offline,
  then connect a cloud project when you want managed keys, team review, and
  shared execution history.

## Core Concepts

| Concept | Meaning |
| --- | --- |
| Pawprint | The YAML contract that declares metadata, capabilities, and boundaries. |
| Capability | A named action the agent may ask Pawly to use. |
| Skill | Local Python code registered to implement a capability. |
| Objective | The goal delegated by the agent runtime. |
| Execution envelope | The scoped runtime boundary for a goal: resources, capabilities, limits, and approvals. |
| Action receipt | The auditable result of a goal attempt. |

## Install

From PyPI:

```bash
pip install pawly
```

From GitHub:

```bash
pip install "git+https://github.com/dustin-aploy/pawprint.git"
pip install "git+https://github.com/dustin-aploy/open_pawly.git" --no-deps
```

From source:

```bash
git clone git@github.com:dustin-aploy/open_pawly.git
cd open_pawly
pip install -e ../pawprint
pip install --no-build-isolation --no-deps -e ".[dev]"
```

The PyPI package dependency is `pawly-pawprint`. Do not install the unrelated
package named `pawprint`.

## Quickstart

### 1. Declare the agent boundary

Create `worker.yaml`. The `capabilities` list describes what the agent may ask
Pawly to do. The `boundaries` section is the policy: allow safe work, require
review for sensitive work, and block work that should never run automatically.

```yaml
id: support-worker
name: Support Worker
role: Support action runner
summary: Handles low-risk support replies and hands off sensitive customer actions.

capabilities:
  # Capabilities are the actions your agent may delegate to Pawly.
  - safe_reply
  - issue_refund

boundaries:
  # Safe to run automatically.
  auto:
    - safe_reply
  # Must produce a review path before execution.
  ask_first:
    - issue_refund
  # Never run automatically.
  never:
    - delete_customer

handoff:
  to: support-lead
  when:
    - refund requested
    - customer asks for an exception

style:
  tone: clear and practical
  format: concise support update
```

Validate it:

```bash
python -m pawprint.validate ./worker.yaml
```

If validation reports different boundary field names, update `pawprint` and
`pawly-pawprint` together. The Pawprint file, the local runtime, and any cloud
project connection should all use the same schema version.

### 2. Register the skills Pawly is allowed to run

Start with an explicit local skill map. A map works for one skill or many, so the
same shape can grow with your agent.

```python
from pawly import HeuristicPolicy, Pawly, PolicyService, SkillService

def safe_reply(args, context):
    return {
        "message": "We checked your order and will follow up safely.",
        "objective": args["objective"],
        "order_id": context.get("order_id"),
    }

pawly = Pawly(
    "./worker.yaml",
    skills=SkillService.local({"safe_reply": safe_reply}),
    policy=PolicyService.local(routing=HeuristicPolicy()),
)
```

Pawly only executes registered skills. This keeps prompt output separate from
real system actions.

### 3. Delegate a goal and inspect the receipt

```python
result = pawly.achieve(
    # Your agent delegates an objective; Pawly chooses an allowed skill.
    objective="safe reply to the duplicate charge question",
    # Context becomes the resource scope recorded in the receipt.
    context={"order_id": "123", "channel": "chat"},
    # Constraints become execution limits or approval policy inputs.
    constraints={"max_cost": 2},
)

print(result.status)
print(result.result)
print(result.action_receipt["execution_envelope"])
```

If the objective matches a registered skill and the policy allows it, Pawly runs
the skill. If the objective needs review or is blocked, the receipt tells you
which boundary stopped it.

### 4. Batch-register a skills folder

After the first skill works, move your real tool code into a folder and import
that folder. The default directory loader reads Pawly's Python export shape. If
the folder comes from another framework, choose the matching adapter explicitly.

Example folder:

```text
skills/
  support.py
  billing.py
```

```python
# skills/support.py
def safe_reply(args, context):
    return {"message": "Handled safely.", "order_id": context.get("order_id")}

skills = {"safe_reply": safe_reply}
```

```python
from pawly import HeuristicPolicy, Pawly, PolicyService, SkillService

pawly = Pawly(
    "./worker.yaml",
    skills=SkillService.from_directory("./skills"),
    policy=PolicyService.local(routing=HeuristicPolicy()),
)
```

### 5. Choose policy, audit, and cloud skills

Open Pawly and Pawly Cloud use the same constructor shape. Your Pawprint stays
the source of capabilities and boundaries. `PolicyService` decides how a run is
reviewed and routed. `AuditService` decides where action records go.
`SkillService.cloud(...)` lets your project call cloud-managed skills. The cloud
key already identifies the project.

```bash
# Paste the one-time cloud key from the web console.
export PAWLY_API_KEY="paste_the_project_key"
```

Local policy and local audit:

```python
from pawly import AuditService, HeuristicPolicy, Pawly, PolicyService, SkillService

local = Pawly(
    "./worker.yaml",
    skills=SkillService.from_directory("./skills"),
    policy=PolicyService.local(routing=HeuristicPolicy()),
    audit=AuditService.local("./pawly-audit.jsonl"),
)
```

Cloud audit, local policy:

```python
import os
from pawly import AuditService, HeuristicPolicy, Pawly, PolicyService, SkillService

cloud_audit = Pawly(
    "./worker.yaml",
    skills=SkillService.from_directory("./skills"),
    policy=PolicyService.local(routing=HeuristicPolicy()),
    audit=AuditService.cloud(api_key=os.getenv("PAWLY_API_KEY")),
)

result = cloud_audit.achieve(
    objective="safe reply to the duplicate charge question",
    context={"order_id": "123"},
)
print(result.action_receipt["audit"]["alerts"])
```

Cloud audit plus local audit file:

```python
cloud_and_file = Pawly(
    "./worker.yaml",
    skills=SkillService.from_directory("./skills"),
    policy=PolicyService.local(routing=HeuristicPolicy()),
    audit=AuditService.cloud(
        api_key=os.getenv("PAWLY_API_KEY"),
        local_path="./pawly-audit.jsonl",
    ),
)
```

Cloud skills from your local folder:

```python
cloud_skills = Pawly(
    "./worker.yaml",
    # Pawly reads your local skills folder and lets Cloud index/manage the project skills.
    skills=SkillService.cloud(
        api_key=os.getenv("PAWLY_API_KEY"),
        directory="./skills",
    ),
    policy=PolicyService.local(routing=HeuristicPolicy()),
    audit=AuditService.cloud(api_key=os.getenv("PAWLY_API_KEY")),
)
```

Cloud marketplace skills can also be searched, tested, and added in the
dashboard. The SDK does not need a manual skill-id list for that path; project
skill selection is handled by Cloud.

Cloud policy:

```python
cloud_policy = Pawly(
    "./worker.yaml",
    skills=SkillService.from_directory("./skills"),
    policy=PolicyService.cloud(
        api_key=os.getenv("PAWLY_API_KEY"),
        routing=HeuristicPolicy(),
    ),
    audit=AuditService.cloud(api_key=os.getenv("PAWLY_API_KEY")),
)
```

The public API intentionally uses one `PolicyService`. Internally, Open Pawly
bridges that service to boundary review and action routing, so you do not need
to decide between similarly named policy hooks. If cloud policy is unavailable
for the current key or environment, the receipt includes a dashboard entry and
the local development path remains usable.

### 6. Import existing framework folders

Different frameworks store tools and skills differently. Pick the adapter that
matches the folder you are importing.

OpenAI-style Python folder:

```python
skills = SkillService.from_directory("./openai_tools", adapter="openai")
```

Claude-style Python folder:

```python
skills = SkillService.from_directory("./claude_skills", adapter="claude")
```

If your framework already builds tool objects in code, register those objects
directly instead of reading a folder:

```python
from pawly import AuditService, Pawly, PolicyService, SkillService

openai_tools = [
    {
        "tool_name": "safe_reply",
        "executor": lambda payload: ticket_system.reply(
            ticket_id=payload["payload"]["ticket_id"],
            body=f"We checked this safely: {payload['payload']['objective']}",
        ),
    },
    {
        "tool_name": "summarize_ticket",
        "executor": lambda payload: ticket_system.summarize(payload["payload"]["ticket_id"]),
    },
]

pawly = Pawly(
    "./worker.yaml",
    skills=SkillService.from_openai_tools(openai_tools),
    policy=PolicyService.local(),
    audit=AuditService.cloud(api_key=os.getenv("PAWLY_API_KEY")),
)
```

Think of the constructor as three replaceable pieces behind the same Pawprint:

| Piece | Local mode | Cloud mode |
| --- | --- | --- |
| `skills` | A `skills/` directory, local callables, a `SkillRegistry`, or existing framework tools through adapters | Read a local skills directory for cloud registration, or use marketplace/project skills managed in the dashboard |
| `policy` | Rule-based review plus optional local routing | Cloud policy when selected |
| `audit` | JSONL file or custom sink | Cloud dashboard sync, optionally also local JSONL |

When `PAWLY_API_KEY` is missing, Pawly returns a configuration-required result
with a link to the developer console instead of failing with an unclear error.
When a cloud key is provided without a Pawprint path, Pawly returns
`missing_pawprint` because services are runtime wiring, not the local execution
contract.

## Public API

The recommended integration surface is goal-oriented:

```python
Pawly(...).achieve(objective=..., context=..., constraints=...)
```

Lower-level APIs are available for adapters and migration work:

| API | Use when |
| --- | --- |
| `achieve(...)` | You want the top-level helper around `Pawly(...).achieve(...)`. |
| `DecisionEngine.run_actions(...)` | You already have explicit `Action` objects. |
| `run_actions(...)` | You want the top-level explicit-action helper. |
| `decide(...)` | You only need decision output, not execution. |
| `run(...)` | You need the legacy task/action evaluation helper. |
| `wrap_*` adapters | You are inserting Pawly into an existing tool executor. |

## Receipts

`achieve(...)` returns `GoalExecutionResult`.

```python
{
    "status": "completed",
    "objective": "safe reply to the duplicate charge question",
    "selected_capability": "safe_reply",
    "execution_envelope": {
        "resource_scope": {"order_id": "123", "channel": "chat"},
        "allowed_capabilities": ["safe_reply"],
        "financial_limits": {"max_cost": 2},
        "execution_limits": {},
        "approval_policy": {},
    },
}
```

Common statuses:

| Status | Meaning |
| --- | --- |
| `completed` | A matching local skill ran successfully. |
| `unsupported_goal` | No registered skill matched the delegated objective. |
| `configuration_required` | A Pawprint path or cloud key is missing; the receipt includes the next step. |
| `failed` | Local execution failed or was blocked. |

## Architecture

Pawly keeps the core runtime small:

```text
Agent runtime
    |
    | objective + context + constraints
    v
Pawly
    |-- Pawprint boundary
    |-- Skill registry
    |-- Policy engine
    |-- Execution gateway
    v
Local skill executor
```

The package intentionally has no dependency on cloud services. Managed
planning, credential brokering, marketplace access, and organization governance
are optional integrations, not Open Pawly runtime requirements.

## Adapters

Pawly can be inserted at the point where an existing framework is about to run a
tool, transition, or skill:

- OpenAI Agents
- Claude Skills
- LangGraph
- CrewAI
- OpenClaw-style loops
- self-hosted HTTP workers

See [`src/pawly/adapters/README.md`](src/pawly/adapters/README.md) and
[`adapters/`](adapters/).

## Documentation

- [Architecture](docs/architecture.md)
- [Execution gateway](docs/execution_gateway.md)
- [Run actions](docs/run_actions.md)
- [Approval flow](docs/approval_flow.md)
- [Audit and replay](docs/audit_and_replay.md)
- [Pawprint policy engine](docs/pawprint_policy_engine.md)
- [Protected skills](docs/protected_skills.md)
- [Project status](docs/status.md)

## Development

```bash
pip install -e ../pawprint
pip install --no-build-isolation --no-deps -e ".[dev]"
python -m pytest
```

Focused smoke tests:

```bash
python -m pytest tests/test_goal_interface.py tests/test_run_actions.py tests/test_runtime_smoke.py
```

## Contributing

Issues and pull requests are welcome. For code changes, include focused tests and
keep cloud-service behavior out of the Open Pawly runtime. If a change affects
the Pawprint contract, update the sibling `pawprint` package and relevant docs
in the same patch.

## Repository Layout

```text
src/pawly/       core runtime package
examples/        runnable examples
docs/            architecture and runtime notes
tests/           package tests
adapters/        adapter docs and stubs
scripts/         bootstrap and smoke-test helpers
```

## License

Apache-2.0. See [LICENSE](LICENSE).
