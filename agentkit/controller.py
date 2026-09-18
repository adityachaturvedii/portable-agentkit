"""Transactional Phase 3 controller state. Worker data never confers authority."""

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import sqlite3
import threading
import uuid


SCHEMA_VERSION = 1
TRANSITIONS = {
    'received': {'contracted', 'blocked', 'cancelled'},
    'contracted': {'workspace_ready', 'blocked', 'cancelled'},
    'workspace_ready': {'implementing', 'blocked', 'cancelled'},
    'implementing': {'implemented', 'blocked', 'cancelled'},
    'implemented': {'verifying', 'blocked', 'cancelled'},
    'verifying': {'verified', 'repairing', 'blocked', 'cancelled'},
    'verified': {'reviewing', 'blocked', 'cancelled'},
    'reviewing': {'review_complete', 'repairing', 'blocked', 'cancelled'},
    'review_complete': {'packaging', 'repairing', 'blocked', 'cancelled'},
    'repairing': {'implemented', 'blocked', 'cancelled'},
    'packaging': {'awaiting_pr_approval', 'blocked', 'cancelled'},
}
ROLE_STATES = {
    'implementer': 'implementing',
    'repair': 'repairing',
    'verification': 'verifying',
    'reviewer': 'reviewing',
}


class ControllerError(ValueError):
    pass


class IllegalTransition(ControllerError):
    pass


class DuplicateEvent(ControllerError):
    pass


class BudgetExceeded(ControllerError):
    pass


class StaleEvidence(ControllerError):
    pass


class StaleApproval(ControllerError):
    pass


class ReconciliationRequired(ControllerError):
    pass


@dataclass(frozen=True)
class UsageRecord:
    input_tokens: object = None
    output_tokens: object = None
    cached_input_tokens: object = None
    cache_creation_tokens: object = None
    reasoning_tokens: object = None
    estimated_cost_usd: object = None
    billed_cost_usd: object = None
    source: str = 'unavailable'

    def __post_init__(self):
        for name in ('input_tokens', 'output_tokens', 'cached_input_tokens',
                     'cache_creation_tokens', 'reasoning_tokens'):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value < 0):
                raise ControllerError('usage counters must be nonnegative integers or unknown')
        for name in ('estimated_cost_usd', 'billed_cost_usd'):
            value = getattr(self, name)
            if value is not None and (type(value) not in (int, float) or
                                      not math.isfinite(value) or value < 0):
                raise ControllerError('cost values must be nonnegative or unknown')


def _now():
    return datetime.now(timezone.utc).isoformat()


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


class ControllerStore:
    """One-process controller with durable transactional state and event history."""

    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db_path = self.root / 'controller.sqlite3'
        self.artifact_root = self.root / 'artifacts' / 'sha256'
        self.artifact_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._authority = object()
        self._local = threading.local()
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(str(self.db_path), timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA busy_timeout=10000')
        return connection

    def _initialize(self):
        with self._connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('PRAGMA synchronous=FULL')
            db.executescript('''
            CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS tasks(
              task_id TEXT PRIMARY KEY, state TEXT NOT NULL, objective TEXT NOT NULL,
              contract_json TEXT, dependencies_json TEXT NOT NULL,
              implementer_engine TEXT, implementer_model TEXT,
              reviewer_engine TEXT, reviewer_model TEXT,
              base_revision TEXT, head_revision TEXT, branch TEXT, worktree TEXT,
              repair_count INTEGER NOT NULL DEFAULT 0, max_repairs INTEGER NOT NULL DEFAULT 2,
              next_action TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events(
              sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT UNIQUE NOT NULL,
              task_id TEXT NOT NULL REFERENCES tasks(task_id), event_type TEXT NOT NULL,
              payload_json TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS budgets(
              task_id TEXT PRIMARY KEY REFERENCES tasks(task_id), max_calls INTEGER NOT NULL,
              max_elapsed_seconds REAL NOT NULL, max_concurrency INTEGER NOT NULL,
              max_timeout_seconds REAL NOT NULL, verification_reserve INTEGER NOT NULL,
              reserved_calls INTEGER NOT NULL DEFAULT 0, completed_calls INTEGER NOT NULL DEFAULT 0,
              active_calls INTEGER NOT NULL DEFAULT 0, elapsed_seconds REAL NOT NULL DEFAULT 0,
              reserved_elapsed_seconds REAL NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS executions(
              execution_id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(task_id),
              role TEXT NOT NULL, engine TEXT NOT NULL, model TEXT,
              allocation_seconds REAL NOT NULL, status TEXT NOT NULL,
              pid INTEGER, process_token TEXT, started_at TEXT, finished_at TEXT,
              elapsed_seconds REAL, usage_json TEXT, result_json TEXT,
              reconciliation_note TEXT
            );
            CREATE TABLE IF NOT EXISTS evidence(
              evidence_id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(task_id),
              revision TEXT NOT NULL, kind TEXT NOT NULL, status TEXT NOT NULL,
              artifact_sha256 TEXT NOT NULL, details_json TEXT NOT NULL,
              stale INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS approvals(
              approval_id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(task_id),
              repository TEXT NOT NULL, branch TEXT NOT NULL, head_revision TEXT NOT NULL,
              action TEXT NOT NULL, expires_at TEXT NOT NULL, source TEXT NOT NULL,
              stale INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS failure_signatures(
              task_id TEXT NOT NULL REFERENCES tasks(task_id), signature TEXT NOT NULL,
              count INTEGER NOT NULL, last_details TEXT NOT NULL,
              PRIMARY KEY(task_id, signature)
            );
            CREATE TRIGGER IF NOT EXISTS events_no_update
              BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;
            CREATE TRIGGER IF NOT EXISTS events_no_delete
              BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;
            ''')
            existing = db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
            if existing and int(existing['value']) != SCHEMA_VERSION:
                raise ControllerError('unsupported controller schema')
            db.execute("INSERT OR IGNORE INTO meta(key,value) VALUES('schema_version',?)", (str(SCHEMA_VERSION),))

    @contextmanager
    def transaction(self):
        db = self._connect()
        try:
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.execute('COMMIT')
        except Exception:
            db.execute('ROLLBACK')
            raise
        finally:
            db.close()

    def _require(self, authority):
        if authority is not self._authority:
            raise PermissionError('trusted controller authority required')

    def create_task(self, task_id, objective, dependencies=(), *, implementer=('codex', None),
                    reviewer=('claude', None), max_repairs=2, max_calls=6,
                    max_elapsed_seconds=300, max_concurrency=1,
                    max_timeout_seconds=90, verification_reserve=2):
        if (not isinstance(task_id, str) or not task_id or len(task_id) > 128 or
                not task_id.replace('-', '').replace('_', '').isalnum()):
            raise ControllerError('invalid task id')
        if type(max_repairs) is not int or max_repairs < 0 or max_repairs > 2:
            raise ControllerError('Phase 3 allows at most two repairs')
        if (type(max_calls) is not int or max_calls < 1 or
                type(verification_reserve) is not int or verification_reserve < 1 or
                verification_reserve >= max_calls or
                type(max_concurrency) is not int or max_concurrency < 1 or
                type(max_timeout_seconds) not in (int, float) or
                not math.isfinite(max_timeout_seconds) or max_timeout_seconds <= 0 or
                type(max_elapsed_seconds) not in (int, float) or
                not math.isfinite(max_elapsed_seconds) or max_elapsed_seconds <= 0):
            raise ControllerError('invalid budget')
        now = _now()
        with self.transaction() as db:
            db.execute('''INSERT INTO tasks(task_id,state,objective,dependencies_json,
              implementer_engine,implementer_model,reviewer_engine,reviewer_model,max_repairs,
              next_action,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
              (task_id, 'received', objective, _json(list(dependencies)), implementer[0], implementer[1],
               reviewer[0], reviewer[1], max_repairs, 'validate task contract', now, now))
            db.execute('''INSERT INTO budgets(task_id,max_calls,max_elapsed_seconds,max_concurrency,
              max_timeout_seconds,verification_reserve) VALUES(?,?,?,?,?,?)''',
              (task_id, max_calls, max_elapsed_seconds, max_concurrency,
               max_timeout_seconds, verification_reserve))
            self._append(db, task_id, 'task-created-' + task_id, 'task_created',
                         {'objective': objective, 'dependencies': list(dependencies)})
        return self.task(task_id)

    def _append(self, db, task_id, event_id, event_type, payload):
        try:
            db.execute('INSERT INTO events(event_id,task_id,event_type,payload_json,created_at) VALUES(?,?,?,?,?)',
                       (event_id, task_id, event_type, _json(payload), _now()))
        except sqlite3.IntegrityError as exc:
            if 'events.event_id' in str(exc) or 'UNIQUE constraint failed: events.event_id' in str(exc):
                raise DuplicateEvent(event_id) from exc
            raise

    def append_event(self, task_id, event_id, event_type, payload, *, authority=None):
        self._require(authority)
        with self.transaction() as db:
            self._append(db, task_id, event_id, event_type, payload)

    def transition(self, task_id, expected, target, event_id, payload=None, *,
                   next_action='', authority=None):
        self._require(authority)
        with self.transaction() as db:
            row = db.execute('SELECT * FROM tasks WHERE task_id=?', (task_id,)).fetchone()
            if not row:
                raise ControllerError('unknown task')
            if row['state'] != expected or target not in TRANSITIONS.get(expected, set()):
                raise IllegalTransition(row['state'] + ' -> ' + target)
            if target == 'contracted' and row['contract_json'] is None:
                raise IllegalTransition('task contract is not recorded')
            if target == 'workspace_ready':
                if not all(row[name] for name in ('branch', 'worktree', 'base_revision', 'head_revision')):
                    raise IllegalTransition('workspace and revisions are not recorded')
                dependencies = json.loads(row['dependencies_json'])
                for dependency in dependencies:
                    dep = db.execute('SELECT state FROM tasks WHERE task_id=?', (dependency,)).fetchone()
                    if not dep or dep['state'] != 'awaiting_pr_approval':
                        raise IllegalTransition('dependency is not review-ready: ' + dependency)
            evidence_kind = {
                'verified': 'independent-check',
                'review_complete': 'independent-review',
                'awaiting_pr_approval': 'approval-package',
            }.get(target)
            if evidence_kind:
                evidence = db.execute('''SELECT 1 FROM evidence WHERE task_id=? AND revision=? AND
                                       kind=? AND status='passed' AND stale=0 LIMIT 1''',
                                      (task_id, row['head_revision'], evidence_kind)).fetchone()
                if not evidence:
                    raise IllegalTransition('current passing ' + evidence_kind + ' evidence is required')
            self._append(db, task_id, event_id, 'transition',
                         {'from': expected, 'to': target, **(payload or {})})
            db.execute('UPDATE tasks SET state=?,next_action=?,version=version+1,updated_at=? WHERE task_id=?',
                       (target, next_action, _now(), task_id))
        return self.task(task_id)

    def set_contract(self, task_id, contract, *, authority=None):
        self._require(authority)
        if not isinstance(contract, dict) or not contract.get('acceptance') or not contract.get('scope'):
            raise ControllerError('validated contract requires scope and acceptance')
        with self.transaction() as db:
            row = db.execute('SELECT state FROM tasks WHERE task_id=?', (task_id,)).fetchone()
            if not row or row['state'] != 'received':
                raise ControllerError('contract can be set only on a received task')
            db.execute('UPDATE tasks SET contract_json=?,updated_at=? WHERE task_id=?',
                       (_json(contract), _now(), task_id))

    def set_workspace(self, task_id, branch, worktree, base_revision, *, authority=None):
        self._require(authority)
        with self.transaction() as db:
            row = db.execute('SELECT state FROM tasks WHERE task_id=?', (task_id,)).fetchone()
            if not row or row['state'] != 'contracted':
                raise ControllerError('workspace can be set only on a contracted task')
            db.execute('''UPDATE tasks SET branch=?,worktree=?,base_revision=?,head_revision=?,
                          updated_at=? WHERE task_id=?''',
                       (branch, worktree, base_revision, base_revision, _now(), task_id))

    def set_head(self, task_id, revision, *, authority=None):
        self._require(authority)
        with self.transaction() as db:
            row = db.execute('SELECT head_revision FROM tasks WHERE task_id=?', (task_id,)).fetchone()
            if not row:
                raise ControllerError('unknown task')
            if row['head_revision'] != revision:
                db.execute('UPDATE evidence SET stale=1 WHERE task_id=? AND revision<>?', (task_id, revision))
                db.execute('UPDATE approvals SET stale=1 WHERE task_id=? AND head_revision<>?', (task_id, revision))
            db.execute('UPDATE tasks SET head_revision=?,version=version+1,updated_at=? WHERE task_id=?',
                       (revision, _now(), task_id))

    def reserve_execution(self, task_id, role, engine, model, timeout_seconds, *, authority=None):
        self._require(authority)
        if role not in ROLE_STATES:
            raise ControllerError('invalid execution role')
        if (type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds) or
                timeout_seconds <= 0):
            raise ControllerError('execution timeout must be a finite positive number')
        execution_id = str(uuid.uuid4())
        with self.transaction() as db:
            budget = db.execute('''SELECT budgets.*,tasks.state AS task_state FROM budgets
                                   JOIN tasks USING(task_id) WHERE task_id=?''', (task_id,)).fetchone()
            if not budget:
                raise ControllerError('unknown task')
            uncertain = db.execute("""SELECT 1 FROM executions WHERE task_id=? AND
                                    status='reconciliation_required' LIMIT 1""", (task_id,)).fetchone()
            if uncertain:
                raise ReconciliationRequired('outstanding execution uncertainty must be resolved')
            if budget['task_state'] != ROLE_STATES[role]:
                raise ControllerError('role ' + role + ' is invalid while task is ' + budget['task_state'])
            if timeout_seconds > budget['max_timeout_seconds']:
                raise BudgetExceeded('execution timeout exceeds task maximum')
            if budget['active_calls'] >= budget['max_concurrency']:
                raise BudgetExceeded('concurrency limit reached')
            consumed = budget['completed_calls'] + budget['reserved_calls']
            remaining_after = budget['max_calls'] - consumed - 1
            if remaining_after < 0:
                raise BudgetExceeded('call limit reached')
            if role != 'verification' and remaining_after < budget['verification_reserve']:
                raise BudgetExceeded('verification reserve protected')
            if (budget['elapsed_seconds'] + budget['reserved_elapsed_seconds'] + timeout_seconds >
                    budget['max_elapsed_seconds']):
                raise BudgetExceeded('elapsed-time allocation exhausted')
            db.execute('''UPDATE budgets SET reserved_calls=reserved_calls+1,active_calls=active_calls+1,
                          reserved_elapsed_seconds=reserved_elapsed_seconds+? WHERE task_id=?''',
                       (timeout_seconds, task_id))
            db.execute('''INSERT INTO executions(execution_id,task_id,role,engine,model,
                          allocation_seconds,status) VALUES(?,?,?,?,?,?,?)''',
                       (execution_id, task_id, role, engine, model, timeout_seconds, 'reserved'))
            self._append(db, task_id, 'reserve-' + execution_id, 'execution_reserved',
                         {'execution_id': execution_id, 'role': role, 'timeout_seconds': timeout_seconds})
        return execution_id

    def start_execution(self, execution_id, pid=None, process_token=None, *, authority=None):
        self._require(authority)
        with self.transaction() as db:
            row = db.execute('''SELECT executions.status,executions.task_id,executions.role,
                              executions.allocation_seconds,tasks.state AS task_state
                              FROM executions JOIN tasks USING(task_id) WHERE execution_id=?''',
                             (execution_id,)).fetchone()
            if not row or row['status'] != 'reserved':
                raise ControllerError('execution is not reserved')
            if row['task_state'] != ROLE_STATES.get(row['role']):
                raise ControllerError('execution role is invalid for current task state')
            uncertain = db.execute("""SELECT 1 FROM executions WHERE task_id=? AND
                                    status='reconciliation_required' LIMIT 1""",
                                   (row['task_id'],)).fetchone()
            if uncertain:
                raise ReconciliationRequired('outstanding execution uncertainty must be resolved')
            db.execute('UPDATE executions SET status=?,pid=?,process_token=?,started_at=? WHERE execution_id=?',
                       ('running', pid, process_token, _now(), execution_id))
            self._append(db, row['task_id'], 'start-' + execution_id, 'execution_started',
                         {'execution_id': execution_id, 'pid': pid})

    def finish_execution(self, execution_id, status, elapsed_seconds, usage=UsageRecord(), result=None,
                         *, authority=None):
        self._require(authority)
        if (status not in ('succeeded', 'failed', 'cancelled', 'blocked') or
                type(elapsed_seconds) not in (int, float) or not math.isfinite(elapsed_seconds) or
                elapsed_seconds < 0 or not isinstance(usage, UsageRecord)):
            raise ControllerError('invalid execution outcome')
        with self.transaction() as db:
            row = db.execute('SELECT status,task_id,allocation_seconds FROM executions WHERE execution_id=?',
                             (execution_id,)).fetchone()
            if not row or row['status'] not in ('reserved', 'running', 'cancel_requested'):
                raise ControllerError('execution is not active')
            db.execute('''UPDATE executions SET status=?,finished_at=?,elapsed_seconds=?,usage_json=?,
                          result_json=? WHERE execution_id=?''',
                       (status, _now(), elapsed_seconds, _json(asdict(usage)), _json(result or {}), execution_id))
            db.execute('''UPDATE budgets SET reserved_calls=reserved_calls-1,active_calls=active_calls-1,
                          completed_calls=completed_calls+1,elapsed_seconds=elapsed_seconds+?,
                          reserved_elapsed_seconds=reserved_elapsed_seconds-?
                          WHERE task_id=?''',
                       (elapsed_seconds, row['allocation_seconds'], row['task_id']))
            self._append(db, row['task_id'], 'finish-' + execution_id, 'execution_finished',
                         {'execution_id': execution_id, 'status': status, 'elapsed_seconds': elapsed_seconds})

    def request_cancellation(self, execution_id, *, authority=None):
        self._require(authority)
        with self.transaction() as db:
            row = db.execute('SELECT status,task_id FROM executions WHERE execution_id=?', (execution_id,)).fetchone()
            if not row or row['status'] != 'running':
                raise ControllerError('execution is not running')
            db.execute("UPDATE executions SET status='cancel_requested' WHERE execution_id=?", (execution_id,))
            self._append(db, row['task_id'], 'cancel-' + execution_id, 'cancellation_requested',
                         {'execution_id': execution_id})

    def reconcile_active(self, *, authority=None):
        self._require(authority)
        blocked = []
        with self.transaction() as db:
            rows = db.execute(
                "SELECT * FROM executions WHERE status IN ('reserved','running','cancel_requested')"
            ).fetchall()
            for row in rows:
                note = 'Controller restarted; process ownership/termination cannot be established.'
                db.execute("UPDATE executions SET status='reconciliation_required',reconciliation_note=? WHERE execution_id=?",
                           (note, row['execution_id']))
                db.execute("""UPDATE tasks SET state='blocked',next_action=?,version=version+1,
                           updated_at=? WHERE task_id=?""",
                           ('reconcile execution ' + row['execution_id'], _now(), row['task_id']))
                self._append(db, row['task_id'], 'reconcile-' + row['execution_id'],
                             'reconciliation_required', {'execution_id': row['execution_id'], 'note': note})
                blocked.append(row['execution_id'])
        return blocked

    def resolve_execution_uncertainty(self, execution_id, resolution, note, *, authority=None):
        """Release a reconciled reservation; the task intentionally remains blocked."""
        self._require(authority)
        if resolution not in ('not_started', 'terminated') or not isinstance(note, str) or not note.strip():
            raise ControllerError('resolution requires not_started/terminated and a concrete note')
        with self.transaction() as db:
            row = db.execute('''SELECT execution_id,task_id,status,allocation_seconds FROM executions
                              WHERE execution_id=?''', (execution_id,)).fetchone()
            if not row or row['status'] != 'reconciliation_required':
                raise ReconciliationRequired('execution has no outstanding uncertainty')
            final_status = 'reconciled_' + resolution
            db.execute('''UPDATE executions SET status=?,finished_at=?,reconciliation_note=?
                          WHERE execution_id=?''',
                       (final_status, _now(), note, execution_id))
            db.execute('''UPDATE budgets SET reserved_calls=reserved_calls-1,
                          active_calls=active_calls-1,completed_calls=completed_calls+1,
                          reserved_elapsed_seconds=reserved_elapsed_seconds-?
                          WHERE task_id=?''', (row['allocation_seconds'], row['task_id']))
            self._append(db, row['task_id'], 'resolve-' + execution_id,
                         'execution_uncertainty_resolved',
                         {'execution_id': execution_id, 'resolution': resolution, 'note': note})
        return final_status

    def add_evidence(self, task_id, evidence_id, revision, kind, status, artifact_sha256,
                     details, *, authority=None):
        self._require(authority)
        if status not in ('passed', 'failed', 'blocked', 'unverified'):
            raise ControllerError('invalid evidence status')
        with self.transaction() as db:
            task = db.execute('SELECT head_revision FROM tasks WHERE task_id=?', (task_id,)).fetchone()
            if not task or revision != task['head_revision']:
                raise StaleEvidence('evidence does not match current head')
            db.execute('''INSERT INTO evidence(evidence_id,task_id,revision,kind,status,
                          artifact_sha256,details_json,created_at) VALUES(?,?,?,?,?,?,?,?)''',
                       (evidence_id, task_id, revision, kind, status, artifact_sha256,
                        _json(details), _now()))
            self._append(db, task_id, 'evidence-' + evidence_id, 'evidence_recorded',
                         {'evidence_id': evidence_id, 'revision': revision, 'kind': kind, 'status': status})

    def record_failure(self, task_id, signature, details, *, authority=None):
        self._require(authority)
        with self.transaction() as db:
            task = db.execute('SELECT state,repair_count,max_repairs FROM tasks WHERE task_id=?',
                              (task_id,)).fetchone()
            if not task or task['state'] not in ('verifying', 'reviewing'):
                raise ControllerError('repair findings require verifying or reviewing state')
            current = db.execute('SELECT count FROM failure_signatures WHERE task_id=? AND signature=?',
                                 (task_id, signature)).fetchone()
            count = (current['count'] if current else 0) + 1
            db.execute('''INSERT INTO failure_signatures(task_id,signature,count,last_details) VALUES(?,?,?,?)
                          ON CONFLICT(task_id,signature) DO UPDATE SET count=excluded.count,last_details=excluded.last_details''',
                       (task_id, signature, count, details))
            if count >= 2:
                self._append(db, task_id, task_id + '-failure-repeat-' + signature,
                             'repeated_failure_checkpoint', {'signature': signature, 'count': count})
                db.execute("""UPDATE tasks SET state='blocked',next_action=?,version=version+1,
                           updated_at=? WHERE task_id=?""",
                           ('inspect repeated failure: ' + signature, _now(), task_id))
                return 'repeated_failure'
            if task['repair_count'] >= task['max_repairs']:
                self._append(db, task_id, task_id + '-repair-exhausted-' + signature,
                             'repair_exhausted', {'signature': signature,
                                                  'repair_count': task['repair_count']})
                db.execute("""UPDATE tasks SET state='blocked',next_action=?,version=version+1,
                           updated_at=? WHERE task_id=?""",
                           ('repair budget exhausted', _now(), task_id))
                return 'repair_exhausted'
            db.execute('UPDATE tasks SET repair_count=repair_count+1,updated_at=? WHERE task_id=?',
                       (_now(), task_id))
            self._append(db, task_id, task_id + '-repair-allowed-' + signature,
                         'repair_allowed', {'signature': signature,
                                            'repair_count': task['repair_count'] + 1})
            return 'repair_allowed'

    def record_user_approval(self, task_id, repository, branch, head_revision, action,
                             expires_at, source, *, authority=None):
        self._require(authority)
        try:
            expiry = datetime.fromisoformat(expires_at)
        except (TypeError, ValueError) as exc:
            raise StaleApproval('approval expiry must be an ISO timestamp') from exc
        if expiry.tzinfo is None or expiry <= datetime.now(timezone.utc):
            raise StaleApproval('approval expiry must be a future timezone-aware timestamp')
        task = self.task(task_id)
        if task['state'] != 'awaiting_pr_approval' or head_revision != task['head_revision'] or branch != task['branch']:
            raise StaleApproval('approval target is not the current awaiting head')
        approval_id = str(uuid.uuid4())
        with self.transaction() as db:
            db.execute('''INSERT INTO approvals(approval_id,task_id,repository,branch,head_revision,
                          action,expires_at,source,created_at) VALUES(?,?,?,?,?,?,?,?,?)''',
                       (approval_id, task_id, repository, branch, head_revision, action,
                        expires_at, source, _now()))
            self._append(db, task_id, 'approval-' + approval_id, 'user_approval_recorded',
                         {'approval_id': approval_id, 'action': action, 'head_revision': head_revision})
        return approval_id

    def validate_approval(self, approval_id, repository, branch, head_revision, action):
        with self._connect() as db:
            row = db.execute('SELECT * FROM approvals WHERE approval_id=?', (approval_id,)).fetchone()
        if (not row or row['stale'] or row['repository'] != repository or row['branch'] != branch or
                row['head_revision'] != head_revision or row['action'] != action or
                datetime.fromisoformat(row['expires_at']) <= datetime.now(timezone.utc)):
            raise StaleApproval('approval is absent, stale, expired, or bound to another action/head')
        return dict(row)

    def put_artifact(self, content):
        import hashlib
        raw = content if isinstance(content, bytes) else content.encode()
        digest = hashlib.sha256(raw).hexdigest()
        target = self.artifact_root / digest[:2] / digest
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if target.exists():
            if target.read_bytes() != raw:
                raise ControllerError('artifact hash collision')
        else:
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        return digest

    def task(self, task_id):
        with self._connect() as db:
            row = db.execute('SELECT * FROM tasks WHERE task_id=?', (task_id,)).fetchone()
        if not row:
            raise ControllerError('unknown task')
        result = dict(row)
        for key in ('contract_json', 'dependencies_json'):
            if result.get(key) is not None:
                result[key[:-5] if key.endswith('_json') else key] = json.loads(result.pop(key))
        return result

    def snapshot(self, task_id):
        with self._connect() as db:
            task = db.execute('SELECT * FROM tasks WHERE task_id=?', (task_id,)).fetchone()
            if not task:
                raise ControllerError('unknown task')
            budget = db.execute('SELECT * FROM budgets WHERE task_id=?', (task_id,)).fetchone()
            events = db.execute('SELECT * FROM events WHERE task_id=? ORDER BY sequence', (task_id,)).fetchall()
            executions = db.execute('SELECT * FROM executions WHERE task_id=? ORDER BY rowid', (task_id,)).fetchall()
            evidence = db.execute('SELECT * FROM evidence WHERE task_id=? ORDER BY rowid', (task_id,)).fetchall()
            approvals = db.execute('SELECT * FROM approvals WHERE task_id=? ORDER BY rowid', (task_id,)).fetchall()
        return {'task': dict(task), 'budget': dict(budget), 'events': [dict(x) for x in events],
                'executions': [dict(x) for x in executions], 'evidence': [dict(x) for x in evidence],
                'approvals': [dict(x) for x in approvals]}

    @property
    def authority(self):
        """Controller-process capability. Never serialize or pass into worker input."""
        return self._authority
