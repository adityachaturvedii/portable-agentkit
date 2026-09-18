import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest

from agentkit.controller import (BudgetExceeded, ControllerStore, DuplicateEvent,
                                 IllegalTransition, StaleApproval, StaleEvidence,
                                 UsageRecord)
from agentkit.delivery import DeliveryWorkflow, FakeImplementer, FakeReviewer, validate_review
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
        self.create(store, max_calls=3, max_concurrency=2, max_elapsed_seconds=10,
                    max_timeout_seconds=10, verification_reserve=2)
        first = store.reserve_execution('task', 'implementer', 'codex', None, 6,
                                        authority=store.authority)
        with self.assertRaises(BudgetExceeded):
            store.reserve_execution('task', 'verification', 'local', None, 5,
                                    authority=store.authority)
        with self.assertRaises(BudgetExceeded):
            store.reserve_execution('task', 'reviewer', 'claude', None, 1,
                                    authority=store.authority)
        budget = store.snapshot('task')['budget']
        self.assertEqual(budget['reserved_elapsed_seconds'], 6)
        store.finish_execution(first, 'cancelled', .1, authority=store.authority)
        self.assertEqual(store.snapshot('task')['budget']['reserved_elapsed_seconds'], 0)

    def test_cancellation_and_restart_reconciliation(self):
        store = self.store()
        self.create(store, max_calls=4, verification_reserve=1)
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
        workflow = DeliveryWorkflow(root, FakeImplementer(), FakeReviewer())
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
        workflow = DeliveryWorkflow(root, FakeImplementer(failures=1), FakeReviewer())
        result = workflow.run()
        self.assertEqual(result['task']['state'], 'awaiting_pr_approval')
        self.assertEqual(result['task']['repair_count'], 1)
        evidence = result['snapshot']['evidence']
        failed = [record for record in evidence if record['status'] == 'failed']
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]['stale'], 1)
        self.assertEqual(result['snapshot']['budget']['completed_calls'], 5)

    def test_review_snapshot_mutation_blocks_delivery(self):
        class MutatingReviewer(FakeReviewer):
            def run(self, snapshot, revision, output, prompt, policy):
                (Path(snapshot) / 'calculator.py').write_text('tampered\n')
                return super().run(snapshot, revision, output, prompt, policy)

        result = DeliveryWorkflow(self.root / 'review-mutation', FakeImplementer(), MutatingReviewer()).run()
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
        workflow = DeliveryWorkflow(self.root / 'capture', implementer, FakeReviewer())
        workflow.run()
        denied = set(implementer.boundary.denied_read_paths)
        self.assertIn(str(workflow.controller_root), denied)
        self.assertIn(str(workflow.approval_root), denied)
        self.assertTrue(any(path.endswith('/.git') for path in denied))
        self.assertTrue(any('/worktrees/' in path for path in denied))


if __name__ == '__main__':
    unittest.main()
