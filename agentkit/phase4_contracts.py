"""Validated Phase 4 intake, role, graph, routing, and budget contracts."""

from dataclasses import asdict, dataclass
import math
from pathlib import PurePosixPath
from typing import Dict, Optional, Tuple


PHASE4_SCHEMA_VERSION = 1
MAX_GRAPH_NODES = 12
MAX_IMPLEMENTATION_NODES = 2
MAX_REPAIR_ATTEMPTS = 2


@dataclass(frozen=True)
class RoleContract:
    role: str
    inputs: Tuple[str, ...]
    outputs: Tuple[str, ...]
    allowed_tools: Tuple[str, ...]
    scope: str
    completion: str
    escalation: str


ROLE_CONTRACTS = {
    'chief_of_staff': RoleContract(
        'chief_of_staff', ('user request', 'controller status'),
        ('validated intake', 'concise status', 'attention request'), ('controller-read',),
        'intent, priorities, and user-facing checkpoints',
        'requirements and assumptions are separated and next action is explicit',
        'material ambiguity, authority change, access need, or final approval'),
    'tech_lead': RoleContract(
        'tech_lead', ('validated intake', 'fixture contract'),
        ('decomposition', 'interfaces', 'acceptance design'), ('controller-read',),
        'technical plan and controller-owned integration decisions',
        'bounded acyclic implementation graph and immutable acceptance are recorded',
        'contradictory requirements or unsupported integration'),
    'manager': RoleContract(
        'manager', ('validated graph', 'budget ledger'),
        ('dependency schedule', 'bounded allocations'), ('controller-read',),
        'at most two independent implementation assignments',
        'dependencies, concurrency, and verification/review reserves are valid',
        'capacity exhaustion or unresolved execution ownership'),
    'implementer': RoleContract(
        'implementer', ('assignment', 'candidate revision', 'bounded feedback'),
        ('candidate changes', 'structured execution result'), ('owned-code',),
        'one controller-created worker copy and declared paths only',
        'allowed changes are brokered into the assigned worktree',
        'authentication, sandbox failure, failed acceptance, or authority request'),
    'reviewer': RoleContract(
        'reviewer', ('immutable candidate', 'task contract', 'evidence references'),
        ('validated concrete findings',), ('model-only',),
        'read-only independent review of one exact revision',
        'no findings or actionable material findings with criteria',
        'authentication, unavailable cross-provider review, or unresolved finding'),
    'verifier': RoleContract(
        'verifier', ('immutable candidate', 'controller acceptance test'),
        ('measured evidence',), ('local-seatbelt',),
        'fresh controller-created verification copy',
        'candidate remains unchanged and independent acceptance passes',
        'sandbox unavailable, failed check, or candidate identity change'),
}


def _bounded_text(value, name, maximum=8192):
    if not isinstance(value, str) or not value.strip() or len(value.encode()) > maximum:
        raise ValueError(name + ' must be a nonempty bounded string')
    return value.strip()


@dataclass(frozen=True)
class TaskContract:
    task_id: str
    user_request: str
    objective: str
    scope: Tuple[str, ...]
    acceptance: Tuple[dict, ...]
    non_goals: Tuple[str, ...]
    dependencies: Tuple[str, ...]
    risk: str
    difficulty: str
    execution_profile: str
    assumptions: Tuple[str, ...]
    max_calls: int
    max_elapsed_seconds: float
    max_concurrency: int
    max_timeout_seconds: float
    verification_reserve: int
    review_reserve: int
    max_subtasks: int
    max_output_bytes_per_call: int = 1048576
    context_allocation: str = 'provider-managed-unknown'
    max_repairs: int = 2
    schema_version: int = PHASE4_SCHEMA_VERSION

    def __post_init__(self):
        _bounded_text(self.task_id, 'task id', 128)
        _bounded_text(self.user_request, 'user request')
        _bounded_text(self.objective, 'objective')
        if self.risk not in ('routine', 'material') or self.difficulty not in ('routine', 'substantial'):
            raise ValueError('unsupported risk or difficulty')
        if self.execution_profile != 'trusted-disposable-macos':
            raise ValueError('only the tested trusted disposable macOS profile is supported')
        if (not self.scope or not self.acceptance or
                any(not isinstance(path, str) or not path for path in self.scope) or
                any(not isinstance(item, dict) or not item.get('id') or not item.get('expected')
                    for item in self.acceptance)):
            raise ValueError('scope and observable acceptance criteria are required')
        for value in self.scope:
            path = PurePosixPath(value)
            if (path.is_absolute() or '..' in path.parts or value.startswith('.git') or
                    value.startswith('controller')):
                raise ValueError('task scope expands worker authority')
        if (not self.assumptions or not self.non_goals or
                any(not isinstance(value, str) or not value for value in
                    self.assumptions + self.non_goals + self.dependencies)):
            raise ValueError('assumptions, non-goals, and dependencies must be bounded strings')
        if type(self.schema_version) is not int or self.schema_version != PHASE4_SCHEMA_VERSION:
            raise ValueError('unsupported Phase 4 contract schema')
        integer_limits = (self.max_calls, self.max_concurrency, self.verification_reserve,
                          self.review_reserve, self.max_subtasks, self.max_repairs,
                          self.max_output_bytes_per_call)
        if any(type(value) is not int for value in integer_limits):
            raise ValueError('budget counts must be integers')
        if (self.max_calls < 3 or self.max_concurrency < 1 or self.max_concurrency > 2 or
                self.verification_reserve < 1 or self.review_reserve < 1 or
                self.verification_reserve + self.review_reserve >= self.max_calls or
                self.max_subtasks < 1 or self.max_subtasks > MAX_IMPLEMENTATION_NODES or
                self.max_repairs < 0 or self.max_repairs > MAX_REPAIR_ATTEMPTS or
                not 1024 <= self.max_output_bytes_per_call <= 4194304):
            raise ValueError('invalid Phase 4 count budget')
        if self.context_allocation != 'provider-managed-unknown':
            raise ValueError('provider context allocation is not enforceable by the tested CLIs')
        for value in (self.max_elapsed_seconds, self.max_timeout_seconds):
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError('time budgets must be finite positive numbers')

    def controller_contract(self):
        return {
            'objective': self.objective,
            'scope': list(self.scope),
            'acceptance': list(self.acceptance),
            'non_goals': list(self.non_goals),
            'risk': self.risk,
            'execution_profile': self.execution_profile,
            'requirements': {'user_request': self.user_request},
            'assumptions': list(self.assumptions),
        }

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class ModelProfile:
    profile_id: str
    provider: str
    model: Optional[str]
    effort: Optional[str]
    roles: Tuple[str, ...]
    capabilities: Tuple[str, ...]
    relative_cost: str
    evidence: str
    enabled: bool = True

    def __post_init__(self):
        _bounded_text(self.profile_id, 'profile id', 128)
        if self.provider not in ('codex', 'claude'):
            raise ValueError('unsupported provider')
        if self.model is not None:
            _bounded_text(self.model, 'model identifier', 128)
        if self.effort is not None:
            _bounded_text(self.effort, 'effort', 32)
        if self.relative_cost not in ('unknown', 'lower', 'higher'):
            raise ValueError('invalid relative cost evidence')
        if not self.roles or not self.capabilities:
            raise ValueError('model profile requires roles and capabilities')


@dataclass(frozen=True)
class RouteDecision:
    node_id: str
    role: str
    profile_id: str
    provider: str
    model: Optional[str]
    effort: Optional[str]
    reason: str
    relative_cost: str

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class GraphNode:
    node_id: str
    role: str
    kind: str
    objective: str
    dependencies: Tuple[str, ...] = ()
    allowed_paths: Tuple[str, ...] = ()
    provider: Optional[str] = None
    model: Optional[str] = None
    effort: Optional[str] = None
    routing_reason: Optional[str] = None
    max_attempts: int = 1
    initial_status: str = 'pending'

    def __post_init__(self):
        _bounded_text(self.node_id, 'node id', 128)
        _bounded_text(self.objective, 'node objective', 2048)
        if self.role not in ROLE_CONTRACTS or self.kind not in (
                'intake', 'plan', 'schedule', 'implementation', 'integration',
                'verification', 'review', 'repair', 'package'):
            raise ValueError('unsupported graph role or kind')
        if type(self.max_attempts) is not int or not 1 <= self.max_attempts <= 3:
            raise ValueError('node attempts must be between one and three')
        if self.initial_status not in ('pending', 'succeeded', 'dormant'):
            raise ValueError('invalid initial node status')
        if self.kind in ('implementation', 'repair', 'review') and self.provider not in ('codex', 'claude'):
            raise ValueError('model nodes require a supported provider')
        if self.kind in ('implementation', 'repair') and not self.allowed_paths:
            raise ValueError('implementation nodes require bounded paths')
        for value in self.allowed_paths:
            if not isinstance(value, str) or not value:
                raise ValueError('allowed paths must be nonempty relative paths')
            path = PurePosixPath(value)
            if (path.is_absolute() or '..' in path.parts or value.startswith('.git') or
                    value.startswith('controller')):
                raise ValueError('allowed path expands worker authority')

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class GraphEdge:
    source: str
    target: str
    edge_type: str = 'dependency'
    max_iterations: int = 0

    def __post_init__(self):
        if self.edge_type not in ('dependency', 'bounded_repair'):
            raise ValueError('unsupported graph edge type')
        if self.edge_type == 'dependency' and self.max_iterations != 0:
            raise ValueError('dependency edges cannot have iterations')
        if self.edge_type == 'bounded_repair' and self.max_iterations not in (1, 2):
            raise ValueError('repair edges must be explicitly bounded')

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class ExecutionPlan:
    task_id: str
    mode: str
    nodes: Tuple[GraphNode, ...]
    edges: Tuple[GraphEdge, ...]
    routes: Tuple[RouteDecision, ...]
    selected_skills: Tuple[dict, ...]
    management_calls: int = 0
    schema_version: int = PHASE4_SCHEMA_VERSION

    def __post_init__(self):
        if self.mode not in ('single', 'decomposed') or not self.nodes or len(self.nodes) > MAX_GRAPH_NODES:
            raise ValueError('invalid bounded execution plan')
        identifiers = [node.node_id for node in self.nodes]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError('duplicate graph node')
        known = set(identifiers)
        if any(edge.source not in known or edge.target not in known for edge in self.edges):
            raise ValueError('graph edge references an unknown node')
        implementations = [node for node in self.nodes if node.kind == 'implementation']
        if not 1 <= len(implementations) <= MAX_IMPLEMENTATION_NODES:
            raise ValueError('plan requires one or two implementation nodes')
        if self.mode == 'single' and len(implementations) != 1:
            raise ValueError('single mode requires one implementation node')
        if self.mode == 'decomposed' and len(implementations) < 2:
            raise ValueError('decomposed mode requires independent subtasks')
        normal = {node_id: set() for node_id in identifiers}
        for edge in self.edges:
            if edge.edge_type == 'dependency':
                normal[edge.target].add(edge.source)
            elif not ({edge.source, edge.target} &
                      {node.node_id for node in self.nodes if node.kind == 'repair'}):
                raise ValueError('bounded repair edges must involve the repair node')
        for node in self.nodes:
            if set(node.dependencies) != normal[node.node_id]:
                raise ValueError('node dependencies must match dependency edges')
        ready = [node_id for node_id, deps in normal.items() if not deps]
        visited = []
        while ready:
            current = ready.pop()
            visited.append(current)
            for target in normal:
                if current in normal[target]:
                    normal[target].remove(current)
                    if not normal[target] and target not in visited and target not in ready:
                        ready.append(target)
        if len(visited) != len(identifiers):
            raise ValueError('ordinary graph dependencies must be acyclic')
        if type(self.management_calls) is not int or self.management_calls != 0:
            raise ValueError('Phase 4 planning roles are deterministic and consume no model calls')

    def to_dict(self):
        return asdict(self)


class ModelRegistry:
    def __init__(self, profiles, defaults):
        profiles = tuple(profiles)
        self.profiles = {profile.profile_id: profile for profile in profiles}
        self.defaults = dict(defaults)
        if len(self.profiles) != len(profiles):
            raise ValueError('duplicate model profile')
        for role, profile_id in self.defaults.items():
            if profile_id not in self.profiles or role not in self.profiles[profile_id].roles:
                raise ValueError('registry default is incompatible with its role')

    @classmethod
    def account_defaults(cls, implementer='codex', reviewer='claude'):
        profiles = (
            ModelProfile('codex-account-default', 'codex', None, None,
                         ('implementer', 'repair', 'reviewer'), ('owned-code', 'model-only'),
                         'unknown', 'Installed CLI/account default; exact model and relative cost are unknown.'),
            ModelProfile('claude-account-default', 'claude', None, None,
                         ('implementer', 'repair', 'reviewer'), ('owned-code', 'model-only'),
                         'unknown', 'Installed CLI/account default; exact model and relative cost are unknown.'),
        )
        return cls(profiles, {'implementer': implementer + '-account-default',
                              'repair': implementer + '-account-default',
                              'reviewer': reviewer + '-account-default'})

    def route(self, node_id, role, required_capability, *, exclude_provider=None):
        preferred = self.profiles[self.defaults[role]]
        candidates = [profile for profile in self.profiles.values()
                      if profile.enabled and role in profile.roles and
                      required_capability in profile.capabilities and
                      profile.provider != exclude_provider]
        lower_cost = [profile for profile in candidates if profile.relative_cost == 'lower']
        selected = (lower_cost[0] if lower_cost else
                    preferred if preferred in candidates else
                    candidates[0] if candidates else None)
        if selected is None:
            raise ValueError('no configured model profile satisfies ' + role)
        reason = ('Configured profile satisfies the tested ' + required_capability +
                  ' capability. Exact availability is checked by the read-only provider preflight at execution. '
                  + ('Available evidence marks it lower relative cost. '
                     if selected.relative_cost == 'lower' else
                     'Relative price and quality are unknown, so the explicit default is used. ') +
                  'No larger or second model is added.')
        if exclude_provider:
            reason += ' Provider differs from implementation for independent review.'
        return RouteDecision(node_id, role, selected.profile_id, selected.provider,
                             selected.model, selected.effort, reason, selected.relative_cost)

    def to_dict(self):
        return {'schema_version': PHASE4_SCHEMA_VERSION,
                'profiles': [asdict(value) for value in self.profiles.values()],
                'defaults': self.defaults}
