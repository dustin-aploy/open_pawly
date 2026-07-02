import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

from pawly.runtime import PawlyRuntime


class ReportTests(unittest.TestCase):
    def test_runtime_builds_internal_report(self):
        runtime = PawlyRuntime(REPO_ROOT / "examples" / "agents" / "basic_worker.yaml")
        runtime.evaluate("Answer order status questions for a customer", "draft helpful reply", 0.95)
        report = runtime.build_report()
        self.assertEqual(report["worker_id"], "support-triage-worker")
        self.assertEqual(report["summary"]["status"], "ok")
        self.assertEqual(report["policy_summary"]["status"], "ok")
        self.assertEqual(report["runtime_overlay_summary"]["notes"][0], "overlay_decisions=0")


if __name__ == "__main__":
    unittest.main()
