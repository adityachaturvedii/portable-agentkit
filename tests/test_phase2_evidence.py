"""Replay live evidence offline; these tests never launch a provider."""
import hashlib
import json
from pathlib import Path
import unittest

from agentkit.adapters import normalize, stop_on_limit
from agentkit.process import ProcessOutcome
from agentkit.runtime_contracts import CancellationStatus, ExecutionRequest
from agentkit.smoke import acceptance

ROOT = Path(__file__).resolve().parents[1] / 'evidence/phase2'
FOLLOWUP = Path(__file__).resolve().parents[1] / 'evidence/phase2-followup'


class EvidenceTests(unittest.TestCase):
    def test_followup_evidence_hashes_and_acceptance(self):
        manifest = json.loads((FOLLOWUP / 'manifest.json').read_text())
        self.assertEqual(manifest['base_revision'], '6bfb981670a1f4e553c870995414452f2ce06b21')
        self.assertGreater(len(manifest['files']), 30)
        for name, digest in manifest['files'].items():
            with self.subTest(name=name):
                path = FOLLOWUP / name
                self.assertIn(FOLLOWUP, path.resolve().parents)
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
        for engine in ('codex', 'claude'):
            acceptance_record = json.loads((FOLLOWUP / ('live-' + engine) / 'acceptance.json').read_text())
            self.assertTrue(acceptance_record['passed'])
            self.assertTrue(acceptance_record['provider_test_execution']['passed'])
            self.assertEqual(acceptance_record['changed_files'], ['arithmetic.py'])
            result = json.loads((FOLLOWUP / ('live-' + engine) / 'result.json').read_text())
            self.assertIsNone(result['usage']['billed_cost_usd'])
        self.assertTrue(json.loads((FOLLOWUP / 'boundary/boundary.json').read_text())['passed'])
        self.assertTrue(json.loads((FOLLOWUP / 'lifecycle/lifecycle.json').read_text())['passed'])

    def test_preserved_phase2_evidence_hashes(self):
        manifest = json.loads((ROOT / 'manifest.json').read_text())
        self.assertGreater(len(manifest['files']), 15)
        for name, digest in manifest['files'].items():
            with self.subTest(name=name):
                path = ROOT / name
                self.assertIn(ROOT, path.resolve().parents)
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)

    def test_claude_live_output_replay_and_independent_oracle(self):
        folder = ROOT / 'live-claude'
        original = json.loads((folder / 'result.json').read_text())
        for name, digest in original['artifacts'].items():
            self.assertEqual(hashlib.sha256((folder / name).read_bytes()).hexdigest(), digest)
        raw = (folder / 'stdout.redacted.jsonl').read_bytes()
        self.assertIsNone(stop_on_limit(raw, b''))
        # Preserve observed exit/cancellation; only correct the false stop classification.
        out = ProcessOutcome(raw, b'', original['exit_code'], original['elapsed_seconds'], None,
                             CancellationStatus(**original['cancellation']))
        request = ExecutionRequest('claude', 'offline-replay', 'synthetic', '/unused')
        result = normalize(request, out)
        self.assertTrue(acceptance(result, [17, 25])['passed'])
        self.assertEqual(result.usage.input_tokens, 2)
        self.assertEqual(result.usage.output_tokens, 10)
        self.assertEqual(result.usage.cache_creation_tokens, 2506)
        self.assertEqual(result.usage.estimated_cost_usd, .02532)
        self.assertIsNone(result.usage.billed_cost_usd)
        self.assertEqual(result.provider_details['tools'], [])
        self.assertEqual(result.provider_details['mcp_servers'], [])

    def test_codex_guard_failure_is_not_promoted_to_live_success(self):
        folder = ROOT / 'live-codex-final'
        original = json.loads((folder / 'result.json').read_text())
        out = ProcessOutcome((folder / 'stdout.redacted.jsonl').read_bytes(),
                             (folder / 'stderr.redacted.txt').read_bytes(), original['exit_code'],
                             original['elapsed_seconds'], None, CancellationStatus(**original['cancellation']))
        result = normalize(ExecutionRequest('codex', 'offline-replay', 'synthetic', '/unused'), out)
        self.assertEqual(result.error_class, 'guard_denied')
        self.assertFalse(acceptance(result, [17, 25])['passed'])
        self.assertIsNone(result.usage.input_tokens)


if __name__ == '__main__':
    unittest.main()
