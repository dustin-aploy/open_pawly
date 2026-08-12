# Skill Action Pawprints

Pawprint can be generated from `SkillService` action names. The compact form is a
skill/action decision table:

```yaml
skills:
  customer-support:
    get_order_status: allow
    issue_refund: smart
    export_customer_data: block
```

Every generated action starts as `block`. A user selects exactly one of `block`,
`review`, `allow`, or `smart`. Requests for actions absent from the table are
explicitly blocked.

`smart` runs the local deterministic heuristic by default. It examines request
context, arguments, risk hints, verification, and amount limits, then returns
`block`, `review`, or `allow`. A hosted policy may replace this for smart actions,
but model failure must fall back to the local policy or `review`; input ordering is
not a policy signal.
