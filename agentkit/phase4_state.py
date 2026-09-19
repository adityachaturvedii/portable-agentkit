"""Phase 4 graph persistence in the authoritative controller database."""

import hashlib
import json
import uuid

from .controller import ControllerError, _json, _now
from .phase4_contracts import ExecutionPlan, TaskContract


NODE_TRANSITIONS = {
    'pending': {'running', 'blocked', 'cancelled'},
    'dormant': {'running', 'cancelled'},
    'running': {'succeeded', 'failed', 'authentication_required', 'cancelled'},
    'authentication_required': {'pending', 'cancelled'},
    'failed': {'pending', 'running', 'blocked', 'cancelled'},
    'succeeded': {'pending'},  # quality nodes reset explicitly; success is never directly re-claimed
    'blocked': set(),
    'cancelled': set(),
}


class Phase4State:
    def __init__(self, store):
        self.store = store

    def _require(self, authority):
        self.store._require(authority)

    def record_intake(self, contract, fixture_id, *, authority=None):
        self._require(authority)
        if not isinstance(contract, TaskContract):
            raise ControllerError('validated Phase 4 task contract required')
        now = _now()
        with self.store.transaction() as db:
            task = db.execute('SELECT state FROM tasks WHERE task_id=?', (contract.task_id,)).fetchone()
            if not task or task['state'] != 'received':
                raise ControllerError('intake requires a received task')
            db.execute('''INSERT INTO phase4_intake(task_id,request_text,fixture_id,
                          requirements_json,assumptions_json,execution_profile,created_at)
                          VALUES(?,?,?,?,?,?,?)''',
                       (contract.task_id, contract.user_request, fixture_id,
                        _json({'user_request': contract.user_request}),
                        _json(list(contract.assumptions)), contract.execution_profile, now))
            db.execute('''INSERT INTO phase4_controls(task_id,updated_at) VALUES(?,?)''',
                       (contract.task_id, now))
            self.store._append(db, contract.task_id,
                               contract.task_id + '-phase4-intake-' + str(uuid.uuid4()),
                               'phase4_intake_recorded',
                               {'fixture_id': fixture_id, 'execution_profile': contract.execution_profile})

    def record_plan(self, plan, *, authority=None):
        self._require(authority)
        if not isinstance(plan, ExecutionPlan):
            raise ControllerError('validated Phase 4 execution plan required')
        raw = _json(plan.to_dict())
        digest = hashlib.sha256(raw.encode()).hexdigest()
        now = _now()
        with self.store.transaction() as db:
            task = db.execute('SELECT state FROM tasks WHERE task_id=?', (plan.task_id,)).fetchone()
            if not task or task['state'] != 'contracted':
                raise ControllerError('plan requires a contracted task')
            db.execute('''INSERT INTO phase4_plans(task_id,plan_json,plan_sha256,status,created_at,updated_at)
                          VALUES(?,?,?,?,?,?)''',
                       (plan.task_id, raw, digest, 'proposed', now, now))
            for node in plan.nodes:
                db.execute('''INSERT INTO phase4_nodes(task_id,node_id,role,kind,objective,
                              dependencies_json,allowed_paths_json,provider,model,effort,routing_reason,
                              status,max_attempts,created_at,updated_at)
                              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                           (plan.task_id, node.node_id, node.role, node.kind, node.objective,
                            _json(list(node.dependencies)), _json(list(node.allowed_paths)),
                            node.provider, node.model, node.effort, node.routing_reason,
                            node.initial_status, node.max_attempts, now, now))
            for edge in plan.edges:
                db.execute('''INSERT INTO phase4_edges(task_id,source_node,target_node,edge_type,max_iterations)
                              VALUES(?,?,?,?,?)''',
                           (plan.task_id, edge.source, edge.target, edge.edge_type, edge.max_iterations))
            for skill in plan.selected_skills:
                db.execute('''INSERT INTO phase4_skills(task_id,skill_id,relative_path,sha256,reason,
                              roles_json) VALUES(?,?,?,?,?,?)''',
                           (plan.task_id, skill['id'], skill['path'], skill['sha256'], skill['reason'],
                            _json(list(skill['roles']))))
            self.store._append(db, plan.task_id,
                               plan.task_id + '-phase4-plan-' + str(uuid.uuid4()),
                               'phase4_plan_recorded',
                               {'mode': plan.mode, 'nodes': len(plan.nodes),
                                'implementation_nodes': len([n for n in plan.nodes
                                                             if n.kind == 'implementation']),
                                'management_calls': plan.management_calls,
                                'plan_sha256': digest})
        return digest

    def activate_plan(self, task_id, *, authority=None):
        self._require(authority)
        with self.store.transaction() as db:
            row = db.execute('SELECT status FROM phase4_plans WHERE task_id=?', (task_id,)).fetchone()
            if not row or row['status'] not in ('proposed', 'active'):
                raise ControllerError('task has no startable Phase 4 plan')
            db.execute("UPDATE phase4_plans SET status='active',updated_at=? WHERE task_id=?",
                       (_now(), task_id))

    def node(self, task_id, node_id):
        with self.store._connect() as db:
            row = db.execute('SELECT * FROM phase4_nodes WHERE task_id=? AND node_id=?',
                             (task_id, node_id)).fetchone()
        if not row:
            raise ControllerError('unknown graph node')
        return self._decode_node(row)

    def nodes(self, task_id):
        with self.store._connect() as db:
            rows = db.execute('SELECT * FROM phase4_nodes WHERE task_id=? ORDER BY rowid',
                              (task_id,)).fetchall()
        return [self._decode_node(row) for row in rows]

    def _decode_node(self, row):
        value = dict(row)
        value['dependencies'] = json.loads(value.pop('dependencies_json'))
        value['allowed_paths'] = json.loads(value.pop('allowed_paths_json'))
        value['result'] = json.loads(value.pop('result_json')) if value.get('result_json') else None
        return value

    def _decode_skill(self, row):
        value = dict(row)
        value['roles'] = json.loads(value.pop('roles_json'))
        return value

    def transition_node(self, task_id, node_id, target, *, execution_id=None, result=None,
                        authority=None):
        self._require(authority)
        now = _now()
        with self.store.transaction() as db:
            row = db.execute('SELECT * FROM phase4_nodes WHERE task_id=? AND node_id=?',
                             (task_id, node_id)).fetchone()
            if not row or target not in NODE_TRANSITIONS.get(row['status'], set()):
                raise ControllerError('illegal graph node transition')
            attempts = row['attempts'] + (1 if target == 'running' else 0)
            if target == 'running' and attempts > row['max_attempts']:
                raise ControllerError('graph node attempt bound exhausted')
            if target == 'running':
                dependencies = json.loads(row['dependencies_json'])
                if dependencies:
                    placeholders = ','.join('?' for _ in dependencies)
                    completed = db.execute(
                        'SELECT node_id,status FROM phase4_nodes WHERE task_id=? AND node_id IN (' +
                        placeholders + ')', (task_id, *dependencies)).fetchall()
                    statuses = {item['node_id']: item['status'] for item in completed}
                    if any(statuses.get(node_id) != 'succeeded' for node_id in dependencies):
                        raise ControllerError('graph node dependencies are not complete')
            db.execute('''UPDATE phase4_nodes SET status=?,attempts=?,execution_id=?,result_json=?,
                          updated_at=? WHERE task_id=? AND node_id=?''',
                       (target, attempts, execution_id or row['execution_id'],
                        _json(result) if result is not None else row['result_json'],
                        now, task_id, node_id))
            self.store._append(db, task_id,
                               task_id + '-node-' + node_id + '-' + target + '-' + str(uuid.uuid4()),
                               'phase4_node_transition',
                               {'node_id': node_id, 'from': row['status'], 'to': target,
                                'attempt': attempts, 'execution_id': execution_id})
        return self.node(task_id, node_id)

    def claim_implementation(self, task_id, expected, owner_id, owner_pid, *, authority=None):
        """Atomically claim one exact scheduler selection.

        A stale caller receives ``None``. It cannot turn a completed assignment back into
        running or overwrite another controller's ownership.
        """
        self._require(authority)
        if (not isinstance(expected, dict) or expected.get('kind') != 'implementation' or
                expected.get('status') not in ('pending', 'failed') or
                not isinstance(owner_id, str) or not owner_id or
                isinstance(owner_pid, bool) or not isinstance(owner_pid, int) or owner_pid <= 0):
            raise ControllerError('invalid implementation claim')
        now = _now()
        with self.store.transaction() as db:
            control = db.execute('SELECT cancel_requested FROM phase4_controls WHERE task_id=?',
                                 (task_id,)).fetchone()
            if not control or control['cancel_requested']:
                return None
            row = db.execute('SELECT * FROM phase4_nodes WHERE task_id=? AND node_id=?',
                             (task_id, expected.get('node_id'))).fetchone()
            if (not row or row['kind'] != 'implementation' or
                    row['status'] != expected.get('status') or
                    row['updated_at'] != expected.get('updated_at') or
                    row['attempts'] != expected.get('attempts')):
                return None
            dependencies = json.loads(row['dependencies_json'])
            if dependencies:
                placeholders = ','.join('?' for _ in dependencies)
                completed = db.execute(
                    'SELECT node_id,status FROM phase4_nodes WHERE task_id=? AND node_id IN (' +
                    placeholders + ')', (task_id, *dependencies)).fetchall()
                statuses = {item['node_id']: item['status'] for item in completed}
                if any(statuses.get(node_id) != 'succeeded' for node_id in dependencies):
                    return None
            attempts = row['attempts'] + 1
            if attempts > row['max_attempts']:
                raise ControllerError('graph node attempt bound exhausted')
            result = json.loads(row['result_json']) if row['result_json'] else {}
            result.update(scheduler_owner=owner_id, scheduler_pid=owner_pid,
                          selection_updated_at=expected['updated_at'])
            changed = db.execute(
                '''UPDATE phase4_nodes SET status='running',attempts=?,result_json=?,updated_at=?
                   WHERE task_id=? AND node_id=? AND status=? AND updated_at=? AND attempts=?''',
                (attempts, _json(result), now, task_id, row['node_id'], row['status'],
                 row['updated_at'], row['attempts'])).rowcount
            if changed != 1:
                return None
            self.store._append(
                db, task_id,
                task_id + '-node-' + row['node_id'] + '-claim-' + str(uuid.uuid4()),
                'phase4_implementation_claimed',
                {'node_id': row['node_id'], 'from': row['status'], 'to': 'running',
                 'attempt': attempts, 'scheduler_owner': owner_id, 'scheduler_pid': owner_pid,
                 'selection_updated_at': expected['updated_at']})
        return self.node(task_id, row['node_id'])

    def record_assignment_identity(self, task_id, node_id, identity, *, dependency_contributions=(),
                                   authority=None):
        """Persist controller-observed workspace identity before a provider is launched."""
        self._require(authority)
        required = {'repository', 'worktree', 'branch', 'revision', 'clean', 'manifest_sha256'}
        if (not isinstance(identity, dict) or set(identity) != required or
                not identity.get('clean') or
                any(not isinstance(identity.get(name), str) or not identity[name]
                    for name in required - {'clean'})):
            raise ControllerError('complete clean assignment identity is required')
        if not isinstance(dependency_contributions, (tuple, list)):
            raise ControllerError('dependency contributions must be an ordered sequence')
        normalized = []
        for contribution in dependency_contributions:
            required_contribution = {'node_id', 'starting_revision', 'revision', 'changed_paths'}
            if (not isinstance(contribution, dict) or
                    set(contribution) != required_contribution or
                    any(not isinstance(contribution.get(name), str) or not contribution[name]
                        for name in ('node_id', 'starting_revision', 'revision')) or
                    not isinstance(contribution.get('changed_paths'), list) or
                    any(not isinstance(path, str) or not path
                        for path in contribution['changed_paths'])):
                raise ControllerError('invalid dependency contribution identity')
            normalized.append(contribution)
        now = _now()
        with self.store.transaction() as db:
            row = db.execute('SELECT kind,status,result_json FROM phase4_nodes '
                             'WHERE task_id=? AND node_id=?', (task_id, node_id)).fetchone()
            if not row or row['kind'] != 'implementation' or row['status'] != 'running':
                raise ControllerError('assignment identity requires a running implementation node')
            current = json.loads(row['result_json']) if row['result_json'] else {}
            current['assignment_identity'] = identity
            current['starting_revision'] = identity['revision']
            current['dependency_contributions'] = normalized
            db.execute('UPDATE phase4_nodes SET result_json=?,updated_at=? '
                       'WHERE task_id=? AND node_id=?',
                       (_json(current), now, task_id, node_id))
            self.store._append(
                db, task_id, task_id + '-assignment-identity-' + node_id + '-' + str(uuid.uuid4()),
                'phase4_assignment_identity_recorded',
                {'node_id': node_id, 'branch': identity['branch'],
                 'revision': identity['revision'], 'manifest_sha256': identity['manifest_sha256'],
                 'dependency_revisions': [item['revision'] for item in normalized]})
        return self.node(task_id, node_id)

    def request_cancellation(self, task_id, reason='user_requested', *, authority=None):
        self._require(authority)
        if reason not in ('user_requested', 'controller_interrupt'):
            raise ControllerError('invalid cancellation reason')
        with self.store.transaction() as db:
            task = db.execute('SELECT state FROM tasks WHERE task_id=?', (task_id,)).fetchone()
            if not task or task['state'] in ('cancelled', 'awaiting_pr_approval'):
                raise ControllerError('task cannot be cancelled in its current state')
            db.execute('''UPDATE phase4_controls SET cancel_requested=1,cancellation_reason=?,updated_at=?
                          WHERE task_id=?''', (reason, _now(), task_id))
            active = db.execute("SELECT execution_id FROM executions WHERE task_id=? AND status='running'",
                                (task_id,)).fetchall()
            for execution in active:
                db.execute("UPDATE executions SET status='cancel_requested' WHERE execution_id=?",
                           (execution['execution_id'],))
            self.store._append(db, task_id, task_id + '-phase4-cancel-' + str(uuid.uuid4()),
                               'phase4_cancellation_requested',
                               {'reason': reason, 'active_executions': [x['execution_id'] for x in active]})
        return len(active)

    def cancellation_requested(self, task_id):
        with self.store._connect() as db:
            row = db.execute('SELECT * FROM phase4_controls WHERE task_id=?', (task_id,)).fetchone()
        return bool(row and row['cancel_requested'])

    def plan(self, task_id):
        with self.store._connect() as db:
            row = db.execute('SELECT * FROM phase4_plans WHERE task_id=?', (task_id,)).fetchone()
        if not row:
            raise ControllerError('task has no Phase 4 plan')
        result = dict(row)
        result['plan'] = json.loads(result.pop('plan_json'))
        return result

    def snapshot(self, task_id):
        with self.store._connect() as db:
            intake = db.execute('SELECT * FROM phase4_intake WHERE task_id=?', (task_id,)).fetchone()
            plan = db.execute('SELECT * FROM phase4_plans WHERE task_id=?', (task_id,)).fetchone()
            edges = db.execute('SELECT * FROM phase4_edges WHERE task_id=? ORDER BY rowid',
                               (task_id,)).fetchall()
            skills = db.execute('SELECT * FROM phase4_skills WHERE task_id=? ORDER BY skill_id',
                                (task_id,)).fetchall()
            controls = db.execute('SELECT * FROM phase4_controls WHERE task_id=?', (task_id,)).fetchone()
        return {
            'controller': self.store.snapshot(task_id),
            'intake': dict(intake) if intake else None,
            'plan': ({**dict(plan), 'plan': json.loads(plan['plan_json'])} if plan else None),
            'nodes': self.nodes(task_id),
            'edges': [dict(row) for row in edges],
            'skills': [self._decode_skill(row) for row in skills],
            'controls': dict(controls) if controls else None,
        }
