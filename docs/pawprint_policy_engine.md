# Pawprint Policy Engine

In this document `pawly` means the open-source package published from `open_pawly`.

The Open Pawly path now has one deterministic Pawprint policy engine entrypoint:

`evaluate_pawprint(intent, pawprint)`

It accepts:
- a normalized `Intent`
- a developer-authored `Pawprint`

It returns a deterministic policy evaluation with:
- decision type candidate
- reason codes
- matched rules
- risk score

## Purpose

This engine is the central rule evaluator for the open-source path. It is rule-based only.

It does not call models.
It does not depend on cloud services.
It does not rewrite planner logic.
It does not introduce an approval queue.

## Inputs

### Intent

Intent is an internal normalized execution object. It may come from:
- tool calls
- planner outputs
- execution requests

The engine evaluates the normalized action, summary, confidence, and metadata already attached to that Intent.

### Pawprint

Pawprint remains the small developer-facing worker card:
- identity
- role
- capabilities
- boundaries
- handoff conditions
- style

The engine reads only the policy-relevant parts:
- `capabilities`
- `boundaries.allow`
- `boundaries.review`
- `boundaries.block`
- `handoff.when`
- `handoff.to`

## Rule Coverage

The engine currently evaluates:
- capability match vs capability mismatch
- `allow`, `review`, and `block` boundaries
- handoff trigger conditions
- obvious boundary violations through deterministic text and token matching
- low-confidence handoff trigger when confidence is present and below threshold

If a cloud-assisted decision path is unavailable, the Open Pawly path still falls back to the deterministic rule-based evaluation described here.

## Decision Recommendation

The engine returns a candidate decision type:
- `allow`
- `deny`
- `require_approval`
- `simulate` when the normalized request explicitly asks for simulation, for example through `metadata.simulate=true`

Current precedence is:
1. `block` boundary
2. `review` boundary
3. handoff trigger
4. capability mismatch
5. allow

## Risk Scoring

Risk scoring is deterministic and local.

The current rule-based score considers:
- `review` matches
- `block` matches
- handoff-triggering categories
- capability mismatch
- obvious external side effects
- low confidence when present

This score is advisory runtime output for the Open Pawly path. It is not model-based review.

## Core Boundary

This engine is the central Open Pawly policy path.

Modules like budget, memory, and performance may still exist around the runtime, but they are not the policy engine and should not define the core execution-boundary architecture.
