from pathlib import Path

from pawly_test_suite.loader import load_fixture
from pawly_test_suite.runner import ComplianceRunner


def test_ask_first_escalates():
    result = ComplianceRunner().check_ask_first_escalates(load_fixture("valid_agent.yaml"))
    assert result.passed
