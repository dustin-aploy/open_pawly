from pathlib import Path

from pawly_test_suite.loader import load_fixture
from pawly_test_suite.runner import ComplianceRunner


def test_audit_fields():
    result = ComplianceRunner().check_audit_fields(load_fixture("valid_agent.yaml"))
    assert result.passed
