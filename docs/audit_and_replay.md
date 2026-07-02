# Audit And Replay

In this document `pawly` means the open-source package published from `open_pawly`.

Pawly now emits two local-first JSONL audit shapes during governed execution:

1. `action-proposed`
   The runtime decision event emitted when Pawly evaluates the intent.
2. `governed-execution`
   The full execution trace emitted by the execution gateway after the execution path is resolved.

## What the governed trace captures

Each `governed-execution` event stores:
- original intent
- normalized intent
- matched policy rules
- risk score
- final decision
- approval info when present
- executed action when execution happens
- execution result reference when one is available
- action diff between proposed and executed action

## Main modules

- `open_pawly/src/pawly/audit/events.py`
  Structured event model for `action-proposed` and `governed-execution`
- `open_pawly/src/pawly/audit/ledger.py`
  Local JSONL append plus event loading and lookup
- `open_pawly/src/pawly/audit/replay.py`
  Load and reconstruct governed paths from stored audit events
- `open_pawly/src/pawly/audit/diff.py`
  Compare original proposed action versus executed action

## Replay flow

Replay is local and code-level:

1. Load a stored audit record from JSONL
2. Select the `governed-execution` event
3. Reconstruct:
   - original intent
   - normalized intent
   - policy evaluation
   - final decision
   - approval path
   - executed action
   - action diff

## Diff behavior

Pawly stores:
- `action`
  the original proposed action
- `executed_action`
  the action that actually reached the executor
- `action_diff`
  a structured field-by-field comparison

This captures edits introduced by approval or future rewrite paths.

## Logging format

The OSS logging format remains structured JSONL.

Each line is a self-contained JSON object. That keeps local append simple while still making replay and diff operations deterministic.

## Example traced lifecycle

Example: refund request with edited approval

1. Original intent
   - task: `Issue refunds for a customer`
   - action: `process refund`
2. Pawly decision
   - type: `require_approval`
   - matched rule: `issue refunds`
   - risk score: `0.8`
3. Approval response
   - status: `approved`
   - reviewer: `human-approver`
   - edited action: `draft refund response`
4. Execution
   - real executor runs with `draft refund response`
5. Replayable trace
   - original action: `process refund`
   - executed action: `draft refund response`
   - diff: `name` changed, arguments may change

This lets an OSS user inspect exactly what Pawly reviewed, what a human changed, and what finally executed.
