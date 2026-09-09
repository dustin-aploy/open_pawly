# Open Pawly Architecture

**Product scope: [OSS].**

Open Pawly is a local execution boundary for an agent. Your application plans
the work; Pawly decides whether a registered Skill action may run, handles a
review when needed, executes the action, and writes a receipt.

## Execution path

```text
Agent runtime
    |
    | objective + context + constraints
    v
Pawly
    |-- Pawprint decision table
    |-- local Skill registry
    |-- policy decision
    |-- approval when required
    |-- JSONL audit receipt
    v
Registered Skill action
```

The usual entry point is:

```python
result = pawly.achieve(objective=objective, context=context, constraints=constraints)
```

Pawly does not plan conversations or store application credentials. Keep those
concerns in the host application and register the action functions that Pawly is
allowed to call.

## Decision table

A Pawprint maps each `skill + action` pair to one decision:

- `block`: exclude the action from execution.
- `review`: pause for an approval handler before execution.
- `allow`: make the action eligible for execution.
- `smart`: use the local deterministic policy to return `block`, `review`, or
  `allow` from the request context.

An action that is absent from the table is blocked. Explicit `block`, `review`,
and `allow` entries are fixed boundaries; a custom policy only decides `smart`
actions.

## Main modules

- `goal.py`: `Pawly(...).achieve(...)` facade.
- `services/`: local Skill, policy, and audit service setup.
- `skill_registry.py`: action registration and dispatch.
- `action_selection.py`: candidate construction.
- `policy_engine/`: deterministic Pawprint decisions and smart policy hooks.
- `approval/`: in-memory or file-backed approval queue and handlers.
- `audit/`: JSONL receipts, replay, and action diffs.
- `gateway/`: wrappers for frameworks that already selected an action.
- `adapters/`: adapters for common agent and tool formats.

## Extension points

The runtime has small interfaces for local customization:

- Register Skill actions with `SkillService`.
- Provide a custom policy for `smart` decisions.
- Provide an approval handler for `review` decisions.
- Provide an audit sink when JSONL is not the right local destination.

Extensions receive the same candidate and context data as the built-in runtime.
They cannot make an explicit `block` action executable or skip a `review`
requirement.

## Audit and approval

Each governed execution produces structured records with the selected action,
decision, approval result, and execution outcome. The local JSONL ledger can be
replayed to explain what was proposed, what was approved or changed, and what
actually ran.

See [Approval flow](approval_flow.md) and [Audit and replay](audit_and_replay.md)
for the record shapes and lifecycle.

## Pawly Cloud

Pawly Cloud is optional managed infrastructure and is not part of this OSS
runtime. Cloud Starter adds hosted Skills, Cloud Session, Hosted Auth,
Credential Vault, basic Cloud Skill Discovery and Selection, and basic
Progressive Disclosure while Policy remains local. Cloud Policy starts with
Cloud Plus. See [Open Pawly and Pawly Cloud](oss_vs_cloud.md).
