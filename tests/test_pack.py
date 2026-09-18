import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from agentkit.pack import catalog, check_pack, render, select
from agentkit.validation import ROOT, ValidationError


class PackTests(unittest.TestCase):
    def test_offline_pack_consistency(self):
        report = check_pack()
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["skills"], 10)

    def test_explicit_selection_rejects_unknown_or_injected_intent(self):
        for intent in ("publish", "review; gh pr create", "../../secret"):
            with self.assertRaises(ValidationError):
                select(intent)

    def test_domains_are_progressively_loaded(self):
        plain = render("behavioral-testing")
        enriched = render("behavioral-testing", "training-correctness")
        self.assertNotIn("Overfit a small synthetic dataset", plain)
        self.assertIn("Overfit a small synthetic dataset", enriched)
        self.assertNotIn("exclusive GPU access", enriched)
        with self.assertRaises(ValidationError):
            render("behavioral-testing", "../../secret")

    def test_relocated_checkout_works_with_empty_home(self):
        with tempfile.TemporaryDirectory(prefix="agentkit-portability-") as tmp:
            dst = Path(tmp) / "toolkit with spaces"
            shutil.copytree(ROOT, dst, ignore=shutil.ignore_patterns(".git", "__pycache__", ".local"))
            home = Path(tmp) / "empty-home"
            home.mkdir()
            env = {"PATH": os.environ.get("PATH", ""), "HOME": str(home), "PYTHONDONTWRITEBYTECODE": "1"}
            result = subprocess.run([sys.executable, "-m", "agentkit", "check"], cwd=dst,
                                    env=env, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["skills"], 10)
            self.assertEqual(list(home.iterdir()), [])

    def test_planned_commands_are_not_available(self):
        for command in ("run", "approve-pr", "doctor", "update"):
            result = subprocess.run([sys.executable, "-m", "agentkit", command], cwd=ROOT,
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
