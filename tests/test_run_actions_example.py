from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


class RunActionsExampleTests(unittest.TestCase):
    def test_run_actions_basic_example_executes(self) -> None:
        env = dict(os.environ)
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{REPO_ROOT / 'src'}:{REPO_ROOT.parent / 'pawprint' / 'src'}" + (f":{existing}" if existing else "")

        completed = subprocess.run(
            [sys.executable, str(REPO_ROOT / "examples" / "run_actions_basic.py")],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["allowed"]["status"], "completed")
        self.assertEqual(payload["review_required"]["status"], "needs_review")
        self.assertEqual(payload["blocked"]["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
