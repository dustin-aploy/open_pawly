from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class CheckResult:
    name: str
    category: str
    passed: bool
    details: str
    evidence: list[str] = field(default_factory=list)

    def to_pawprint_check(self) -> dict[str, Any]:
        payload = {
            "id": self.name,
            "category": self.category,
            "description": self.details,
            "status": "pass" if self.passed else "fail",
            "evidence": self.evidence,
        }
        if not self.passed:
            payload["remediation"] = f"Address failing {self.category} check: {self.name}."
        return payload

@dataclass(slots=True)
class ComplianceSummary:
    kind: str
    report_id: str
    generated_at: str
    subject: dict[str, Any]
    pawprint_version: str
    profile: dict[str, Any]
    summary: dict[str, Any]
    checks: list[CheckResult]
    attestations: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "report_id": self.report_id,
            "generated_at": self.generated_at,
            "subject": self.subject,
            "pawprint_version": self.pawprint_version,
            "profile": self.profile,
            "summary": self.summary,
            "checks": [check.to_pawprint_check() for check in self.checks],
            "attestations": self.attestations,
        }
