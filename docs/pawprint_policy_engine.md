# Pawprint Policy Engine

**Product scope: [OSS].**

The Pawprint policy engine evaluates the action boundary declared by a
developer. It is deterministic and runs locally.

## Inputs

The engine receives a normalized execution request and a Pawprint. The
recommended Pawprint form is a generated Skill/action table:

```yaml
skills:
  customer-support:
    get_order_status: allow
    issue_refund: smart
    export_customer_data: block
```

Every action has one decision: `block`, `review`, `allow`, or `smart`.
Undeclared actions are blocked.

## Evaluation order

1. Match the requested action against the Pawprint table.
2. Apply explicit `block`, `review`, and `allow` decisions.
3. Resolve `smart` with the configured local policy.
4. Return an executable decision or an approval requirement.

The built-in smart policy reads structured context, action arguments, risk hints,
verification signals, and amount limits. It returns `block`, `review`, or
`allow` without a model call. Applications can supply their own policy for
`smart` actions when their domain needs additional business rules.

## Guarantees

- Explicit `block` actions are never candidates for execution.
- `review` actions still require approval after local Policy evaluation.
- A policy cannot invent an action that is absent from Pawprint.
- The returned receipt includes the decision, reason, and governed action.

## Compatibility API

`evaluate_pawprint(intent, pawprint)` remains available for integrations that
already provide a normalized `Intent`. New goal-oriented integrations should use
`Pawly(...).achieve(...)`.
