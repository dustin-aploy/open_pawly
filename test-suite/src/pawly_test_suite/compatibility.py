from __future__ import annotations

from pawly_test_suite.result_types import CheckResult


REQUIRED_CATEGORIES_FOR_COMPATIBLE = {"schema", "behavior", "audit"}
REQUIRED_CATEGORIES_FOR_CERTIFIED = {"schema", "behavior", "audit", "reporting"}


def determine_compatibility(checks: list[CheckResult]) -> str:
    passed_categories = {check.category for check in checks if check.passed}
    failed = any(not check.passed for check in checks)
    if not failed and REQUIRED_CATEGORIES_FOR_CERTIFIED.issubset(passed_categories):
        return "certified"
    if not failed and REQUIRED_CATEGORIES_FOR_COMPATIBLE.issubset(passed_categories):
        return "compatible"
    return "self-tested"
