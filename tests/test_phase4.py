from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path
import tempfile
import threading
import time
import unittest

from agentkit.controller import (AuthenticationRecoveryError, BudgetExceeded, ControllerError,
                                 ReconciliationRequired, StaleEvidence, UsageRecord)
from agentkit.delivery import EngineOutcome
from agentkit.orchestration import (DeterministicReviewer, DeterministicSpecialist,
                                    Phase4Workflow, build_contract, build_plan)
from agentkit.phase4_contracts import (ExecutionPlan, GraphEdge, GraphNode, ModelProfile,
                                       ModelRegistry, ROLE_CONTRACTS, TaskContract)
from agentkit.phase4_fixtures import CALCULATOR, TEXT_METRICS


ROOT = Path(__file__).resolve().parents[1]


class FeedbackSpecialist:
    engine = 'codex'
    model = None

    def __init__(self):
        self.prompts = []

    def run_assignment(self, workspace, assignment, output, boundary, prompt, policy):
        self.prompts.append(prompt)
        if assignment['node_id'] == 'repair':
            if 'review_findings' not in prompt or 'remove-todo' not in prompt:
                return EngineOutcome('failed', .001, UsageRecord(source='fake'),
                                     {'error_class': 'missing_repair_feedback'})
            content = CALCULATOR.final_files['calculator.py']
        else:
            content = CALCULATOR.final_files['calculator.py'].replace(
                'return left + right', 'return left + right  # TODO remove provisional marker')
        (Path(workspace) / 'calculator.py').write_text(content)
        return EngineOutcome('succeeded', .001, UsageRecord(source='fake'), {'simulated': True})


class BrokenThenFixedSpecialist:
    engine = 'codex'
    model = None

    def __init__(self, always_broken=False):
        self.calls = 0
        self.always_broken = always_broken

    def run_assignment(self, workspace, assignment, output, boundary, prompt, policy):
        self.calls += 1
        broken = self.always_broken or assignment['node_id'] != 'repair'
        content = CALCULATOR.final_files['calculator.py']
        if broken:
            content = content.replace('return left + right', 'return left * right')
        (Path(workspace) / 'calculator.py').write_text(content)
        return EngineOutcome('succeeded', .001, UsageRecord(source='fake'), {'simulated': True})


class AuthOnceSpecialist:
    engine = 'codex'
    model = None

    def __init__(self):
        self.calls = 0

    def run_assignment(self, workspace, assignment, output, boundary, prompt, policy):
        self.calls += 1
        if self.calls == 1:
            return EngineOutcome('failed', .001, UsageRecord(source='unavailable'),
                                 {'error_class': 'authentication',
                                  'authentication_failure': 'expired'})
        (Path(workspace) / 'calculator.py').write_text(CALCULATOR.final_files['calculator.py'])
        return EngineOutcome('succeeded', .001, UsageRecord(source='fake'), {'simulated': True})


class AuthOnceReviewer:
    engine = 'claude'
    model = None

    def __init__(self):
        self.calls = 0

    def run(self, snapshot, revision, output, prompt, policy):
        self.calls += 1
        if self.calls == 1:
            return EngineOutcome('failed', .001, UsageRecord(source='unavailable'),
                                 {'error_class': 'authentication',
                                  'authentication_failure': 'expired',
                                  'candidate_revision': revision})
        return EngineOutcome('succeeded', .001, UsageRecord(source='fake'),
                             {'candidate_revision': revision}, ())


class CancellableSpecialist:
    engine = 'codex'
    model = None

    def __init__(self):
        self.started = threading.Event()

    def run(self, workspace, output, boundary, prompt, policy, cancel_event=None):
        self.started.set()
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and not cancel_event.is_set():
            time.sleep(.02)
        status = 'cancelled' if cancel_event.is_set() else 'failed'
        return EngineOutcome(status, .1, UsageRecord(source='fake'), {'simulated': True})


class Phase4Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='agentkit-phase4-test-')
        self.root = Path(self.tmp.name).resolve()
        self.addCleanup(self.tmp.cleanup)

    def workflow(self, name, fixture='calculator', **kwargs):
        target = self.root / name
        return Phase4Workflow.submit(target, name, 'Repair the selected disposable fixture.',
                                     fixture, **kwargs)

    def test_simple_task_uses_minimum_workflow_and_binds_package(self):
        workflow = self.workflow('simple', max_calls=5)
        self.assertIsNone(workflow.status('simple')['budget']['token_usage']['input_tokens'])
        plan = workflow.state.plan('simple')['plan']
        self.assertEqual(plan['mode'], 'single')
        self.assertEqual(plan['management_calls'], 0)
        self.assertFalse(any(node['role'] == 'manager' for node in plan['nodes']))
        result = workflow.start('simple')
        self.assertEqual(result['task']['state'], 'awaiting_pr_approval')
        self.assertEqual(len(result['status']['executions']), 3)
        self.assertEqual(result['status']['budget']['verification_reserve'], 1)
        self.assertEqual(result['status']['budget']['review_reserve'], 1)
        self.assertIsNone(result['status']['budget']['token_usage']['input_tokens'])
        package = result['approval_package']
        self.assertEqual(package['head_revision'], result['task']['head_revision'])
        self.assertFalse(package['approval']['recorded'])
        self.assertEqual(package['approval']['bound_head'], package['head_revision'])

    def test_decomposed_subtasks_are_isolated_then_controller_integrated(self):
        workflow = self.workflow('decomposed', fixture='text-metrics')
        result = workflow.start('decomposed')
        self.assertEqual(result['task']['state'], 'awaiting_pr_approval')
        nodes = {node['node_id']: node for node in workflow.state.nodes('decomposed')}
        specialists = [node for node in nodes.values() if node['kind'] == 'implementation']
        self.assertEqual(len(specialists), 2)
        self.assertEqual(len({node['result']['worktree'] for node in specialists}), 2)
        self.assertTrue(all(node['result']['worktree'] != result['task']['worktree']
                            for node in specialists))
        integrated = nodes['integrate']['result']
        self.assertEqual(set(integrated['changed_paths']), {'lines.py', 'words.py'})
        self.assertIn('return len(text.split())', result['approval_package']['diff'])
        self.assertIn('return len(text.splitlines())', result['approval_package']['diff'])
        self.assertEqual(result['status']['management_model_calls'], 0)

    def test_graph_contract_rejects_cycles_dependency_mismatch_and_authority_expansion(self):
        with self.assertRaises(ValueError):
            GraphNode('bad', 'implementer', 'implementation', 'bad',
                      allowed_paths=('../controller/state',), provider='codex')
        with self.assertRaises(ValueError):
            GraphNode('bad', 'implementer', 'implementation', 'bad',
                      allowed_paths=('/tmp/outside',), provider='codex')
        contract = build_contract('graph', 'repair fixture', CALCULATOR)
        plan = build_plan(contract, CALCULATOR, ModelRegistry.account_defaults(), ROOT)
        implementation = next(node for node in plan.nodes if node.kind == 'implementation')
        verify = next(node for node in plan.nodes if node.kind == 'verification')
        nodes = tuple(replace(node, dependencies=(verify.node_id,))
                      if node.node_id == implementation.node_id else node for node in plan.nodes)
        edges = tuple(edge for edge in plan.edges
                      if not (edge.target == implementation.node_id and edge.edge_type == 'dependency')) + (
                          GraphEdge(verify.node_id, implementation.node_id),)
        with self.assertRaisesRegex(ValueError, 'acyclic'):
            ExecutionPlan(plan.task_id, plan.mode, nodes, edges, plan.routes,
                          plan.selected_skills)
        with self.assertRaisesRegex(ValueError, 'must match'):
            ExecutionPlan(plan.task_id, plan.mode, plan.nodes, plan.edges[:-1], plan.routes,
                          plan.selected_skills)

    def test_persisted_dependencies_gate_node_launch(self):
        workflow = self.workflow('dependencies')
        with self.assertRaisesRegex(ControllerError, 'dependencies'):
            workflow.state.transition_node('dependencies', 'verify', 'running',
                                           authority=workflow.store.authority)

    def test_adversarial_worker_cannot_expand_scope(self):
        workflow = self.workflow('adversarial')
        workflow.specialist_factory = lambda provider, fixture: DeterministicSpecialist(
            provider, fixture, unauthorized=True)
        result = workflow.start('adversarial')
        self.assertEqual(result['task']['state'], 'blocked')
        implementation = next(node for node in workflow.state.nodes('adversarial')
                              if node['kind'] == 'implementation')
        self.assertIn('authority_violation', implementation['result'])
        candidate = Path(result['task']['worktree'])
        self.assertEqual((candidate / 'README.md').read_text(), CALCULATOR.files['README.md'])
        self.assertIsNone(result['approval_package'])

    def test_routing_uses_configured_account_defaults_and_preserves_unknowns(self):
        registry = ModelRegistry.account_defaults(implementer='claude', reviewer='codex')
        workflow = self.workflow('routing', fixture='inventory', registry=registry)
        routes = workflow.state.plan('routing')['plan']['routes']
        implementers = [route for route in routes if route['role'] == 'implementer']
        reviewer = next(route for route in routes if route['role'] == 'reviewer')
        self.assertTrue(all(route['provider'] == 'claude' for route in implementers))
        self.assertEqual(reviewer['provider'], 'codex')
        self.assertTrue(all(route['model'] is None and route['relative_cost'] == 'unknown'
                            for route in routes))
        self.assertIn('preflight', reviewer['reason'])

        unavailable = ModelRegistry((ModelProfile(
            'disabled', 'codex', None, None, ('implementer',), ('owned-code',),
            'unknown', 'fixture', enabled=False),), {'implementer': 'disabled'})
        with self.assertRaisesRegex(ValueError, 'no configured model'):
            unavailable.route('node', 'implementer', 'owned-code')
        cost_aware = ModelRegistry((
            ModelProfile('default', 'codex', None, None, ('implementer',), ('owned-code',),
                         'unknown', 'no comparative result'),
            ModelProfile('measured-lower', 'claude', None, None, ('implementer',), ('owned-code',),
                         'lower', 'fixture outcome met the same acceptance with lower measured use'),
        ), {'implementer': 'default'})
        decision = cost_aware.route('node', 'implementer', 'owned-code')
        self.assertEqual(decision.profile_id, 'measured-lower')
        self.assertIn('lower relative cost', decision.reason)

    def test_budget_contract_rejects_invalid_types_ranges_and_nonfinite_values(self):
        valid = build_contract('valid', 'repair fixture', CALCULATOR)
        cases = {
            'max_calls': (-1, 0, 2, True, 1.5),
            'max_elapsed_seconds': (-1, 0, True, math.nan, math.inf),
            'max_concurrency': (-1, 0, 3, True, 1.5),
            'max_timeout_seconds': (-1, 0, True, math.nan, math.inf),
            'verification_reserve': (-1, 0, True, 1.5),
            'review_reserve': (-1, 0, True, 1.5),
            'max_subtasks': (-1, 0, 3, True, 1.5),
            'max_repairs': (-1, 3, True, 1.5),
            'max_output_bytes_per_call': (-1, 0, 1023, 4194305, True, 1.5),
        }
        for field, values in cases.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ValueError):
                        replace(valid, **{field: value})
        for field in ('max_calls', 'max_elapsed_seconds', 'max_concurrency'):
            with self.subTest(builder_field=field):
                with self.assertRaises(ValueError):
                    build_contract('invalid-builder-' + field, 'repair fixture', CALCULATOR,
                                   **{field: 0})

    def test_quality_reserves_survive_implementation_pressure(self):
        workflow = self.workflow('reserves', max_calls=3)
        result = workflow.start('reserves')
        self.assertEqual(result['task']['state'], 'awaiting_pr_approval')
        self.assertEqual(result['status']['budget']['completed_calls'], 3)
        self.assertEqual(result['status']['budget']['remaining_calls'], 0)

        pressured = self.workflow('pressure', max_calls=3)
        store = pressured.store
        task_id = 'pressure'
        pressured.state.activate_plan(task_id, authority=store.authority)
        fixture = CALCULATOR
        repository, base = pressured.broker.create_repository(task_id, fixture.files)
        branch, worktree, base = pressured.broker.create_task_worktree(repository, task_id, base)
        store.set_workspace(task_id, branch, str(worktree), base, authority=store.authority)
        pressured._transition(task_id, 'contracted', 'workspace_ready', 'workspace', 'implement')
        pressured._transition(task_id, 'workspace_ready', 'implementing', 'implementing', 'implement')
        first = store.reserve_execution(task_id, 'implementer', 'codex', None, 1,
                                        authority=store.authority)
        store.start_execution(first, authority=store.authority)
        store.finish_execution(first, 'succeeded', .01, UsageRecord(source='fake'),
                               authority=store.authority)
        with self.assertRaises(BudgetExceeded):
            store.reserve_execution(task_id, 'implementer', 'codex', None, 1,
                                    authority=store.authority)

    def test_review_feedback_is_structured_and_repair_is_bounded(self):
        specialist = FeedbackSpecialist()
        finding = ({'id': 'remove-todo', 'severity': 'material', 'path': 'calculator.py',
                    'criterion': 'production-ready source',
                    'description': 'Remove the provisional TODO marker.'},)
        reviewer = DeterministicReviewer('claude', findings=(finding, ()))
        workflow = self.workflow('feedback')
        workflow.specialist_factory = lambda provider, fixture: specialist
        workflow.reviewer_override = reviewer
        result = workflow.start('feedback')
        self.assertEqual(result['task']['state'], 'awaiting_pr_approval')
        self.assertEqual(result['task']['repair_count'], 1)
        self.assertEqual(len(specialist.prompts), 2)
        self.assertIn('remove-todo', specialist.prompts[-1])
        self.assertEqual(result['approval_package']['review_findings'], [])

    def test_repeated_identical_failure_stops_without_unbounded_repairs(self):
        specialist = BrokenThenFixedSpecialist(always_broken=True)
        workflow = self.workflow('repeated')
        workflow.specialist_factory = lambda provider, fixture: specialist
        result = workflow.start('repeated')
        self.assertEqual(result['task']['state'], 'blocked')
        self.assertEqual(result['task']['repair_count'], 1)
        self.assertEqual(specialist.calls, 2)
        self.assertLessEqual(result['status']['budget']['completed_calls'], 4)

    def test_authentication_resume_preserves_completed_work_budget_and_repairs(self):
        specialist = AuthOnceSpecialist()
        workflow = self.workflow('auth')
        workflow.specialist_factory = lambda provider, fixture: specialist
        first = workflow.start('auth')
        self.assertEqual(first['task']['state'], 'authentication_required')
        before = first['status']['budget']['completed_calls']
        claim = workflow.store.claim_authentication_login(
            'auth', 'codex', authority=workflow.store.authority)
        workflow.store.finish_authentication_login(
            claim['session_id'], 'succeeded', auth_mode='subscription', reason='authenticated',
            owner_nonce=claim['owner_nonce'], authority=workflow.store.authority)
        resumed = workflow.resume('auth')
        self.assertEqual(resumed['task']['state'], 'awaiting_pr_approval')
        self.assertEqual(resumed['task']['repair_count'], 0)
        self.assertEqual(specialist.calls, 2)
        self.assertEqual(resumed['status']['budget']['completed_calls'], before + 3)

    def test_actual_candidate_change_rejects_authentication_resume_and_package(self):
        reviewer = AuthOnceReviewer()
        workflow = self.workflow('stale-auth')
        workflow.reviewer_override = reviewer
        first = workflow.start('stale-auth')
        self.assertEqual(first['task']['state'], 'authentication_required')
        Path(first['task']['worktree'], 'calculator.py').write_text('tampered = True\n')
        claim = workflow.store.claim_authentication_login(
            'stale-auth', 'claude', authority=workflow.store.authority)
        workflow.store.finish_authentication_login(
            claim['session_id'], 'succeeded', auth_mode='subscription', reason='authenticated',
            owner_nonce=claim['owner_nonce'], authority=workflow.store.authority)
        with self.assertRaises(StaleEvidence):
            workflow.resume('stale-auth')
        self.assertFalse((workflow.approval_root / 'approval-package.json').exists())

    def test_reviewer_authentication_resume_preserves_implementation_and_verification(self):
        reviewer = AuthOnceReviewer()
        specialist = DeterministicSpecialist('codex', CALCULATOR)
        workflow = self.workflow('review-auth')
        workflow.specialist_factory = lambda provider, fixture: specialist
        workflow.reviewer_override = reviewer
        first = workflow.start('review-auth')
        self.assertEqual(first['task']['state'], 'authentication_required')
        head = first['task']['head_revision']
        checks = tuple(first['status']['verification'])
        claim = workflow.store.claim_authentication_login(
            'review-auth', 'claude', authority=workflow.store.authority)
        workflow.store.finish_authentication_login(
            claim['session_id'], 'succeeded', auth_mode='subscription', reason='authenticated',
            owner_nonce=claim['owner_nonce'], authority=workflow.store.authority)
        resumed = workflow.resume('review-auth')
        self.assertEqual(resumed['task']['state'], 'awaiting_pr_approval')
        self.assertEqual(resumed['task']['head_revision'], head)
        self.assertEqual(tuple(resumed['status']['verification']), checks)
        self.assertEqual(specialist.calls, 1)
        self.assertEqual(reviewer.calls, 2)

    def test_cancellation_and_execution_uncertainty_prevent_unsafe_launch(self):
        cancelled = self.workflow('cancelled')
        status = cancelled.cancel('cancelled')
        self.assertEqual(status['state'], 'cancelled')
        result = cancelled.start('cancelled')
        self.assertEqual(result['task']['state'], 'cancelled')
        self.assertEqual(result['status']['executions'], [])

        uncertain = self.workflow('uncertain')
        store = uncertain.store
        task_id = 'uncertain'
        uncertain.state.activate_plan(task_id, authority=store.authority)
        repository, base = uncertain.broker.create_repository(task_id, CALCULATOR.files)
        branch, worktree, base = uncertain.broker.create_task_worktree(repository, task_id, base)
        store.set_workspace(task_id, branch, str(worktree), base, authority=store.authority)
        uncertain._transition(task_id, 'contracted', 'workspace_ready', 'workspace', 'implement')
        uncertain._transition(task_id, 'workspace_ready', 'implementing', 'implementing', 'implement')
        execution = store.reserve_execution(task_id, 'implementer', 'codex', None, 5,
                                            authority=store.authority)
        store.start_execution(execution, pid=999999, process_token='fixture', authority=store.authority)
        reopened = Phase4Workflow(uncertain.root)
        stopped = reopened.start(task_id)
        self.assertEqual(stopped['task']['state'], 'blocked')
        self.assertEqual(len(stopped['status']['executions']), 1)
        self.assertEqual(stopped['status']['executions'][0]['status'], 'reconciliation_required')
        with self.assertRaises(ReconciliationRequired):
            store.reserve_execution(task_id, 'implementer', 'codex', None, 1,
                                    authority=store.authority)

    def test_active_live_execution_observes_durable_cancellation(self):
        specialist = CancellableSpecialist()
        workflow = self.workflow('active-cancel')
        workflow.live = True
        workflow.specialist_factory = lambda provider, fixture: specialist
        results = []
        errors = []

        def run():
            try:
                results.append(workflow.start('active-cancel'))
            except Exception as exc:  # surfaced below with its concrete type
                errors.append(exc)

        thread = threading.Thread(target=run)
        thread.start()
        self.assertTrue(specialist.started.wait(2))
        cancelling = Phase4Workflow(workflow.root)
        cancelling.cancel('active-cancel')
        thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(results[0]['task']['state'], 'cancelled')
        execution = results[0]['status']['executions'][0]
        self.assertEqual(execution['status'], 'cancelled')
        node = next(item for item in workflow.state.nodes('active-cancel')
                    if item['kind'] == 'implementation')
        self.assertEqual(node['status'], 'cancelled')

    def test_role_and_skill_contracts_are_recorded_with_content_hashes(self):
        self.assertEqual(set(ROLE_CONTRACTS), {'chief_of_staff', 'tech_lead', 'manager',
                                              'implementer', 'reviewer', 'verifier'})
        workflow = self.workflow('skills')
        for skill in workflow.state.snapshot('skills')['skills']:
            source = ROOT / skill['relative_path']
            self.assertTrue(source.is_file())
            self.assertEqual(skill['sha256'], hashlib.sha256(source.read_bytes()).hexdigest())

    def test_archived_live_evidence_is_hash_bound_and_unapproved(self):
        manifest = json.loads((ROOT / 'evidence/phase4/manifest.json').read_text())
        recorded = {item['path'] for item in manifest['files']}
        actual = {str(path.relative_to(ROOT)) for path in
                  (ROOT / 'evidence/phase4/live-complete').iterdir() if path.is_file()}
        self.assertEqual(recorded, actual)
        for item in manifest['files']:
            path = ROOT / item['path']
            self.assertEqual(path.stat().st_size, item['bytes'])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item['sha256'])
        summary = json.loads((ROOT / 'evidence/phase4/live-complete/summary.json').read_text())
        package = json.loads((ROOT / 'evidence/phase4/live-complete/approval-package.json').read_text())
        status = json.loads((ROOT / 'evidence/phase4/live-complete/status.json').read_text())
        self.assertEqual(summary['result'], 'awaiting_pr_approval')
        self.assertEqual(summary['candidate']['head_revision'], package['head_revision'])
        self.assertEqual(status['verification'][0]['revision'], package['head_revision'])
        self.assertFalse(package['approval']['recorded'])
        self.assertFalse(summary['publication_performed'])


if __name__ == '__main__':
    unittest.main()
