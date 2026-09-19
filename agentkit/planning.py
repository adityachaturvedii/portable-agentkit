"""Request-driven planning for bounded controller-created disposable projects."""

from dataclasses import dataclass
import hashlib
import json
from pathlib import PurePosixPath

from .controller import ControllerError


class ClarificationRequired(ControllerError):
    """The request contains a material contradiction that deterministic policy cannot resolve."""

    def __init__(self, questions):
        self.questions = tuple(questions)
        super().__init__('clarification required: ' + '; '.join(self.questions))


def bounded_inventory(fixture):
    """Describe controller-owned project shape without exposing expected solutions."""
    files = []
    for path, content in sorted(fixture.files.items()):
        files.append({'path': path, 'bytes': len(content.encode()),
                      'sha256': hashlib.sha256(content.encode()).hexdigest()})
    payload = {'project': fixture.fixture_id, 'files': files,
               'interfaces': sorted({interface for subtask in fixture.subtasks
                                     for interface in subtask.interfaces})}
    payload['sha256'] = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return payload


def _request_tokens(request):
    return {token.strip('.,:;()[]{}').lower() for token in request.split() if token.strip()}


def _selected_subtasks(request, fixture):
    tokens = _request_tokens(request)
    lower = request.lower()
    contradictory = (
        ('lowercase' in lower and 'uppercase' in lower) or
        ('preserve case' in lower and ('lowercase' in lower or 'uppercase' in lower))
    )
    if contradictory:
        raise ClarificationRequired((
            'Choose one output case policy: preserve case, lowercase, or uppercase.',
        ))
    matched = [subtask for subtask in fixture.subtasks
               if subtask.request_terms and tokens.intersection(subtask.request_terms)]
    selected = {item.subtask_id: item for item in (matched or fixture.subtasks)}
    pending = list(selected.values())
    while pending:
        current = pending.pop()
        for dependency in current.dependencies:
            if dependency not in selected:
                value = next((item for item in fixture.subtasks
                              if item.subtask_id == dependency), None)
                if value is None:
                    raise ValueError('project scenario contains an unknown subtask dependency')
                selected[dependency] = value
                pending.append(value)
    return tuple(item for item in fixture.subtasks if item.subtask_id in selected)


def _acceptance_for(fixture, subtasks):
    if len(subtasks) == len(fixture.subtasks):
        return [dict(item) for item in fixture.acceptance]
    criteria = []
    for subtask in subtasks:
        criteria.extend(dict(item) for item in subtask.acceptance)
    if not criteria:
        raise ValueError('selected project assignments have no observable acceptance criteria')
    return criteria


def propose(request, fixture, *, planner='deterministic-controller'):
    """Build an inspectable proposal from request, inventory, and declared interfaces."""
    if not isinstance(request, str) or not request.strip():
        raise ValueError('task request must be a nonempty bounded string')
    inventory = bounded_inventory(fixture)
    subtasks = _selected_subtasks(request, fixture)
    assignments = []
    dependencies = []
    interfaces = []
    for subtask in subtasks:
        assignment_id = 'implement-' + subtask.subtask_id
        deps = ['implement-' + item for item in subtask.dependencies]
        assignments.append({'id': assignment_id, 'objective': subtask.objective,
                            'allowed_paths': list(subtask.allowed_paths),
                            'dependencies': deps,
                            'interfaces': list(subtask.interfaces)})
        dependencies.extend({'source': dependency, 'target': assignment_id}
                            for dependency in deps)
        interfaces.extend({'assignment': assignment_id, 'contract': item}
                          for item in subtask.interfaces)
    mode = 'single' if len(assignments) == 1 else 'decomposed'
    assumptions = [
        'The target is the named controller-created disposable project.',
        'Only declared tracked source paths may change.',
        'No network, dependency installation, publication, deployment, or external repository access is authorized.',
        'Configured account-default models have unknown comparative price and quality unless evidence says otherwise.',
    ]
    return {
        'objective': request.strip(),
        'requirements': [{'source': 'user', 'text': request.strip()}],
        'assumptions': assumptions,
        'acceptance': _acceptance_for(fixture, subtasks),
        'assignments': assignments,
        'interfaces': interfaces,
        'dependencies': dependencies,
        'integration_strategy': ('apply one broker-validated contribution' if mode == 'single' else
                                 'integrate declared non-overlapping contributions after dependencies succeed'),
        'verification_requirements': ['controller-owned acceptance on the exact integrated revision',
                                      'candidate unchanged by verification'],
        'review_requirements': ['independent read-only review of the verified revision'],
        'roles': (['chief_of_staff', 'tech_lead', 'implementer', 'verifier', 'reviewer']
                  if mode == 'single' else
                  ['chief_of_staff', 'tech_lead', 'manager', 'implementer', 'verifier', 'reviewer']),
        'model_profiles': {'implementer': 'selected by validated routing registry',
                           'repair': 'selected separately and used only after concrete failure',
                           'reviewer': 'independent provider required for material work'},
        'resource_allocations': {'implementation_calls': len(assignments),
                                 'verification_calls': 1, 'review_calls': 1,
                                 'maximum_concurrent_implementers': min(2, len(assignments))},
        'inventory_sha256': inventory['sha256'],
        'planner': {'kind': planner, 'model_call': planner != 'deterministic-controller'},
    }


def validate_proposal(proposal, fixture, contract):
    """Validate untrusted planner output against controller-owned authority and budgets."""
    required = {'objective', 'requirements', 'assumptions', 'acceptance', 'assignments',
                'interfaces', 'dependencies', 'integration_strategy',
                'verification_requirements', 'review_requirements', 'roles', 'model_profiles',
                'resource_allocations', 'inventory_sha256', 'planner'}
    if not isinstance(proposal, dict) or set(proposal) != required:
        raise ValueError('planner output has an unsupported shape')
    if proposal['inventory_sha256'] != bounded_inventory(fixture)['sha256']:
        raise ValueError('planner output targets a stale project inventory')
    proposed_ids = {assignment['id'].removeprefix('implement-')
                    for assignment in proposal.get('assignments', ())}
    selected = tuple(item for item in fixture.subtasks if item.subtask_id in proposed_ids)
    if proposal['acceptance'] != _acceptance_for(fixture, selected):
        raise ValueError('planner output changed controller-owned acceptance')
    if not proposal['assignments'] or len(proposal['assignments']) > contract.max_subtasks:
        raise ValueError('planner output exceeds the subtask bound')
    known_scope = set(contract.scope)
    identifiers = set()
    paths_by_id = {}
    for assignment in proposal['assignments']:
        if set(assignment) != {'id', 'objective', 'allowed_paths', 'dependencies', 'interfaces'}:
            raise ValueError('planner assignment is incomplete')
        if assignment['id'] in identifiers:
            raise ValueError('planner output contains duplicate assignments')
        identifiers.add(assignment['id'])
        paths = set(assignment['allowed_paths'])
        if not paths or not paths <= known_scope:
            raise ValueError('planner output expands path authority')
        for value in paths:
            path = PurePosixPath(value)
            if path.is_absolute() or '..' in path.parts or value.startswith(('.git', 'controller')):
                raise ValueError('planner output contains an unsafe path')
        paths_by_id[assignment['id']] = paths
    graph = {assignment['id']: set(assignment['dependencies'])
             for assignment in proposal['assignments']}
    if any(not deps <= identifiers for deps in graph.values()):
        raise ValueError('planner dependency references an unknown assignment')
    for left in identifiers:
        for right in identifiers:
            if left < right and not graph[left] and not graph[right] and paths_by_id[left] & paths_by_id[right]:
                raise ValueError('independent assignments cannot share writable paths')
    ready = [node for node, deps in graph.items() if not deps]
    visited = set()
    while ready:
        node = ready.pop()
        visited.add(node)
        for candidate, deps in graph.items():
            if node in deps:
                deps.remove(node)
                if not deps and candidate not in visited:
                    ready.append(candidate)
    if visited != identifiers:
        raise ValueError('planner output contains a dependency cycle')
    allocations = proposal['resource_allocations']
    planning_calls = 1 if proposal['planner'].get('model_call') else 0
    mandatory_calls = allocations.get('implementation_calls', -1) + 2 + planning_calls
    if (mandatory_calls > contract.max_calls or
            allocations.get('implementation_calls') != len(identifiers) or
            allocations.get('maximum_concurrent_implementers', 0) > contract.max_concurrency):
        raise ValueError('proposed plan cannot fit the call or concurrency budget')
    provider_calls = len(identifiers) + 1 + planning_calls
    if (provider_calls > contract.max_provider_calls or
            planning_calls > contract.max_planning_calls):
        raise ValueError('proposed plan cannot fit the provider or planning call budget')
    allocated_time = (len(identifiers) * contract.implementation_timeout_seconds +
                      contract.verification_timeout_seconds + contract.review_timeout_seconds)
    if allocated_time > contract.max_elapsed_seconds:
        raise ValueError('proposed plan cannot fit the allocated execution-time budget')
    return proposal
