# CrewAI Adapter Notes

## Conceptual mapping

Crew-style systems often model agents, tasks, and delegations. Paw should sit around task dispatch, delegation approval, and side-effecting task completion rather than trying to replace the crew orchestration model.

## Where pre-action scope/authority checks should happen

Before assigning or executing a task that would call tools, mutate external systems, or send outbound communications.

## Where escalation should happen

When a task requires approval, exceeds declared authority, reaches a restricted domain, or should be routed to a human owner or supervisor.

## Where audit should happen

At task dispatch, on denied or `require_approval` delegations, and after task completion when evidence should be retained.

## Where budget checks should happen

Before dispatching repeated subtasks, multi-agent loops, or tool-heavy executions that consume request or cost budgets.

## What is intentionally not implemented here

This is not a full CrewAI plugin, orchestration backend, or cross-agent state manager. It is a thin structural note and stub only.
