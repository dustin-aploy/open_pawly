# OpenClaw Adapter Notes

**Product scope: [OSS].**

## Conceptual mapping

OpenClaw-style agent loops usually expose a central decision/tool-execution path. Pawly should wrap that path as a local Action Layer: translate the candidate tool call or action into a Pawly action context, ask Pawly for a pre-action decision, and only then let the framework continue.

## Where pre-action scope/authority checks should happen

Immediately before the framework executes a tool call, side effect, or user-visible outbound action.

## Where escalation should happen

When the framework detects low confidence or a pending handoff condition. The adapter should convert that into a Pawly handoff route rather than encode OpenClaw-specific semantics as the source of truth.

## Where audit should happen

At action proposal time and again on denied or `require_approval` outcomes so the framework’s decisions remain reconstructable later.

## Where budget checks should happen

Before expensive tool chains, repeated retries, or outward side effects. Any execution checks should come from the current Pawly runtime behavior, not ad hoc framework defaults.

## What is intentionally not implemented here

This directory is a minimal Pawly hook, not a complete OpenClaw connector.
