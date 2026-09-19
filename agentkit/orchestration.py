"""Selective Phase 4 orchestration for controller-created disposable fixtures."""

from dataclasses import asdict
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile
import time

from .controller import (AuthenticationRecoveryError, ControllerError, ControllerStore,
                         ReconciliationRequired, StaleEvidence, UsageRecord)
from .delivery import EngineOutcome, LiveImplementer, LiveReviewer, validate_review
from .doctor import clean_environment, native_sandbox_capability, verification_profile
from .git_broker import GitBroker, GitBrokerError
from .phase4_contracts import (ExecutionPlan, GraphEdge, GraphNode, ModelRegistry,
                               ROLE_CONTRACTS, RouteDecision, TaskContract)
from .phase4_fixtures import FIXTURES, fixture_catalog, get_fixture
from .phase4_state import Phase4State
from .process import run_process
from .runtime_contracts import ExecutionBoundary, LivePolicy


def _safe_scope(paths):
    result = []
    for value in paths:
        path = PurePosixPath(value)
        if (not isinstance(value, str) or not value or path.is_absolute() or '..' in path.parts or
                value.startswith('.git') or value.startswith('controller')):
            raise ControllerError('task scope contains an unsupported path')
        result.append(value)
    return tuple(result)


def _manifest(root):
    root = Path(root)
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(root.rglob('*')) if path.is_file() and '.git' not in path.parts}


class DeterministicSpecialist:
    """Fixture-only implementation adapter; provider identity is simulated for routing tests."""
    model = None

    def __init__(self, provider, fixture, *, unauthorized=False, fail_paths=()):
        self.engine = provider
        self.fixture = fixture
        self.unauthorized = unauthorized
        self.fail_paths = set(fail_paths)
        self.calls = 0

    def run_assignment(self, workspace, assignment, output, boundary, prompt, policy):
        self.calls += 1
        for relative in assignment['allowed_paths']:
            content = self.fixture.final_files[relative]
            if relative in self.fail_paths:
                content = content.replace('+', '-')
            (Path(workspace) / relative).write_text(content)
        if self.unauthorized:
            (Path(workspace) / 'README.md').write_text('agent requested unauthorized expansion\n')
        return EngineOutcome('succeeded', 0.001, UsageRecord(source='fake'),
                             {'simulated': True, 'assignment': assignment['node_id']})


class DeterministicReviewer:
    model = None

    def __init__(self, provider='claude', findings=()):
        self.engine = provider
        self.findings = list(findings)
        self.calls = 0

    def run(self, snapshot, revision, output, prompt, policy):
        self.calls += 1
        findings = self.findings.pop(0) if self.findings else ()
        return EngineOutcome('succeeded', 0.001, UsageRecord(source='fake'),
                             {'simulated': True, 'candidate_revision': revision}, tuple(findings))


class ControllerCancellation:
    """Read the durable cancellation flag without exposing controller authority to a worker."""
    def __init__(self, state, task_id, interval=.1):
        self.state = state
        self.task_id = task_id
        self.interval = interval
        self.checked_at = 0.0
        self.cancelled = False

    def is_set(self):
        now = time.monotonic()
        if not self.cancelled and now - self.checked_at >= self.interval:
            self.cancelled = self.state.cancellation_requested(self.task_id)
            self.checked_at = now
        return self.cancelled


class Phase4FixtureVerifier:
    engine = 'local'
    model = 'deterministic-fixture-unittest'

    def __init__(self, broker, fixture):
        self.broker = broker
        self.fixture = fixture

    def run(self, repository, worktree, head, attempt, cancel_event=None):
        before = self.broker.worktree_identity(repository, worktree)
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix='agentkit-phase4-fixture-') as tmp:
            workspace = Path(tmp)
            for relative in before['manifest']:
                target = workspace / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((Path(worktree) / relative).read_bytes())
            (workspace / 'test_acceptance.py').write_text(self.fixture.acceptance_test)
            run = subprocess.run([sys.executable, '-B', '-m', 'unittest', '-v'], cwd=str(workspace),
                                 env={'PATH': '/usr/bin:/bin', 'HOME': str(workspace),
                                      'PYTHONDONTWRITEBYTECODE': '1'},
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 timeout=10, check=False)
        after = self.broker.worktree_identity(repository, worktree)
        unchanged = before == after and before['revision'] == head and before['clean']
        return EngineOutcome('succeeded' if run.returncode == 0 and unchanged else 'failed',
                             time.monotonic() - started, UsageRecord(source='local-command'),
                             {'exit_code': run.returncode,
                              'output': (run.stdout + run.stderr).decode('utf-8', 'replace'),
                              'candidate_unchanged': unchanged, 'simulated': True})


class Phase4ConstrainedVerifier(Phase4FixtureVerifier):
    model = 'python-unittest-seatbelt-v1'

    def __init__(self, broker, fixture, controller_root, approval_root, evidence_root,
                 *, capability_check=native_sandbox_capability, process_runner=run_process):
        super().__init__(broker, fixture)
        self.controller_root = Path(controller_root).resolve()
        self.approval_root = Path(approval_root).resolve()
        self.evidence_root = Path(evidence_root).resolve()
        self.capability_check = capability_check
        self.process_runner = process_runner

    def run(self, repository, worktree, head, attempt, cancel_event=None):
        capability = self.capability_check()
        if capability.state != 'verified':
            return EngineOutcome('blocked', 0, UsageRecord(source='unavailable'),
                                 {'error_class': 'sandbox_unavailable', 'output': capability.evidence,
                                  'candidate_unchanged': None})
        before = self.broker.worktree_identity(repository, worktree)
        if before['revision'] != head or not before['clean']:
            return EngineOutcome('failed', 0, UsageRecord(source='local-command'),
                                 {'error_class': 'candidate_identity',
                                  'output': 'candidate worktree is dirty or at another revision',
                                  'candidate_unchanged': False})
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix='agentkit-phase4-verify-', dir='/private/tmp') as tmp:
            root = Path(tmp).resolve()
            workspace, runtime, fake_home = root / 'candidate', root / 'runtime', root / 'empty-home'
            for path in (workspace, runtime, fake_home):
                path.mkdir(mode=0o700)
            for relative in before['manifest']:
                target = workspace / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((Path(worktree) / relative).read_bytes())
            (workspace / 'test_acceptance.py').write_text(self.fixture.acceptance_test)
            controlled_before = _manifest(workspace)
            denied = tuple(str(path) for path in (
                self.controller_root, self.approval_root, self.evidence_root,
                Path(repository).resolve(), Path(worktree).resolve(), Path.home().resolve()))
            profile = verification_profile(runtime, denied)
            environment = clean_environment()
            environment.update(HOME=str(fake_home), TMPDIR=str(runtime), PATH='/usr/bin:/bin',
                               PYTHONDONTWRITEBYTECODE='1')
            outcome = self.process_runner(
                ['/usr/bin/sandbox-exec', '-p', profile, sys.executable, '-B', '-m', 'unittest', '-v'],
                cwd=str(workspace), env=environment, timeout=10, max_bytes=1048576,
                cancel_event=cancel_event)
            controlled_after = _manifest(workspace)
        after = self.broker.worktree_identity(repository, worktree)
        unchanged = (before == after and before['revision'] == head and before['clean'] and
                     controlled_before == controlled_after)
        status = 'succeeded' if outcome.exit_code == 0 and unchanged else 'failed'
        if outcome.stop_reason == 'sandbox_unavailable':
            status = 'blocked'
        return EngineOutcome(status, time.monotonic() - started, UsageRecord(source='local-command'),
                             {'exit_code': outcome.exit_code,
                              'stop_reason': outcome.stop_reason,
                              'output': (outcome.stdout + outcome.stderr).decode('utf-8', 'replace'),
                              'candidate_unchanged': unchanged, 'sandbox': capability.evidence})


def _selected_skills(root, fixture):
    ids = ['task-contract', 'behavioral-testing', 'independent-review', 'delivery-evidence']
    if fixture.difficulty == 'substantial':
        ids.insert(1, 'interface-design')
    result = []
    for skill_id in ids:
        relative = 'skills/' + skill_id + '/SKILL.md'
        content = (root / relative).read_bytes()
        result.append({'id': skill_id, 'path': relative,
                       'sha256': hashlib.sha256(content).hexdigest(),
                       'reason': 'Selected for ' + fixture.fixture_id + ' ' + fixture.difficulty + ' workflow.'})
    domain_path = 'domains/' + fixture.domain + '.md'
    content = (root / domain_path).read_bytes()
    result.append({'id': 'domain:' + fixture.domain, 'path': domain_path,
                   'sha256': hashlib.sha256(content).hexdigest(),
                   'reason': 'Fixture domain context only.'})
    return tuple(result)


def build_contract(task_id, request, fixture, *, risk=None, max_calls=None,
                   max_elapsed_seconds=None, max_concurrency=None):
    fixture = get_fixture(fixture) if isinstance(fixture, str) else fixture
    _safe_scope(fixture.scope)
    assumptions = (
        'The request targets only the selected controller-created fixture.',
        'Public interfaces and controller-owned acceptance criteria remain unchanged.',
        'No network, dependency installation, publication, deployment, or external repository access is authorized.',
        'Provider model and relative price use account defaults and remain unknown unless reported by the CLI.',
    )
    decomposed = len(fixture.subtasks) > 1
    return TaskContract(
        task_id=task_id, user_request=request, objective=request.strip(), scope=fixture.scope,
        acceptance=fixture.acceptance,
        non_goals=('personal repositories', 'dependency installation', 'publication', 'merge',
                   'deployment', 'GPU or remote execution'), dependencies=(),
        risk=risk or fixture.risk, difficulty=fixture.difficulty,
        execution_profile='trusted-disposable-macos', assumptions=assumptions,
        max_calls=(10 if decomposed else 8) if max_calls is None else max_calls,
        max_elapsed_seconds=((600 if decomposed else 420) if max_elapsed_seconds is None
                             else max_elapsed_seconds),
        max_concurrency=(2 if decomposed else 1) if max_concurrency is None else max_concurrency,
        max_timeout_seconds=60, verification_reserve=1, review_reserve=1,
        max_subtasks=len(fixture.subtasks), max_output_bytes_per_call=1048576,
        context_allocation='provider-managed-unknown', max_repairs=2)


def build_plan(contract, fixture, registry, toolkit_root):
    nodes = [GraphNode('intake', 'chief_of_staff', 'intake',
                       'Normalize user intent without expanding authority.', initial_status='succeeded'),
             GraphNode('plan', 'tech_lead', 'plan',
                       'Define interfaces, decomposition, and immutable acceptance.',
                       dependencies=('intake',), initial_status='succeeded')]
    edges = [GraphEdge('intake', 'plan')]
    if len(fixture.subtasks) > 1:
        nodes.append(GraphNode('schedule', 'manager', 'schedule',
                               'Allocate two isolated subtasks within the parent budget.',
                               dependencies=('plan',), initial_status='succeeded'))
        edges.append(GraphEdge('plan', 'schedule'))
        predecessor = 'schedule'
    else:
        predecessor = 'plan'
    routes = []
    implementation_ids = []
    for subtask in fixture.subtasks:
        node_id = 'implement-' + subtask.subtask_id
        route = registry.route(node_id, 'implementer', 'owned-code')
        routes.append(route)
        nodes.append(GraphNode(node_id, 'implementer', 'implementation', subtask.objective,
                               dependencies=(predecessor,), allowed_paths=_safe_scope(subtask.allowed_paths),
                               provider=route.provider, model=route.model, effort=route.effort,
                               routing_reason=route.reason, max_attempts=2))
        edges.append(GraphEdge(predecessor, node_id))
        implementation_ids.append(node_id)
    if len(implementation_ids) > 1:
        nodes.append(GraphNode('integrate', 'tech_lead', 'integration',
                               'Integrate disjoint broker-validated subtask revisions.',
                               dependencies=tuple(implementation_ids)))
        for node_id in implementation_ids:
            edges.append(GraphEdge(node_id, 'integrate'))
        verification_dependency = 'integrate'
        mode = 'decomposed'
    else:
        verification_dependency = implementation_ids[0]
        mode = 'single'
    nodes.append(GraphNode('verify', 'verifier', 'verification',
                           'Run controller-owned acceptance under the tested execution profile.',
                           dependencies=(verification_dependency,), max_attempts=3))
    edges.append(GraphEdge(verification_dependency, 'verify'))
    implementer_provider = routes[0].provider
    review_route = registry.route('review', 'reviewer', 'model-only',
                                  exclude_provider=implementer_provider if contract.risk == 'material' or
                                  contract.difficulty == 'substantial' else None)
    routes.append(review_route)
    nodes.append(GraphNode('review', 'reviewer', 'review',
                           'Independently review the integrated candidate against the contract.',
                           dependencies=('verify',), provider=review_route.provider,
                           model=review_route.model, effort=review_route.effort,
                           routing_reason=review_route.reason, max_attempts=3))
    edges.append(GraphEdge('verify', 'review'))
    repair_route = registry.route('repair', 'repair', 'owned-code')
    routes.append(repair_route)
    nodes.append(GraphNode('repair', 'implementer', 'repair',
                           'Apply only controller-supplied failed-check or review feedback.',
                           allowed_paths=_safe_scope(contract.scope), provider=repair_route.provider,
                           model=repair_route.model, effort=repair_route.effort,
                           routing_reason=repair_route.reason, max_attempts=2, initial_status='dormant'))
    edges.extend((GraphEdge('verify', 'repair', 'bounded_repair', 2),
                  GraphEdge('review', 'repair', 'bounded_repair', 2),
                  GraphEdge('repair', 'verify', 'bounded_repair', 2)))
    nodes.append(GraphNode('package', 'chief_of_staff', 'package',
                           'Prepare a revision-bound local approval package.', dependencies=('review',)))
    edges.append(GraphEdge('review', 'package'))
    return ExecutionPlan(contract.task_id, mode, tuple(nodes), tuple(edges), tuple(routes),
                         _selected_skills(toolkit_root, fixture), management_calls=0)


class Phase4Workflow:
    def __init__(self, root, *, live=False, authorized=False, specialist_factory=None,
                 reviewer=None, verifier_factory=None):
        self.root = Path(root).resolve()
        self.controller_root = self.root / 'controller'
        self.managed_root = self.root / 'managed'
        self.evidence_root = self.root / 'evidence'
        self.approval_root = self.root / 'approval'
        if not self.root.is_dir():
            raise ControllerError('Phase 4 workflow root does not exist')
        for path in (self.evidence_root, self.approval_root):
            path.mkdir(exist_ok=True, mode=0o700)
        self.store = ControllerStore(self.controller_root)
        self.state = Phase4State(self.store)
        self.broker = GitBroker(self.managed_root)
        self.live = live
        self.authorized = authorized
        self.specialist_factory = specialist_factory
        self.reviewer_override = reviewer
        self.verifier_factory = verifier_factory
        self.policy = LivePolicy(authorized,
            'Operator authorized one bounded Phase 4 disposable subscription demonstration.')

    @classmethod
    def submit(cls, root, task_id, request, fixture_id, *, registry=None, risk=None,
               max_calls=None, max_elapsed_seconds=None, max_concurrency=None):
        root = Path(root).resolve()
        if root.exists() or root.is_symlink():
            raise ControllerError('submission root must be fresh')
        root.mkdir(parents=True, mode=0o700)
        for name in ('evidence', 'approval'):
            (root / name).mkdir(mode=0o700)
        self = cls(root)
        fixture = get_fixture(fixture_id)
        registry = registry or ModelRegistry.account_defaults()
        contract = build_contract(task_id, request, fixture, risk=risk, max_calls=max_calls,
                                  max_elapsed_seconds=max_elapsed_seconds,
                                  max_concurrency=max_concurrency)
        plan = build_plan(contract, fixture, registry, Path(__file__).resolve().parents[1])
        implementation = next(route for route in plan.routes if route.role == 'implementer')
        review = next(route for route in plan.routes if route.role == 'reviewer')
        self.store.create_task(
            task_id, contract.objective, dependencies=contract.dependencies,
            implementer=(implementation.provider, implementation.model),
            reviewer=(review.provider, review.model), max_repairs=contract.max_repairs,
            max_calls=contract.max_calls, max_elapsed_seconds=contract.max_elapsed_seconds,
            max_concurrency=contract.max_concurrency,
            max_timeout_seconds=contract.max_timeout_seconds,
            verification_reserve=contract.verification_reserve,
            review_reserve=contract.review_reserve)
        self.state.record_intake(contract, fixture_id, authority=self.store.authority)
        self.store.set_contract(task_id, contract.controller_contract(), authority=self.store.authority)
        self.store.transition(task_id, 'received', 'contracted', task_id + '-phase4-contracted',
                              next_action='review proposed execution plan', authority=self.store.authority)
        self.state.record_plan(plan, authority=self.store.authority)
        self._write_json('contract.json', contract.to_dict())
        self._write_json('plan.json', plan.to_dict())
        self._write_json('registry.json', registry.to_dict())
        self._write_status(task_id)
        return self

    def _write_json(self, relative, value):
        target = self.root / relative
        target.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')

    def _fixture(self, task_id):
        snapshot = self.state.snapshot(task_id)
        return get_fixture(snapshot['intake']['fixture_id'])

    def _fresh(self, parent, stem):
        candidate = Path(parent) / stem
        counter = 0
        while candidate.exists() or candidate.is_symlink():
            counter += 1
            candidate = Path(parent) / (stem + '-' + str(counter))
        return candidate

    def _transition(self, task_id, expected, target, label, next_action):
        return self.store.transition(task_id, expected, target,
                                     task_id + '-phase4-' + label + '-' + str(time.time_ns()),
                                     next_action=next_action, authority=self.store.authority)

    def _run_engine(self, task_id, role, engine, model, timeout, callback):
        execution_id = self.store.reserve_execution(task_id, role, engine, model, timeout,
                                                    authority=self.store.authority)
        self.store.start_execution(execution_id, process_token='phase4-controller-supervised',
                                   authority=self.store.authority)
        try:
            outcome = callback()
        except Exception as exc:
            self.store.finish_execution(execution_id, 'failed', 0, UsageRecord(),
                                        {'exception': type(exc).__name__}, authority=self.store.authority)
            raise
        self.store.finish_execution(execution_id, outcome.status, outcome.elapsed_seconds,
                                    outcome.usage, outcome.details, authority=self.store.authority)
        return outcome, execution_id

    def _cancellation(self, task_id):
        return ControllerCancellation(self.state, task_id)

    def _adapter(self, provider, fixture):
        if self.specialist_factory:
            return self.specialist_factory(provider, fixture)
        return LiveImplementer(provider) if self.live else DeterministicSpecialist(provider, fixture)

    def _reviewer(self, provider):
        if self.reviewer_override:
            return self.reviewer_override
        return LiveReviewer(provider) if self.live else DeterministicReviewer(provider)

    def _verifier(self, fixture):
        if self.verifier_factory:
            return self.verifier_factory(self.broker, fixture)
        if self.live:
            return Phase4ConstrainedVerifier(self.broker, fixture, self.controller_root,
                                             self.approval_root, self.evidence_root)
        return Phase4FixtureVerifier(self.broker, fixture)

    def _candidate_identity(self, task_id):
        task = self.store.task(task_id)
        repository = (self.broker.repositories / task_id).resolve()
        worktree = Path(task['worktree']).resolve()
        expected = (self.broker.worktrees / task_id).resolve()
        if worktree != expected:
            raise ControllerError('task worktree is not controller-owned')
        identity = self.broker.worktree_identity(repository, worktree)
        manifest_hash = hashlib.sha256(json.dumps(identity['manifest'], sort_keys=True,
                                                  separators=(',', ':')).encode()).hexdigest()
        return {'repository': str(repository), 'worktree': str(worktree),
                'branch': identity['branch'], 'revision': identity['revision'],
                'clean': identity['clean'], 'manifest_sha256': manifest_hash}

    def _checkpoint_auth(self, task_id, node_id, execution_id, outcome, evidence_refs=()):
        node = self.state.node(task_id, node_id)
        self.state.transition_node(task_id, node_id, 'authentication_required',
                                   execution_id=execution_id, result=outcome.details,
                                   authority=self.store.authority)
        return self.store.checkpoint_authentication(
            task_id, execution_id, node['provider'], evidence_refs=evidence_refs,
            auth_reason=outcome.details.get('authentication_failure') or 'missing_or_expired',
            candidate_identity=self._candidate_identity(task_id), authority=self.store.authority)

    def start(self, task_id):
        task = self.store.task(task_id)
        if task['state'] == 'authentication_required':
            raise AuthenticationRecoveryError('use task resume after verified subscription login')
        if task['state'] == 'contracted':
            self.state.activate_plan(task_id, authority=self.store.authority)
            fixture = self._fixture(task_id)
            repository, base = self.broker.create_repository(task_id, fixture.files)
            branch, worktree, base = self.broker.create_task_worktree(repository, task_id, base)
            self.store.set_workspace(task_id, branch, str(worktree), base, authority=self.store.authority)
            self._transition(task_id, 'contracted', 'workspace_ready', 'workspace',
                             'execute bounded implementation assignments')
        elif task['state'] in ('cancelled', 'awaiting_pr_approval', 'blocked'):
            return self.result(task_id)
        active = [item for item in self.store.snapshot(task_id)['executions']
                  if item['status'] in ('reserved', 'running', 'cancel_requested')]
        if active:
            self.store.reconcile_active(authority=self.store.authority)
            return self.result(task_id)
        return self._drive(task_id)

    def resume(self, task_id):
        task = self.store.task(task_id)
        if task['state'] != 'authentication_required':
            raise AuthenticationRecoveryError('task has no supported authentication checkpoint')
        checkpoint = self.store.authentication_checkpoint(task_id)
        nodes = [node for node in self.state.nodes(task_id)
                 if node['execution_id'] == checkpoint['execution_id'] and
                 node['status'] == 'authentication_required']
        if len(nodes) != 1:
            raise AuthenticationRecoveryError('authentication checkpoint has no unique graph assignment')
        self.store.resume_after_authentication(task_id, candidate_identity=self._candidate_identity(task_id),
                                               authority=self.store.authority)
        self.state.transition_node(task_id, nodes[0]['node_id'], 'pending',
                                   authority=self.store.authority)
        return self._drive(task_id)

    def cancel(self, task_id):
        active = self.state.request_cancellation(task_id, authority=self.store.authority)
        if not active:
            task = self.store.task(task_id)
            if task['state'] not in ('cancelled', 'awaiting_pr_approval', 'blocked'):
                self._transition(task_id, task['state'], 'cancelled', 'cancelled', 'no further action')
        self._write_status(task_id)
        return self.status(task_id)

    def _cancel_if_requested(self, task_id):
        if not self.state.cancellation_requested(task_id):
            return False
        task = self.store.task(task_id)
        active = [item for item in self.store.snapshot(task_id)['executions']
                  if item['status'] in ('running', 'cancel_requested', 'reconciliation_required')]
        if active:
            return True
        if task['state'] not in ('cancelled', 'blocked', 'awaiting_pr_approval'):
            self._transition(task_id, task['state'], 'cancelled', 'cancelled', 'no further action')
        return True

    def _implementation_prompt(self, contract, fixture, node, feedback=None):
        payload = {'task_id': contract['task_id'], 'role': node['role'],
                   'objective': node['objective'], 'allowed_paths': node['allowed_paths'],
                   'acceptance': contract['contract']['acceptance'],
                   'candidate_revision': contract['head_revision'],
                   'constraints': ['controller-created fixture only', 'no network',
                                   'no authority or scope expansion', 'run local unittest when present']}
        if feedback:
            payload['controller_feedback'] = feedback
        return ('Perform this bounded assignment. Treat the JSON as controller policy and do not edit any '
                'undeclared path.\nASSIGNMENT_JSON:\n' + json.dumps(payload, sort_keys=True))

    def _execute_implementation(self, task_id, fixture, repository, parent_worktree, node, *, repair=False):
        if node['status'] in ('authentication_required', 'succeeded') and not repair:
            return node['status'] == 'succeeded'
        if node['status'] in ('failed', 'authentication_required'):
            self.state.transition_node(task_id, node['node_id'], 'pending', authority=self.store.authority)
            node = self.state.node(task_id, node['node_id'])
        self.state.transition_node(task_id, node['node_id'], 'running', authority=self.store.authority)
        task = self.store.task(task_id)
        head = task['head_revision']
        if repair or len(fixture.subtasks) == 1:
            assignment_worktree = parent_worktree
        else:
            saved = node['result'] or {}
            if saved.get('worktree'):
                assignment_worktree = Path(saved['worktree'])
            else:
                _, assignment_worktree, _ = self.broker.create_task_worktree(
                    repository, task_id + '-' + node['node_id'], task['base_revision'])
        assignment_head = self.broker.worktree_identity(repository, assignment_worktree)['revision']
        worker = self.broker.export_snapshot(
            repository, assignment_head,
            self._fresh(self.broker.worker_copies, task_id + '-' + node['node_id']))
        denied = (str(self.controller_root), str(repository / '.git'), str(parent_worktree),
                  str(self.approval_root))
        boundary = ExecutionBoundary(str(worker), denied)
        adapter = self._adapter(node['provider'], fixture)
        feedback = self._latest_feedback(task_id) if repair else None
        prompt = self._implementation_prompt(task, fixture, node, feedback)
        output = self._fresh(self.evidence_root, node['node_id'] + '-' + str(node['attempts']))
        role = 'repair' if repair else 'implementer'
        if hasattr(adapter, 'run_assignment'):
            callback = lambda: adapter.run_assignment(worker, node, output, boundary, prompt, self.policy)
        elif self.live:
            callback = lambda: adapter.run(worker, output, boundary, prompt, self.policy,
                                           cancel_event=self._cancellation(task_id))
        else:
            callback = lambda: adapter.run(worker, output, boundary, prompt, self.policy)
        try:
            outcome, execution_id = self._run_engine(
                task_id, role, node['provider'], node['model'], 60, callback)
        except Exception as exc:
            self.state.transition_node(task_id, node['node_id'], 'failed',
                                       result={'exception': type(exc).__name__},
                                       authority=self.store.authority)
            self._transition(task_id, task['state'], 'blocked', 'assignment-exception',
                             'inspect failed assignment')
            return False
        if outcome.details.get('error_class') == 'authentication':
            self._checkpoint_auth(task_id, node['node_id'], execution_id, outcome)
            return False
        if self.state.cancellation_requested(task_id):
            self.state.transition_node(task_id, node['node_id'], 'cancelled', execution_id=execution_id,
                                       result=outcome.details, authority=self.store.authority)
            self._transition(task_id, task['state'], 'cancelled', 'cancelled-during-assignment',
                             'no further action')
            return False
        if outcome.status != 'succeeded':
            self.state.transition_node(task_id, node['node_id'], 'failed', execution_id=execution_id,
                                       result=outcome.details, authority=self.store.authority)
            self._transition(task_id, task['state'], 'blocked', 'assignment-blocked',
                             'inspect failed assignment')
            return False
        try:
            revision, changed = self.broker.apply_worker_changes(
                repository, assignment_worktree, worker, node['allowed_paths'],
                ('Repair integrated fixture' if repair else 'Complete ' + node['node_id']))
        except GitBrokerError as exc:
            self.state.transition_node(task_id, node['node_id'], 'failed', execution_id=execution_id,
                                       result={'authority_violation': str(exc)},
                                       authority=self.store.authority)
            self._transition(task_id, task['state'], 'blocked', 'authority-violation',
                             'inspect rejected worker scope expansion')
            return False
        result = {'revision': revision, 'changed_paths': list(changed),
                  'worktree': str(assignment_worktree), 'execution_id': execution_id}
        self.state.transition_node(task_id, node['node_id'], 'succeeded', execution_id=execution_id,
                                   result=result, authority=self.store.authority)
        if repair or len(fixture.subtasks) == 1:
            self.store.set_head(task_id, revision, authority=self.store.authority)
        return True

    def _latest_feedback(self, task_id):
        task = self.store.task(task_id)
        for item in reversed(self.store.snapshot(task_id)['evidence']):
            if item['status'] != 'failed':
                continue
            details = json.loads(item['details_json'])
            if item['kind'] == 'independent-check':
                return {'kind': 'failed_test', 'revision': item['revision'],
                        'acceptance': task['contract']['acceptance'],
                        'output': str(details.get('output', ''))[-8192:]}
            if item['kind'] == 'independent-review':
                return {'kind': 'review_findings', 'revision': item['revision'],
                        'findings': details.get('findings', [])}
        return None

    def _drive(self, task_id):
        fixture = self._fixture(task_id)
        repository = self.broker.repositories / task_id
        while True:
            task = self.store.task(task_id)
            if task['state'] in ('awaiting_pr_approval', 'blocked', 'cancelled', 'authentication_required'):
                break
            if self._cancel_if_requested(task_id):
                break
            worktree = Path(task['worktree'])
            state = task['state']
            if state == 'workspace_ready':
                self._transition(task_id, state, 'implementing', 'implementing',
                                 'execute ready implementation assignments')
                continue
            if state == 'implementing':
                implementation_nodes = [node for node in self.state.nodes(task_id)
                                        if node['kind'] == 'implementation']
                for node in implementation_nodes:
                    if node['status'] != 'succeeded':
                        if not self._execute_implementation(task_id, fixture, repository, worktree, node):
                            break
                task = self.store.task(task_id)
                if task['state'] != 'implementing':
                    continue
                implementation_nodes = [self.state.node(task_id, node['node_id'])
                                        for node in implementation_nodes]
                if not all(node['status'] == 'succeeded' for node in implementation_nodes):
                    break
                if len(implementation_nodes) > 1:
                    integration = self.state.node(task_id, 'integrate')
                    if integration['status'] != 'succeeded':
                        self.state.transition_node(task_id, 'integrate', 'running',
                                                   authority=self.store.authority)
                        contributions = [{'worktree': node['result']['worktree'],
                                          'revision': node['result']['revision'],
                                          'allowed_paths': node['allowed_paths']}
                                         for node in implementation_nodes]
                        try:
                            head, changed = self.broker.integrate_contributions(
                                repository, worktree, task['base_revision'], contributions,
                                'Integrate Phase 4 specialist changes')
                        except GitBrokerError as exc:
                            self.state.transition_node(task_id, 'integrate', 'failed',
                                                       result={'integration_error': str(exc)},
                                                       authority=self.store.authority)
                            self._transition(task_id, 'implementing', 'blocked', 'integration-blocked',
                                             'inspect integration failure')
                            continue
                        self.store.set_head(task_id, head, authority=self.store.authority)
                        self.state.transition_node(task_id, 'integrate', 'succeeded',
                                                   result={'revision': head, 'changed_paths': list(changed)},
                                                   authority=self.store.authority)
                self._transition(task_id, 'implementing', 'implemented', 'implemented',
                                 'run independent verification')
                continue
            if state == 'repairing':
                repair = self.state.node(task_id, 'repair')
                if not self._execute_implementation(task_id, fixture, repository, worktree, repair,
                                                    repair=True):
                    continue
                for node_id in ('verify', 'review'):
                    node = self.state.node(task_id, node_id)
                    if node['status'] in ('failed', 'succeeded'):
                        self.state.transition_node(task_id, node_id, 'pending',
                                                   authority=self.store.authority)
                self._transition(task_id, 'repairing', 'implemented', 'repaired',
                                 'rerun independent verification')
                continue
            if state == 'implemented':
                self._transition(task_id, 'implemented', 'verifying', 'verifying',
                                 'evaluate controller-owned acceptance')
                continue
            if state == 'verifying':
                node = self.state.node(task_id, 'verify')
                if node['status'] == 'failed':
                    self.state.transition_node(task_id, 'verify', 'pending', authority=self.store.authority)
                self.state.transition_node(task_id, 'verify', 'running', authority=self.store.authority)
                verifier = self._verifier(fixture)
                if self.live:
                    verify_callback = lambda: verifier.run(
                        repository, worktree, task['head_revision'], task['repair_count'],
                        cancel_event=self._cancellation(task_id))
                else:
                    verify_callback = lambda: verifier.run(
                        repository, worktree, task['head_revision'], task['repair_count'])
                outcome, execution_id = self._run_engine(
                    task_id, 'verification', verifier.engine, verifier.model, 10, verify_callback)
                if self.state.cancellation_requested(task_id):
                    self.state.transition_node(task_id, 'verify', 'cancelled', execution_id=execution_id,
                                               result=outcome.details, authority=self.store.authority)
                    self._transition(task_id, 'verifying', 'cancelled', 'cancelled-during-verification',
                                     'no further action')
                    continue
                artifact = self.store.put_artifact(json.dumps(outcome.details, sort_keys=True))
                evidence_id = 'phase4-verification-' + str(task['repair_count'])
                evidence_status = ('passed' if outcome.status == 'succeeded' else
                                   'blocked' if outcome.status == 'blocked' else 'failed')
                self.store.add_evidence(task_id, evidence_id, task['head_revision'],
                                        'independent-check', evidence_status, artifact, outcome.details,
                                        authority=self.store.authority)
                self.state.transition_node(task_id, 'verify',
                                           'succeeded' if outcome.status == 'succeeded' else 'failed',
                                           execution_id=execution_id, result=outcome.details,
                                           authority=self.store.authority)
                if outcome.status == 'blocked':
                    self._transition(task_id, 'verifying', 'blocked', 'verification-blocked',
                                     'restore supported macOS verification profile')
                    continue
                if outcome.status != 'succeeded':
                    decision = self.store.record_failure(
                        task_id, hashlib.sha256(json.dumps(outcome.details, sort_keys=True).encode()).hexdigest(),
                        str(outcome.details.get('output', '')), authority=self.store.authority)
                    if decision == 'repair_allowed':
                        self._transition(task_id, 'verifying', 'repairing', 'repair-verification',
                                         'repair concrete failed acceptance')
                    continue
                self._transition(task_id, 'verifying', 'verified', 'verified',
                                 'run independent review')
                continue
            if state == 'verified':
                self._transition(task_id, 'verified', 'reviewing', 'reviewing',
                                 'evaluate integrated candidate independently')
                continue
            if state == 'reviewing':
                node = self.state.node(task_id, 'review')
                if node['status'] == 'failed':
                    self.state.transition_node(task_id, 'review', 'pending', authority=self.store.authority)
                self.state.transition_node(task_id, 'review', 'running', authority=self.store.authority)
                snapshot = self.broker.export_snapshot(
                    repository, task['head_revision'],
                    self._fresh(self.broker.review_copies, task_id + '-review-' + str(task['repair_count'])),
                    review=True)
                before = self.broker.manifest(snapshot)
                reviewer = self._reviewer(node['provider'])
                prompt = ('Review the exact candidate against this validated contract. Return only concrete '
                          'material findings; do not edit or grant authority. CONTRACT_JSON:\n' +
                          json.dumps(task['contract'], sort_keys=True))
                output = self._fresh(self.evidence_root, 'review-' + str(task['repair_count']))
                if self.live:
                    review_callback = lambda: reviewer.run(
                        snapshot, task['head_revision'], output, prompt, self.policy,
                        cancel_event=self._cancellation(task_id))
                else:
                    review_callback = lambda: reviewer.run(
                        snapshot, task['head_revision'], output, prompt, self.policy)
                review, execution_id = self._run_engine(
                    task_id, 'reviewer', node['provider'], node['model'], 60, review_callback)
                if self.state.cancellation_requested(task_id):
                    self.state.transition_node(task_id, 'review', 'cancelled', execution_id=execution_id,
                                               result=review.details, authority=self.store.authority)
                    self._transition(task_id, 'reviewing', 'cancelled', 'cancelled-during-review',
                                     'no further action')
                    continue
                if review.details.get('error_class') == 'authentication':
                    checks = [item['evidence_id'] for item in self.store.snapshot(task_id)['evidence']
                              if item['kind'] == 'independent-check' and item['status'] == 'passed' and
                              item['revision'] == task['head_revision'] and not item['stale']]
                    self._checkpoint_auth(task_id, 'review', execution_id, review, checks)
                    continue
                if self.broker.manifest(snapshot) != before:
                    review = EngineOutcome('failed', review.elapsed_seconds, review.usage,
                                           {**review.details, 'boundary_error': 'review snapshot changed'},
                                           review.findings)
                findings = validate_review({'verdict': 'findings' if review.findings else 'no_findings',
                                            'findings': list(review.findings)})
                payload = {'status': review.status, 'findings': list(findings),
                           'details': review.details, 'revision': task['head_revision']}
                artifact = self.store.put_artifact(json.dumps(payload, sort_keys=True))
                evidence_id = 'phase4-review-' + str(task['repair_count'])
                passed = review.status == 'succeeded' and not findings
                self.store.add_evidence(task_id, evidence_id, task['head_revision'], 'independent-review',
                                        'passed' if passed else 'failed', artifact, payload,
                                        authority=self.store.authority)
                self.state.transition_node(task_id, 'review', 'succeeded' if passed else 'failed',
                                           execution_id=execution_id, result=payload,
                                           authority=self.store.authority)
                if review.status != 'succeeded':
                    self._transition(task_id, 'reviewing', 'blocked', 'review-blocked',
                                     'inspect failed independent review')
                    continue
                if findings:
                    signature = hashlib.sha256(json.dumps(findings, sort_keys=True).encode()).hexdigest()
                    decision = self.store.record_failure(task_id, signature, json.dumps(findings),
                                                         authority=self.store.authority)
                    if decision == 'repair_allowed':
                        self._transition(task_id, 'reviewing', 'repairing', 'repair-review',
                                         'repair concrete review finding')
                    continue
                self._transition(task_id, 'reviewing', 'review_complete', 'review-complete',
                                 'prepare local approval package')
                continue
            if state == 'review_complete':
                self._transition(task_id, 'review_complete', 'packaging', 'packaging',
                                 'bind package to integrated candidate')
                continue
            if state == 'packaging':
                node = self.state.node(task_id, 'package')
                self.state.transition_node(task_id, 'package', 'running', authority=self.store.authority)
                package = self._package(task_id, repository)
                digest = self.store.put_artifact(json.dumps(package, sort_keys=True))
                self.store.add_evidence(task_id, 'phase4-approval-package', task['head_revision'],
                                        'approval-package', 'passed', digest,
                                        {'head_revision': task['head_revision'],
                                         'base_revision': task['base_revision']},
                                        authority=self.store.authority)
                package['artifact_sha256'] = digest
                self._write_json('approval/approval-package.json', package)
                (self.approval_root / 'approval-package.md').write_text(self._package_markdown(package))
                self.state.transition_node(task_id, 'package', 'succeeded',
                                           result={'artifact_sha256': digest},
                                           authority=self.store.authority)
                self._transition(task_id, 'packaging', 'awaiting_pr_approval', 'awaiting-approval',
                                 'await explicit publication approval bound to this revision')
                continue
            raise ControllerError('unexpected Phase 4 task state: ' + state)
        self._write_status(task_id)
        return self.result(task_id)

    def _package(self, task_id, repository):
        task = self.store.task(task_id)
        status = self.status(task_id)
        return {'schema_version': 1, 'task_id': task_id, 'status': 'awaiting_pr_approval',
                'summary': task['objective'], 'why': task['contract']['requirements'],
                'repository': str(Path(repository).resolve()), 'branch': task['branch'],
                'base_revision': task['base_revision'], 'head_revision': task['head_revision'],
                'diff': self.broker.diff(repository, task['base_revision'], task['head_revision']),
                'verification': status['verification'], 'review_findings': status['findings'],
                'resolved_findings': status['resolved_findings'],
                'routing': status['routing'], 'skills': status['skills'],
                'resources': status['budget'],
                'limitations': ['Trusted controller-created disposable macOS fixtures only.',
                                'Interactive login recovery is fixture-tested, not live-tested.',
                                'No publication, merge, deployment, detached-process containment, or remote cancellation.'],
                'proposed_pr': {'title': 'Repair ' + self.state.snapshot(task_id)['intake']['fixture_id'] +
                                         ' disposable fixture',
                                'body': 'Implements the validated fixture contract and passes independent checks.'},
                'approval': {'recorded': False, 'required_action': 'push_and_create_pr',
                             'bound_head': task['head_revision']}}

    def _package_markdown(self, package):
        return ('# Local approval package\n\n' + package['summary'] + '\n\n'
                '**Base:** `' + package['base_revision'] + '`  \n'
                '**Head:** `' + package['head_revision'] + '`  \n'
                '**Branch:** `' + package['branch'] + '`\n\n'
                'Verification: ' + json.dumps(package['verification'], sort_keys=True) + '\n\n'
                'Review findings: ' + json.dumps(package['review_findings'], sort_keys=True) + '\n\n'
                'No publication approval is recorded.\n')

    def status(self, task_id):
        snapshot = self.state.snapshot(task_id)
        controller = snapshot['controller']
        task = self.store.task(task_id)
        budget = controller['budget']
        usage_fields = ('input_tokens', 'output_tokens', 'cached_input_tokens',
                        'cache_creation_tokens', 'reasoning_tokens')
        observed = {name: 0 for name in usage_fields}
        unknown = {name: False for name in usage_fields}
        executions = []
        for row in controller['executions']:
            usage = json.loads(row['usage_json']) if row['usage_json'] else {}
            for name in usage_fields:
                if usage.get(name) is None:
                    unknown[name] = True
                else:
                    observed[name] += usage[name]
            executions.append({'execution_id': row['execution_id'], 'role': row['role'],
                               'engine': row['engine'], 'model': row['model'],
                               'status': row['status'], 'elapsed_seconds': row['elapsed_seconds'],
                               'usage': usage or None})
        token_usage = {name: (None if not executions or unknown[name] else observed[name])
                       for name in usage_fields}
        plan = snapshot['plan']['plan']
        findings = []
        resolved_findings = []
        verification = []
        for evidence in controller['evidence']:
            details = json.loads(evidence['details_json'])
            if evidence['kind'] == 'independent-review' and evidence['status'] == 'failed':
                destination = resolved_findings if evidence['stale'] else findings
                destination.extend(details.get('findings', []))
            if evidence['kind'] == 'independent-check':
                verification.append({'id': evidence['evidence_id'], 'revision': evidence['revision'],
                                     'status': evidence['status'], 'stale': bool(evidence['stale'])})
        active = [{'node_id': node['node_id'], 'role': node['role'], 'status': node['status'],
                   'provider': node['provider'], 'model': node['model']}
                  for node in snapshot['nodes'] if node['status'] in ('running', 'authentication_required')]
        blocker = None
        attention = None
        if task['state'] == 'authentication_required':
            checkpoint = self.store.authentication_checkpoint(task_id)
            blocker = checkpoint['provider'] + ' subscription authentication required'
            attention = 'Complete official login, then run task resume.'
        elif task['state'] == 'blocked':
            blocker = task['next_action']
            attention = 'Inspect the blocker; unsafe automatic relaunch is disabled.'
        elif task['state'] == 'awaiting_pr_approval':
            attention = 'Review the local package; publication remains separately authorized.'
        return {'task_id': task_id, 'state': task['state'], 'stage': task['state'],
                'next_action': task['next_action'], 'active_assignments': active,
                'routing': plan['routes'], 'skills': snapshot['skills'],
                'budget': {'max_calls': budget['max_calls'], 'completed_calls': budget['completed_calls'],
                           'active_calls': budget['active_calls'],
                           'remaining_calls': budget['max_calls'] - budget['completed_calls'] -
                                              budget['reserved_calls'],
                           'verification_reserve': budget['verification_reserve'],
                           'review_reserve': budget['review_reserve'],
                           'max_output_bytes_per_call': json.loads(
                               (self.root / 'contract.json').read_text())['max_output_bytes_per_call'],
                           'context_allocation': json.loads(
                               (self.root / 'contract.json').read_text())['context_allocation'],
                           'max_elapsed_seconds': budget['max_elapsed_seconds'],
                           'elapsed_seconds': budget['elapsed_seconds'],
                           'remaining_elapsed_seconds': max(0, budget['max_elapsed_seconds'] -
                                                            budget['elapsed_seconds'] -
                                                            budget['reserved_elapsed_seconds']),
                           'token_usage': token_usage,
                           'estimated_cost_usd': None, 'billed_cost_usd': None,
                           'cost_note': 'Unknown remains unknown; CLI estimates are not billing.'},
                'blocker': blocker, 'attention': attention, 'findings': findings,
                'resolved_findings': resolved_findings,
                'verification': verification, 'executions': executions,
                'plan_mode': plan['mode'], 'management_model_calls': plan['management_calls'],
                'approval_package': (str(self.approval_root / 'approval-package.json')
                                     if (self.approval_root / 'approval-package.json').is_file() else None)}

    def result(self, task_id):
        package = None
        package_path = self.approval_root / 'approval-package.json'
        if package_path.is_file():
            package = json.loads(package_path.read_text())
        return {'task': self.store.task(task_id), 'status': self.status(task_id),
                'approval_package': package, 'root': str(self.root)}

    def _write_status(self, task_id):
        self._write_json('status.json', self.status(task_id))


def phase4_fixture_catalog():
    return fixture_catalog()
