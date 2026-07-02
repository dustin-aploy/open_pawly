from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from pawly_test_suite.compatibility import determine_compatibility
from pawly_test_suite.loader import load_local_report_schema_copy
from pawly_test_suite.result_types import CheckResult, ComplianceSummary


class ReportValidationError(ValueError):
    pass


SUITE_VERSION = (Path(__file__).resolve().parents[2] / "VERSION").read_text(encoding="utf-8").strip()


def build_report(
    *,
    project: str,
    pawprint_version: str,
    worker_id: str,
    card_digest: str,
    artifact_uri: str,
    checks: list[CheckResult],
    timestamp: str | None = None,
) -> ComplianceSummary:
    tests_run = len(checks)
    tests_passed = sum(1 for check in checks if check.passed)
    tests_failed = tests_run - tests_passed
    compatibility_level = determine_compatibility(checks)
    status = _summary_status(compatibility_level, tests_failed)
    timestamp = timestamp or datetime.now(timezone.utc).isoformat()
    report_id = _build_report_id(project, pawprint_version, checks)
    summary = ComplianceSummary(
        kind="PawKitValidationReport",
        report_id=report_id,
        generated_at=timestamp,
        subject={
            "worker_id": worker_id,
            "card_digest": card_digest,
            "artifact_uri": artifact_uri,
        },
        pawprint_version=pawprint_version,
        profile={
            "name": project,
            "version": SUITE_VERSION,
            "issuer": "pawly-test-suite",
        },
        summary={
            "status": status,
            "passed": tests_passed,
            "failed": tests_failed,
            "warnings": 0,
            "notes": [
                f"project={project}",
                f"compatibility_level={compatibility_level}",
                f"tests_run={tests_run}",
                f"tests_passed={tests_passed}",
                f"tests_failed={tests_failed}",
                f"test_suite_version={SUITE_VERSION}",
            ],
        },
        checks=checks,
        attestations=[
            {
                "name": "pawly-test-suite",
                "role": "suite-runner",
                "timestamp": timestamp,
                "statement": f"Generated {compatibility_level} local validation evidence for {project}.",
            }
        ],
    )
    validate_report(summary.to_dict())
    return summary


def write_report(path: str | Path, summary: ComplianceSummary) -> Path:
    path = Path(path)
    path.write_text(json.dumps(summary.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def validate_report(report: dict[str, Any]) -> None:
    schema = load_local_report_schema_copy()
    errors = _validate_with_schema(report, schema, "$", schema)
    if errors:
        raise ReportValidationError("; ".join(errors))


def _validate_with_schema(instance: Any, schema: dict[str, Any], path: str, root_schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if "$ref" in schema:
        ref = schema["$ref"]
        if ref.startswith("#/"):
            target = root_schema
            for part in ref[2:].split("/"):
                target = target[part]
            return _validate_with_schema(instance, target, path, root_schema)
        return [f"{path} uses unsupported schema reference"]
    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path} must equal {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path} must be one of {schema['enum']!r}")
    if instance is None:
        return errors
    schema_type = schema.get("type")
    if schema_type == "object":
        if not isinstance(instance, dict):
            return errors + [f"{path} must be an object"]
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}.{key} is required")
        properties = schema.get("properties", {})
        for key, value in instance.items():
            if key not in properties:
                if schema.get("additionalProperties", True) is False:
                    errors.append(f"{path}.{key} is not allowed")
                continue
            errors.extend(_validate_with_schema(value, properties[key], f"{path}.{key}", root_schema))
        return errors
    if schema_type == "array":
        if not isinstance(instance, list):
            return errors + [f"{path} must be an array"]
        if len(instance) < schema.get("minItems", 0):
            errors.append(f"{path} must contain at least {schema['minItems']} items")
        item_schema = schema.get("items")
        if item_schema is not None:
            for index, item in enumerate(instance):
                errors.extend(_validate_with_schema(item, item_schema, f"{path}[{index}]", root_schema))
        return errors
    if schema_type == "string":
        if not isinstance(instance, str):
            return errors + [f"{path} must be a string"]
        if len(instance) < schema.get("minLength", 0):
            errors.append(f"{path} must be at least {schema['minLength']} characters")
        return errors
    if schema_type == "integer":
        if not isinstance(instance, int) or isinstance(instance, bool):
            return errors + [f"{path} must be an integer"]
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path} must be >= {schema['minimum']}")
        return errors
    if schema_type == "boolean":
        if not isinstance(instance, bool):
            return errors + [f"{path} must be a boolean"]
        return errors
    return errors


def _summary_status(compatibility_level: str, tests_failed: int) -> str:
    if tests_failed:
        return "fail"
    if compatibility_level == "certified":
        return "pass"
    return "conditional-pass"


def _build_report_id(project: str, pawprint_version: str, checks: list[CheckResult]) -> str:
    digest_source = json.dumps(
        {
            "project": project,
            "pawprint_version": pawprint_version,
            "checks": [check.to_pawprint_check() for check in checks],
            "suite_version": SUITE_VERSION,
        },
        sort_keys=True,
    )
    return hashlib.sha256(digest_source.encode("utf-8")).hexdigest()[:16]
