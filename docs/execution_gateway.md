# Execution Gateway

In this document `pawly` means the open-source package published from `open_pawly`.

The main Pawly integration model is executor wrapping.

Pawly wraps execution.
It does not replace planning.
It does not replace the host agent runtime.

## Core idea

The host agent keeps its own:
- planner
- tool selection
- memory
- workflow model

Pawly attaches at the execution boundary:

`Intent -> Pawly deterministic review -> Decision -> execution outcome`

If the decision is:
- `allow`: the real executor runs
- `deny`: the real executor is not called
- `require_approval`: execution pauses unless a local approval handler approves it
- `simulate`: execution does not run

## Main interfaces

The current OSS gateway surface is:

- `wrap_executor(executor, pawprint, reviewer="rules")`
- `wrap_execute_fn(fn, pawprint, reviewer="rules")`
- `ExecutionGateway`

These wrappers hide branching from developer-facing code. The caller invokes the wrapped executor or execute function and receives the structured Pawly result back without writing manual `if/else` around decision types.

## Reviewer model

The default reviewer is `rules`.

That means:
- deterministic Pawprint policy evaluation
- no cloud dependency
- no model-based review in the OSS execution path

## Host runtime boundary

Pawly does not rewrite the host planner.

Instead, it wraps the point where a tool call, action execution, skill invocation, or transition would actually happen.

This keeps the host executor or tool runner intact wherever possible.

## Concrete path

The current semi-real example is:

- [execution_gateway_demo.py](../examples/execution_gateway_demo.py)

It wraps a simple execute function with `wrap_execute_fn(...)` and shows:
- one allowed action that executes
- one `require_approval` action that is interrupted before execution unless approval is supplied

## Adapter role

Adapters are execution-boundary wrappers.

They should translate framework-native action proposals into Pawly gateway calls and then let the host framework continue with its own runtime behavior. They should not become planner rewrites or alternate runtime systems.
