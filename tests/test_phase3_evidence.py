import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'evidence' / 'phase3'


class Phase3EvidenceTests(unittest.TestCase):
    def test_manifest_hashes_every_archived_file(self):
        manifest = json.loads((EVIDENCE / 'manifest.json').read_text())
        recorded = {item['path']: item for item in manifest['files']}
        actual = {
            str(path.relative_to(ROOT)): path
            for path in EVIDENCE.rglob('*')
            if path.is_file() and path.name != 'manifest.json'
        }
        self.assertEqual(set(recorded), set(actual))
        for relative, path in actual.items():
            self.assertEqual(recorded[relative]['bytes'], path.stat().st_size)
            self.assertEqual(recorded[relative]['sha256'], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_simulated_workflow_is_complete_without_approval(self):
        summary = json.loads((EVIDENCE / 'simulated-complete' / 'summary.json').read_text())
        package = json.loads((EVIDENCE / 'simulated-complete' / 'approval-package.json').read_text())
        state = json.loads((EVIDENCE / 'simulated-complete' / 'controller-state.json').read_text())
        self.assertEqual(summary['classification'], 'simulated')
        self.assertEqual(summary['state'], 'awaiting_pr_approval')
        self.assertEqual(summary['head_revision'], package['head_revision'])
        self.assertEqual(package['approval']['recorded'], False)
        self.assertEqual(state['approvals'], [])
        self.assertTrue(all(record['revision'] == package['head_revision']
                            for record in package['verification']))

    def test_live_attempt_passed_candidate_check_then_failed_closed(self):
        summary = json.loads((EVIDENCE / 'live-partial' / 'summary.json').read_text())
        state = json.loads((EVIDENCE / 'live-partial' / 'controller-state.json').read_text())
        self.assertEqual(summary['classification'], 'live-partial')
        self.assertEqual(summary['candidate_independent_check'], 'passed')
        self.assertEqual(summary['state'], 'blocked')
        self.assertFalse(summary['approval_package_created'])
        self.assertEqual(state['approvals'], [])
        executions = {item['role']: item for item in summary['executions']}
        self.assertEqual(executions['implementer']['status'], 'succeeded')
        self.assertEqual(executions['reviewer']['result']['error_class'], 'authentication')
        self.assertIsNone(executions['reviewer']['usage']['input_tokens'])
        self.assertIsNone(executions['reviewer']['usage']['billed_cost_usd'])


if __name__ == '__main__':
    unittest.main()
