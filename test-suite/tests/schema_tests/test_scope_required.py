from pathlib import Path

from pawly_test_suite.loader import load_fixture
from pawly_test_suite.runner import ComplianceRunner


def test_boundaries_required():
    result = ComplianceRunner().check_boundaries_required(load_fixture("valid_agent.yaml"))
    assert result.passed
