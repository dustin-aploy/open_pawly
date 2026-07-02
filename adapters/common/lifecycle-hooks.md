# Lifecycle Hooks

## Core hook moments

Across most frameworks, Pawly logic should be attached at the following moments.

### 1. Before a meaningful action

Before a tool call, outbound message, workflow transition, or external side effect, the adapter should run scope, authority, and budget checks.

### 2. When the framework detects uncertainty or denied execution

When confidence falls, boundary conflicts appear, or an action needs handoff, the adapter should trigger the Pawly handoff path rather than silently continuing. If a local approval handler is configured, the adapter should let the execution gateway resolve that review before deciding whether to continue.

### 3. When the framework emits an event worth reconstructing later

Audit hooks should capture action proposals, denied actions, approval paths, simulated actions, and relevant policy references.

### 4. After the framework finishes a decision cycle

A post-decision hook can emit summary metadata for reporting, counters, or downstream compliance evidence.

## Mapping to the current Pawly implementation

`../runtime` demonstrates this lifecycle shape already:

- `HookRegistry.run_before()` is the pre-action insertion point.
- `evaluate_pawprint()` is the core deterministic pre-execution policy check.
- `ExecutionGateway.execute()` is the execution-boundary wrapper around a real executor callable.
- `StaticApprovalHandler` is the minimal local approval example for `require_approval` decisions.
- `check_budget()` is the current runtime overlay example.
- `AuditLedger.append()` is the audit persistence point.
- `HookRegistry.run_after()` is the post-decision/reporting insertion point.

Framework adapters in this directory should mirror those stages conceptually, even if the host framework uses different callback names.
