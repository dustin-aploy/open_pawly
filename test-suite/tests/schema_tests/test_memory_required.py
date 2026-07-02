from pathlib import Path

from pawly_test_suite.loader import load_fixture
from pawly_test_suite.runner import ComplianceRunner


def test_metadata_required():
    result = ComplianceRunner().check_metadata_required(load_fixture("valid_agent.yaml"))
    assert result.passed
