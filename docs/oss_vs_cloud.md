# Open Pawly and Pawly Cloud

**Product scope: [OSS].** Cloud is described only to explain the upgrade boundary.

Open Pawly is the local execution runtime. It gives an agent a declared action
boundary, deterministic decisions, approvals, and local audit receipts.

Pawly Cloud is managed Action Layer infrastructure for agents serving real
users. It is a separate product under the same Pawly brand, not an OSS feature
bundle.

Choose Cloud Starter when you want to:

- host Skills and execute them through Cloud;
- keep resumable Cloud Sessions;
- use Hosted Auth and the Credential Vault;
- use basic Cloud Skill Discovery and Skill Selection; or
- use basic Progressive Disclosure while Policy remains local.

Cloud Plus adds production Cloud Policy, persistent User Context and Memory,
multi-account and Developer-owned OAuth, auth-aware and user-aware routing,
production Skill Selection, protected paid Skills, and production trace/audit.
Cloud Pro adds adaptive outcome, cost, token, latency, reliability, fallback,
memory-conflict, permission-escalation, and governance optimization.

Credential-Verified is a trust verification layer on Cloud Plus or Cloud Pro.
It is not a plan and does not replace the Credential Vault included in Starter.

Start with the [Open Pawly quickstart](../README.md#quickstart), then create a
project in [Pawly Developer](https://developer.aploy.ai/pawly) when managed
infrastructure is needed.
