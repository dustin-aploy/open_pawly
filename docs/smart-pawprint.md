# Skill Action Pawprints

Pawprint can be generated from `SkillService` action names. The compact form is
a Skill/action decision table:

```yaml
skills:
  customer-support:
    get_order_status: allow
    issue_refund: smart
    export_customer_data: block
```

Every generated action starts as `block`. Change it to `review`, `allow`, or
`smart` when its boundary is known. An action absent from the table is blocked.

## Smart decisions

`smart` is for actions whose decision depends on the request. Open Pawly uses a
local deterministic heuristic that examines structured context, arguments, risk
hints, verification signals, and amount limits. It returns `block`, `review`,
or `allow` without a model call, which keeps the decision path fast and
predictable.

Use `smart` for a business action such as a refund where a verified, low-value
request may be allowed while an uncertain or high-value request needs review.
Use explicit `block`, `review`, or `allow` when the boundary is fixed.

Applications can provide a custom local policy for `smart` actions. The policy
receives the same action and context data, but it cannot change an explicit
Pawprint boundary or make an undeclared action executable.

Cloud Policy and feedback-driven managed decisions begin with Cloud Plus, not
Cloud Starter. They use the same Pawprint table and cannot override an explicit
`block`, `review`, or `allow` boundary.
