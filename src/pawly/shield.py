from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from pawly.action_selection import ActionCandidate
from pawly.contracts import Action
from pawly.pawprint_loader import PawprintConfig

_PROMPT_INJECTION_PATTERNS = (
    r"ignore previous instructions",
    r"reveal system prompt",
    r"show hidden instructions",
    r"dump tool schema",
    r"bypass policy",
    r"print hidden instructions",
    r"show retrieved context",
)
_SECRET_PATTERNS = (
    r"sk-[a-zA-Z0-9]{16,}",
    r"api[_-]?key[\s:=]+[a-zA-Z0-9_\-]{8,}",
    r"token[\s:=]+[a-zA-Z0-9_\-]{8,}",
    r"-----BEGIN [A-Z ]+PRIVATE KEY-----",
)
_EMAIL_PATTERN = r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"
_PHONE_PATTERN = r"\b(?:\+?\d[\d .-]{7,}\d)\b"
_SYSTEM_LEAK_PATTERNS = (
    r"system prompt",
    r"developer instructions",
    r"hidden instructions",
    r"tool schema",
    r"retrieved context",
)


@dataclass(slots=True)
class ShieldInputPolicy:
    inspection: str
    pii: str


@dataclass(slots=True)
class ShieldExecutionPolicy:
    approval: str
    rate_limit: str


@dataclass(slots=True)
class ShieldOutputPolicy:
    inspection: str
    pii: str
    secret_handling: str
    failure_mode: str


@dataclass(slots=True)
class ShieldTracePolicy:
    input_storage: str
    output_storage: str
    cot_storage: str = "none"


@dataclass(slots=True)
class ShieldAuditPolicy:
    mode: str


@dataclass(slots=True)
class ShieldEnvelope:
    mode: str
    level: str
    handling: str
    assets: list[str] = field(default_factory=list)
    input: ShieldInputPolicy = field(default_factory=lambda: ShieldInputPolicy("basic", "off"))
    execution: ShieldExecutionPolicy = field(default_factory=lambda: ShieldExecutionPolicy("high_risk", "default"))
    output: ShieldOutputPolicy = field(default_factory=lambda: ShieldOutputPolicy("basic", "off", "redact", "redact"))
    trace: ShieldTracePolicy = field(default_factory=lambda: ShieldTracePolicy("redacted", "redacted"))
    audit: ShieldAuditPolicy = field(default_factory=lambda: ShieldAuditPolicy("standard"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "level": self.level,
            "handling": self.handling,
            "assets": list(self.assets),
            "input": {"inspection": self.input.inspection, "pii": self.input.pii},
            "execution": {"approval": self.execution.approval, "rate_limit": self.execution.rate_limit},
            "output": {
                "inspection": self.output.inspection,
                "pii": self.output.pii,
                "secret_handling": self.output.secret_handling,
                "failure_mode": self.output.failure_mode,
            },
            "trace": {
                "input_storage": self.trace.input_storage,
                "output_storage": self.trace.output_storage,
                "cot_storage": self.trace.cot_storage,
            },
            "audit": {"mode": self.audit.mode},
        }


@dataclass(slots=True)
class OutputProtectionResult:
    status: str
    result: Any
    reasons: list[str] = field(default_factory=list)
    redactions: list[str] = field(default_factory=list)


class ShieldPolicy:
    def envelope_for(self, pawprint: PawprintConfig) -> ShieldEnvelope:
        config = pawprint.resolved_protection()
        assets = list(config.assets)
        envelope = _base_envelope(config.level, config.handling, assets)
        envelope = _apply_handling_adjustments(envelope)
        return envelope

    def apply_to_candidate(
        self,
        candidate: ActionCandidate,
        *,
        pawprint: PawprintConfig,
        state: dict[str, Any] | None = None,
    ) -> tuple[str, ActionCandidate, list[str]]:
        del pawprint, state
        # Pawprint is the authorization contract. Shield protects data on the
        # way in and out, but does not reinterpret an explicit allow/review/block
        # boundary from a heuristic operational score or missing metadata.
        return ("review" if candidate.requires_review else "allow"), candidate, []

    def sanitize_action(self, action: Action, envelope: ShieldEnvelope) -> tuple[Action, list[str]]:
        redactions: list[str] = []
        updated_arguments = _sanitize_value(
            action.arguments,
            pii_mode=envelope.input.pii,
            inspection_mode=envelope.input.inspection,
            redactions=redactions,
        )
        if updated_arguments == action.arguments:
            return action, redactions
        return Action(name=action.name, arguments=updated_arguments, target=action.target), redactions

    def protect_output(self, result: Any, envelope: ShieldEnvelope) -> OutputProtectionResult:
        inspected = result
        redactions: list[str] = []
        reasons: list[str] = []

        if envelope.output.pii == "redact":
            inspected = _redact_pii_value(inspected, redactions)

        detected_issue = False
        if envelope.output.inspection != "off":
            flattened = _flatten_value(inspected).lower()
            if _contains_secret(flattened):
                detected_issue = True
                reasons.append("output_secret_detected")
            if envelope.output.inspection == "strict" and _contains_system_leak(flattened):
                detected_issue = True
                reasons.append("output_system_leak_detected")

        if detected_issue and envelope.output.secret_handling == "redact":
            inspected = _redact_secret_value(inspected, redactions)
        if detected_issue and envelope.output.secret_handling == "review":
            return OutputProtectionResult(status="needs_review", result=inspected, reasons=reasons, redactions=redactions)
        if detected_issue and envelope.output.secret_handling == "block":
            return OutputProtectionResult(status="blocked", result=None, reasons=reasons, redactions=redactions)

        if detected_issue and envelope.output.failure_mode == "review":
            return OutputProtectionResult(status="needs_review", result=inspected, reasons=reasons, redactions=redactions)
        if detected_issue and envelope.output.failure_mode == "block":
            return OutputProtectionResult(status="blocked", result=None, reasons=reasons, redactions=redactions)

        return OutputProtectionResult(status="completed", result=inspected, reasons=reasons, redactions=redactions)


def _base_envelope(level: str, handling: str, assets: list[str]) -> ShieldEnvelope:
    pii_mode = "redact" if "customer_data" in assets else "off"
    if level == "open":
        envelope = ShieldEnvelope(
            mode="opaque",
            level="open",
            handling=handling,
            assets=assets,
            input=ShieldInputPolicy("off", "off"),
            execution=ShieldExecutionPolicy("none", "default"),
            output=ShieldOutputPolicy("basic", "off", "redact", "redact"),
            trace=ShieldTracePolicy("redacted", "redacted"),
            audit=ShieldAuditPolicy("minimal"),
        )
    elif level == "protected":
        envelope = ShieldEnvelope(
            mode="opaque",
            level="protected",
            handling=handling,
            assets=assets,
            input=ShieldInputPolicy("basic", pii_mode),
            execution=ShieldExecutionPolicy("external_write" if "external_write" in assets else "high_risk", "strict" if {"paid_api", "internal_workflow"} & set(assets) else "default"),
            output=ShieldOutputPolicy("strict", pii_mode, "review", "review" if "external_write" in assets else "redact"),
            trace=ShieldTracePolicy("summary" if {"customer_data", "private_knowledge"} & set(assets) else "redacted", "summary" if {"customer_data", "private_knowledge"} & set(assets) else "redacted"),
            audit=ShieldAuditPolicy("detailed"),
        )
    elif level == "confidential":
        envelope = ShieldEnvelope(
            mode="opaque",
            level="confidential",
            handling=handling,
            assets=assets,
            input=ShieldInputPolicy("strict", "redact"),
            execution=ShieldExecutionPolicy("external_write" if "external_write" in assets else "high_risk", "strict"),
            output=ShieldOutputPolicy("strict", "redact", "block", "review"),
            trace=ShieldTracePolicy("summary", "summary"),
            audit=ShieldAuditPolicy("detailed"),
        )
    else:
        envelope = ShieldEnvelope(
            mode="opaque",
            level="standard",
            handling=handling,
            assets=assets,
            input=ShieldInputPolicy("basic", pii_mode),
            execution=ShieldExecutionPolicy("high_risk", "default"),
            output=ShieldOutputPolicy("basic", pii_mode, "redact", "redact"),
            trace=ShieldTracePolicy("redacted", "redacted"),
            audit=ShieldAuditPolicy("standard"),
        )
    return envelope


def _apply_handling_adjustments(envelope: ShieldEnvelope) -> ShieldEnvelope:
    assets = set(envelope.assets)
    trace_input = envelope.trace.input_storage
    trace_output = envelope.trace.output_storage
    output_failure = envelope.output.failure_mode
    execution_approval = envelope.execution.approval
    audit_mode = envelope.audit.mode
    input_inspection = envelope.input.inspection
    output_inspection = envelope.output.inspection

    if envelope.handling == "cautious":
        trace_input = "summary" if trace_input == "raw" else trace_input
        trace_output = "summary" if trace_output == "raw" else trace_output
        if output_failure == "allow":
            output_failure = "redact"
        if output_failure == "redact" and "external_write" in assets:
            output_failure = "review"
        if "external_write" in assets:
            execution_approval = "external_write"
    elif envelope.handling == "strict":
        input_inspection = "strict"
        output_inspection = "strict"
        trace_input = "summary" if trace_input not in {"summary", "none"} else trace_input
        trace_output = "summary" if trace_output not in {"summary", "none"} else trace_output
        if envelope.level == "confidential" and "external_write" in assets:
            execution_approval = "always"
        if envelope.level != "open":
            audit_mode = "detailed"

    return ShieldEnvelope(
        mode=envelope.mode,
        level=envelope.level,
        handling=envelope.handling,
        assets=list(envelope.assets),
        input=ShieldInputPolicy(input_inspection, envelope.input.pii),
        execution=ShieldExecutionPolicy(execution_approval, envelope.execution.rate_limit),
        output=ShieldOutputPolicy(output_inspection, envelope.output.pii, envelope.output.secret_handling, output_failure),
        trace=ShieldTracePolicy(trace_input, trace_output, envelope.trace.cot_storage),
        audit=ShieldAuditPolicy(audit_mode),
    )


def _contains_prompt_injection(text: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in _PROMPT_INJECTION_PATTERNS)


def _contains_secret(text: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in _SECRET_PATTERNS)


def _contains_system_leak(text: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in _SYSTEM_LEAK_PATTERNS)


def _sanitize_value(value: Any, *, pii_mode: str, inspection_mode: str, redactions: list[str]) -> Any:
    if isinstance(value, dict):
        return {key: _sanitize_value(item, pii_mode=pii_mode, inspection_mode=inspection_mode, redactions=redactions) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_value(item, pii_mode=pii_mode, inspection_mode=inspection_mode, redactions=redactions) for item in value]
    if not isinstance(value, str):
        return value
    result = value
    if pii_mode == "redact":
        updated = re.sub(_EMAIL_PATTERN, "[redacted-email]", result, flags=re.IGNORECASE)
        if updated != result:
            redactions.append("input_email_redacted")
        result = updated
        updated = re.sub(_PHONE_PATTERN, "[redacted-phone]", result, flags=re.IGNORECASE)
        if updated != result:
            redactions.append("input_phone_redacted")
        result = updated
        updated = re.sub(r"\b(?:sk-[A-Za-z0-9]{16,}|[A-Za-z0-9_\-]{24,})\b", "[redacted-token]", result)
        if updated != result:
            redactions.append("input_token_redacted")
        result = updated
    if inspection_mode in {"basic", "strict"} and _contains_prompt_injection(result):
        redactions.append("input_prompt_injection_detected")
    return result


def _redact_pii_value(value: Any, redactions: list[str]) -> Any:
    if isinstance(value, dict):
        return {key: _redact_pii_value(item, redactions) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_pii_value(item, redactions) for item in value]
    if not isinstance(value, str):
        return value
    updated = re.sub(_EMAIL_PATTERN, "[redacted-email]", value, flags=re.IGNORECASE)
    if updated != value:
        redactions.append("output_email_redacted")
    value = updated
    updated = re.sub(_PHONE_PATTERN, "[redacted-phone]", value, flags=re.IGNORECASE)
    if updated != value:
        redactions.append("output_phone_redacted")
    return updated


def _redact_secret_value(value: Any, redactions: list[str]) -> Any:
    if isinstance(value, dict):
        return {key: _redact_secret_value(item, redactions) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_secret_value(item, redactions) for item in value]
    if not isinstance(value, str):
        return value
    result = value
    for pattern in _SECRET_PATTERNS:
        updated = re.sub(pattern, "[redacted-secret]", result, flags=re.IGNORECASE)
        if updated != result:
            redactions.append("output_secret_redacted")
        result = updated
    return result


def _flatten_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        return " ".join(_flatten_value(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_flatten_value(item) for item in value)
    return str(value)
