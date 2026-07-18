# Open Pawly vs Pawly Cloud (Open Pawly view)

This document describes the boundary from the Open Pawly side. `pawly` means the open-source package
published from `open_pawly`. The cloud-side responsibilities are documented in
the Pawly Cloud documentation at https://developer.aploy.ai/pawly.

`pawly` is designed so the Open Pawly runtime path works fully offline with deterministic rule-based logic only.

`pawly-cloud` is a separate sibling package, not an internal Pawly module. When present, it plugs in through the same `Policy` interface as any other scoring provider.

## Open Pawly runtime path

The default local path is:

1. `Intent`
2. `RuleReviewer`
3. `LocalRiskProvider`
4. `Decision`
5. `LocalApprovalBackend` when the decision is `require_approval`
6. wrapped executor
7. `LocalAuditSink`

The active Open Pawly implementations are:

- reviewer backend: `pawly.backends.reviewer.RuleReviewer`
- risk provider: `pawly.backends.risk.LocalRiskProvider`
- approval backend: `pawly.backends.approval.LocalApprovalBackend`
- audit sink: `pawly.backends.audit.LocalAuditSink`

These defaults keep the runtime self-contained:

- no network calls
- no hosted reviewer
- no hosted approval queue
- no cloud audit service
- local JSONL audit output only

## Cloud extension boundaries

Cloud-only behavior must plug in through replaceable interfaces. The Open Pawly package now exposes these boundaries:

- reviewer backend: `ReviewerBackend`
- risk provider: `RiskProvider`
- approval backend: `ApprovalBackend`
- audit sink: `AuditSink`

The main wrapper entrypoints preserve those boundaries too:

- `wrap_executor(..., reviewer_backend=..., risk_provider=..., approval_backend=..., audit_sink=...)`
- `wrap_execute_fn(..., reviewer_backend=..., risk_provider=..., approval_backend=..., audit_sink=...)`

Cloud placeholders exist only as stubs in Open Pawly:

- `CloudReviewerStub`
- `AdvancedRiskProviderStub`
- `CloudApprovalBackendStub`
- `CloudAuditSinkStub`

These stubs raise `NotImplementedError` on use. They document the boundary without adding mandatory network behavior to the local runtime path.

For candidate-action scoring, the main optional cloud boundary is `CloudPolicy` from `pawly-cloud`. Pawly accepts it as an injected `Policy`; it does not require `pawly-cloud` by default.

Skill-protection metadata follows the same rule:

- Open Pawly can parse the `pawprint` skill-protection schema for compatibility
- Open Pawly only avoids exposing obvious private fields to model-visible context
- Open Pawly does not guarantee anti-absorption or cloud-grade skill-protection controls
- full enforcement belongs in `pawly-cloud`

## What Open Pawly owns

Open Pawly keeps, with no required network calls:

- deterministic rule review
- local risk scoring
- local approval backends
- local JSONL audit output
- wrapped execution control

Open Pawly is also allowed to connect outward through two replaceable boundaries:

- it can accept an injected cloud scoring policy (`CloudPolicy` from `pawly-cloud`)
- it can upload audit events to a cloud audit service through an audit-sink boundary
  (`HostedActionSyncAuditSink`), while still always writing the local JSONL audit

The cloud audit service itself (storage, query APIs, multi-user review, trust workflows) and the
full set of cloud responsibilities live in `pawly_cloud`. See
the Pawly Cloud documentation at https://developer.aploy.ai/pawly. The key boundary is that
cloud services may consume runtime artifacts and decisions by reference, but they do not replace the
local execution-boundary controller inside the Open Pawly path.

For cloud-backed action selection specifically:

- Pawprint does not define a cloud toggle; cloud activation comes from runtime `scoring_policy`
- `CloudPolicy` is the official Aploy cloud scoring provider
- developers may also provide custom scoring policies
- if no configured scoring policy is available, Pawly uses `scoring_policy_fallback_mode`
- cloud cannot override `block` and cannot bypass `review`

## Where cloud could have leaked before

Before this refactor, the runtime path was coupled directly to concrete local implementations:

- `PawlyRuntime` called `evaluate_pawprint(...)` directly
- `PawlyRuntime` wrote directly to `AuditLedger`
- `ExecutionGateway` created `ApprovalRouter(...)` directly
- policy risk scoring was hard-wired inside `evaluate_pawprint(...)`

Those paths now depend on interfaces instead:

- `PawlyRuntime` depends on a `ReviewerBackend`
- `evaluate_pawprint(...)` accepts a `RiskProvider`
- `ExecutionGateway` depends on an `ApprovalBackend`
- `PawlyRuntime` and `ExecutionGateway` append through an `AuditSink`

## Integration model

Cloud plugins must preserve the same execution flow:

`Intent -> reviewer backend -> decision -> approval backend if needed -> wrapped executor -> audit sink`

That means cloud can enhance review, risk, approval, or audit storage without changing host planning logic or executor wrapping.

## Standalone Open Pawly checklist

- `RuleReviewer` works without any model or network call
- `LocalRiskProvider` computes risk locally from deterministic rules
- `LocalApprovalBackend` works with `InMemoryApprovalQueue` or `FileApprovalQueue`
- `LocalAuditSink` writes structured JSONL locally
- `wrap_executor(...)` and `wrap_execute_fn(...)` still run end to end without cloud services
