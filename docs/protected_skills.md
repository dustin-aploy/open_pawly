# Skill Protection Compatibility

**Product scope: [OSS].**

In this document `pawly` means the open-source package published from `open_pawly`.

`pawly` reads the optional skill-protection metadata declared in `pawprint`.

## What Open Pawly does

- parses `skill.protection` and `skill.license` metadata when present
- accepts `protection.level` values of `open`, `protected`, and `vault`
- emits a compatibility warning for `protected` and `vault`
- exposes only a small model-visible skill card with safe public fields

### Limited local guardrail

Open Pawly also runs a small deterministic guardrail around protected or vault
skills:

- when `protection.monitor_extraction` is set on a `protected`/`vault` skill, it runs a deterministic
  extraction-attempt heuristic (`detect_extraction_attempt`) against the intent text
- on a detected attempt, `apply_extraction_guardrail` downgrades the decision to
  `require_approval`, or `deny` for high-severity matches
- audit events for protected or vault skills are redacted through `ProtectedAuditRedactingSink`
  (`redact_audit_event`), removing protected intent metadata, action arguments, and execution results

These pattern-based checks reduce accidental disclosure. Treat sensitive data as
application data and apply the storage, access, and credential controls required
by your environment.

## What Open Pawly does not do

- does not guarantee that sensitive prompts cannot be extracted
- does not store secrets for the host application
- does not replace application access controls

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
