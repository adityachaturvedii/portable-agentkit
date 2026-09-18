import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest

from agentkit.controller import (BudgetExceeded, ControllerStore, DuplicateEvent,
                                 IllegalTransition, ReconciliationRequired, StaleApproval, StaleEvidence,
                                 UsageRecord)
from agentkit.delivery import (DeliveryWorkflow, EngineOutcome, FakeImplementer, FakeReviewer,
                               FixtureVerifier, SOURCE_FIXED, validate_review)
from agentkit.git_broker import GitBroker, GitBrokerError


class Phase3Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='agentkit-phase3-test-')
        self.root = Path(self.tmp.name).resolve()
        self.addCleanup(self.tmp.cleanup)

    def store(self, name='controller'):
        return ControllerStore(self.root / name)

    def create(self, store, task_id='task', **kw):
        return store.create_task(task_id, 'fixture objective', **kw)

    def delivery(self, name, implementer=None, reviewer=None):
        workflow = DeliveryWorkflow(self.root / name, implementer or FakeImplementer(),
                                    reviewer or FakeReviewer())
        workflow.verifier = FixtureVerifier(workflow.broker)
        return workflow

    def contract(self, store, task_id='task'):
        auth = store.authority
        store.set_contract(task_id, {'scope': ['source.py'], 'acceptance': [{'id': 'case'}]}, authority=auth)
        store.transition(task_id, 'received', 'contracted', task_id + '-contract', authority=auth)
        store.set_workspace(task_id, 'agentkit/' + task_id, str(self.root / task_id), 'a' * 40, authority=auth)

    def advance_to_approval(self, store, task_id='task'):
        auth = store.authority
        self.contract(store, task_id)
        steps = [('contracted', 'workspace_ready'), ('workspace_ready', 'implementing'),
                 ('implementing', 'implemented'), ('implemented', 'verifying'),
                 ('verifying', 'verified'), ('verified', 'reviewing'),
                 ('reviewing', 'review_complete'), ('review_complete', 'packaging'),
                 ('packaging', 'awaiting_pr_approval')]
        for index, (source, target) in enumerate(steps):
            kind = {'verified': 'independent-check', 'review_complete': 'independent-review',
                    'awaiting_pr_approval': 'approval-package'}.get(target)
            if kind:
                store.add_evidence(task_id, task_id + '-' + kind, 'a' * 40, kind, 'passed',
                                   str(index) * 64, {}, authority=auth)
            store.transition(task_id, source, target, task_id + '-step-' + str(index), authority=auth)

    def advance_to_verifying(self, store, task_id='task'):
        auth = store.authority
        self.contract(store, task_id)
        for index, (source, target) in enumerate((
                ('contracted', 'workspace_ready'), ('workspace_ready', 'implementing'),
                ('implementing', 'implemented'), ('implemented', 'verifying'))):
            store.transition(task_id, source, target, task_id + '-verify-step-' + str(index), authority=auth)

    def advance_to_implementing(self, store, task_id='task'):
        auth = store.authority
        self.contract(store, task_id)
        store.transition(task_id, 'contracted', 'workspace_ready', task_id + '-ready', authority=auth)
        store.transition(task_id, 'workspace_ready', 'implementing', task_id + '-implementing', authority=auth)

    def test_illegal_transition_and_duplicate_event_roll_back(self):
        store = self.store()
        self.create(store)
        with self.assertRaises(IllegalTransition):
            store.transition('task', 'received', 'implementing', 'bad', authority=store.authority)
        self.assertEqual(store.task('task')['state'], 'received')
        store.append_event('task', 'once', 'fixture', {}, authority=store.authority)
        with self.assertRaises(DuplicateEvent):
            store.append_event('task', 'once', 'fixture', {}, authority=store.authority)
        self.assertEqual(len([e for e in store.snapshot('task')['events'] if e['event_id'] == 'once']), 1)

    def test_event_history_is_database_append_only(self):
        store = self.store()
        self.create(store)
        db = sqlite3.connect(str(store.db_path))
        self.addCleanup(db.close)
        with self.assertRaises(sqlite3.IntegrityError):
            db.execute("UPDATE events SET event_type='forged'")
        with self.assertRaises(sqlite3.IntegrityError):
            db.execute('DELETE FROM events')

    def test_state_gates_require_current_revision_evidence(self):
        store = self.store()
        self.create(store)
        self.advance_to_verifying(store)
        with self.assertRaises(IllegalTransition):
            store.transition('task', 'verifying', 'verified', 'skip-check', authority=store.authority)
        store.add_evidence('task', 'passed-check', 'a' * 40, 'independent-check', 'passed',
                           'b' * 64, {}, authority=store.authority)
        store.set_head('task', 'c' * 40, authority=store.authority)
        with self.assertRaises(IllegalTransition):
            store.transition('task', 'verifying', 'verified', 'stale-check', authority=store.authority)

    def test_worker_data_cannot_change_state_budget_or_approval(self):
        store = self.store()
        self.create(store)
        fake_authority = {'approved': True, 'budget': 999}
        with self.assertRaises(PermissionError):
            store.transition('task', 'received', 'contracted', 'forged', authority=fake_authority)
        with self.assertRaises(PermissionError):
            store.reserve_execution('task', 'implementer', 'codex', None, 1, authority=fake_authority)
        with self.assertRaises(PermissionError):
            store.record_user_approval('task', 'repo', 'branch', 'a' * 40, 'create_pr',
                                       (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
                                       'worker-output', authority=fake_authority)

    def test_dependencies_must_be_review_ready(self):
        store = self.store()
        self.create(store, 'parent')
        self.create(store, 'child', dependencies=('parent',))
        self.contract(store, 'child')
        with self.assertRaises(IllegalTransition):
            store.transition('child', 'contracted', 'workspace_ready', 'child-workspace', authority=store.authority)
        self.advance_to_approval(store, 'parent')
        store.transition('child', 'contracted', 'workspace_ready', 'child-workspace-2', authority=store.authority)

    def test_atomic_budget_reservation_enforces_concurrency(self):
        primary = self.store()
        self.create(primary, max_calls=3, max_concurrency=1, verification_reserve=1)
        self.advance_to_verifying(primary)
        barrier = threading.Barrier(2)
        results = []
        lock = threading.Lock()

        def reserve():
            local = ControllerStore(primary.root)
            barrier.wait()
            try:
                value = local.reserve_execution('task', 'verification', 'local', None, 1,
                                                authority=local.authority)
            except BudgetExceeded:
                value = 'blocked'
            with lock:
                results.append(value)

        threads = [threading.Thread(target=reserve) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sum(value == 'blocked' for value in results), 1)
        budget = primary.snapshot('task')['budget']
        self.assertEqual(budget['active_calls'], 1)
        self.assertEqual(budget['reserved_calls'], 1)

    def test_budget_protects_verification_and_preserves_unknown_usage(self):
        store = self.store()
        self.create(store, max_calls=3, verification_reserve=2)
        self.advance_to_implementing(store)
        execution = store.reserve_execution('task', 'implementer', 'codex', None, 1, authority=store.authority)
        store.start_execution(execution, authority=store.authority)
        store.finish_execution(execution, 'succeeded', .2, UsageRecord(source='provider'),
                               authority=store.authority)
        with self.assertRaises(BudgetExceeded):
            store.reserve_execution('task', 'implementer', 'codex', None, 1, authority=store.authority)
        record = store.snapshot('task')['executions'][0]
        usage = json.loads(record['usage_json'])
        self.assertIsNone(usage['input_tokens'])
        self.assertIsNone(usage['cached_input_tokens'])
        self.assertIsNone(usage['billed_cost_usd'])

    def test_budget_atomically_holds_elapsed_allocation_and_verification_reserve(self):
        store = self.store()
        self.create(store, max_calls=5, max_concurrency=2, max_elapsed_seconds=10,
                    max_timeout_seconds=10, verification_reserve=1)
        self.advance_to_implementing(store)
        first = store.reserve_execution('task', 'implementer', 'codex', None, 6,
                                        authority=store.authority)
        with self.assertRaises(BudgetExceeded):
            store.reserve_execution('task', 'implementer', 'codex', None, 5,
                                    authority=store.authority)
        budget = store.snapshot('task')['budget']
        self.assertEqual(budget['reserved_elapsed_seconds'], 6)
        store.finish_execution(first, 'cancelled', .1, authority=store.authority)
        self.assertEqual(store.snapshot('task')['budget']['reserved_elapsed_seconds'], 0)

    def test_budget_and_timeout_numbers_reject_invalid_types_and_nonfinite_values(self):
        cases = {
            'max_repairs': (-1, 3, True, 1.5, math.nan, math.inf),
            'max_calls': (-1, 0, True, 1.5, math.nan, math.inf),
            'max_elapsed_seconds': (-1, 0, True, math.nan, math.inf, -math.inf),
            'max_concurrency': (-1, 0, True, 1.5, math.nan, math.inf),
            'max_timeout_seconds': (-1, 0, True, math.nan, math.inf, -math.inf),
            'verification_reserve': (-1, 0, True, 1.5, math.nan, math.inf),
        }
        index = 0
        for field, values in cases.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    store = self.store('invalid-' + str(index))
                    index += 1
                    with self.assertRaises(ValueError):
                        self.create(store, **{field: value})

        store = self.store('invalid-execution-values')
        self.create(store, max_calls=4, max_timeout_seconds=10, verification_reserve=1)
        self.advance_to_implementing(store)
        for value in (-1, 0, True, math.nan, math.inf, -math.inf):
            with self.subTest(timeout=value):
                with self.assertRaises(ValueError):
                    store.reserve_execution('task', 'implementer', 'codex', None, value,
                                            authority=store.authority)
        execution = store.reserve_execution('task', 'implementer', 'codex', None, 1,
                                            authority=store.authority)
        for value in (-1, True, math.nan, math.inf, -math.inf):
            with self.subTest(elapsed=value):
                with self.assertRaises(ValueError):
                    store.finish_execution(execution, 'failed', value, authority=store.authority)
        store.finish_execution(execution, 'cancelled', 0, authority=store.authority)
        for value in (True, math.nan, math.inf, -math.inf, -1):
            with self.subTest(cost=value):
                with self.assertRaises(ValueError):
                    UsageRecord(estimated_cost_usd=value)

    def test_execution_roles_and_task_states_gate_reservation_and_start(self):
        store = self.store()
        self.create(store, 'implementing')
        self.advance_to_implementing(store, 'implementing')
        with self.assertRaises(ValueError):
            store.reserve_execution('implementing', 'reviewer', 'claude', None, 1,
                                    authority=store.authority)
        pending = store.reserve_execution('implementing', 'implementer', 'codex', None, 1,
                                          authority=store.authority)
        store.transition('implementing', 'implementing', 'blocked', 'blocked-before-start',
                         authority=store.authority)
        with self.assertRaises(ValueError):
            store.start_execution(pending, authority=store.authority)

        self.create(store, 'cancelled')
        store.transition('cancelled', 'received', 'cancelled', 'cancel-task', authority=store.authority)
        with self.assertRaises(ValueError):
            store.reserve_execution('cancelled', 'implementer', 'codex', None, 1,
                                    authority=store.authority)

        self.create(store, 'blocked')
        store.transition('blocked', 'received', 'blocked', 'block-task', authority=store.authority)
        with self.assertRaises(ValueError):
            store.reserve_execution('blocked', 'implementer', 'codex', None, 1,
                                    authority=store.authority)

        self.create(store, 'completed')
        self.advance_to_approval(store, 'completed')
        with self.assertRaises(ValueError):
            store.reserve_execution('completed', 'reviewer', 'claude', None, 1,
                                    authority=store.authority)

    def test_cancellation_and_restart_reconciliation(self):
        store = self.store()
        self.create(store, max_calls=4, verification_reserve=1)
        self.advance_to_verifying(store)
        first = store.reserve_execution('task', 'verification', 'local', None, 2, authority=store.authority)
        store.start_execution(first, pid=123, process_token='owned', authority=store.authority)
        store.request_cancellation(first, authority=store.authority)
        store.finish_execution(first, 'cancelled', .1, authority=store.authority)
        second = store.reserve_execution('task', 'verification', 'local', None, 2, authority=store.authority)
        restarted = ControllerStore(store.root)
        self.assertEqual(restarted.reconcile_active(authority=restarted.authority), [second])
        snapshot = restarted.snapshot('task')
        self.assertEqual(snapshot['task']['state'], 'blocked')
        active = [x for x in snapshot['executions'] if x['execution_id'] == second][0]
        self.assertEqual(active['status'], 'reconciliation_required')
        self.assertIn('cannot be established', active['reconciliation_note'])
        with self.assertRaises(ReconciliationRequired):
            restarted.reserve_execution('task', 'verification', 'local', None, 1,
                                         authority=restarted.authority)
        self.assertEqual(restarted.resolve_execution_uncertainty(
            second, 'not_started', 'confirmed no child was launched', authority=restarted.authority),
            'reconciled_not_started')
        with self.assertRaises(ValueError):
            restarted.reserve_execution('task', 'verification', 'local', None, 1,
                                         authority=restarted.authority)

    def test_revision_change_stales_evidence_and_approval(self):
        store = self.store()
        self.create(store)
        self.advance_to_approval(store)
        store.add_evidence('task', 'check', 'a' * 40, 'test', 'passed', 'b' * 64, {}, authority=store.authority)
        approval = store.record_user_approval(
            'task', 'repo', 'agentkit/task', 'a' * 40, 'create_pr',
            (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(), 'explicit-user',
            authority=store.authority)
        store.set_head('task', 'c' * 40, authority=store.authority)
        snapshot = store.snapshot('task')
        self.assertEqual(snapshot['evidence'][0]['stale'], 1)
        with self.assertRaises(StaleApproval):
            store.validate_approval(approval, 'repo', 'agentkit/task', 'a' * 40, 'create_pr')
        with self.assertRaises(StaleEvidence):
            store.add_evidence('task', 'late', 'a' * 40, 'test', 'passed', 'd' * 64, {}, authority=store.authority)

    def test_repeated_failure_and_repair_exhaustion_checkpoint(self):
        store = self.store()
        self.create(store, max_repairs=1)
        self.advance_to_verifying(store)
        first = store.record_failure('task', 'same', 'concrete criterion failed', authority=store.authority)
        second = store.record_failure('task', 'same', 'concrete criterion failed', authority=store.authority)
        self.assertEqual(first, 'repair_allowed')
        self.assertEqual(second, 'repeated_failure')
        self.assertEqual(store.task('task')['state'], 'blocked')
        events = store.snapshot('task')['events']
        self.assertTrue(any(event['event_type'] == 'repeated_failure_checkpoint' for event in events))

        exhausted = self.store('exhausted')
        self.create(exhausted, max_repairs=1)
        self.advance_to_verifying(exhausted)
        self.assertEqual(exhausted.record_failure('task', 'first', 'criterion one',
                                                  authority=exhausted.authority), 'repair_allowed')
        self.assertEqual(exhausted.record_failure('task', 'second', 'criterion two',
                                                  authority=exhausted.authority), 'repair_exhausted')
        self.assertEqual(exhausted.task('task')['state'], 'blocked')

    def test_failure_event_ids_are_namespaced_by_task(self):
        store = self.store()
        for task_id in ('first', 'second'):
            self.create(store, task_id)
            self.advance_to_verifying(store, task_id)
            self.assertEqual(store.record_failure(task_id, 'same-signature', 'same concrete defect',
                                                  authority=store.authority), 'repair_allowed')
            self.assertEqual(store.record_failure(task_id, 'same-signature', 'same concrete defect',
                                                  authority=store.authority), 'repeated_failure')
        for task_id in ('third', 'fourth'):
            self.create(store, task_id, max_repairs=0)
            self.advance_to_verifying(store, task_id)
            self.assertEqual(store.record_failure(task_id, 'exhausted-signature', 'same concrete defect',
                                                  authority=store.authority), 'repair_exhausted')
        first_ids = {event['event_id'] for event in store.snapshot('first')['events']}
        second_ids = {event['event_id'] for event in store.snapshot('second')['events']}
        self.assertFalse(first_ids & second_ids)
        third_ids = {event['event_id'] for event in store.snapshot('third')['events']}
        fourth_ids = {event['event_id'] for event in store.snapshot('fourth')['events']}
        self.assertFalse(third_ids & fourth_ids)

    def test_git_broker_isolates_worker_and_rejects_protected_changes(self):
        broker = GitBroker(self.root / 'managed')
        repository, base = broker.create_repository('fixture', {'source.py': 'bad\n', 'test_source.py': 'fixed\n'})
        branch, worktree, _ = broker.create_task_worktree(repository, 'task', base)
        worker = broker.export_snapshot(repository, base, broker.worker_copies / 'task')
        self.assertFalse((worker / '.git').exists())
        (worker / 'source.py').write_text('fixed\n')
        (worker / 'test_source.py').write_text('tampered\n')
        with self.assertRaises(GitBrokerError):
            broker.apply_worker_changes(repository, worktree, worker, ('source.py',), 'candidate')
        self.assertEqual((worktree / 'test_source.py').read_text(), 'fixed\n')
        self.assertEqual(broker.revision(repository, branch), base)

    def test_complete_simulated_workflow_and_head_bound_package(self):
        root = self.root / 'demo'
        workflow = self.delivery('demo')
        result = workflow.run()
        task = result['task']
        package = result['approval_package']
        self.assertEqual(task['state'], 'awaiting_pr_approval')
        self.assertEqual(package['head_revision'], task['head_revision'])
        self.assertEqual(package['base_revision'], task['base_revision'])
        self.assertIn('return left + right', package['diff'])
        self.assertFalse(package['approval']['recorded'])
        self.assertEqual(result['snapshot']['approvals'], [])
        self.assertEqual(result['snapshot']['budget']['completed_calls'], 3)
        self.assertTrue((root / 'approval/approval-package.md').is_file())

    def test_verification_failure_gets_one_bounded_repair(self):
        root = self.root / 'repair-demo'
        workflow = self.delivery('repair-demo', FakeImplementer(failures=1))
        result = workflow.run()
        self.assertEqual(result['task']['state'], 'awaiting_pr_approval')
        self.assertEqual(result['task']['repair_count'], 1)
        evidence = result['snapshot']['evidence']
        failed = [record for record in evidence if record['status'] == 'failed']
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]['stale'], 1)
        self.assertEqual(result['snapshot']['budget']['completed_calls'], 5)

    def test_failed_test_output_is_required_by_feedback_dependent_repair(self):
        class FeedbackImplementer(FakeImplementer):
            feedback = None

            def run(self, workspace, output, boundary, prompt, policy):
                self.calls += 1
                if self.calls == 1:
                    (Path(workspace) / 'calculator.py').write_text(
                        SOURCE_FIXED.replace('left + right', 'left * right'))
                else:
                    marker = 'Controller-generated repair feedback (JSON): '
                    self.feedback = json.loads(prompt.split(marker, 1)[1])
                    if (self.feedback['kind'] == 'failed_test' and
                            'FAILED' in self.feedback['failed_test']['output']):
                        (Path(workspace) / 'calculator.py').write_text(SOURCE_FIXED)
                return EngineOutcome('succeeded', 0.001, UsageRecord(source='fake'),
                                     {'simulated': True})

        implementer = FeedbackImplementer()
        result = self.delivery('test-feedback', implementer).run()
        self.assertEqual(result['task']['state'], 'awaiting_pr_approval')
        self.assertEqual(implementer.feedback['kind'], 'failed_test')
        self.assertEqual(implementer.feedback['acceptance'][0]['id'], 'total')
        self.assertIn('FAILED', implementer.feedback['failed_test']['output'])

    def test_structured_review_findings_are_required_by_feedback_dependent_repair(self):
        class ReviewAwareImplementer(FakeImplementer):
            feedback = None

            def run(self, workspace, output, boundary, prompt, policy):
                self.calls += 1
                if self.calls == 1:
                    source = ('def total(left, right):\n'
                              '    if (left, right) == (17, 25): return 42\n'
                              '    if (left, right) == (-4, 9): return 5\n'
                              '    return 0\n')
                    (Path(workspace) / 'calculator.py').write_text(source)
                else:
                    marker = 'Controller-generated repair feedback (JSON): '
                    self.feedback = json.loads(prompt.split(marker, 1)[1])
                    if self.feedback['findings'][0]['criterion'] == 'total must add arbitrary inputs':
                        (Path(workspace) / 'calculator.py').write_text(SOURCE_FIXED)
                return EngineOutcome('succeeded', 0.001, UsageRecord(source='fake'), {'simulated': True})

        finding = {'id': 'F-general', 'severity': 'material', 'path': 'calculator.py',
                   'criterion': 'total must add arbitrary inputs',
                   'description': 'implementation is hard-coded to the two acceptance examples'}
        implementer = ReviewAwareImplementer()
        reviewer = FakeReviewer(findings=((finding,), ()))
        result = self.delivery('review-feedback', implementer, reviewer).run()
        self.assertEqual(result['task']['state'], 'awaiting_pr_approval')
        self.assertEqual(implementer.feedback['kind'], 'review_findings')
        self.assertEqual(implementer.feedback['findings'], [finding])

    def test_review_snapshot_mutation_blocks_delivery(self):
        class MutatingReviewer(FakeReviewer):
            def run(self, snapshot, revision, output, prompt, policy):
                (Path(snapshot) / 'calculator.py').write_text('tampered\n')
                return super().run(snapshot, revision, output, prompt, policy)

        result = self.delivery('review-mutation', reviewer=MutatingReviewer()).run()
        self.assertEqual(result['task']['state'], 'blocked')
        self.assertIsNone(result['approval_package'])

    def test_review_findings_require_concrete_material_criteria(self):
        valid = {'verdict': 'findings', 'findings': [{
            'id': 'F1', 'severity': 'material', 'path': 'calculator.py',
            'criterion': 'total must add both inputs', 'description': 'implementation subtracts'
        }]}
        self.assertEqual(len(validate_review(valid)), 1)
        for invalid in (
            {'verdict': 'no_findings', 'findings': valid['findings']},
            {'verdict': 'findings', 'findings': []},
            {'verdict': 'findings', 'findings': [{'id': 'F1'}]},
        ):
            with self.assertRaises(ValueError):
                validate_review(invalid)

    def test_execution_boundary_names_controller_git_and_worktree(self):
        class CapturingImplementer(FakeImplementer):
            boundary = None

            def run(self, workspace, output, boundary, prompt, policy):
                self.boundary = boundary
                return super().run(workspace, output, boundary, prompt, policy)

        implementer = CapturingImplementer()
        workflow = self.delivery('capture', implementer)
        workflow.run()
        denied = set(implementer.boundary.denied_read_paths)
        self.assertIn(str(workflow.controller_root), denied)
        self.assertIn(str(workflow.approval_root), denied)
        self.assertTrue(any(path.endswith('/.git') for path in denied))
        self.assertTrue(any('/worktrees/' in path for path in denied))


if __name__ == '__main__':
    unittest.main()
