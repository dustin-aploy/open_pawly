from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
from typing import Callable

from pawly.runtime import PawlyRuntime
from pawly.validator.validator import PawprintValidator

from pawly_test_suite.loader import declaration_digest, load_agent, load_json_fixture, load_pawprint_version
from pawly_test_suite.report import build_report, write_report
from pawly_test_suite.result_types import CheckResult


CheckFunc = Callable[[dict], CheckResult]


class ComplianceRunner:
    def __init__(self) -> None:
        self.validator = PawprintValidator()
        self.catalog: list[CheckFunc] = [
            self.check_metadata_required,
            self.check_id_required,
            self.check_capabilities_required,
            self.check_boundaries_required,
            self.check_never_boundary_blocks,
            self.check_ask_first_escalates,
            self.check_low_confidence_escalates,
            self.check_audit_fields,
            self.check_audit_event_types,
            self.check_audit_on_block,
            self.check_audit_on_escalation,
            self.check_report_required_fields,
        ]

    def run(self, *, agent_path: str | Path, project: str, output_path: str | Path = "compliance-report.json") -> dict:
        agent_path = Path(agent_path)
        config = load_agent(agent_path)
        checks = [check(config) for check in self.catalog]
        summary = build_report(
            project=project,
            pawprint_version=load_pawprint_version(),
            worker_id=_worker_id(config),
            card_digest=declaration_digest(agent_path),
            artifact_uri=agent_path.resolve().as_uri(),
            checks=checks,
        )
        write_report(output_path, summary)
        return summary.to_dict()

    def check_id_required(self, config: dict) -> CheckResult:
        candidate = dict(config)
        metadata = dict(candidate.get("metadata", {}))
        metadata.pop("id", None)
        candidate["metadata"] = metadata
        result = self.validator.validate_agent_config(candidate)
        return CheckResult("id-required", "schema", not result.valid, "id must be required", result.errors)

    def check_metadata_required(self, config: dict) -> CheckResult:
        candidate = dict(config)
        candidate.pop("metadata", None)
        result = self.validator.validate_agent_config(candidate)
        return CheckResult("metadata-required", "schema", not result.valid, "metadata must be required", result.errors)

    def check_capabilities_required(self, config: dict) -> CheckResult:
        candidate = dict(config)
        candidate.pop("capabilities", None)
        result = self.validator.validate_agent_config(candidate)
        return CheckResult("capabilities-required", "schema", not result.valid, "capabilities must be required", result.errors)

    def check_boundaries_required(self, config: dict) -> CheckResult:
        candidate = dict(config)
        candidate.pop("boundaries", None)
        result = self.validator.validate_agent_config(candidate)
        return CheckResult("boundaries-required", "schema", not result.valid, "boundaries must be required", result.errors)

    def check_never_boundary_blocks(self, config: dict) -> CheckResult:
        runtime = self._runtime_with_config(config)
        result = runtime.evaluate("Give legal advice about a dispute", "write legal answer", 0.95)
        return CheckResult("never-boundary-block", "behavior", result["type"] == "deny", "never boundaries should deny", [result["reason"]])

    def check_ask_first_escalates(self, config: dict) -> CheckResult:
        runtime = self._runtime_with_config(config)
        result = runtime.evaluate("Send an external status update to a partner", "send_external_message", 0.90)
        return CheckResult(
            "ask-first-escalates",
            "behavior",
            result["type"] == "require_approval",
            "review boundaries should require approval",
            [result["reason"]],
        )

    def check_low_confidence_escalates(self, config: dict) -> CheckResult:
        runtime = self._runtime_with_config(config)
        result = runtime.evaluate("Answer a vague customer question", "draft helpful reply", 0.55)
        return CheckResult("low-confidence-escalates", "behavior", result["type"] == "require_approval", "low confidence should require approval", [result["reason"]])

    def check_audit_fields(self, config: dict) -> CheckResult:
        audit_path = Path(tempfile.gettempdir()) / "pawly-test-suite-audit-fields.jsonl"
        runtime = self._runtime_with_config(config, audit_path=audit_path)
        runtime.evaluate("Answer order status questions for a customer", "draft helpful reply", 0.95)
        payload = json.loads(audit_path.read_text(encoding="utf-8").splitlines()[-1])
        expected = load_json_fixture("expected_audit.json")
        missing = [key for key in expected["required_fields"] if key not in payload]
        return CheckResult("audit-fields", "audit", not missing, "audit events must contain required fields", missing or list(payload.keys()))

    def check_audit_event_types(self, config: dict) -> CheckResult:
        audit_path = Path(tempfile.gettempdir()) / "pawly-test-suite-audit-types.jsonl"
        runtime = self._runtime_with_config(config, audit_path=audit_path)
        runtime.evaluate("Answer order status questions for a customer", "draft helpful reply", 0.95)
        payload = json.loads(audit_path.read_text(encoding="utf-8").splitlines()[-1])
        return CheckResult("audit-event-type", "audit", payload.get("event_type") == "action-proposed", "audit events should use action-proposed", [payload.get("event_type", "missing")])

    def check_audit_on_block(self, config: dict) -> CheckResult:
        audit_path = Path(tempfile.gettempdir()) / "pawly-test-suite-audit-block.jsonl"
        runtime = self._runtime_with_config(config, audit_path=audit_path)
        runtime.evaluate("Give legal advice about a dispute", "write legal answer", 0.95)
        payload = json.loads(audit_path.read_text(encoding="utf-8").splitlines()[-1])
        return CheckResult("audit-on-block", "audit", payload.get("outcome") == "deny", "deny decisions must be audited", [payload.get("outcome", "missing")])

    def check_audit_on_escalation(self, config: dict) -> CheckResult:
        audit_path = Path(tempfile.gettempdir()) / "pawly-test-suite-audit-escalation.jsonl"
        runtime = self._runtime_with_config(config, audit_path=audit_path)
        runtime.evaluate("Send an external status update to a partner", "send_external_message", 0.65)
        payload = json.loads(audit_path.read_text(encoding="utf-8").splitlines()[-1])
        return CheckResult("audit-on-escalation", "audit", payload.get("outcome") == "require_approval", "require_approval decisions must be audited", [payload.get("outcome", "missing")])

    def check_report_required_fields(self, config: dict) -> CheckResult:
        runtime = self._runtime_with_config(config)
        runtime.evaluate("Answer order status questions for a customer", "draft helpful reply", 0.95)
        report = runtime.build_report()
        required = load_json_fixture("sample_daily_report.json")["required_fields"]
        missing = [key for key in required if key not in report]
        return CheckResult("report-required-fields", "reporting", not missing, "runtime reports should include required fields", missing or required)

    def _runtime_with_config(self, config: dict, audit_path: str | Path | None = None) -> PawlyRuntime:
        temp_path = Path(tempfile.gettempdir()) / f"pawly-test-suite-{_worker_id(config).replace('.', '-')}.yaml"
        temp_path.write_text(_dump_yaml(config), encoding="utf-8")
        return PawlyRuntime(temp_path, audit_path=audit_path)


def _worker_id(config: dict) -> str:
    metadata = config.get("metadata")
    if isinstance(metadata, dict):
        worker_id = metadata.get("id")
        if isinstance(worker_id, str):
            return worker_id
    worker_id = config.get("id")
    if isinstance(worker_id, str):
        return worker_id
    raise KeyError("Worker id not found in config")


def _dump_yaml(value, indent: int = 0) -> str:
    pad = " " * indent
    if isinstance(value, dict):
        lines = []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                lines.append(f"{pad}{key}:")
                lines.append(_dump_yaml(item, indent + 2))
            else:
                lines.append(f"{pad}{key}: {_scalar(item)}")
        return "\n".join(lines)
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, dict):
                dict_lines = _dump_yaml(item, indent + 2).splitlines()
                first = dict_lines[0].lstrip()
                lines.append(f"{pad}- {first}")
                lines.extend(dict_lines[1:])
            elif isinstance(item, list):
                lines.append(f"{pad}-")
                lines.append(_dump_yaml(item, indent + 2))
            else:
                lines.append(f"{pad}- {_scalar(item)}")
        return "\n".join(lines)
    return f"{pad}{_scalar(value)}"


def _scalar(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str) and any(char in value for char in [":", "#", "[", "]"]):
        return json.dumps(value)
    return str(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pawly-test-suite", description="Pawprint validation runner")
    parser.add_argument("--agent", required=True, help="Path to the Pawprint worker card YAML file to test")
    parser.add_argument("--project", required=True, help="Project name for the validation report")
    parser.add_argument("--output", default="compliance-report.json", help="Path to write the validation report JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    report = ComplianceRunner().run(agent_path=args.agent, project=args.project, output_path=args.output)
    print(json.dumps(report, indent=2, sort_keys=True))
    summary = report.get("summary", {})
    if summary.get("status") == "fail" or summary.get("failed", 0):
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
