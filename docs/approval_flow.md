# Approval Flow

In this document `pawly` means the open-source package published from `open_pawly`.

Pawly now treats `require_approval` as a real runtime path.

The OSS implementation stays lightweight:
- in-memory or file-backed queue
- local callback approval handler
- timeout-based expiry
- no cloud dependency

## Core flow

1. Pawly evaluates an `Intent`.
2. If the decision is `require_approval`, the execution gateway creates an approval record.
3. The approval router stores that record in the approval queue.
4. An approval handler may:
   - approve the action
   - reject the action
   - approve an edited action
5. If approval is granted, the gateway continues to the real executor.
6. If approval is rejected or expires, execution stops with a clear result.

## Main modules

- `open_pawly/src/pawly/approval/models.py`
  Approval records, request/response models, statuses, timestamps, edited action support.
- `open_pawly/src/pawly/approval/queue.py`
  In-memory and file-backed approval queue implementations.
- `open_pawly/src/pawly/approval/router.py`
  Approval submission, queue integration, response application, status payload building.
- `open_pawly/src/pawly/approval/handler.py`
  Local callback-style approval handler interface and static local handler.
- `open_pawly/src/pawly/approval/timeout.py`
  Expiry calculation and timeout checks.
- `open_pawly/src/pawly/gateway/wrapper.py`
  Execution gateway integration with approval pause/continue/terminate behavior.

## Approval record contents

Each approval record carries:
- original intent
- proposed action
- optional edited action
- status: `pending`, `approved`, `rejected`, `expired`
- created and updated timestamps
- expiry timestamp when a timeout applies
- reviewer identity when available
- notes

## Timeout behavior

The OSS default is lightweight timeout expiry.

If an approval is still pending when its timeout is reached:
- the router marks the record as `expired`
- the execution gateway returns a `require_approval` result with `execution.blocked_by="expired"`
- the real executor is not called

## Edited action behavior

Approval can modify the action before execution.

When an approval response includes an edited action:
- the approval record stores that edit
- the gateway builds an approved intent from the edited action
- the real executor receives the edited action instead of the original one in the current gateway and wrapper paths

## Result behavior

The execution result remains structured and explicit:
- pending approval: `type=require_approval`, execution paused
- approved: execution continues
- rejected: execution terminated
- expired: execution terminated
