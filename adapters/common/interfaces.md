# Thin Adapter Interfaces

## Principle

A thin Paw adapter should expose only the minimum structure needed to:

- describe an action about to happen;
- request a scope/authority/budget decision;
- surface escalation requirements;
- emit audit-friendly events; and
- pass control back to the host framework.

## Suggested conceptual interface

A framework adapter usually needs three kinds of objects:

1. **Action context** — a small record describing the current task, action name, confidence, metadata, and optional framework-native payload.
2. **Policy gateway** — a callable surface that asks the Paw layer for pre-action checks, local approval handling, and audit logging.
3. **Framework callback wrapper** — a tiny shim that translates framework lifecycle events into Paw-shaped calls.

## What adapters should not own

Adapters should not become the place where:

- public Pawprint schemas are redefined;
- approval policy is reimplemented outside the runtime approval handler;
- audit persistence is re-architected;
- budget ledgers are centralized; or
- framework internals are abstracted into a fake universal SDK.

Those concerns belong either to Pawprint, the runtime, or a dedicated integration repository.
