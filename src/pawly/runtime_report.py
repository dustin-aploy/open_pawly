from __future__ import annotations

from pawly.pawprint_loader import PawprintConfig
from pawly.performance.report import build_daily_report
from pawly.validator.validator import PawprintValidator, SchemaValidationError


def build_validated_runtime_report(
    *,
    validator: PawprintValidator,
    pawprint: PawprintConfig,
    decisions: list[dict],
) -> dict:
    report = build_daily_report(pawprint, decisions)
    validation = validator.validate_report(report)
    if not validation.valid:
        raise SchemaValidationError("; ".join(validation.errors))
    return report
