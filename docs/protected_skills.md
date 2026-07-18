# Skill Protection Compatibility

In this document `pawly` means the open-source package published from `open_pawly`.

`pawly` is compatible with skill-protection metadata declared in `pawprint`.

This compatibility is intentionally limited. Full, cloud-grade skill-protection enforcement lives in
`pawly-cloud`.

## What Open Pawly does

- parses `skill.protection` and `skill.license` metadata when present
- accepts `protection.level` values of `open`, `protected`, and `vault`
- emits an Open Pawly compatibility warning for `protected` and `vault`
- exposes only a small model-visible skill card with safe public fields
- remains independent from `pawly-cloud`

### Limited local guardrail

Open Pawly also runs a small deterministic, local-only guardrail around protected or vault skills. This is best
effort heuristic protection, not cloud-grade enforcement:

- when `protection.monitor_extraction` is set on a `protected`/`vault` skill, it runs a deterministic
  extraction-attempt heuristic (`detect_extraction_attempt`) against the intent text
- on a detected attempt, `apply_extraction_guardrail` downgrades the decision to
  `require_approval`, or `deny` for high-severity matches
- audit events for protected or vault skills are redacted through `ProtectedAuditRedactingSink`
  (`redact_audit_event`), removing protected intent metadata, action arguments, and execution results

These behaviors are pattern-based and easy to bypass. They reduce obvious leakage in the local path
but do not replace cloud enforcement.

## What Open Pawly does not do

- does not guarantee anti-absorption
- does not implement prompt vaulting
- does not implement no-train routing
- does not implement watermarking
- does not implement model-based or robust extraction monitoring beyond the local heuristic above
- does not implement marketplace licensing enforcement

Open Pawly only avoids exposing obvious private fields to model-visible context, plus the limited local
guardrail described above.

Private fields filtered from model-visible skill context include:

- `raw_prompt`
- `core_prompt`
- `private_prompt`
- `private_rubric`
- `private_examples`
- `private_assets`
- `private_notes`
- `internal_rules`
- `developer_secret`
- `hidden_instructions`

Safe public model-visible fields are limited to:

- `name`
- `description`
- `input_schema`
- `output_schema`
- `public_usage_notes`

Full enforcement belongs in `pawly-cloud`.
