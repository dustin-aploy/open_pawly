# Pawly (OSS) Architecture

In this document `pawly` means the open-source package published from `open_pawly`.
The full product (open source plus the cloud version) is referred to as the Pawly platform.
Cloud-only behavior lives in `pawly_cloud` and is never required for the OSS path.

## Pipeline

The current governed execution pipeline is:

`Agent -> Intent -> Pawly -> Decision -> Approval if needed -> Execution -> Audit`

More concretely:

1. the host agent or tool runner produces an execution request
2. Pawly normalizes it into an `Intent`
   In the current workspace this is direct `Intent` input or `TaskRequest -> Intent` adaptation rather than a larger standalone normalization subsystem.
3. Pawly loads the declarative Pawprint file and converts it into internal runtime config
4. Pawly applies Pawprint boundaries to candidate actions or incoming execution requests
5. Pawly produces a `Decision`
6. if the decision is `require_approval`, the approval backend resolves it
7. the execution gateway either blocks, simulates, or calls the real executor
8. audit events capture the governed path for replay and diff

Pawly wraps execution. It does not replace planning.

## Core modules

### Pawprint

Declarative worker-card spec:

- [pawprint schema](https://github.com/dustin-aploy/pawprint/blob/main/schemas/pawprint.schema.json)
- [pawprint/examples/basic_worker.yaml](../examples/agents/basic_worker.yaml)

Internal runtime schemas:

- [open_pawly/src/pawly/schemas/intent.schema.json](../src/pawly/schemas/intent.schema.json)
- [open_pawly/src/pawly/schemas/decision.schema.json](../src/pawly/schemas/decision.schema.json)
- [open_pawly/src/pawly/schemas/report.schema.json](../src/pawly/schemas/report.schema.json)

### Pawly runtime core

- types and runtime entrypoint:
  - [types.py](../src/pawly/types.py)
  - [runtime.py](../src/pawly/runtime.py)
- Pawprint loading and conversion:
  - [pawprint_loader.py](../src/pawly/pawprint_loader.py)
  - skill-protection support in OSS is parse plus a limited local guardrail (see `protected_oss.py`); it does not implement cloud-grade enforcement
- candidate action selection:
  - [action_selection.py](../src/pawly/action_selection.py)
- deterministic policy engine:
  - [policy_engine/engine.py](../src/pawly/policy_engine/engine.py)
  - [policy_engine/decision.py](../src/pawly/policy_engine/decision.py)
- execution gateway:
  - [gateway/wrapper.py](../src/pawly/gateway/wrapper.py)
- approval:
  - [approval/models.py](../src/pawly/approval/models.py)
  - [approval/router.py](../src/pawly/approval/router.py)
  - [approval/queue.py](../src/pawly/approval/queue.py)
- audit and replay:
  - [audit/events.py](../src/pawly/audit/events.py)
  - [audit/ledger.py](../src/pawly/audit/ledger.py)
  - [audit/replay.py](../src/pawly/audit/replay.py)
  - [audit/diff.py](../src/pawly/audit/diff.py)

### Replaceable backend boundaries

- reviewer backend:
  - [backends/reviewer.py](../src/pawly/backends/reviewer.py)
- risk provider:
  - [backends/risk.py](../src/pawly/backends/risk.py)
- approval backend:
  - [backends/approval.py](../src/pawly/backends/approval.py)
- audit sink:
  - [backends/audit.py](../src/pawly/backends/audit.py)

## OSS and cloud boundary

The OSS runtime path is fully local:

- `RuleReviewer`
- `LocalRiskProvider`
- `LocalApprovalBackend`
- `LocalAuditSink`

These run without network calls or hosted services.

`pawly_cloud/` is a sibling package to `open_pawly/`. It is not an internal Pawly module and it is not required for OSS Pawly to run.

Skill-protection metadata follows the same boundary:

- OSS Pawly can parse `skill.protection` and `skill.license`
- OSS Pawly only exposes a small safe model-visible skill card
- OSS Pawly runs a limited local extraction guardrail and audit redaction for protected or vault skills
- OSS Pawly does not guarantee anti-absorption or protected-prompt enforcement
- full cloud skill-protection enforcement belongs in `pawly-cloud`

Cloud behavior is intentionally optional. The OSS package exposes only stub placeholders:

- `CloudReviewerStub`
- `AdvancedRiskProviderStub`
- `CloudApprovalBackendStub`
- `CloudAuditSinkStub`

Those stubs define extension boundaries but do not implement hosted behavior. They are separate from `CloudPolicy`, which is the optional sibling-package scorer used for candidate-action ranking.

For candidate-action ranking, the boundary is narrower:

- Pawprint defines only hard boundaries: `allow`, `review`, and `block`
- `DecisionEngine` applies those hard constraints before any policy scoring
- `allow` candidates may be ranked by the configured scoring policy
- `review` candidates can be scored but still require approval before execution
- `block` candidates are removed completely
- `HeuristicPolicy` is the default OSS policy
- `CustomPolicy` is a developer-provided policy implementation
- `CloudPolicy` is the optional cloud scoring provider from the sibling `pawly_cloud` package
- the cloud version is not a hardcoded requirement for candidate-action scoring
- if the configured scoring provider is unavailable, Pawly uses `scoring_policy_fallback_mode`
- the default scoring-policy fallback mode is `review`
- optional scoring-policy fallback modes are `heuristic` and `deny`
- policy never removes blocked actions, bypasses review requirements, or invents boundary outcomes
- `block` always wins over any policy result
- cloud and custom policies cannot override hard boundaries
- cloud may downgrade an `allow` candidate to `review` through uncertainty or escalation metadata, but it does not create new hard boundary types
- `decision_source` reflects the actual provider path: `heuristic`, `custom`, `cloud`, or `fallback`
- `DecisionEngine.log_decision(...)` records structured candidate-action decision logs with `trace_id`, `boundary_type`, `decision_source`, `policy_name`, `policy_supports_scoring`, `policy_fallback_used`, `reason`, `uncertainty`, and `scores` when present

Cloud remains only a scoring provider in this architecture:

- `pawly_cloud` implements the same `Policy.evaluate(state, actions)` interface as any other policy
- `pawly` may accept `CloudPolicy(...)` as an injected policy, but does not depend on `pawly_cloud` internals
- cloud does not execute actions, apply constraints, bypass review, or override block boundaries

## Approval flow

The current approval path is:

1. policy evaluation returns `require_approval`
2. [ExecutionGateway](../src/pawly/gateway/wrapper.py) submits the request through the approval backend
3. the backend creates an `ApprovalRecord`
4. a local handler may approve, reject, or edit the action
5. approved edited actions continue to the real executor
6. rejected or expired approvals stop execution

Relevant modules:

- [approval/models.py](../src/pawly/approval/models.py)
- [approval/router.py](../src/pawly/approval/router.py)
- [approval/timeout.py](../src/pawly/approval/timeout.py)
- [backends/approval.py](../src/pawly/backends/approval.py)

## Execution gateway flow

The main wrapper interfaces are:

- `wrap_executor(...)`
- `wrap_execute_fn(...)`
- `wrap_framework_adapter(...)`

They keep host executors intact and move the branching inside Pawly:

1. wrap an existing executor or execute function
2. normalize the request to `Intent`
3. run Pawly review
4. resolve approval if needed
5. only call the real executor when execution is permitted

Relevant module:

- [gateway/wrapper.py](../src/pawly/gateway/wrapper.py)

## Audit and replay flow

Each governed execution now records:

- original intent
- normalized intent
- matched policy rules
- risk score
- final decision
- approval info
- executed action
- execution result reference if available
- action diff

Replay and inspection path:

1. events are written as structured JSONL
2. the ledger loads stored events
3. replay reconstructs the governed path
4. diff shows original action versus executed action

Relevant modules:

- [audit/events.py](../src/pawly/audit/events.py)
- [audit/ledger.py](../src/pawly/audit/ledger.py)
- [audit/replay.py](../src/pawly/audit/replay.py)
- [audit/diff.py](../src/pawly/audit/diff.py)

## Actual folder structure

The current code layout matches the architecture closely:

```text
pawprint/
  schemas/
  examples/
  README.md

open_pawly/
  src/pawly/
    action_selection.py
    approval/
    audit/
    backends/
    budget/
    gateway/
    performance/
    policy_engine/
    runtime.py
    types.py
  test-suite/
  adapters/
  examples/
  scripts/

pawly_cloud/
  src/pawly_cloud/
    auth.py
    client.py
    errors.py
    policy.py
    types.py
  tests/
```

Remaining deviation:

- `budget/` and `performance/` still live inside the runtime package even though they are overlays around the core policy path rather than part of the central policy engine.
- `loader/`, `validator/`, `middleware/`, `memory/`, and `escalation/` also remain inside the runtime package as support modules around the main boundary path.
