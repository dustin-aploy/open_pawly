from pathlib import Path

from pawly_test_suite.loader import load_fixture
from pawly_test_suite.runner import ComplianceRunner


def test_audit_on_block():
    result = ComplianceRunner().check_audit_on_block(load_fixture("valid_agent.yaml"))
    assert result.passed
