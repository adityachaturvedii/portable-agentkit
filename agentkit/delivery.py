"""Minimum durable delivery graph for trusted disposable fixtures."""

from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

from .adapters import execute, execute_owned_code
from .controller import (ControllerError, ControllerStore, UsageRecord)
from .git_broker import GitBroker
from .runtime_contracts import ExecutionBoundary, ExecutionRequest, LivePolicy


SOURCE_BROKEN = '''def total(left, right):
    """Return the arithmetic sum."""
    return left - right
'''
SOURCE_FIXED = '''def total(left, right):
    """Return the arithmetic sum."""
    return left + right
'''
TEST_SOURCE = '''import unittest

from calculator import total


class CalculatorTest(unittest.TestCase):
    def test_total(self):
        self.assertEqual(total(17, 25), 42)
        self.assertEqual(total(-4, 9), 5)


if __name__ == "__main__":
    unittest.main()
'''


@dataclass
class EngineOutcome:
    status: str
    elapsed_seconds: float
    usage: UsageRecord
    details: dict
    findings: tuple = ()


class FakeImplementer:
    engine = 'fake-codex'
    model = 'deterministic-v1'

    def __init__(self, failures=0):
        self.failures = failures
        self.calls = 0

    def run(self, workspace, output, boundary, prompt, policy):
        started = time.monotonic()
        self.calls += 1
        path = Path(workspace) / 'calculator.py'
        if self.calls > self.failures:
            path.write_text(SOURCE_FIXED)
        else:
            path.write_text(SOURCE_BROKEN.replace('left - right', 'left * right'))
        return EngineOutcome('succeeded', time.monotonic() - started, UsageRecord(source='fake'),
                             {'simulated': True, 'call': self.calls})


class FakeReviewer:
    engine = 'fake-claude'
    model = 'deterministic-v1'

    def __init__(self, findings=()):
        self.findings = list(findings)
        self.calls = 0

    def run(self, snapshot, revision, output, prompt, policy):
        self.calls += 1
        findings = self.findings.pop(0) if self.findings else ()
        return EngineOutcome('succeeded', 0.001, UsageRecord(source='fake'),
                             {'simulated': True, 'revision': revision}, tuple(findings))


def _usage_from_result(result):
    usage = result.usage
    return UsageRecord(usage.input_tokens, usage.output_tokens, usage.cached_input_tokens,
                       usage.cache_creation_tokens, usage.reasoning_tokens,
                       usage.estimated_cost_usd, usage.billed_cost_usd, usage.source)


class LiveImplementer:
    def __init__(self, engine='codex', model=None):
        self.engine = engine
        self.model = model

    def run(self, workspace, output, boundary, prompt, policy):
        request = ExecutionRequest(self.engine, 'phase3-live-implementer', prompt, str(Path(workspace).resolve()),
                                   timeout_seconds=60, max_output_bytes=1048576,
                                   model=self.model, mode='owned-code')
        result = execute_owned_code(request, output, boundary, policy=policy)
        return EngineOutcome(result.status, result.elapsed_seconds, _usage_from_result(result),
                             {'error_class': result.error_class, 'artifacts': result.artifacts,
                              'limitations': result.limitations})


class LiveReviewer:
    def __init__(self, engine='claude', model=None):
        self.engine = engine
        self.model = model

    def run(self, snapshot, revision, output, prompt, policy):
        files = {}
        for path in sorted(Path(snapshot).rglob('*')):
            if path.is_file():
                files[str(path.relative_to(snapshot))] = path.read_text()
        review_prompt = prompt + '\nCandidate revision: ' + revision + '\nFiles:\n' + json.dumps(files)
        review_prompt += ('\nReturn only JSON: {"verdict":"no_findings"|"findings","findings":['
                          '{"id":"...","severity":"material","path":"...","criterion":"...","description":"..."}]}')
        with tempfile.TemporaryDirectory(prefix='agentkit-review-empty-') as tmp:
            request = ExecutionRequest(self.engine, 'phase3-live-reviewer', review_prompt, str(Path(tmp).resolve()),
                                       timeout_seconds=60, max_output_bytes=1048576,
                                       model=self.model, mode='model-only')
            result = execute(request, output, policy=policy)
        findings = ()
        parse_error = None
        if result.status == 'succeeded' and isinstance(result.structured_output, dict):
            try:
                findings = validate_review(result.structured_output)
            except ControllerError as exc:
                parse_error = str(exc)
        elif result.status == 'succeeded':
            parse_error = 'reviewer did not return a JSON object'
        status = result.status if parse_error is None else 'failed'
        return EngineOutcome(status, result.elapsed_seconds, _usage_from_result(result),
                             {'error_class': result.error_class, 'parse_error': parse_error,
                              'artifacts': result.artifacts, 'limitations': result.limitations,
                              'candidate_revision': revision}, findings)


def validate_review(value):
    if not isinstance(value, dict) or set(value) != {'verdict', 'findings'}:
        raise ControllerError('invalid review shape')
    if value['verdict'] not in ('no_findings', 'findings') or not isinstance(value['findings'], list):
        raise ControllerError('invalid review verdict')
    if (value['verdict'] == 'no_findings') != (not value['findings']):
        raise ControllerError('review verdict contradicts findings')
    result = []
    for finding in value['findings']:
        required = {'id', 'severity', 'path', 'criterion', 'description'}
        if (not isinstance(finding, dict) or set(finding) != required or
                any(not isinstance(finding[x], str) or not finding[x].strip() for x in required) or
                finding['severity'] != 'material'):
            raise ControllerError('finding must identify a concrete material defect and criterion')
        result.append(finding)
    return tuple(result)


class DeliveryWorkflow:
    def __init__(self, root, implementer, reviewer, *, live_authorized=False):
        self.root = Path(root).resolve()
        if self.root.exists() or self.root.is_symlink():
            raise ControllerError('workflow root must be fresh')
        self.root.mkdir(parents=True, mode=0o700)
        self.controller_root = self.root / 'controller'
        self.managed_root = self.root / 'managed'
        self.evidence_root = self.root / 'evidence'
        self.approval_root = self.root / 'approval'
        for path in (self.evidence_root, self.approval_root):
            path.mkdir(mode=0o700)
        self.store = ControllerStore(self.controller_root)
        self.broker = GitBroker(self.managed_root)
        self.implementer = implementer
        self.reviewer = reviewer
        self.policy = LivePolicy(live_authorized,
            'Operator authorized a bounded Phase 3 disposable end-to-end demonstration; no auth/billing changes.')

    def _transition(self, task_id, expected, target, label, next_action):
        return self.store.transition(task_id, expected, target, task_id + '-' + label,
                                     next_action=next_action, authority=self.store.authority)

    def _run_engine(self, task_id, role, engine, model, timeout, callback):
        execution_id = self.store.reserve_execution(task_id, role, engine, model, timeout,
                                                    authority=self.store.authority)
        self.store.start_execution(execution_id, process_token='controller-supervised',
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

    def _verify(self, worktree):
        started = time.monotonic()
        run = subprocess.run(['python3', '-B', '-m', 'unittest', '-v'], cwd=str(worktree),
                             env={'PATH': os.environ.get('PATH', ''), 'PYTHONDONTWRITEBYTECODE': '1'},
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10, check=False)
        elapsed = time.monotonic() - started
        text = run.stdout + run.stderr
        return EngineOutcome('succeeded' if run.returncode == 0 else 'failed', elapsed,
                             UsageRecord(source='local-command'),
                             {'exit_code': run.returncode, 'output': text.decode('utf-8', 'replace')})

    def run(self, task_id='phase3-demo'):
        contract = {
            'objective': 'Correct the disposable arithmetic defect and prepare a local PR approval package.',
            'scope': ['calculator.py'],
            'non_goals': ['publication', 'merge', 'personal repositories'],
            'acceptance': [{'id': 'total', 'expected': 'all immutable unittest cases pass'}],
            'risk': 'routine', 'max_repairs': 2
        }
        task = self.store.create_task(task_id, contract['objective'], implementer=(self.implementer.engine, self.implementer.model),
                                      reviewer=(self.reviewer.engine, self.reviewer.model), max_calls=9,
                                      max_elapsed_seconds=540, max_concurrency=1,
                                      max_timeout_seconds=60, verification_reserve=2)
        self.store.set_contract(task_id, contract, authority=self.store.authority)
        self._transition(task_id, 'received', 'contracted', 'contracted', 'create isolated worktree')
        repository, base = self.broker.create_repository(task_id, {
            'calculator.py': SOURCE_BROKEN, 'test_calculator.py': TEST_SOURCE,
            'README.md': '# Disposable Phase 3 fixture\n'
        })
        branch, worktree, base = self.broker.create_task_worktree(repository, task_id, base)
        self.store.set_workspace(task_id, branch, str(worktree), base, authority=self.store.authority)
        self._transition(task_id, 'contracted', 'workspace_ready', 'workspace', 'run bounded implementation')
        attempt = 0
        review_findings = ()
        verification_records = []
        while True:
            state = self.store.task(task_id)['state']
            if state == 'workspace_ready':
                self._transition(task_id, state, 'implementing', 'implementing-' + str(attempt), 'apply worker patch')
                implementation_from = 'implementing'
            elif state == 'repairing':
                implementation_from = 'repairing'
            else:
                raise ControllerError('unexpected implementation state: ' + state)
            worker = self.broker.export_snapshot(repository, self.store.task(task_id)['head_revision'],
                                                 self.broker.worker_copies / (task_id + '-' + str(attempt)))
            denied = (str(self.controller_root), str(repository / '.git'), str(worktree), str(self.approval_root))
            boundary = ExecutionBoundary(str(worker), denied)
            prompt = ('Read calculator.py and test_calculator.py. Fix the arithmetic defect by editing calculator.py only. '
                      'Run python3 -B -m unittest -v. Do not access any other path or network.')
            impl_output = self.evidence_root / ('implementer-' + str(attempt))
            outcome, _ = self._run_engine(task_id, 'repair' if attempt else 'implementer',
                                          self.implementer.engine, self.implementer.model, 60,
                                          lambda: self.implementer.run(worker, impl_output, boundary, prompt, self.policy))
            if outcome.status != 'succeeded':
                self._transition(task_id, implementation_from, 'blocked', 'implementation-blocked-' + str(attempt),
                                 'inspect implementation execution')
                break
            head, changed = self.broker.apply_worker_changes(repository, worktree, worker,
                                                              contract['scope'], 'Fix disposable arithmetic defect')
            if changed != ['calculator.py']:
                raise ControllerError('unexpected changed paths')
            self.store.set_head(task_id, head, authority=self.store.authority)
            self._transition(task_id, implementation_from, 'implemented', 'implemented-' + str(attempt),
                             'run independent checks')
            self._transition(task_id, 'implemented', 'verifying', 'verifying-' + str(attempt),
                             'evaluate immutable tests')
            verification, _ = self._run_engine(task_id, 'verification', 'local', 'python-unittest', 10,
                                                lambda: self._verify(worktree))
            artifact = self.store.put_artifact(json.dumps(verification.details, sort_keys=True))
            evidence_id = 'verification-' + str(attempt)
            evidence_status = 'passed' if verification.status == 'succeeded' else 'failed'
            self.store.add_evidence(task_id, evidence_id, head, 'independent-check', evidence_status,
                                    artifact, verification.details, authority=self.store.authority)
            verification_records.append({'id': evidence_id, 'revision': head,
                                         'status': evidence_status, 'artifact_sha256': artifact})
            if verification.status != 'succeeded':
                decision = self.store.record_failure(task_id, hashlib.sha256(artifact.encode()).hexdigest(),
                                                     verification.details['output'], authority=self.store.authority)
                if decision == 'repair_allowed':
                    self._transition(task_id, 'verifying', 'repairing', 'repair-check-' + str(attempt),
                                     'repair concrete verification failure')
                    attempt += 1
                    continue
                break
            self._transition(task_id, 'verifying', 'verified', 'verified-' + str(attempt), 'run independent review')
            self._transition(task_id, 'verified', 'reviewing', 'reviewing-' + str(attempt), 'evaluate review findings')
            snapshot = self.broker.export_snapshot(repository, head,
                                                   self.broker.review_copies / (task_id + '-' + str(attempt)), review=True)
            review_manifest = self.broker.manifest(snapshot)
            review_output = self.evidence_root / ('reviewer-' + str(attempt))
            review_prompt = ('Independently review this candidate against the requirement that total returns arithmetic sum '
                             'and tests cover positive and negative inputs. Identify only concrete material defects.')
            review, _ = self._run_engine(task_id, 'reviewer', self.reviewer.engine, self.reviewer.model, 60,
                                         lambda: self.reviewer.run(snapshot, head, review_output,
                                                                   review_prompt, self.policy))
            if self.broker.manifest(snapshot) != review_manifest:
                review = EngineOutcome('failed', review.elapsed_seconds, review.usage,
                                       {**review.details, 'boundary_error': 'reviewer modified read-only snapshot'},
                                       review.findings)
            review_findings = review.findings
            review_payload = {'status': review.status, 'findings': list(review.findings),
                              'details': review.details, 'revision': head}
            review_artifact = self.store.put_artifact(json.dumps(review_payload, sort_keys=True))
            self.store.add_evidence(task_id, 'review-' + str(attempt), head, 'independent-review',
                                    'passed' if review.status == 'succeeded' and not review.findings else 'failed',
                                    review_artifact, review_payload, authority=self.store.authority)
            if review.status != 'succeeded':
                self._transition(task_id, 'reviewing', 'blocked', 'review-blocked-' + str(attempt),
                                 'inspect invalid or failed review')
                break
            if review.findings:
                signature = hashlib.sha256(json.dumps(review.findings, sort_keys=True).encode()).hexdigest()
                decision = self.store.record_failure(task_id, signature, json.dumps(review.findings),
                                                     authority=self.store.authority)
                if decision == 'repair_allowed':
                    self._transition(task_id, 'reviewing', 'repairing', 'repair-review-' + str(attempt),
                                     'repair concrete review finding')
                    attempt += 1
                    continue
                break
            self._transition(task_id, 'reviewing', 'review_complete', 'reviewed-' + str(attempt),
                             'prepare local approval package')
            self._transition(task_id, 'review_complete', 'packaging', 'packaging', 'bind package to current head')
            package = self._package(task_id, repository, branch, base, head, verification_records, review_findings)
            digest = self.store.put_artifact(json.dumps(package, sort_keys=True))
            self.store.add_evidence(task_id, 'approval-package', head, 'approval-package', 'passed',
                                    digest, {'base_revision': base, 'head_revision': head},
                                    authority=self.store.authority)
            package['artifact_sha256'] = digest
            self._write_package(package)
            self._transition(task_id, 'packaging', 'awaiting_pr_approval', 'awaiting-pr-approval',
                             'await explicit user approval bound to this head')
            break
        snapshot = self.store.snapshot(task_id)
        self._write_state(snapshot)
        return {'task': self.store.task(task_id), 'snapshot': snapshot,
                'approval_package': self._read_package(), 'root': str(self.root)}

    def _package(self, task_id, repository, branch, base, head, verification, findings):
        snapshot = self.store.snapshot(task_id)
        budget = snapshot['budget']
        usage = []
        for record in snapshot['executions']:
            usage.append({'execution_id': record['execution_id'], 'role': record['role'],
                          'engine': record['engine'], 'elapsed_seconds': record['elapsed_seconds'],
                          'usage': json.loads(record['usage_json']) if record['usage_json'] else None})
        return {
            'schema_version': 1, 'task_id': task_id, 'status': 'awaiting_pr_approval',
            'summary': 'Correct arithmetic total implementation in the disposable fixture.',
            'repository': str(repository), 'branch': branch, 'base_revision': base,
            'head_revision': head, 'diff': self.broker.diff(repository, base, head),
            'verification': verification, 'review_findings': list(findings),
            'limitations': ['Trusted disposable macOS workflow only.',
                            'No publication, merge, hostile-code, detached-process or remote-cancellation support.',
                            'Reported usage is observational; billed cost remains unknown.'],
            'resources': {'budget': dict(budget), 'executions': usage},
            'proposed_pr': {'title': 'Fix disposable arithmetic total',
                            'body': 'Correct `total` to add its operands. Verified with the immutable unittest suite and independent review.'},
            'approval': {'recorded': False, 'note': 'Worker output is not approval; explicit head-bound user approval is required.'}
        }

    def _write_package(self, package):
        json_path = self.approval_root / 'approval-package.json'
        json_path.write_text(json.dumps(package, indent=2, allow_nan=False) + '\n')
        md = ('# Local PR approval package\n\n' + package['summary'] + '\n\n'
              '- Base: `' + package['base_revision'] + '`\n'
              '- Head: `' + package['head_revision'] + '`\n'
              '- Branch: `' + package['branch'] + '`\n'
              '- Status: `awaiting_pr_approval`\n\n'
              '## Proposed PR\n\n**' + package['proposed_pr']['title'] + '**\n\n' +
              package['proposed_pr']['body'] + '\n\n## Diff\n\n```diff\n' + package['diff'] + '\n```\n')
        (self.approval_root / 'approval-package.md').write_text(md)

    def _read_package(self):
        path = self.approval_root / 'approval-package.json'
        return json.loads(path.read_text()) if path.exists() else None

    def _write_state(self, snapshot):
        safe = json.loads(json.dumps(snapshot))
        (self.root / 'controller-state.json').write_text(json.dumps(safe, indent=2, allow_nan=False) + '\n')


def run_demo(directory, live=False, authorized=False, implementer_engine='codex'):
    if live and not authorized:
        raise ControllerError('live demonstration requires explicit existing-subscription authorization')
    if implementer_engine not in ('codex', 'claude'):
        raise ControllerError('unsupported implementer engine')
    reviewer_engine = 'claude' if implementer_engine == 'codex' else 'codex'
    implementer = LiveImplementer(implementer_engine) if live else FakeImplementer()
    reviewer = LiveReviewer(reviewer_engine) if live else FakeReviewer()
    workflow = DeliveryWorkflow(directory, implementer, reviewer, live_authorized=authorized)
    return workflow.run()
