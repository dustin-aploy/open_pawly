# OpenAI Agents Adapter Notes

**Product scope: [OSS].**

## Conceptual mapping

For OpenAI agent-style orchestration, Pawly should sit around tool invocation, handoff, and outbound action boundaries. Pawly is not meant to replace the framework planner; it governs what planned actions are allowed to proceed.

## Where pre-action scope/authority checks should happen

Right before tool execution, external API mutation, or user-visible outbound communication.

## Where escalation should happen

At the point where the agent decides it needs human review, encounters restricted actions, or crosses a confidence/risk threshold.

## Where audit should happen

When the framework proposes a tool/action, when Pawly blocks it, and when Pawly hands it off. That keeps the local audit trail attached to the agent lifecycle.

## Where budget checks should happen

Before costly model/tool loops or before side-effecting actions that should respect request, cost, or throughput limits.

## What is intentionally not implemented here

This is a thin adapter sketch, not a complete framework integration.
