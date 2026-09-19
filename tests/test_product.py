import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from agentkit.controller import ControllerError, UsageRecord
from agentkit.delivery import EngineOutcome
from agentkit.orchestration import DeterministicReviewer
from agentkit.product import (PRODUCT_PROJECT_POLICY, LiveProductPlanner, ProductPlanningError,
                              ProductWorkflow, StaticProductPlanner,
                              static_web_inventory, validate_product_document)
from agentkit.runtime_contracts import (CancellationStatus, ExecutionResult, UsageObservation)


BRIEF = 'Build a small accessible browser counter with keyboard and touch controls.'
ACCEPTANCE = [
    {'id': 'counter', 'expected': 'The counter increments and resets deterministically.'},
    {'id': 'interaction', 'expected': 'Keyboard and pointer controls expose readable labels.'},
]
MECHANICS = r'''import assert from 'node:assert/strict';
import app from './game.js';
assert.equal(app.increment(2), 3);
assert.equal(app.reset(), 0);
console.log('controller mechanics passed');
'''


def proposal(assignments=None):
    assignments = assignments or [{
        'id': 'implement-product',
        'objective': 'Implement the bounded counter product.',
        'allowed_paths': ['README.md', 'game.js', 'index.html', 'styles.css'],
        'dependencies': [],
        'interfaces': ['window and CommonJS expose increment and reset'],
    }]
    dependencies = [{'source': source, 'target': item['id']}
                    for item in assignments for source in item['dependencies']]
    interfaces = [{'assignment': item['id'], 'contract': contract}
                  for item in assignments for contract in item['interfaces']]
    return {
        'project': dict(PRODUCT_PROJECT_POLICY),
        'proposal': {
            'objective': BRIEF,
            'requirements': [{'source': 'user', 'text': BRIEF}],
            'assumptions': ['Use the controller-provided dependency-free static stack.'],
            'acceptance': list(ACCEPTANCE),
            'assignments': assignments,
            'interfaces': interfaces,
            'dependencies': dependencies,
            'integration_strategy': 'Apply broker-validated changes after dependencies succeed.',
            'verification_requirements': ['Run protected mechanics acceptance.'],
            'review_requirements': ['Review the exact verified candidate independently.'],
            'roles': ['chief_of_staff', 'tech_lead', 'implementer', 'verifier', 'reviewer'],
            'model_profiles': {'implementer': 'controller-route', 'repair': 'controller-route',
                               'reviewer': 'controller-independent-route'},
            'resource_allocations': {
                'implementation_calls': len(assignments),
                'verification_calls': 1,
                'review_calls': 1,
                'maximum_concurrent_implementers': min(2, len(assignments)),
            },
            'inventory_sha256': static_web_inventory()['sha256'],
            'planner': {'kind': 'provider-tech-lead', 'model_call': True},
        },
    }


FILES = {
    'README.md': '# Counter\n\nUse the + button, Enter, or Space. Use Reset to restart.\n',
    'game.js': r'''function increment(value) { return value + 1; }
function reset() { return 0; }
const api = { increment, reset };
if (typeof module !== 'undefined') module.exports = api;
if (typeof document !== 'undefined') {
  let value = 0;
  const output = document.querySelector('#value');
  const draw = () => { output.textContent = String(value); };
  document.querySelector('#increment').addEventListener('click', () => { value = increment(value); draw(); });
  document.querySelector('#reset').addEventListener('click', () => { value = reset(); draw(); });
  document.addEventListener('keydown', event => {
    if (event.key === 'Enter' || event.key === ' ') { value = increment(value); draw(); }
  });
  draw();
}
''',
    'index.html': '''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="styles.css"><title>Counter</title>
<main><h1>Counter</h1><output id="value" aria-live="polite">0</output>
<button id="increment" type="button">Add one</button>
<button id="reset" type="button">Reset</button></main><script src="game.js"></script></html>\n''',
    'styles.css': 'body{font:18px system-ui;margin:2rem}button{min-height:44px;margin:.5rem}\n',
}


class ProductSpecialist:
    engine = 'codex'
    model = None

    def __init__(self):
        self.prompts = []

    def run_assignment(self, workspace, assignment, output, boundary, prompt, policy):
        self.prompts.append(prompt)
        for relative in assignment['allowed_paths']:
            Path(workspace, relative).write_text(FILES[relative])
        return EngineOutcome('succeeded', .01, UsageRecord(source='fake'), {'simulated': True})


class ProductTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='agentkit-product-test-')
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def workflow(self, name='product', document=None, **kwargs):
        specialist = ProductSpecialist()
        workflow = ProductWorkflow.submit_product(
            self.root / name, name, BRIEF, ACCEPTANCE, MECHANICS,
            planner=StaticProductPlanner(document or proposal()), live=False,
            max_repairs=kwargs.pop('max_repairs', 0),
            max_escalations=kwargs.pop('max_escalations', 0), **kwargs)
        workflow.specialist_factory = lambda provider, fixture: specialist
        workflow.reviewer_override = DeterministicReviewer('claude')
        return workflow, specialist

    def test_provider_plan_is_validated_and_drives_a_disposable_product(self):
        workflow, specialist = self.workflow()
        plan = workflow.state.plan('product')['plan']
        self.assertEqual(plan['management_calls'], 1)
        self.assertEqual(plan['proposal']['planner']['kind'], 'provider-tech-lead')
        self.assertEqual(plan['proposal']['planner']['provider'], 'claude')
        result = workflow.start('product')
        self.assertEqual(result['task']['state'], 'review_complete')
        self.assertIn('VERIFIED_SKILL_CONTEXT_JSON', specialist.prompts[0])
        worktree = Path(result['task']['worktree'])
        self.assertEqual((worktree / 'game.js').read_text(), FILES['game.js'])
        self.assertFalse((worktree / 'controller-acceptance.mjs').exists())
        self.assertNotIn(workflow.controller_root, worktree.parents)
        evidence = workflow.store.snapshot('product')['evidence']
        verification = next(item for item in evidence if item['kind'] == 'independent-check')
        self.assertEqual(verification['status'], 'passed')
        self.assertEqual(verification['revision'], result['task']['head_revision'])

    def test_browser_gate_binds_evidence_and_package_to_exact_revision(self):
        workflow, _ = self.workflow('browser')
        result = workflow.start('browser')
        head = result['task']['head_revision']
        self.assertIsNone(result['approval_package'])
        (workflow.evidence_root / 'preview-session.json').write_text(json.dumps({
            'candidate_revision': head, 'status': 'stopped', 'cleanup_confirmed': True,
            'test_fixture': True,
        }))
        evidence = {
            'schema_version': 1,
            'candidate_revision': head,
            'browser': {'name': 'fixture-browser', 'version': 'fixture'},
            'checks': [{'id': item['id'], 'status': 'passed',
                        'observation': 'fixture observed ' + item['id']}
                       for item in ACCEPTANCE],
            'screenshots': [],
            'visual_judgment': 'user_review_required',
            'preview_cleanup': True,
        }
        final = workflow.record_browser_evidence('browser', evidence)
        self.assertEqual(final['task']['state'], 'awaiting_pr_approval')
        package = final['approval_package']
        self.assertEqual(package['head_revision'], head)
        self.assertFalse(package['approval']['recorded'])
        self.assertEqual(package['browser_verification'][0]['revision'], head)

    def test_preview_process_lifecycle_when_loopback_is_available(self):
        workflow, _ = self.workflow('preview')
        workflow.start('preview')
        stop = threading.Event()
        ready = threading.Event()
        observed = {}
        errors = []

        def serve():
            try:
                workflow.serve_preview(
                    'preview', stop_event=stop,
                    ready_callback=lambda session: (observed.update(session), ready.set()))
            except Exception as exc:
                errors.append(exc)

        thread = threading.Thread(target=serve, daemon=True)
        try:
            thread.start()
            thread.join(.2)
            if not thread.is_alive() and not ready.is_set():
                self.skipTest(str(errors[0]) if errors else
                              'loopback preview is unavailable in this execution context')
            self.assertTrue(ready.wait(3))
            self.assertTrue(observed['url'].startswith('http://127.0.0.1:'))
        finally:
            stop.set()
            thread.join(3)
        if ready.is_set():
            session = json.loads((workflow.evidence_root / 'preview-session.json').read_text())
            self.assertEqual(session['status'], 'stopped')
            self.assertTrue(session['cleanup_confirmed'])

    def test_browser_evidence_rejects_a_changed_candidate(self):
        workflow, _ = self.workflow('stale')
        result = workflow.start('stale')
        Path(result['task']['worktree'], 'styles.css').write_text('changed outside controller')
        evidence = {
            'schema_version': 1, 'candidate_revision': result['task']['head_revision'],
            'browser': {'name': 'fixture-browser'},
            'checks': [{'id': item['id'], 'status': 'passed', 'observation': 'observed'}
                       for item in ACCEPTANCE],
            'screenshots': [], 'visual_judgment': 'user_review_required',
            'preview_cleanup': True,
        }
        with self.assertRaisesRegex(ControllerError, 'another candidate'):
            workflow.record_browser_evidence('stale', evidence)
        self.assertIsNone(workflow.result('stale')['approval_package'])

    def test_untrusted_product_plans_fail_before_implementation(self):
        inventory = static_web_inventory()
        unsafe = proposal()
        unsafe['proposal']['assignments'][0]['allowed_paths'] = ['../controller/state']
        with self.assertRaisesRegex(ProductPlanningError, 'path authority'):
            validate_product_document(unsafe, BRIEF, ACCEPTANCE, inventory,
                                      max_subtasks=2, max_concurrency=2)
        cyclic = proposal([
            {'id': 'implement-a', 'objective': 'A',
             'allowed_paths': ['game.js', 'README.md'],
             'dependencies': ['implement-b'], 'interfaces': ['A']},
            {'id': 'implement-b', 'objective': 'B',
             'allowed_paths': ['index.html', 'styles.css'],
             'dependencies': ['implement-a'], 'interfaces': ['B']},
        ])
        with self.assertRaisesRegex(ProductPlanningError, 'cycle'):
            validate_product_document(cyclic, BRIEF, ACCEPTANCE, inventory,
                                      max_subtasks=2, max_concurrency=2)
        changed_acceptance = proposal()
        changed_acceptance['proposal']['acceptance'] = [{'id': 'weak', 'expected': 'screenshot'}]
        with self.assertRaisesRegex(ProductPlanningError, 'acceptance'):
            validate_product_document(changed_acceptance, BRIEF, ACCEPTANCE, inventory,
                                      max_subtasks=2, max_concurrency=2)

    def test_mandatory_plan_capacity_is_checked_after_planning(self):
        two = proposal([
            {'id': 'implement-logic', 'objective': 'Logic',
             'allowed_paths': ['game.js', 'README.md'], 'dependencies': [],
             'interfaces': ['logic API']},
            {'id': 'implement-ui', 'objective': 'UI',
             'allowed_paths': ['index.html', 'styles.css'], 'dependencies': [],
             'interfaces': ['DOM API']},
        ])
        workflow = ProductWorkflow.submit_product(
            self.root / 'budget', 'budget', BRIEF, ACCEPTANCE, MECHANICS,
            planner=StaticProductPlanner(two), max_calls=4, max_provider_calls=3,
            max_concurrency=2, max_repairs=0, max_escalations=0, live=False)
        self.assertEqual(workflow.store.task('budget')['state'], 'blocked')
        rejection = json.loads((workflow.root / 'planner-rejection.json').read_text())
        self.assertIn('cannot fit', rejection['reason'])

    def test_changed_product_spec_is_rejected_before_worker_execution(self):
        workflow, specialist = self.workflow('changed-spec')
        spec = workflow.root / 'product-spec.json'
        value = json.loads(spec.read_text())
        value['fixture']['acceptance_test'] = 'console.log("weakened")\n'
        spec.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
        with self.assertRaisesRegex(ProductPlanningError, 'changed after planning'):
            workflow.start('changed-spec')
        self.assertEqual(specialist.prompts, [])

    def test_live_planner_constructs_the_real_model_only_request(self):
        captured = {}

        def fake_execute(request, output, policy, cancel_event=None):
            captured['request'] = request
            return ExecutionResult(
                'claude', request.task_id, 'succeeded', None, 0, .1,
                structured_output=proposal(), usage=UsageObservation(source='fixture', final=True),
                cancellation=CancellationStatus(), provider_details={})

        output = self.root / 'planner-output'
        with patch('agentkit.product.execute', side_effect=fake_execute):
            result = LiveProductPlanner('claude', model=None, effort='low',
                                        timeout_seconds=12).run(
                'bounded prompt with verified planning skill content', output, object())
        request = captured['request']
        self.assertEqual((request.engine, request.mode, request.effort, request.timeout_seconds),
                         ('claude', 'model-only', 'low', 12))
        self.assertEqual(request.max_generated_output_tokens, 8192)
        self.assertIn('verified planning skill content', request.prompt)
        self.assertIsNone(result.details['provider_reported_configuration']['model'])

    def test_screenshot_records_are_hash_checked_inside_evidence_root(self):
        workflow, _ = self.workflow('screenshot')
        result = workflow.start('screenshot')
        screenshot = workflow.evidence_root / 'actual.png'
        screenshot.write_bytes(b'fixture png')
        (workflow.evidence_root / 'preview-session.json').write_text(json.dumps({
            'candidate_revision': result['task']['head_revision'], 'status': 'stopped',
            'cleanup_confirmed': True, 'test_fixture': True,
        }))
        evidence = {
            'schema_version': 1, 'candidate_revision': result['task']['head_revision'],
            'browser': {'name': 'fixture-browser'},
            'checks': [{'id': item['id'], 'status': 'passed', 'observation': 'observed'}
                       for item in ACCEPTANCE],
            'screenshots': [{'path': 'actual.png',
                             'sha256': hashlib.sha256(b'fixture png').hexdigest(),
                             'viewport': '800x600'}],
            'visual_judgment': 'user_review_required', 'preview_cleanup': True,
        }
        evidence['screenshots'][0]['sha256'] = '0' * 64
        with self.assertRaisesRegex(ControllerError, 'changed'):
            workflow.record_browser_evidence('screenshot', evidence)


if __name__ == '__main__':
    unittest.main()
