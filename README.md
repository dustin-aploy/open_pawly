# Open Pawly

**Product scope: [OSS].**

<p align="center">
  <img src="docs/assets/icon.png" alt="Pawly icon" width="128">
</p>

<p align="center">
  <strong>The local, open-source Action Layer for AI agents.</strong>
</p>

Pawly is the Action Layer between AI agents and real-world execution. Open Pawly
provides that layer locally: an agent delegates a goal, local Policy evaluates
every registered Skill/action, approved work runs through the local execution
boundary, and Pawly writes a receipt you can debug or audit later.

It is built for the moment an agent is about to touch the outside world: send an
email, publish content, issue a refund, update a record, call an API, or trigger
a payment. AI can think freely. Once it acts, Pawly takes control.

Pawly is not another agent framework, a Skill marketplace, or an MCP
replacement. MCP and agent frameworks can expose or propose capabilities; Open
Pawly controls how a goal reaches registered local actions under local Policy.

This repository contains Open Pawly only. It provides goal-first execution,
local Skill registration and execution, local Policy, Session/Context/Memory
adapter interfaces, a local Credential Provider interface, local AuditService,
and JSONL receipts. It does not provide Skill Discovery, Skill Selection, or
Progressive Disclosure as product capabilities.

## Why Pawly

Building agent products gets painful and risky right after the demo works. You
start with tool calls, then quickly need action boundaries, permission checks, blocked
actions, review paths, audit logs, reproducible receipts, and framework adapters.
The hardest bugs are not syntax errors; they are agents calling the wrong tool,
acting outside their scope, or leaving no useful trace when something goes wrong.

Pawly packages that execution work into a small runtime:

- **Stop hand-rolling execution control.** Delegate an objective and apply one
  local Policy across all registered Skill actions.
- **Make external actions safer.** Put policy checks before calls that can email,
  publish, refund, delete, pay, or modify user data.
- **Keep permissions out of prompt glue.** Declare each Skill action as
  `block`, `review`, `allow`, or `smart` in Pawprint instead of relying on
  model instructions.
- **Make execution inspectable.** Every goal attempt can return an action receipt
  with the governed action, Policy result, and execution envelope.
- **Keep your existing framework.** Insert Pawly before the tool or skill
  executor instead of rebuilding your agent loop.
- **Stay local and extensible.** Use local adapters for Session, Context, Memory,
  credentials, and audit without requiring a Cloud account.

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

For generated Skill/action Pawprints and local `smart` decisions, see
[`docs/smart-pawprint.md`](docs/smart-pawprint.md).

### 1. Define the agent boundary

Start with the agent, not with a tool wrapper. Create
`agents/support_agent.pawprint.yaml` to describe what this agent is allowed to
do when it reaches the execution layer.

Keep the first version small: one safe action, one review action, and one
action that should stay blocked.

```yaml
metadata:
  id: support-agent
  name: Support Agent
  description: Handles routine support requests and keeps risky actions behind review.

capabilities:
  - name: safe_reply
    description: Send a low-risk customer reply that stays within approved guidance.
  - name: lookup_order
    description: Read order status for the current customer.
  - name: issue_refund
    description: Refund a customer account.
  - name: delete_customer
    description: Delete a customer record.

skills:
  customer-support:
    safe_reply: allow
    lookup_order: allow
    issue_refund: smart
    delete_customer: block
```

Validate it:

```bash
python -m pawprint.validate ./agents/support_agent.pawprint.yaml
```

### 2. Put Pawly on the execution path

The main integration is goal-first execution. Your agent runtime keeps planning
and conversation state, but it does not call production tools directly. Register
the real functions behind Pawly, then have your runtime pass the user's goal to
`pawly.achieve(...)`.

This is the important boundary: Pawly is not an optional model tool. It is the
only execution path your app calls when an agent wants to act.

Create `support_agent.py`:

```python
from typing import Any, NotRequired, TypedDict

from pawly import AuditService, Pawly, PolicyService, SkillService


class AgentPlan(TypedDict):
    objective: str
    context: dict[str, Any]
    constraints: NotRequired[dict[str, Any]]


def lookup_order(args, context):
    return {
        "order_id": context["order_id"],
        "status": "paid",
        "duplicate_charge": True,
    }


def safe_reply(args, context):
    return {
        "message": "We checked your order and will follow up safely.",
        "objective": args["objective"],
        "order_id": context.get("order_id"),
    }


def issue_refund(args, context):
    return {
        "status": "queued_for_refund",
        "order_id": context["order_id"],
    }


pawly = Pawly(
    "./agents/support_agent.pawprint.yaml",
    skills=SkillService.local(
        {
            "lookup_order": lookup_order,
            "safe_reply": safe_reply,
            "issue_refund": issue_refund,
        }
    ),
    policy=PolicyService.local(),
    audit=AuditService.local("./pawly-audit.jsonl"),
)


class SupportAgentRuntime:
    """The agent owns conversation/planning; Pawly owns execution."""

    def plan(self, user_message, *, order_id, customer_id) -> AgentPlan:
        # In production, this method is usually your framework's structured
        # output call. Keep the same contract: objective, context, constraints.
        normalized = user_message.lower()
        if "refund" in normalized or "charged" in normalized:
            objective = (
                "safe_reply about a billing question; "
                f"do not issue_refund automatically: {user_message}"
            )
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


agent_runtime = SupportAgentRuntime()
plan = agent_runtime.plan(
    "I was charged twice. Can you refund me?",
    order_id="ord_123",
    customer_id="cus_123",
)
result = pawly.achieve(
    **plan,
    user_id="user_123",
    session_id="sess_456",
)

print(result.status)
print(result.result)
print(result.action_receipt)
```

Pawly applies the Pawprint decision table across every registered local Skill
action, blocks undeclared actions, enforces review where required, runs eligible
work through the local execution boundary, and returns a receipt. Internal
deterministic ordering is part of the local Policy path; it is not the Cloud
Skill Discovery or Skill Selection product.

The agent runtime can still use an LLM to understand the conversation and
produce the structured plan. The production credentials stay behind the
registered skill functions, and application code calls `pawly.achieve(...)`
instead of exposing those functions as unguarded model tools.

In an agent framework with structured output, the runtime output is just the
`AgentPlan` shape above. Pass it directly into `pawly.achieve(**plan)` as long as
it contains `objective`, `context`, and optional `constraints`. If the workflow
is deterministic business logic, use the same shape from normal code; Pawly does
not require an LLM.

Metadata can be attached during local registration for receipts and developer
tooling:

```python
registry.register(
    "lookup_order",
    lookup_order,
    metadata={
        "description": "Read order status for a customer",
        "tags": ["orders", "support"],
        "category": "commerce",
        "schema": {"order_id": "string"},
    },
)
```

The same flow is available as a runnable example:

```bash
python examples/goal_first_support_agent.py
```

That example starts from `examples/agents/goal_first_support_agent.yaml`, binds
the agent's real skills, creates an agent-runtime plan, and routes the support
message through `pawly.achieve`.

### Pawly Cloud

Open Pawly is complete as a local product and requires no Cloud account. Pawly
Cloud is available separately for managed production infrastructure. See the
[Pawly Cloud product page](https://developer.aploy.ai/pawly) for plan-specific
capabilities.

### 3. Connect existing skills

Many agent projects already keep related skills or tools in one folder. Connect
that folder through an adapter so Pawly reads a known format instead of guessing.

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

Replace the `skills=` line:

```python
skills=SkillService.from_directory("./skills", adapter="pawly")
```

Existing framework folders use their own adapters:

```python
skills=SkillService.from_directory("./openai_tools", adapter="openai")
skills=SkillService.from_directory("./claude_skills", adapter="claude")
```

If your framework already creates tool objects in code, pass those directly:

```python
skills=SkillService.from_openai_tools(openai_tools)
```

## Developer API

The developer-facing integration surface is goal-first:

```python
Pawly(...).achieve(objective=..., context=..., constraints=...)
```

Keep real external actions behind `SkillService`; do not expose the same
credentials through unguarded tools. Lower-level candidate-action and executor
wrapper APIs remain in the package for framework adapters, migration work, and
runtime maintainers, but they are not the main developer integration path.

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
| `configuration_required` | A Pawprint path or required local configuration is missing; the receipt includes the next step. |
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
    |-- Policy evaluation across registered actions
    |-- Execution/audit receipt
    v
Local skill executor
```

The package intentionally has no required network service. Your application owns
planning, credentials, and deployment; Pawly owns the local execution boundary.

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
- [Approval flow](docs/approval_flow.md)
- [Audit and replay](docs/audit_and_replay.md)
- [Pawprint policy engine](docs/pawprint_policy_engine.md)
- [Protected skills](docs/protected_skills.md)
- [Open Pawly and Pawly Cloud](docs/oss_vs_cloud.md)

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
keep network-dependent behavior out of the Open Pawly runtime. If a change affects
the Pawprint contract, update the sibling `pawprint` package and relevant docs
in the same patch.

## Source Layout

Open Pawly is split by runtime responsibility, not by product surface:

```text
src/pawly/
  goal.py             goal-oriented Pawly(...).achieve(...) facade
  services/           public SkillService, PolicyService, and AuditService wiring
  runtime*.py         local decision, execution, receipts, and failure handling
  policy*/            local Pawprint policy checks and action scoring
  skill_registry.py   local skill registration and dispatch
  audit/              local audit ledger and replay helpers
  approval/           local approval queue and approval result helpers
  gateway/            wrappers for existing tool executors
  adapters/           OpenAI, Claude, LangGraph, CrewAI, OpenClaw, and HTTP adapters
```

Support packages such as `memory`, `middleware`, `performance`, and
`escalation` are small runtime helpers used by the decision engine. They are not
separate platform products. Generated folders such as `__pycache__`,
`.pytest_cache`, `dist`, and `*.egg-info` are ignored and should not be synced to
GitHub.

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
