import json
from pathlib import Path
import sqlite3
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


class AuthTwiceImplementer:
    engine = 'codex'
    model = 'fixture-auth-twice'

    def __init__(self):
        self.calls = 0

    def run(self, workspace, output, boundary, prompt, policy):
        self.calls += 1
        if self.calls <= 2:
            return EngineOutcome('failed', .01, UsageRecord(source='unavailable'), {
                'error_class': 'authentication', 'authentication_failure': 'expired'})
        (Path(workspace) / 'calculator.py').write_text(SOURCE_FIXED)
        return EngineOutcome('succeeded', .01, UsageRecord(input_tokens=3, source='fake'),
                             {'simulated': True})


class AuthenticationRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='agentkit-auth-recovery-')
        self.root = Path(self.tmp.name).resolve()
        self.addCleanup(self.tmp.cleanup)

    def _store(self):
        return ControllerStore(self.root / 'controller')

    def _identity(self, task_id, revision='a' * 40):
        return {'repository': str((self.root / ('repository-' + task_id)).resolve()),
                'worktree': str((self.root / task_id).resolve()),
                'branch': 'agentkit/' + task_id, 'revision': revision, 'clean': True,
                'manifest_sha256': 'f' * 64}

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
            artifact = store.put_artifact(json.dumps({'fixture': task_id}, sort_keys=True))
            store.add_evidence(task_id, task_id + '-check', 'a' * 40, 'independent-check', 'passed',
                               artifact, {}, authority=auth)
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
                                                     candidate_identity=self._identity(task_id),
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
                                                   owner_nonce=claim['owner_nonce'],
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
                                          reason='authenticated', owner_nonce=claim['owner_nonce'],
                                          authority=store.authority)
        task = store.resume_after_authentication(
            'review-task', candidate_identity=self._identity('review-task'), authority=store.authority)
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
                                                   owner_nonce=claim['owner_nonce'],
                                                   authority=workflow.store.authority)
        result = workflow.resume()
        self.assertEqual(result['task']['state'], 'awaiting_pr_approval')
        self.assertEqual(result['task']['head_revision'], head)
        self.assertEqual(implementer.calls, 1)
        self.assertEqual(reviewer.calls, 2)
        self.assertTrue(all(any(item['evidence_id'] == evidence_id and not item['stale']
                                for item in result['snapshot']['evidence'])
                            for evidence_id in check_ids))

    def test_sequential_provider_checkpoints_preserve_history_and_resume_each_stage(self):
        implementer = AuthOnceImplementer()
        reviewer = AuthOnceReviewer()
        workflow = DeliveryWorkflow(self.root / 'sequential', implementer, reviewer,
                                    live_authorized=True)
        workflow.verifier = FixtureVerifier(workflow.broker)

        first = workflow.run()
        self.assertEqual(first['task']['state'], 'authentication_required')
        codex_claim = workflow.store.claim_authentication_login(
            'phase3-demo', 'codex', authority=workflow.store.authority)
        workflow.store.finish_authentication_login(
            codex_claim['session_id'], 'succeeded', auth_mode='subscription', reason='authenticated',
            owner_nonce=codex_claim['owner_nonce'], authority=workflow.store.authority)

        second = workflow.resume()
        self.assertEqual(second['task']['state'], 'authentication_required')
        history = workflow.store.authentication_checkpoint_history('phase3-demo')
        self.assertEqual([(item['provider'], item['status']) for item in history],
                         [('codex', 'resumed'), ('claude', 'waiting')])
        self.assertEqual(len([item for item in history if item['status'] != 'resumed']), 1)

        claude_claim = workflow.store.claim_authentication_login(
            'phase3-demo', 'claude', authority=workflow.store.authority)
        workflow.store.finish_authentication_login(
            claude_claim['session_id'], 'succeeded', auth_mode='subscription', reason='authenticated',
            owner_nonce=claude_claim['owner_nonce'], authority=workflow.store.authority)
        completed = workflow.resume()
        self.assertEqual(completed['task']['state'], 'awaiting_pr_approval')
        self.assertEqual(implementer.calls, 2)
        self.assertEqual(reviewer.calls, 2)
        self.assertEqual(completed['task']['repair_count'], 0)
        self.assertEqual([item['status'] for item in
                          workflow.store.authentication_checkpoint_history('phase3-demo')],
                         ['resumed', 'resumed'])

    def test_repeated_expiry_creates_new_bounded_checkpoint_for_same_provider(self):
        implementer = AuthTwiceImplementer()
        workflow = DeliveryWorkflow(self.root / 'repeated-expiry', implementer, FakeReviewer(),
                                    live_authorized=True)
        workflow.verifier = FixtureVerifier(workflow.broker)
        result = workflow.run()
        for expected_history in (1, 2):
            self.assertEqual(result['task']['state'], 'authentication_required')
            self.assertEqual(len(workflow.store.authentication_checkpoint_history('phase3-demo')),
                             expected_history)
            claim = workflow.store.claim_authentication_login(
                'phase3-demo', 'codex', authority=workflow.store.authority)
            workflow.store.finish_authentication_login(
                claim['session_id'], 'succeeded', auth_mode='subscription', reason='authenticated',
                owner_nonce=claim['owner_nonce'], authority=workflow.store.authority)
            result = workflow.resume()
        self.assertEqual(result['task']['state'], 'awaiting_pr_approval')
        history = workflow.store.authentication_checkpoint_history('phase3-demo')
        self.assertEqual([(item['provider'], item['status'], item['login_attempts']) for item in history],
                         [('codex', 'resumed', 1), ('codex', 'resumed', 1)])
        self.assertEqual(result['task']['repair_count'], 0)

    def test_abandoned_login_requires_explicit_process_reconciliation_before_reclaim(self):
        store = self._store()
        self._auth_failure(store, 'abandoned')
        original = store.claim_authentication_login('abandoned', 'codex', owner_pid=12345,
                                                     owner_nonce='first-owner',
                                                     authority=store.authority)
        restarted = ControllerStore(store.root)
        duplicate = restarted.claim_authentication_login(
            'abandoned', 'codex', owner_pid=23456, owner_nonce='second-owner',
            authority=restarted.authority)
        self.assertFalse(duplicate['claimed'])
        self.assertTrue(duplicate['reconciliation_required'])

        with self.assertRaises(AuthenticationRecoveryError):
            restarted.reconcile_authentication_login(
                original['session_id'], 'uncertain', 'SYNTHETIC-OAUTH-CODE-DO-NOT-PERSIST',
                authority=restarted.authority)

        restarted.reconcile_authentication_login(
            original['session_id'], 'uncertain', 'process_termination_unconfirmed',
            authority=restarted.authority)
        with self.assertRaises(ReconciliationRequired):
            restarted.claim_authentication_login('abandoned', 'codex',
                                                  authority=restarted.authority)
        restarted.reconcile_authentication_login(
            original['session_id'], 'confirmed_ended',
            'process_exit_confirmed',
            authority=restarted.authority)
        replacement = restarted.claim_authentication_login(
            'abandoned', 'codex', owner_pid=23456, owner_nonce='replacement-owner',
            authority=restarted.authority)
        self.assertTrue(replacement['claimed'])
        self.assertNotEqual(replacement['session_id'], original['session_id'])
        self.assertEqual(restarted.authentication_checkpoint('abandoned')['login_attempts'], 2)

    def test_still_running_login_owner_prevents_duplicate_and_launcher_interrupt_is_uncertain(self):
        store = self._store()
        self._auth_failure(store, 'running')
        owner = store.claim_authentication_login('running', 'codex', owner_nonce='current-owner',
                                                 authority=store.authority)
        self.assertNotIn('current-owner', json.dumps(store.snapshot('running'), sort_keys=True))
        self.assertEqual(store.reconcile_authentication_login(
            owner['session_id'], 'still_running', 'owner_reports_running',
            owner_nonce='current-owner', authority=store.authority), 'in_progress')
        duplicate = store.claim_authentication_login('running', 'codex', authority=store.authority)
        self.assertFalse(duplicate['claimed'])

        missing = AuthenticationStatus('codex', 'unavailable', 'none', 'missing_or_expired', 'codex')
        interrupted = guided_login(
            'codex', terminal_available=True, status_probe=lambda *args, **kwargs: missing,
            launcher=lambda *args: (_ for _ in ()).throw(KeyboardInterrupt()))
        self.assertEqual((interrupted.status, interrupted.termination), ('cancelled', 'uncertain'))
        launcher_failed = guided_login(
            'codex', terminal_available=True, status_probe=lambda *args, **kwargs: missing,
            launcher=lambda *args: (_ for _ in ()).throw(RuntimeError('synthetic launcher failure')))
        self.assertEqual((launcher_failed.status, launcher_failed.termination), ('failed', 'uncertain'))

    def test_dirty_actual_worktree_rejects_reviewer_resume_and_no_package_is_issued(self):
        workflow = DeliveryWorkflow(self.root / 'dirty-resume', FakeImplementer(), AuthOnceReviewer(),
                                    live_authorized=True)
        workflow.verifier = FixtureVerifier(workflow.broker)
        first = workflow.run()
        self.assertEqual(first['task']['state'], 'authentication_required')
        claim = workflow.store.claim_authentication_login(
            'phase3-demo', 'claude', authority=workflow.store.authority)
        workflow.store.finish_authentication_login(
            claim['session_id'], 'succeeded', auth_mode='subscription', reason='authenticated',
            owner_nonce=claim['owner_nonce'], authority=workflow.store.authority)
        task = workflow.store.task('phase3-demo')
        Path(task['worktree']).joinpath('calculator.py').write_text(SOURCE_FIXED + '\n# tampered\n')

        with self.assertRaises(StaleEvidence):
            workflow.resume()
        self.assertEqual(workflow.store.task('phase3-demo')['state'], 'authentication_required')
        self.assertFalse((workflow.approval_root / 'approval-package.json').exists())

    def test_changed_referenced_evidence_artifact_rejects_resume(self):
        workflow = DeliveryWorkflow(self.root / 'stale-evidence-artifact', FakeImplementer(),
                                    AuthOnceReviewer(), live_authorized=True)
        workflow.verifier = FixtureVerifier(workflow.broker)
        first = workflow.run()
        check = next(item for item in first['snapshot']['evidence']
                     if item['kind'] == 'independent-check' and item['status'] == 'passed')
        digest = check['artifact_sha256']
        artifact = workflow.store.artifact_root / digest[:2] / digest
        artifact.write_text('tampered fixture evidence')
        claim = workflow.store.claim_authentication_login(
            'phase3-demo', 'claude', authority=workflow.store.authority)
        workflow.store.finish_authentication_login(
            claim['session_id'], 'succeeded', auth_mode='subscription', reason='authenticated',
            owner_nonce=claim['owner_nonce'], authority=workflow.store.authority)
        with self.assertRaises(StaleEvidence):
            workflow.resume()
        self.assertEqual(workflow.store.task('phase3-demo')['state'], 'authentication_required')
        self.assertFalse((workflow.approval_root / 'approval-package.json').exists())

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
                                                  owner_nonce=claim['owner_nonce'],
                                                  authority=store.authority)
                self.assertEqual(store.task('task-' + str(index))['state'], 'authentication_required')
                self.assertEqual(store.authentication_checkpoint('task-' + str(index))['status'], 'waiting')
        store = ControllerStore(self.root / 'bounded')
        self._auth_failure(store, 'bounded')
        for _ in range(2):
            claim = store.claim_authentication_login('bounded', 'codex', authority=store.authority)
            store.finish_authentication_login(claim['session_id'], 'failed', reason='cli_failed',
                                              owner_nonce=claim['owner_nonce'],
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

    def test_v2_store_migrates_without_reintroducing_per_task_history_uniqueness(self):
        store = self._store()
        self._auth_failure(store, 'migrated')
        with sqlite3.connect(store.db_path) as db:
            db.execute('PRAGMA foreign_keys=OFF')
            db.execute('DROP INDEX one_active_authentication_checkpoint')
            db.execute('ALTER TABLE authentication_checkpoints RENAME TO authentication_checkpoints_v3')
            db.execute('''CREATE TABLE authentication_checkpoints(
                checkpoint_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL UNIQUE REFERENCES tasks(task_id),
                provider TEXT NOT NULL, account_context TEXT NOT NULL,
                interrupted_state TEXT NOT NULL, interrupted_role TEXT NOT NULL,
                candidate_revision TEXT NOT NULL, execution_id TEXT NOT NULL,
                evidence_refs_json TEXT NOT NULL, status TEXT NOT NULL,
                login_session_id TEXT REFERENCES authentication_sessions(session_id),
                login_attempts INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL)''')
            db.execute('''INSERT INTO authentication_checkpoints
                SELECT checkpoint_id,task_id,provider,account_context,interrupted_state,
                interrupted_role,candidate_revision,execution_id,evidence_refs_json,status,
                login_session_id,login_attempts,created_at,updated_at
                FROM authentication_checkpoints_v3''')
            db.execute('DROP TABLE authentication_checkpoints_v3')
            db.execute("UPDATE meta SET value='2' WHERE key='schema_version'")
        migrated = ControllerStore(store.root)
        self.assertEqual(migrated.authentication_checkpoint('migrated')['candidate_identity'], {})
        with migrated.transaction() as db:
            first = db.execute('SELECT * FROM authentication_checkpoints WHERE task_id=?',
                               ('migrated',)).fetchone()
            db.execute("UPDATE authentication_checkpoints SET status='resumed' WHERE checkpoint_id=?",
                       (first['checkpoint_id'],))
            db.execute('''INSERT INTO authentication_checkpoints(
                checkpoint_id,task_id,provider,account_context,interrupted_state,interrupted_role,
                candidate_revision,execution_id,evidence_refs_json,candidate_identity_json,status,
                login_session_id,login_attempts,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                ('new-history-row', first['task_id'], first['provider'], first['account_context'],
                 first['interrupted_state'], first['interrupted_role'], first['candidate_revision'],
                 first['execution_id'], first['evidence_refs_json'], '{}', 'waiting',
                 first['login_session_id'], first['login_attempts'], first['created_at'], first['updated_at']))
        self.assertEqual(len(migrated.authentication_checkpoint_history('migrated')), 2)

    def test_uncertain_execution_and_candidate_change_prevent_resume(self):
        store = self._store()
        self._auth_failure(store, 'uncertain')
        claim = store.claim_authentication_login('uncertain', 'codex', authority=store.authority)
        store.finish_authentication_login(claim['session_id'], 'succeeded', auth_mode='subscription',
                                          reason='authenticated', owner_nonce=claim['owner_nonce'],
                                          authority=store.authority)
        with store.transaction() as db:
            db.execute('''INSERT INTO executions(execution_id,task_id,role,engine,allocation_seconds,status)
                          VALUES(?,?,?,?,?,?)''', ('uncertain-row', 'uncertain', 'implementer', 'codex',
                                                  1, 'reconciliation_required'))
        with self.assertRaises(ReconciliationRequired):
            store.resume_after_authentication('uncertain', candidate_identity=self._identity('uncertain'),
                                              authority=store.authority)

        changed = ControllerStore(self.root / 'changed')
        self._auth_failure(changed, 'changed')
        claim = changed.claim_authentication_login('changed', 'codex', authority=changed.authority)
        changed.finish_authentication_login(claim['session_id'], 'succeeded', auth_mode='subscription',
                                            reason='authenticated', owner_nonce=claim['owner_nonce'],
                                            authority=changed.authority)
        changed.set_head('changed', 'c' * 40, authority=changed.authority)
        with self.assertRaises(StaleEvidence):
            changed.resume_after_authentication('changed', candidate_identity=self._identity('changed'),
                                                authority=changed.authority)

        identity_store = ControllerStore(self.root / 'identity')
        self._auth_failure(identity_store, 'identity')
        claim = identity_store.claim_authentication_login('identity', 'codex',
                                                           authority=identity_store.authority)
        identity_store.finish_authentication_login(
            claim['session_id'], 'succeeded', auth_mode='subscription', reason='authenticated',
            owner_nonce=claim['owner_nonce'], authority=identity_store.authority)
        expected = self._identity('identity')
        mismatches = {
            'repository': str((self.root / 'wrong-repository').resolve()),
            'worktree': str((self.root / 'wrong-worktree').resolve()),
            'branch': 'agentkit/wrong-branch',
            'revision': 'c' * 40,
            'clean': False,
            'manifest_sha256': 'e' * 64,
        }
        for field, value in mismatches.items():
            with self.subTest(candidate_identity_field=field):
                actual = {**expected, field: value}
                with self.assertRaises(StaleEvidence):
                    identity_store.resume_after_authentication(
                        'identity', candidate_identity=actual, authority=identity_store.authority)
                self.assertEqual(identity_store.task('identity')['state'], 'authentication_required')

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
            other.resume_after_authentication('other', candidate_identity=self._identity('other'),
                                              authority=other.authority)

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
