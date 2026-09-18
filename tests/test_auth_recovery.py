import json
from pathlib import Path
import tempfile
import threading
import unittest

from agentkit.adapters import authentication_reason
from agentkit.auth import (AuthenticationStatus, guided_login, login_argv,
                           probe_authentication, safe_login_reason)
from agentkit.controller import (AuthenticationRecoveryError, ControllerStore,
                                 ReconciliationRequired, StaleEvidence, UsageRecord)
from agentkit.delivery import (DeliveryWorkflow, EngineOutcome, FakeImplementer,
                               FakeReviewer, FixtureVerifier, SOURCE_FIXED)
from agentkit.doctor import auth_summary
from agentkit.process import ProcessOutcome
from agentkit.runtime_contracts import CancellationStatus, Capability


ROOT = Path(__file__).resolve().parents[1]


class AuthOnceImplementer:
    engine = 'codex'
    model = 'fixture-auth-once'

    def __init__(self, auth_reason='expired', secret='SYNTHETIC-LOGIN-SECRET'):
        self.calls = 0
        self.prompts = []
        self.auth_reason = auth_reason
        self.secret = secret

    def run(self, workspace, output, boundary, prompt, policy):
        self.calls += 1
        self.prompts.append(prompt)
        if self.calls == 1:
            return EngineOutcome('failed', .01, UsageRecord(source='unavailable'), {
                'error_class': 'authentication', 'authentication_failure': self.auth_reason})
        if self.secret in prompt:
            raise AssertionError('login secret entered model input')
        (Path(workspace) / 'calculator.py').write_text(SOURCE_FIXED)
        return EngineOutcome('succeeded', .01, UsageRecord(input_tokens=3, source='fake'),
                             {'simulated': True})


class FailureImplementer:
    engine = 'codex'
    model = 'fixture-failure'

    def __init__(self, category):
        self.category = category

    def run(self, workspace, output, boundary, prompt, policy):
        return EngineOutcome('failed', .01, UsageRecord(source='unavailable'),
                             {'error_class': self.category})


class AuthOnceReviewer:
    engine = 'claude'
    model = 'fixture-auth-once'

    def __init__(self):
        self.calls = 0

    def run(self, snapshot, revision, output, prompt, policy):
        self.calls += 1
        if self.calls == 1:
            return EngineOutcome('failed', .01, UsageRecord(source='unavailable'), {
                'error_class': 'authentication', 'authentication_failure': 'expired',
                'candidate_revision': revision})
        return EngineOutcome('succeeded', .01, UsageRecord(input_tokens=2, source='fake'),
                             {'candidate_revision': revision}, ())


class AuthenticationRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='agentkit-auth-recovery-')
        self.root = Path(self.tmp.name).resolve()
        self.addCleanup(self.tmp.cleanup)

    def _store(self):
        return ControllerStore(self.root / 'controller')

    def _auth_failure(self, store, task_id, state='implementing', provider='codex', refs=()):
        auth = store.authority
        store.create_task(task_id, 'fixture', max_calls=6, verification_reserve=1)
        store.set_contract(task_id, {'scope': ['source.py'], 'acceptance': [{'id': 'case'}]}, authority=auth)
        store.transition(task_id, 'received', 'contracted', task_id + '-contracted', authority=auth)
        store.set_workspace(task_id, 'agentkit/' + task_id, str(self.root / task_id), 'a' * 40,
                            authority=auth)
        store.transition(task_id, 'contracted', 'workspace_ready', task_id + '-ready', authority=auth)
        store.transition(task_id, 'workspace_ready', 'implementing', task_id + '-implementing', authority=auth)
        if state == 'reviewing':
            store.transition(task_id, 'implementing', 'implemented', task_id + '-implemented', authority=auth)
            store.transition(task_id, 'implemented', 'verifying', task_id + '-verifying', authority=auth)
            store.add_evidence(task_id, task_id + '-check', 'a' * 40, 'independent-check', 'passed',
                               'b' * 64, {}, authority=auth)
            store.transition(task_id, 'verifying', 'verified', task_id + '-verified', authority=auth)
            store.transition(task_id, 'verified', 'reviewing', task_id + '-reviewing', authority=auth)
            provider = 'claude'
            refs = refs or (task_id + '-check',)
        role = {'implementing': 'implementer', 'reviewing': 'reviewer'}[state]
        execution = store.reserve_execution(task_id, role, provider, None, 10, authority=auth)
        store.start_execution(execution, authority=auth)
        store.finish_execution(execution, 'failed', .2, UsageRecord(source='unavailable'),
                               {'error_class': 'authentication'}, authority=auth)
        checkpoint = store.checkpoint_authentication(task_id, execution, provider,
                                                     evidence_refs=refs, auth_reason='expired',
                                                     authority=auth)
        return execution, checkpoint

    def test_official_login_commands_and_already_authenticated_reuse(self):
        self.assertEqual(login_argv('codex', 'codex', 'browser'),
                         ['codex', 'login', '-c', 'forced_login_method="chatgpt"'])
        self.assertEqual(login_argv('codex', 'codex', 'device'),
                         ['codex', 'login', '-c', 'forced_login_method="chatgpt"', '--device-auth'])
        self.assertEqual(login_argv('claude', 'claude', 'browser'),
                         ['claude', 'auth', 'login', '--claudeai'])
        calls = []

        def status(provider, executable=None):
            return AuthenticationStatus(provider, 'verified', 'subscription', 'authenticated',
                                        executable or provider)

        result = guided_login('codex', status_probe=status, terminal_available=True,
                              launcher=lambda *args: calls.append(args))
        self.assertEqual(result.status, 'already_authenticated')
        self.assertEqual(calls, [])

    def test_missing_and_expired_failures_are_bounded_categories(self):
        self.assertEqual(authentication_reason('Not logged in; login required'), 'missing')
        self.assertEqual(authentication_reason('OAuth token has expired'), 'expired')
        self.assertEqual(authentication_reason('authentication failed'), 'missing_or_expired')
        missing = ProcessOutcome(b'{"loggedIn":false,"authMethod":"none","apiProvider":"firstParty"}\n',
                                 b'', 1, .01, None, CancellationStatus())
        capability, mode, details = auth_summary('claude', missing)
        self.assertEqual((capability.state, mode, details), ('unavailable', 'none', {}))

    def test_noninteractive_handoff_does_not_launch_or_capture(self):
        calls = []

        def status(provider, executable=None):
            return AuthenticationStatus(provider, 'unavailable', 'none', 'missing_or_expired',
                                        executable or provider)

        result = guided_login('claude', status_probe=status, terminal_available=False,
                              launcher=lambda *args: calls.append(args))
        self.assertEqual(result.status, 'handoff_required')
        self.assertEqual(result.command, 'claude auth login --claudeai')
        self.assertEqual(calls, [])

    def test_status_probe_does_not_fall_back_without_read_only_guard(self):
        result = probe_authentication(
            'claude', executable='claude',
            capability_check=lambda: Capability('unavailable', 'fixture'),
            runner=lambda *args, **kwargs: self.fail('unguarded status command launched'))
        self.assertEqual((result.state, result.mode, result.reason),
                         ('unknown', 'unknown', 'status_unavailable'))

    def test_successful_login_resumes_only_implementation_stage_and_preserves_counts(self):
        implementer = AuthOnceImplementer()
        workflow = DeliveryWorkflow(self.root / 'workflow', implementer, FakeReviewer(),
                                    live_authorized=True)
        workflow.verifier = FixtureVerifier(workflow.broker)
        first = workflow.run()
        self.assertEqual(first['task']['state'], 'authentication_required')
        before = first['snapshot']['budget']
        self.assertEqual(before['completed_calls'], 1)
        self.assertEqual(before['active_calls'], 0)
        self.assertEqual(first['task']['repair_count'], 0)
        claim = workflow.store.claim_authentication_login('phase3-demo', 'codex',
                                                          authority=workflow.store.authority)
        workflow.store.finish_authentication_login(claim['session_id'], 'succeeded',
                                                   auth_mode='subscription', reason='authenticated',
                                                   authority=workflow.store.authority)
        waiting = workflow.store.snapshot('phase3-demo')['budget']
        self.assertEqual(waiting, before)
        resumed = workflow.resume()
        self.assertEqual(resumed['task']['state'], 'awaiting_pr_approval')
        self.assertEqual(implementer.calls, 2)
        self.assertEqual(resumed['task']['repair_count'], 0)
        self.assertTrue(all(implementer.secret not in prompt for prompt in implementer.prompts))
        durable = ''.join(path.read_text(errors='replace') for path in (self.root / 'workflow').rglob('*')
                          if path.is_file() and path.name != 'controller.sqlite3')
        self.assertNotIn(implementer.secret, durable)

    def test_reviewer_checkpoint_resumes_reviewer_without_repeating_implementation(self):
        store = self._store()
        _, checkpoint = self._auth_failure(store, 'review-task', state='reviewing')
        before = store.snapshot('review-task')['budget']
        claim = store.claim_authentication_login('review-task', 'claude', authority=store.authority)
        store.finish_authentication_login(claim['session_id'], 'succeeded', auth_mode='subscription',
                                          reason='authenticated', authority=store.authority)
        task = store.resume_after_authentication('review-task', authority=store.authority)
        self.assertEqual(task['state'], 'reviewing')
        self.assertEqual(store.snapshot('review-task')['budget'], before)
        self.assertEqual(checkpoint['interrupted_role'], 'reviewer')

    def test_workflow_reviewer_resume_preserves_implementation_and_verification(self):
        implementer = FakeImplementer()
        reviewer = AuthOnceReviewer()
        workflow = DeliveryWorkflow(self.root / 'review-workflow', implementer, reviewer,
                                    live_authorized=True)
        workflow.verifier = FixtureVerifier(workflow.broker)
        first = workflow.run()
        self.assertEqual(first['task']['state'], 'authentication_required')
        head = first['task']['head_revision']
        check_ids = [item['evidence_id'] for item in first['snapshot']['evidence']
                     if item['kind'] == 'independent-check' and item['status'] == 'passed']
        self.assertEqual(implementer.calls, 1)
        claim = workflow.store.claim_authentication_login('phase3-demo', 'claude',
                                                          authority=workflow.store.authority)
        workflow.store.finish_authentication_login(claim['session_id'], 'succeeded',
                                                   auth_mode='subscription', reason='authenticated',
                                                   authority=workflow.store.authority)
        result = workflow.resume()
        self.assertEqual(result['task']['state'], 'awaiting_pr_approval')
        self.assertEqual(result['task']['head_revision'], head)
        self.assertEqual(implementer.calls, 1)
        self.assertEqual(reviewer.calls, 2)
        self.assertTrue(all(any(item['evidence_id'] == evidence_id and not item['stale']
                                for item in result['snapshot']['evidence'])
                            for evidence_id in check_ids))

    def test_cancel_failure_timeout_leave_recoverable_checkpoint_and_bound_retries(self):
        for index, outcome in enumerate(('cancelled', 'failed', 'timed_out')):
            with self.subTest(outcome=outcome):
                store = ControllerStore(self.root / ('controller-' + str(index)))
                self._auth_failure(store, 'task-' + str(index))
                claim = store.claim_authentication_login('task-' + str(index), 'codex',
                                                          authority=store.authority)
                reason = {'cancelled': 'cancelled', 'failed': 'cli_failed',
                          'timed_out': 'timed_out'}[outcome]
                store.finish_authentication_login(claim['session_id'], outcome, reason=reason,
                                                  authority=store.authority)
                self.assertEqual(store.task('task-' + str(index))['state'], 'authentication_required')
                self.assertEqual(store.authentication_checkpoint('task-' + str(index))['status'], 'waiting')
        store = ControllerStore(self.root / 'bounded')
        self._auth_failure(store, 'bounded')
        for _ in range(2):
            claim = store.claim_authentication_login('bounded', 'codex', authority=store.authority)
            store.finish_authentication_login(claim['session_id'], 'failed', reason='cli_failed',
                                              authority=store.authority)
        with self.assertRaises(AuthenticationRecoveryError):
            store.claim_authentication_login('bounded', 'codex', authority=store.authority)

    def test_concurrent_tasks_share_one_provider_login(self):
        store = self._store()
        self._auth_failure(store, 'first')
        self._auth_failure(store, 'second')
        barrier = threading.Barrier(2)
        results = []
        lock = threading.Lock()

        def claim(task_id):
            local = ControllerStore(store.root)
            barrier.wait()
            value = local.claim_authentication_login(task_id, 'codex', authority=local.authority)
            with lock:
                results.append(value)

        threads = [threading.Thread(target=claim, args=(task_id,)) for task_id in ('first', 'second')]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sum(item['claimed'] for item in results), 1)
        self.assertEqual(len({item['session_id'] for item in results}), 1)

    def test_restart_preserves_waiting_checkpoint(self):
        store = self._store()
        self._auth_failure(store, 'task')
        restarted = ControllerStore(store.root)
        self.assertEqual(restarted.task('task')['state'], 'authentication_required')
        self.assertEqual(restarted.authentication_checkpoint('task')['status'], 'waiting')
        self.assertTrue(restarted.claim_authentication_login(
            'task', 'codex', authority=restarted.authority)['claimed'])

    def test_uncertain_execution_and_candidate_change_prevent_resume(self):
        store = self._store()
        self._auth_failure(store, 'uncertain')
        claim = store.claim_authentication_login('uncertain', 'codex', authority=store.authority)
        store.finish_authentication_login(claim['session_id'], 'succeeded', auth_mode='subscription',
                                          reason='authenticated', authority=store.authority)
        with store.transaction() as db:
            db.execute('''INSERT INTO executions(execution_id,task_id,role,engine,allocation_seconds,status)
                          VALUES(?,?,?,?,?,?)''', ('uncertain-row', 'uncertain', 'implementer', 'codex',
                                                  1, 'reconciliation_required'))
        with self.assertRaises(ReconciliationRequired):
            store.resume_after_authentication('uncertain', authority=store.authority)

        changed = ControllerStore(self.root / 'changed')
        self._auth_failure(changed, 'changed')
        claim = changed.claim_authentication_login('changed', 'codex', authority=changed.authority)
        changed.finish_authentication_login(claim['session_id'], 'succeeded', auth_mode='subscription',
                                            reason='authenticated', authority=changed.authority)
        changed.set_head('changed', 'c' * 40, authority=changed.authority)
        with self.assertRaises(StaleEvidence):
            changed.resume_after_authentication('changed', authority=changed.authority)

    def test_network_and_quota_failures_do_not_create_login_checkpoint(self):
        for category in ('network', 'usage_limit', 'rate_limit'):
            with self.subTest(category=category):
                workflow = DeliveryWorkflow(self.root / category, FailureImplementer(category),
                                            FakeReviewer(), live_authorized=True)
                workflow.verifier = FixtureVerifier(workflow.broker)
                result = workflow.run(task_id=category)
                self.assertEqual(result['task']['state'], 'blocked')
                self.assertEqual(result['snapshot']['authentication_checkpoints'], [])

    def test_review_format_recovery_is_limited_to_hash_validated_evidence_path(self):
        store = self._store()
        auth = store.authority
        execution, _ = self._auth_failure(store, 'format', state='reviewing')
        # Replace the fixture auth outcome with the precise historical parser-only shape.
        with store.transaction() as db:
            db.execute("DELETE FROM authentication_checkpoints WHERE task_id='format'")
            db.execute("UPDATE tasks SET state='reviewing' WHERE task_id='format'")
            db.execute("UPDATE executions SET result_json=? WHERE execution_id=?",
                       (json.dumps({'error_class': None,
                                    'parse_error': 'reviewer did not return a JSON object'}), execution))
        store.transition('format', 'reviewing', 'blocked', 'format-blocked', authority=auth)
        store.add_evidence('format', 'format-recovered-review', 'a' * 40, 'independent-review',
                           'passed', 'd' * 64, {'format_revalidated': True}, authority=auth)
        result = store.recover_review_format_failure(
            'format', execution, 'format-recovered-review', 'a' * 40, authority=auth)
        self.assertEqual(result['state'], 'review_complete')

        other = ControllerStore(self.root / 'other-format')
        self._auth_failure(other, 'other', state='reviewing')
        with self.assertRaises(AuthenticationRecoveryError):
            other.resume_after_authentication('other', authority=other.authority)

    def test_synthetic_login_secret_absent_from_durable_state_and_result(self):
        secret = 'SYNTHETIC-OAUTH-CODE-123456'
        statuses = iter((
            AuthenticationStatus('claude', 'unavailable', 'none', 'missing_or_expired', 'claude'),
            AuthenticationStatus('claude', 'verified', 'subscription', 'authenticated', 'claude'),
        ))

        def probe(provider, executable=None):
            return next(statuses)

        def launcher(argv, env, cwd, timeout, cancel_event):
            hidden_transcript = 'Paste code: ' + secret
            self.assertIn(secret, hidden_transcript)
            return 'succeeded'

        result = guided_login('claude', terminal_available=True, launcher=launcher,
                              status_probe=probe)
        serialized = json.dumps(result.to_dict(), sort_keys=True)
        self.assertEqual(result.status, 'succeeded')
        self.assertNotIn(secret, serialized)
        self.assertEqual(safe_login_reason(result), 'authenticated')

    def test_archived_live_completion_is_hash_bound_and_unapproved(self):
        evidence = ROOT / 'evidence' / 'phase3-auth-recovery'
        manifest = json.loads((evidence / 'manifest.json').read_text())
        actual = {str(path.relative_to(ROOT)): path for path in evidence.rglob('*')
                  if path.is_file() and path.name != 'manifest.json'}
        recorded = {item['path']: item for item in manifest['files']}
        self.assertEqual(set(actual), set(recorded))
        import hashlib
        for relative, path in actual.items():
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                             recorded[relative]['sha256'])
        summary = json.loads((evidence / 'live-complete' / 'summary.json').read_text())
        package = json.loads((evidence / 'live-complete' / 'approval' /
                              'approval-package.json').read_text())
        self.assertEqual(summary['state'], 'awaiting_pr_approval')
        self.assertFalse(summary['inference_calls']['repeated_for_evidence'])
        self.assertFalse(package['approval']['recorded'])
        self.assertEqual(summary['head_revision'], package['head_revision'])


if __name__ == '__main__':
    unittest.main()
