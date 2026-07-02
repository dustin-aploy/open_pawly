# OpenClaw Adapter Notes

## Conceptual mapping

OpenClaw-style agent loops usually expose a central decision/tool-execution path. Paw should wrap that path as a governance layer: translate the candidate tool call or action into a Paw action context, ask Paw for a pre-action decision, and only then let the framework continue.

## Where pre-action scope/authority checks should happen

Immediately before the framework executes a tool call, side effect, or user-visible outbound action.

## Where escalation should happen

When the framework detects low confidence or a pending handoff condition. The adapter should convert that into a Paw handoff route rather than encode OpenClaw-specific semantics as the source of truth.

## Where audit should happen

At action proposal time and again on denied or `require_approval` outcomes so the framework’s decisions remain reconstructable later.

## Where budget checks should happen

Before expensive tool chains, repeated retries, or outward side effects. Any execution checks should come from the current Paw runtime behavior, not ad hoc framework defaults.

## What is intentionally not implemented here

This directory does not implement a real OpenClaw connector, tool transport, hosted runtime integration, or policy storage backend. It only shows the minimal structural shape of a Paw hook.
