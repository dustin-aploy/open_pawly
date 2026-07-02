from pathlib import Path

from pawly_test_suite.loader import load_fixture
from pawly_test_suite.runner import ComplianceRunner


def test_never_boundary_blocks():
    result = ComplianceRunner().check_never_boundary_blocks(load_fixture("valid_agent.yaml"))
    assert result.passed
