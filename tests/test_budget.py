import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

from pawly.budget.checker import check_budget
from pawly.budget.state import BudgetState
from pawly.loader.yaml_loader import load_yaml_file
from pawly.types import TaskRequest


class BudgetTests(unittest.TestCase):
    def test_missing_budget_config_is_a_noop(self):
        config = load_yaml_file(REPO_ROOT / "examples" / "agents" / "basic_worker.yaml")
        intent = TaskRequest(task="Answer order status", action="draft reply", confidence=0.9).to_intent()
        result = check_budget(config, BudgetState(), intent)
        self.assertFalse(result.exhausted)
        self.assertEqual(result.consumed, {})


if __name__ == "__main__":
    unittest.main()
