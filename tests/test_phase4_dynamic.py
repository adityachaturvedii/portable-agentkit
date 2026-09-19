import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from agentkit.controller import ControllerError, UsageRecord
from agentkit.delivery import EngineOutcome
from agentkit.runtime_contracts import ExecutionResult
from agentkit.git_broker import GitBrokerError
from agentkit.orchestration import (DeterministicReviewer, Phase4FixtureVerifier,
                                    Phase4Workflow, build_contract, build_plan)
from agentkit.phase4_contracts import ModelProfile, ModelRegistry
from agentkit.phase4_fixtures import CALCULATOR, TEXT_METRICS, TEXT_PIPELINE
from agentkit.planning import (ClarificationRequired, UnsupportedRequest, bounded_inventory,
                               propose)


ROOT = Path(__file__).resolve().parents[1]


class BarrierSpecialist:
    engine = 'codex'
    model = None

    def __init__(self, fixture, barrier):
        self.fixture = fixture
        self.barrier = barrier
        self.lock = threading.Lock()
        self.active = 0
        self.maximum_active = 0
        self.prompts = []

    def run_assignment(self, workspace, assignment, output, boundary, prompt, policy):
        with self.lock:
            self.active += 1
            self.maximum_active = max(self.maximum_active, self.active)
            self.prompts.append(prompt)
        self.barrier.wait(timeout=3)
        for relative in assignment['allowed_paths']:
            Path(workspace, relative).write_text(self.fixture.final_files[relative])
        with self.lock:
            self.active -= 1
        return EngineOutcome('succeeded', .01, UsageRecord(source='fake'), {'simulated': True})


class RecordingSpecialist:
    engine = 'codex'
    model = None

    def __init__(self, fixture):
        self.fixture = fixture
        self.events = []
        self.lock = threading.Lock()

    def run_assignment(self, workspace, assignment, output, boundary, prompt, policy):
        with self.lock:
            self.events.append(('start', assignment['node_id']))
        for relative in assignment['allowed_paths']:
            Path(workspace, relative).write_text(self.fixture.final_files[relative])
        with self.lock:
            self.events.append(('finish', assignment['node_id']))
        return EngineOutcome('succeeded', .01, UsageRecord(source='fake'), {'simulated': True})


class DependencyReadingSpecialist:
    engine = 'codex'
    model = None

    def __init__(self):
        self.produced_marker = None
        self.downstream_observed = None

    def run_assignment(self, workspace, assignment, output, boundary, prompt, policy):
        if assignment['node_id'] == 'implement-normalize':
            self.produced_marker = 'runtime-predecessor-' + str(time.monotonic_ns())
            Path(workspace, 'normalize.py').write_text(
                'PREDECESSOR_MARKER = ' + repr(self.produced_marker) + '\n\n'
                'def normalize(text):\n    return " ".join(text.lower().split())\n')
        else:
            source = Path(workspace, 'normalize.py').read_text()
            marker_line = next((line for line in source.splitlines()
                                if line.startswith('PREDECESSOR_MARKER = ')), None)
            if marker_line is None:
                return EngineOutcome('failed', .01, UsageRecord(source='fake'),
                                     {'missing_dependency_content': True})
            self.downstream_observed = marker_line.split('=', 1)[1].strip().strip("'")
            Path(workspace, 'report.py').write_text(
                'from normalize import normalize\n\n'
                'def report(text):\n'
                '    value = normalize(text)\n'
                '    return {"normalized": value, "length": len(value)}\n'
                '# observed ' + self.downstream_observed + '\n')
        return EngineOutcome('succeeded', .01, UsageRecord(source='fake'), {'simulated': True})


class CountingSpecialist:
    engine = 'codex'
    model = None

    def __init__(self):
        self.calls = 0
        self.lock = threading.Lock()

    def run_assignment(self, workspace, assignment, output, boundary, prompt, policy):
        with self.lock:
            self.calls += 1
        Path(workspace, 'calculator.py').write_text(CALCULATOR.final_files['calculator.py'])
        return EngineOutcome('succeeded', .01, UsageRecord(source='fake'), {'simulated': True})


class BlockingSpecialist:
    engine = 'codex'
    model = None

    def __init__(self, fixture):
        self.fixture = fixture
        self.started = threading.Event()
        self.release = threading.Event()
        self.calls = 0

    def run_assignment(self, workspace, assignment, output, boundary, prompt, policy):
        self.calls += 1
        self.started.set()
        if not self.release.wait(5):
            return EngineOutcome('failed', .01, UsageRecord(source='fake'), {'timeout': True})
        for relative in assignment['allowed_paths']:
            Path(workspace, relative).write_text(self.fixture.final_files[relative])
        return EngineOutcome('succeeded', .01, UsageRecord(source='fake'), {'simulated': True})


class CancelTracker:
    engine = 'codex'
    model = None

    def __init__(self, shared):
        self.shared = shared

    def run(self, workspace, output, boundary, prompt, policy, cancel_event=None):
        with self.shared['lock']:
            self.shared['started'] += 1
            if self.shared['started'] == 2:
                self.shared['both'].set()
        while not cancel_event.is_set():
            time.sleep(.01)
        with self.shared['lock']:
            self.shared['cancelled'] += 1
        return EngineOutcome('cancelled', .01, UsageRecord(source='fake'), {'simulated': True})


class ConflictBroker:
    def __init__(self, delegate):
        self.delegate = delegate

    def __getattr__(self, name):
        return getattr(self.delegate, name)

    def integrate_contributions(self, repository, worktree, base_revision, contributions, message):
        raise GitBrokerError('fixture integration conflict; contributions retained')


class RepairAwareSpecialist:
    engine = 'codex'
    model = None

    def __init__(self):
        self.calls = 0

    def run_assignment(self, workspace, assignment, output, boundary, prompt, policy):
        self.calls += 1
        source = CALCULATOR.final_files['calculator.py']
        if self.calls == 1:
            source = source.replace('return left + right', 'return left + right  # bounded marker')
        Path(workspace, 'calculator.py').write_text(source)
        return EngineOutcome('succeeded', .01, UsageRecord(source='fake'), {'simulated': True})


class DynamicPhase4Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='agentkit-phase4-dynamic-')
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def submit(self, name, fixture='text-metrics', request='Repair word and line metrics.', **kwargs):
        return Phase4Workflow.submit(self.root / name, name, request, fixture, **kwargs)

    def test_requests_drive_different_valid_plans_without_expected_patch_context(self):
        word = self.submit('word-only', request='Repair the word count behavior.')
        both = self.submit('both', request='Repair word and line metrics.')
        word_plan = word.state.plan('word-only')['plan']
        both_plan = both.state.plan('both')['plan']
        self.assertEqual([node['node_id'] for node in word_plan['nodes']
                          if node['kind'] == 'implementation'], ['implement-word-metric'])
        self.assertEqual(len([node for node in both_plan['nodes']
                              if node['kind'] == 'implementation']), 2)
        serialized = json.dumps(both_plan['proposal'])
        self.assertNotIn('return len(text.split())', serialized)
        self.assertEqual(both_plan['proposal']['inventory_sha256'],
                         bounded_inventory(TEXT_METRICS)['sha256'])
        result = word.start('word-only')
        self.assertEqual(result['task']['state'], 'awaiting_pr_approval')
        self.assertEqual(result['task']['contract']['scope'], ['words.py'])

    def test_small_plan_has_no_manager_or_model_planning_call(self):
        workflow = self.submit('small', fixture='calculator', request='Correct total arithmetic.')
        plan = workflow.state.plan('small')['plan']
        self.assertEqual(plan['management_calls'], 0)
        self.assertFalse(any(node['role'] == 'manager' for node in plan['nodes']))
        self.assertEqual(plan['proposal']['planner']['kind'], 'deterministic-controller')

    def test_conflicting_requirements_require_clarification_before_execution(self):
        with self.assertRaises(ClarificationRequired):
            propose('Lowercase the result and preserve case exactly.',
                    __import__('agentkit.phase4_fixtures', fromlist=['CASE_POLICY']).CASE_POLICY)

    def test_unmatched_negated_and_contradictory_requests_do_not_fall_back(self):
        supported = propose('Correct total arithmetic.', CALCULATOR)
        self.assertEqual([item['id'] for item in supported['assignments']],
                         ['implement-calculator-core'])
        with self.assertRaisesRegex(UnsupportedRequest, 'unsupported request'):
            propose('Add a CSV export endpoint.', CALCULATOR)
        with self.assertRaisesRegex(ClarificationRequired, 'Clarify which matched capability'):
            propose('Do not change the calculator total.', CALCULATOR)
        case = __import__('agentkit.phase4_fixtures', fromlist=['CASE_POLICY']).CASE_POLICY
        with self.assertRaisesRegex(ClarificationRequired, 'Choose one output case policy'):
            propose('Lowercase and uppercase the result.', case)

    def test_adversarial_planner_output_is_rejected_before_worker_execution(self):
        proposal = propose('Repair word and line metrics.', TEXT_METRICS)
        proposal['assignments'][0]['allowed_paths'] = ['../controller/state']
        with self.assertRaisesRegex(ValueError, 'authority|unsafe path'):
            self.submit('unsafe-plan', planner_output=proposal)

    def test_two_independent_workers_overlap_using_a_barrier(self):
        specialist = BarrierSpecialist(TEXT_METRICS, threading.Barrier(2))
        workflow = self.submit('overlap', max_calls=4, max_provider_calls=3,
                               max_repairs=0, max_escalations=0)
        workflow.specialist_factory = lambda provider, fixture: specialist
        result = workflow.start('overlap')
        self.assertEqual(result['task']['state'], 'awaiting_pr_approval')
        self.assertEqual(specialist.maximum_active, 2)
        self.assertTrue(all('VERIFIED_SKILL_CONTEXT_JSON' in prompt
                            for prompt in specialist.prompts))
        self.assertTrue(all('return len(text.split())' not in prompt
                            for prompt in specialist.prompts))
        self.assertEqual(result['status']['budget']['completed_provider_calls'], 3)
        self.assertEqual(result['status']['budget']['remaining_provider_calls'], 0)

    def test_dependencies_prevent_premature_launch(self):
        specialist = RecordingSpecialist(TEXT_PIPELINE)
        workflow = self.submit('ordered', fixture='text-pipeline',
                               request='Normalize text, then build the report.')
        workflow.specialist_factory = lambda provider, fixture: specialist
        result = workflow.start('ordered')
        self.assertEqual(result['task']['state'], 'awaiting_pr_approval')
        self.assertLess(specialist.events.index(('finish', 'implement-normalize')),
                        specialist.events.index(('start', 'implement-report')))

    def test_downstream_worker_receives_runtime_predecessor_content_and_records_provenance(self):
        specialist = DependencyReadingSpecialist()
        workflow = self.submit('dependency-content', fixture='text-pipeline',
                               request='Normalize text, then build the report.')
        workflow.specialist_factory = lambda provider, fixture: specialist
        result = workflow.start('dependency-content')
        self.assertEqual(result['task']['state'], 'awaiting_pr_approval')
        self.assertEqual(specialist.downstream_observed, specialist.produced_marker)
        predecessor = workflow.state.node('dependency-content', 'implement-normalize')
        downstream = workflow.state.node('dependency-content', 'implement-report')
        self.assertNotEqual(downstream['result']['starting_revision'],
                            result['task']['base_revision'])
        self.assertEqual(downstream['result']['dependency_contributions'], [{
            'node_id': 'implement-normalize',
            'starting_revision': predecessor['result']['starting_revision'],
            'revision': predecessor['result']['revision'],
            'changed_paths': ['normalize.py'],
        }])
        self.assertEqual(downstream['result']['changed_paths'], ['report.py'])
        diff = workflow.broker.changed_paths(
            workflow.broker.repositories / 'dependency-content',
            result['task']['base_revision'], result['task']['head_revision'])
        self.assertEqual(diff, ('normalize.py', 'report.py'))

    def test_concurrent_scheduler_uses_real_adapter_request_boundary(self):
        registry = ModelRegistry((
            ModelProfile('codex-impl', 'codex', 'fixture-codex-model', None,
                         ('implementer', 'repair'), ('owned-code',), 'unknown', 'fixture',
                         availability='verified', evidence_source='fixture help',
                         evidence_date='2026-09-19'),
            ModelProfile('claude-review', 'claude', 'fixture-claude-model', 'high',
                         ('reviewer',), ('model-only',), 'unknown', 'fixture',
                         availability='verified', evidence_source='fixture help',
                         evidence_date='2026-09-19'),
        ), {'implementer': 'codex-impl', 'repair': 'codex-impl',
            'reviewer': 'claude-review'})
        submitted = self.submit('adapter-concurrency', registry=registry, max_calls=4,
                                max_provider_calls=3, max_repairs=0, max_escalations=0,
                                implementation_timeout_seconds=7, review_timeout_seconds=8)
        workflow = Phase4Workflow(
            submitted.root, live=True, authorized=True,
            verifier_factory=lambda broker, fixture: Phase4FixtureVerifier(broker, fixture))
        barrier = threading.Barrier(2)
        requests = []
        lock = threading.Lock()

        def owned_transport(request, output, boundary, *, policy, cancel_event):
            with lock:
                requests.append(request)
            barrier.wait(timeout=3)
            if Path(request.cwd, 'words.py').exists() and 'words.py' in request.prompt:
                Path(request.cwd, 'words.py').write_text(TEXT_METRICS.final_files['words.py'])
            if Path(request.cwd, 'lines.py').exists() and 'lines.py' in request.prompt:
                Path(request.cwd, 'lines.py').write_text(TEXT_METRICS.final_files['lines.py'])
            return ExecutionResult('codex', request.task_id, 'succeeded', None, 0, .01,
                                   model='reported-codex-model')

        def review_transport(request, output, *, policy, cancel_event):
            requests.append(request)
            return ExecutionResult(
                'claude', request.task_id, 'succeeded', None, 0, .01,
                model='reported-claude-model',
                structured_output={'verdict': 'no_findings', 'findings': []})

        with patch('agentkit.delivery.execute_owned_code', side_effect=owned_transport), \
             patch('agentkit.delivery.execute', side_effect=review_transport):
            result = workflow.start('adapter-concurrency')
        self.assertEqual(result['task']['state'], 'awaiting_pr_approval')
        implementation = [request for request in requests if request.mode == 'owned-code']
        reviewer = [request for request in requests if request.mode == 'model-only']
        self.assertEqual(len(implementation), 2)
        self.assertTrue(all(request.timeout_seconds == 7 and
                            request.model == 'fixture-codex-model' and request.effort is None
                            for request in implementation))
        self.assertEqual((reviewer[0].timeout_seconds, reviewer[0].model, reviewer[0].effort),
                         (8, 'fixture-claude-model', 'high'))

    def test_duplicate_controller_does_not_duplicate_active_assignment(self):
        specialist = BlockingSpecialist(CALCULATOR)
        submitted = self.submit('duplicate', fixture='calculator', request='Correct total arithmetic.')
        first = Phase4Workflow(submitted.root, specialist_factory=lambda provider, fixture: specialist)
        results = []
        thread = threading.Thread(target=lambda: results.append(first.start('duplicate')))
        thread.start()
        self.assertTrue(specialist.started.wait(3))
        duplicate = Phase4Workflow(submitted.root)
        observed = duplicate.start('duplicate')
        self.assertEqual(observed['task']['state'], 'implementing')
        self.assertEqual(specialist.calls, 1)
        specialist.release.set()
        thread.join(8)
        self.assertFalse(thread.is_alive())
        self.assertEqual(results[0]['task']['state'], 'awaiting_pr_approval')

    def test_stale_scheduler_selection_cannot_rerun_completed_assignment(self):
        specialist = CountingSpecialist()
        workflow = self.submit('stale-selection', fixture='calculator',
                               request='Correct total arithmetic.')
        workflow.specialist_factory = lambda provider, fixture: specialist
        store = workflow.store
        workflow.state.activate_plan('stale-selection', authority=store.authority)
        repository, base = workflow.broker.create_repository('stale-selection', CALCULATOR.files)
        branch, worktree, base = workflow.broker.create_task_worktree(
            repository, 'stale-selection', base)
        store.set_workspace('stale-selection', branch, str(worktree), base,
                            authority=store.authority)
        workflow._transition('stale-selection', 'contracted', 'workspace_ready', 'workspace',
                             'implement')
        workflow._transition('stale-selection', 'workspace_ready', 'implementing', 'implement',
                             'implement')
        stale = workflow.state.node('stale-selection', 'implement-calculator-core')
        winner_done = threading.Event()
        stale_result = []

        def stale_contender():
            self.assertTrue(winner_done.wait(5))
            stale_result.append(workflow._execute_implementation(
                'stale-selection', CALCULATOR, repository, Path(worktree), stale,
                coordinated=True))

        contender = threading.Thread(target=stale_contender)
        contender.start()
        self.assertTrue(workflow._execute_implementation(
            'stale-selection', CALCULATOR, repository, Path(worktree), stale,
            coordinated=True))
        successful = workflow.state.node('stale-selection', 'implement-calculator-core')
        winner_done.set()
        contender.join(5)
        self.assertFalse(contender.is_alive())
        self.assertEqual(stale_result, [True])
        self.assertEqual(specialist.calls, 1)
        preserved = workflow.state.node('stale-selection', 'implement-calculator-core')
        self.assertEqual(preserved['status'], 'succeeded')
        self.assertEqual(preserved['result'], successful['result'])
        self.assertEqual(preserved['attempts'], 1)

    def test_integration_failure_preserves_both_contributions_and_blocks(self):
        workflow = self.submit('conflict')
        workflow.broker = ConflictBroker(workflow.broker)
        result = workflow.start('conflict')
        self.assertEqual(result['task']['state'], 'blocked')
        implementations = [node for node in workflow.state.nodes('conflict')
                           if node['kind'] == 'implementation']
        self.assertTrue(all(node['status'] == 'succeeded' for node in implementations))
        for node in implementations:
            self.assertTrue(Path(node['result']['worktree']).is_dir())
            self.assertTrue(node['result']['revision'])

    def test_authentication_in_one_worker_preserves_completed_sibling(self):
        class AuthOne(RecordingSpecialist):
            def run_assignment(inner, workspace, assignment, output, boundary, prompt, policy):
                if assignment['node_id'] == 'implement-word-metric':
                    return EngineOutcome('failed', .01, UsageRecord(source='unavailable'),
                                         {'error_class': 'authentication',
                                          'authentication_failure': 'expired'})
                return super(AuthOne, inner).run_assignment(
                    workspace, assignment, output, boundary, prompt, policy)
        specialist = AuthOne(TEXT_METRICS)
        workflow = self.submit('auth-sibling')
        workflow.specialist_factory = lambda provider, fixture: specialist
        result = workflow.start('auth-sibling')
        self.assertEqual(result['task']['state'], 'authentication_required')
        self.assertEqual(workflow.state.node('auth-sibling', 'implement-line-metric')['status'],
                         'succeeded')

    def test_cancellation_reaches_both_supervised_workers(self):
        shared = {'lock': threading.Lock(), 'started': 0, 'cancelled': 0,
                  'both': threading.Event()}
        submitted = self.submit('cancel-two')
        workflow = Phase4Workflow(
            submitted.root, live=True, authorized=True,
            specialist_factory=lambda provider, fixture: CancelTracker(shared),
            verifier_factory=lambda broker, fixture: Phase4FixtureVerifier(broker, fixture))
        results = []
        thread = threading.Thread(target=lambda: results.append(workflow.start('cancel-two')))
        thread.start()
        self.assertTrue(shared['both'].wait(4))
        Phase4Workflow(submitted.root).cancel('cancel-two')
        thread.join(6)
        self.assertFalse(thread.is_alive())
        self.assertEqual(shared['cancelled'], 2)
        self.assertEqual(results[0]['task']['state'], 'cancelled')

    def test_uncertain_node_owner_prevents_replacement(self):
        workflow = self.submit('uncertain-owner')
        store = workflow.store
        workflow.state.activate_plan('uncertain-owner', authority=store.authority)
        repository, base = workflow.broker.create_repository('uncertain-owner', TEXT_METRICS.files)
        branch, worktree, base = workflow.broker.create_task_worktree(
            repository, 'uncertain-owner', base)
        store.set_workspace('uncertain-owner', branch, str(worktree), base, authority=store.authority)
        workflow._transition('uncertain-owner', 'contracted', 'workspace_ready', 'workspace', 'implement')
        workflow._transition('uncertain-owner', 'workspace_ready', 'implementing', 'implement', 'implement')
        workflow.state.transition_node(
            'uncertain-owner', 'implement-word-metric', 'running',
            result={'scheduler_owner': 'ended', 'scheduler_pid': 999999},
            authority=store.authority)
        reopened = Phase4Workflow(workflow.root)
        result = reopened.start('uncertain-owner')
        self.assertEqual(result['task']['state'], 'blocked')
        self.assertIn('reconcile uncertain assignment', result['task']['next_action'])

    def test_routing_config_is_dated_and_unverified_models_are_not_selected(self):
        registry = ModelRegistry((
            ModelProfile('codex-known', 'codex', 'fixture-codex-model', None,
                         ('implementer', 'repair'), ('owned-code',), 'unknown',
                         'installed help fixture', availability='verified',
                         evidence_source='fixture installed CLI help', evidence_date='2026-09-19'),
            ModelProfile('claude-review', 'claude', None, 'high', ('reviewer',),
                         ('model-only',), 'unknown', 'account default',
                         availability='verified', evidence_source='fixture CLI status'),
            ModelProfile('unknown-model', 'claude', 'not-verified', None, ('implementer',),
                         ('owned-code',), 'lower', 'no evidence', availability='unverified',
                         evidence_source='operator proposal'),
        ), {'implementer': 'codex-known', 'repair': 'codex-known',
            'reviewer': 'claude-review'}, policies=(
                {'role': 'implementer', 'profile_id': 'codex-known', 'difficulty': 'routine',
                 'risk': 'routine', 'required_capability': 'owned-code'},))
        roundtrip = ModelRegistry.from_dict(registry.to_dict())
        workflow = self.submit('routing-policy', fixture='calculator',
                               request='Correct total arithmetic.', registry=roundtrip)
        routes = workflow.state.plan('routing-policy')['plan']['routes']
        implementation = next(item for item in routes if item['role'] == 'implementer')
        self.assertEqual(implementation['model'], 'fixture-codex-model')
        self.assertNotEqual(implementation['profile_id'], 'unknown-model')

    def test_material_review_cannot_share_any_contributing_provider(self):
        profiles = (
            ModelProfile('codex-work', 'codex', None, None, ('implementer', 'repair', 'reviewer'),
                         ('owned-code', 'model-only'), 'unknown', 'fixture'),
            ModelProfile('claude-work', 'claude', None, None, ('implementer', 'repair', 'reviewer'),
                         ('owned-code', 'model-only'), 'unknown', 'fixture'),
        )
        policies = (
            {'role': 'implementer', 'profile_id': 'codex-work', 'difficulty': 'substantial',
             'risk': 'routine', 'required_capability': 'owned-code',
             'node_id': 'implement-word-metric'},
            {'role': 'implementer', 'profile_id': 'claude-work', 'difficulty': 'substantial',
             'risk': 'routine', 'required_capability': 'owned-code',
             'node_id': 'implement-line-metric'},
        )
        registry = ModelRegistry(profiles, {'implementer': 'codex-work', 'repair': 'codex-work',
                                            'reviewer': 'claude-work'}, policies)
        with self.assertRaisesRegex(ValueError, 'no configured model profile satisfies reviewer'):
            self.submit('no-independent-review', registry=registry)

    def test_plan_reports_budget_infeasibility_before_execution(self):
        contract = build_contract('tight', 'Repair word and line metrics.', TEXT_METRICS,
                                  max_elapsed_seconds=100)
        with self.assertRaisesRegex(ValueError, 'execution-time budget'):
            build_plan(contract, TEXT_METRICS, ModelRegistry.account_defaults(), ROOT)

    def test_repair_escalation_stays_within_configured_bound(self):
        finding = ({'id': 'clarify-doc', 'severity': 'material', 'path': 'calculator.py',
                    'criterion': 'documented implementation',
                    'description': 'Apply the bounded repair once.'},)
        specialist = RepairAwareSpecialist()
        workflow = self.submit('one-escalation', fixture='calculator',
                               request='Correct total arithmetic.', max_calls=6,
                               max_provider_calls=4, max_repairs=1, max_escalations=1)
        workflow.specialist_factory = lambda provider, fixture: specialist
        workflow.reviewer_override = DeterministicReviewer('claude', findings=(finding, ()))
        result = workflow.start('one-escalation')
        self.assertEqual(result['task']['state'], 'awaiting_pr_approval')
        self.assertEqual(len([item for item in result['status']['executions']
                              if item['role'] == 'repair']), 1)

        blocked_specialist = RepairAwareSpecialist()
        blocked = self.submit('no-escalation', fixture='calculator',
                              request='Correct total arithmetic.', max_calls=6,
                              max_provider_calls=4, max_repairs=1, max_escalations=0)
        blocked.specialist_factory = lambda provider, fixture: blocked_specialist
        blocked.reviewer_override = DeterministicReviewer('claude', findings=(finding,))
        stopped = blocked.start('no-escalation')
        self.assertEqual(stopped['task']['state'], 'blocked')
        self.assertEqual(len([item for item in stopped['status']['executions']
                              if item['role'] == 'repair']), 0)


if __name__ == '__main__':
    unittest.main()
