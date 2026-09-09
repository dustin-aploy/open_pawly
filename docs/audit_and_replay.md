# Audit And Replay

**Product scope: [OSS].**

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

## Interaction snapshot

An application can attach enough interaction context for a developer to judge an
action without reconstructing the conversation elsewhere:

- `channel_id` and `channel_message_id`
- the immediately preceding conversation in `context_messages`, as a list of
  `{ "role": "user" | "assistant" | "system", "text": "..." }` objects
- the inbound user message in `incoming_message`
- the proposed or delivered response in `reply_message`
- Telegram-style `reply_markup.inline_keyboard` when the response contains choices

Integrations should set these fields when they own the channel transport. Keep
only the messages needed to understand the current request. A receipt can then
be rendered as a conversation timeline: earlier messages, the current request,
Pawly's proposed action, the delivered reply, and the reply buttons.

Sensitive credentials and protected-skill payloads must remain redacted; do not place
them in the interaction snapshot.

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

The Open Pawly logging format remains structured JSONL.

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

This lets an Open Pawly user inspect exactly what Pawly reviewed, what a human changed, and what finally executed.
