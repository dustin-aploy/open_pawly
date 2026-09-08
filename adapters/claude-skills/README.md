# Claude Skills Adapter Notes

**Product scope: [OSS].**

## Conceptual mapping

Claude Skills-style systems center more on bounded task capabilities and invocation patterns than on a monolithic runtime. Pawly should therefore wrap skill invocation boundaries and any side-effecting actions a skill may trigger.

## Where pre-action scope/authority checks should happen

Before a skill executes an operation that can mutate state, call tools, or communicate externally.

## Where `require_approval` should happen

When a skill discovers it is outside declared boundaries or hits a low-confidence/handoff condition.

## Where audit should happen

When a skill invocation starts, when a sensitive step is proposed, and when the skill is denied or routed to approval.

## Where budget checks should happen

Before recursive or repeated skill execution, large tool usage bursts, or expensive downstream calls.

## What is intentionally not implemented here

This directory demonstrates a thin gateway-backed wrapper around the skill execution boundary.
