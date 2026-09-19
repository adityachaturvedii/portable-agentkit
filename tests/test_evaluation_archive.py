"""Reconcile preserved evaluator artifacts and recheck both fixes independently."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from agentkit.validation import ROOT, read_json, validate_handoff


ARCHIVE = ROOT / "audit/evaluations"


class EvaluationArchiveTests(unittest.TestCase):
    def test_archived_files_and_handoff_artifacts_match_recorded_hashes(self):
        manifest = read_json(ARCHIVE / "manifest.json")
        for entry in manifest["files"]:
            path = ARCHIVE / entry["path"]
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), entry["sha256"])
        for path in (ARCHIVE / "skills/handoffs").glob("*.json"):
            handoff = validate_handoff(read_json(path))
            for record in handoff["evidence"]:
                environment = ARCHIVE / "skills/evidence/environment.json"
                self.assertEqual(hashlib.sha256(environment.read_bytes()).hexdigest(), record["environment_digest"])
                for artifact in record["artifacts"]:
                    # Historical temp paths are mapped to the retained archive, never read.
                    archived = ARCHIVE / "skills/evidence" / Path(artifact["path"]).name
                    self.assertEqual(hashlib.sha256(archived.read_bytes()).hexdigest(), artifact["sha256"])

    def test_same_independent_acceptance_oracle_for_both_agent_fixes(self):
        oracle = '''from invoice import invoice_total as total
assert total([(1000,1)],200,10)==1100
assert total([(101,1),(101,1)],7,50)==108
assert total([],200,100)==200
assert total([(100,1)],200,100)==200
assert total(iter([(500,2)]),100,20)==900
for args in [([(-1,1)],0,0), ([(1,0)],0,0), ([(1,-1)],0,0), ([], -1,0), ([],0,-1), ([],0,101)]:
    try: total(*args)
    except ValueError: pass
    else: raise AssertionError('invalid range accepted')
print('common independent acceptance passed')
'''
        for condition in ("baseline", "skills"):
            with self.subTest(condition=condition), tempfile.TemporaryDirectory(prefix="agentkit-matched-") as tmp:
                path = Path(tmp)
                shutil.copyfile(ARCHIVE / condition / "invoice.py", path / "invoice.py")
                (path / "oracle.py").write_text(oracle)
                result = subprocess.run([sys.executable, "oracle.py"], cwd=path, capture_output=True,
                                        text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
