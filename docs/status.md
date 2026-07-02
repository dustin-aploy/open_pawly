# Pawly (OSS) Implementation Status

This status reflects the current `open_pawly` package implementation.
`pawly` here means the open-source package; cloud-side capabilities are tracked in `pawly_cloud`.

## Phase 0 — Core Abstraction

`Done`

Why:
- Pawprint is now a minimal worker-card specification expressed as declarative schema plus examples.
- internal `Intent` and `Decision` schemas exist under Pawly runtime.
- decision vocabulary is `allow`, `deny`, `require_approval`, `simulate`.

Modules:
- [pawprint schema](https://github.com/dustin-aploy/pawprint/blob/main/schemas/pawprint.schema.json)
- [pawprint/examples/basic_worker.yaml](../examples/agents/basic_worker.yaml)
- [open_pawly/src/pawly/types.py](../src/pawly/types.py)

## Phase 1 — Minimal Runtime

`Done`

Why:
- deterministic policy evaluation exists
- rule-based risk scoring exists
- decisions include reasons and risk
- audit logging is active

Modules:
- [policy_engine/engine.py](../src/pawly/policy_engine/engine.py)
- [backends/reviewer.py](../src/pawly/backends/reviewer.py)
- [backends/risk.py](../src/pawly/backends/risk.py)
- [runtime.py](../src/pawly/runtime.py)
- [audit/events.py](../src/pawly/audit/events.py)

## Phase 2 — Agent Integration

`Partial`

Why:
- execution-boundary wrapping exists
- wrapper entrypoints can wrap executors and execute functions
- adapters are framed as execution-boundary wrappers, not planner rewrites
- current framework adapters are still thin stubs rather than production integrations

Modules:
- [gateway/wrapper.py](../src/pawly/gateway/wrapper.py)
- [open_pawly/adapters/README.md](../adapters/README.md)
- [examples/execution_gateway_demo.py](../examples/execution_gateway_demo.py)
- adapter stubs under [open_pawly/adapters](../adapters)

## Phase 3 — Approval System

`Partial`

Why:
- `require_approval` is a real runtime path
- approval records are stored and can carry edited actions
- approval supports approve, reject, and expire outcomes
- the gateway pauses execution until approval resolves
- current approval is local-first and callback/queue based; there is no hosted approval service or operator surface

Modules:
- [approval/models.py](../src/pawly/approval/models.py)
- [approval/queue.py](../src/pawly/approval/queue.py)
- [approval/router.py](../src/pawly/approval/router.py)
- [approval/handler.py](../src/pawly/approval/handler.py)
- [approval/timeout.py](../src/pawly/approval/timeout.py)
- [gateway/wrapper.py](../src/pawly/gateway/wrapper.py)

## Phase 4 — Observability & Audit

`Done`

Why:
- audit events capture replayable governed execution traces
- replay support exists
- diff support exists for proposed versus executed action

Modules:
- [audit/events.py](../src/pawly/audit/events.py)
- [audit/ledger.py](../src/pawly/audit/ledger.py)
- [audit/replay.py](../src/pawly/audit/replay.py)
- [audit/diff.py](../src/pawly/audit/diff.py)

## Phase 5 — Advanced Intelligence

`Partial`

Why:
- basic risk scoring exists
- replaceable interfaces for cloud reviewer and advanced risk now exist
- anomaly detection and richer simulation tooling do not exist
- `simulate` now exists as a real runtime outcome only when explicitly requested by the normalized intent
- cloud-backed intelligence is stubbed only, not implemented

Modules:
- [backends/risk.py](../src/pawly/backends/risk.py)
- [backends/reviewer.py](../src/pawly/backends/reviewer.py)

## Remaining gaps

- no hosted approval UI or webhook service in the OSS workspace
- no advanced anomaly detection module
- no production cloud reviewer implementation
- `budget/` and `performance/` remain runtime overlays inside the same package rather than separate outer packages

## Current verification baseline

- runtime tests: `open_pawly/tests`
- test-suite tests: `open_pawly/test-suite/tests`
- smoke flow: `./open_pawly/scripts/smoke_test.sh`
