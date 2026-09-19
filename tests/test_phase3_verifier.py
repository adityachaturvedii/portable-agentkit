import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from agentkit.delivery import ConstrainedVerifier, TEST_SOURCE
from agentkit.doctor import native_sandbox_capability
from agentkit.git_broker import GitBroker


class ConstrainedVerifierTests(unittest.TestCase):
    def test_candidate_cannot_read_protected_paths_credentials_or_mutate_inputs(self):
        capability = native_sandbox_capability()
        if capability.state != 'verified':
            self.skipTest(capability.evidence)
        with tempfile.TemporaryDirectory(prefix='agentkit-verifier-test-') as tmp:
            root = Path(tmp).resolve()
            broker = GitBroker(root / 'managed')
            controller = root / 'controller'
            approval = root / 'approval'
            evidence = root / 'evidence'
            credential = root / 'fake-credential'
            for path in (controller, approval, evidence):
                path.mkdir()
            (controller / 'state.json').write_text('CONTROLLER-CANARY')
            (approval / 'package.json').write_text('APPROVAL-CANARY')
            credential.write_text('FAKE-CREDENTIAL-CANARY')
            repository, base = broker.create_repository('fixture', {
                'calculator.py': 'def total(left, right):\n    return left + right\n',
                'test_calculator.py': 'worker-controlled test must not be used\n',
            })
            _, worktree, _ = broker.create_task_worktree(repository, 'task', base)
            worker = broker.export_snapshot(repository, base, broker.worker_copies / 'task')
            protected = [controller / 'state.json', approval / 'package.json',
                         repository / '.git/config', worktree / 'calculator.py', credential]
            source = (
                'import os\n'
                'from pathlib import Path\n'
                'for target in ' + repr([str(path) for path in protected]) + ':\n'
                '    try:\n'
                '        Path(target).read_text()\n'
                '    except OSError:\n'
                '        pass\n'
                '    else:\n'
                '        raise RuntimeError("protected path was readable")\n'
                'if os.environ.get("OPENAI_API_KEY"):\n'
                '    raise RuntimeError("credential environment leaked")\n'
                'try:\n'
                '    Path(__file__).write_text("tampered")\n'
                'except OSError:\n'
                '    pass\n'
                'else:\n'
                '    raise RuntimeError("verification source was writable")\n'
                'def total(left, right):\n'
                '    return left + right\n'
            )
            (worker / 'calculator.py').write_text(source)
            head, _ = broker.apply_worker_changes(repository, worktree, worker,
                                                   ('calculator.py',), 'Synthetic boundary candidate')
            before = broker.worktree_identity(repository, worktree)
            verifier = ConstrainedVerifier(
                broker, controller, approval, evidence, additional_denied=(credential,),
                capability_check=lambda: capability)
            with mock.patch.dict(os.environ, {'OPENAI_API_KEY': 'FAKE-ENV-CANARY'}):
                outcome = verifier.run(repository, worktree, head, TEST_SOURCE, 0)
            self.assertEqual(outcome.status, 'succeeded', outcome.details)
            self.assertTrue(outcome.details['candidate_unchanged'])
            self.assertNotIn('OPENAI_API_KEY', outcome.details['environment_keys'])
            self.assertIn(str(Path.home().resolve()), outcome.details['boundary']['denied_read_paths'])
            self.assertIn(str(repository), outcome.details['boundary']['denied_read_paths'])
            self.assertEqual(outcome.details['boundary']['mach_service_lookup'], 'denied')
            self.assertEqual(broker.worktree_identity(repository, worktree), before)
            self.assertEqual((controller / 'state.json').read_text(), 'CONTROLLER-CANARY')
            self.assertEqual((approval / 'package.json').read_text(), 'APPROVAL-CANARY')
            self.assertEqual(credential.read_text(), 'FAKE-CREDENTIAL-CANARY')


if __name__ == '__main__':
    unittest.main()
