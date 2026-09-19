"""Transactional Phase 3 controller state. Worker data never confers authority."""

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import threading
import uuid


SCHEMA_VERSION = 6
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
    'authentication_required': {'cancelled'},
}
ROLE_STATES = {
    'planning': 'received',
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


class AuthenticationRecoveryError(ControllerError):
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


def _validated_candidate_identity(value):
    required = {'repository', 'worktree', 'branch', 'revision', 'clean', 'manifest_sha256'}
    if not isinstance(value, dict) or set(value) != required:
        raise AuthenticationRecoveryError('complete candidate identity is required')
    if (not all(isinstance(value[name], str) and value[name] for name in
                ('repository', 'worktree', 'branch', 'revision', 'manifest_sha256')) or
            not Path(value['repository']).is_absolute() or
            not Path(value['worktree']).is_absolute() or
            type(value['clean']) is not bool or not value['clean'] or
            len(value['manifest_sha256']) != 64 or
            any(character not in '0123456789abcdef' for character in value['manifest_sha256'])):
        raise StaleEvidence('candidate repository identity is incomplete, dirty, or invalid')
    return value


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
              review_reserve INTEGER NOT NULL DEFAULT 0,
              max_provider_calls INTEGER NOT NULL DEFAULT 1000,
              max_planning_calls INTEGER NOT NULL DEFAULT 0,
              provider_reserved_calls INTEGER NOT NULL DEFAULT 0,
              provider_completed_calls INTEGER NOT NULL DEFAULT 0,
              planning_reserved_calls INTEGER NOT NULL DEFAULT 0,
              planning_completed_calls INTEGER NOT NULL DEFAULT 0,
              reserved_calls INTEGER NOT NULL DEFAULT 0, completed_calls INTEGER NOT NULL DEFAULT 0,
              active_calls INTEGER NOT NULL DEFAULT 0, elapsed_seconds REAL NOT NULL DEFAULT 0,
              reserved_elapsed_seconds REAL NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS executions(
              execution_id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(task_id),
              role TEXT NOT NULL, engine TEXT NOT NULL, model TEXT, effort TEXT,
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
            CREATE TABLE IF NOT EXISTS authentication_sessions(
              session_id TEXT PRIMARY KEY, provider TEXT NOT NULL,
              account_context TEXT NOT NULL, status TEXT NOT NULL,
              owner_task_id TEXT NOT NULL REFERENCES tasks(task_id),
              attempt INTEGER NOT NULL, auth_mode TEXT, result_reason TEXT,
              owner_pid INTEGER, owner_nonce TEXT,
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS one_active_authentication_session
              ON authentication_sessions(provider,account_context)
              WHERE status IN ('waiting','in_progress','reconciliation_required');
            CREATE TABLE IF NOT EXISTS authentication_checkpoints(
              checkpoint_id TEXT PRIMARY KEY,
              task_id TEXT NOT NULL REFERENCES tasks(task_id),
              provider TEXT NOT NULL, account_context TEXT NOT NULL,
              interrupted_state TEXT NOT NULL, interrupted_role TEXT NOT NULL,
              candidate_revision TEXT NOT NULL, execution_id TEXT NOT NULL,
              evidence_refs_json TEXT NOT NULL, candidate_identity_json TEXT NOT NULL,
              status TEXT NOT NULL,
              login_session_id TEXT REFERENCES authentication_sessions(session_id),
              login_attempts INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS one_active_authentication_checkpoint
              ON authentication_checkpoints(task_id)
              WHERE status IN ('waiting','ready','login_reconciliation_required');
            CREATE TABLE IF NOT EXISTS phase4_intake(
              task_id TEXT PRIMARY KEY REFERENCES tasks(task_id), request_text TEXT NOT NULL,
              fixture_id TEXT NOT NULL, requirements_json TEXT NOT NULL,
              assumptions_json TEXT NOT NULL, execution_profile TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS phase4_plans(
              task_id TEXT PRIMARY KEY REFERENCES tasks(task_id), plan_json TEXT NOT NULL,
              plan_sha256 TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS phase4_nodes(
              task_id TEXT NOT NULL REFERENCES tasks(task_id), node_id TEXT NOT NULL,
              role TEXT NOT NULL, kind TEXT NOT NULL, objective TEXT NOT NULL,
              dependencies_json TEXT NOT NULL, allowed_paths_json TEXT NOT NULL,
              provider TEXT, model TEXT, effort TEXT, routing_reason TEXT,
              status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
              max_attempts INTEGER NOT NULL, execution_id TEXT, result_json TEXT,
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
              PRIMARY KEY(task_id,node_id)
            );
            CREATE TABLE IF NOT EXISTS phase4_edges(
              task_id TEXT NOT NULL REFERENCES tasks(task_id), source_node TEXT NOT NULL,
              target_node TEXT NOT NULL, edge_type TEXT NOT NULL, max_iterations INTEGER NOT NULL,
              PRIMARY KEY(task_id,source_node,target_node,edge_type)
            );
            CREATE TABLE IF NOT EXISTS phase4_skills(
              task_id TEXT NOT NULL REFERENCES tasks(task_id), skill_id TEXT NOT NULL,
              relative_path TEXT NOT NULL, sha256 TEXT NOT NULL, reason TEXT NOT NULL,
              roles_json TEXT NOT NULL DEFAULT '[]',
              PRIMARY KEY(task_id,skill_id)
            );
            CREATE TABLE IF NOT EXISTS phase4_controls(
              task_id TEXT PRIMARY KEY REFERENCES tasks(task_id), cancel_requested INTEGER NOT NULL DEFAULT 0,
              cancellation_reason TEXT, updated_at TEXT NOT NULL
            );
            CREATE TRIGGER IF NOT EXISTS events_no_update
              BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;
            CREATE TRIGGER IF NOT EXISTS events_no_delete
              BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;
            ''')
            budget_columns = {row['name'] for row in db.execute(
                'PRAGMA table_info(budgets)').fetchall()}
            added_execution_counters = 'provider_reserved_calls' not in budget_columns
            if 'review_reserve' not in budget_columns:
                db.execute('ALTER TABLE budgets ADD COLUMN review_reserve INTEGER NOT NULL DEFAULT 0')
            for name, declaration in (
                    ('max_provider_calls', 'INTEGER NOT NULL DEFAULT 1000'),
                    ('max_planning_calls', 'INTEGER NOT NULL DEFAULT 0'),
                    ('provider_reserved_calls', 'INTEGER NOT NULL DEFAULT 0'),
                    ('provider_completed_calls', 'INTEGER NOT NULL DEFAULT 0'),
                    ('planning_reserved_calls', 'INTEGER NOT NULL DEFAULT 0'),
                    ('planning_completed_calls', 'INTEGER NOT NULL DEFAULT 0')):
                if name not in budget_columns:
                    db.execute('ALTER TABLE budgets ADD COLUMN ' + name + ' ' + declaration)
            if added_execution_counters:
                db.execute('''UPDATE budgets SET
                  provider_reserved_calls=(SELECT COUNT(*) FROM executions e WHERE
                    e.task_id=budgets.task_id AND e.engine IN ('codex','claude') AND
                    e.status IN ('reserved','running','cancel_requested','reconciliation_required')),
                  provider_completed_calls=(SELECT COUNT(*) FROM executions e WHERE
                    e.task_id=budgets.task_id AND e.engine IN ('codex','claude') AND
                    e.status NOT IN ('reserved','running','cancel_requested','reconciliation_required')),
                  planning_reserved_calls=(SELECT COUNT(*) FROM executions e WHERE
                    e.task_id=budgets.task_id AND e.role='planning' AND
                    e.status IN ('reserved','running','cancel_requested','reconciliation_required')),
                  planning_completed_calls=(SELECT COUNT(*) FROM executions e WHERE
                    e.task_id=budgets.task_id AND e.role='planning' AND
                    e.status NOT IN ('reserved','running','cancel_requested','reconciliation_required'))''')
            execution_columns = {row['name'] for row in db.execute(
                'PRAGMA table_info(executions)').fetchall()}
            if 'effort' not in execution_columns:
                db.execute('ALTER TABLE executions ADD COLUMN effort TEXT')
            skill_columns = {row['name'] for row in db.execute(
                'PRAGMA table_info(phase4_skills)').fetchall()}
            if 'roles_json' not in skill_columns:
                db.execute("ALTER TABLE phase4_skills ADD COLUMN roles_json TEXT NOT NULL DEFAULT '[]'")
            db.execute("""UPDATE phase4_skills SET roles_json=CASE
                       WHEN skill_id='task-contract' THEN '[\"chief_of_staff\",\"tech_lead\"]'
                       WHEN skill_id='interface-design' THEN '[\"tech_lead\",\"implementer\"]'
                       WHEN skill_id='behavioral-testing' THEN '[\"implementer\"]'
                       WHEN skill_id='independent-review' THEN '[\"reviewer\"]'
                       WHEN skill_id='delivery-evidence' THEN '[\"chief_of_staff\"]'
                       WHEN skill_id LIKE 'domain:%' THEN '[\"implementer\",\"reviewer\"]'
                       ELSE roles_json END WHERE roles_json='[]'""")
            existing = db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
            if existing and int(existing['value']) not in (1, 2, 3, 4, 5, SCHEMA_VERSION):
                raise ControllerError('unsupported controller schema')
            if existing and int(existing['value']) == 2:
                db.execute('BEGIN IMMEDIATE')
                try:
                    self._migrate_v2_authentication(db)
                    db.execute("UPDATE meta SET value=? WHERE key='schema_version'",
                               (str(SCHEMA_VERSION),))
                    db.execute('COMMIT')
                except Exception:
                    db.execute('ROLLBACK')
                    raise
                return
            if existing:
                db.execute("UPDATE meta SET value=? WHERE key='schema_version'", (str(SCHEMA_VERSION),))
            else:
                db.execute("INSERT INTO meta(key,value) VALUES('schema_version',?)", (str(SCHEMA_VERSION),))

    def _migrate_v2_authentication(self, db):
        """Remove the v2 per-task history constraint and add durable login ownership."""
        session_columns = {row['name'] for row in db.execute(
            'PRAGMA table_info(authentication_sessions)').fetchall()}
        if 'owner_pid' not in session_columns:
            db.execute('ALTER TABLE authentication_sessions ADD COLUMN owner_pid INTEGER')
        if 'owner_nonce' not in session_columns:
            db.execute('ALTER TABLE authentication_sessions ADD COLUMN owner_nonce TEXT')
        db.execute('DROP INDEX IF EXISTS one_active_authentication_session')
        db.execute('''CREATE UNIQUE INDEX one_active_authentication_session
                      ON authentication_sessions(provider,account_context)
                      WHERE status IN ('waiting','in_progress','reconciliation_required')''')
        checkpoint_columns = {row['name'] for row in db.execute(
            'PRAGMA table_info(authentication_checkpoints)').fetchall()}
        if 'candidate_identity_json' in checkpoint_columns:
            return
        db.execute('DROP INDEX IF EXISTS one_active_authentication_checkpoint')
        db.execute('ALTER TABLE authentication_checkpoints RENAME TO authentication_checkpoints_v2')
        db.execute('''CREATE TABLE authentication_checkpoints(
              checkpoint_id TEXT PRIMARY KEY,
              task_id TEXT NOT NULL REFERENCES tasks(task_id),
              provider TEXT NOT NULL, account_context TEXT NOT NULL,
              interrupted_state TEXT NOT NULL, interrupted_role TEXT NOT NULL,
              candidate_revision TEXT NOT NULL, execution_id TEXT NOT NULL,
              evidence_refs_json TEXT NOT NULL, candidate_identity_json TEXT NOT NULL,
              status TEXT NOT NULL,
              login_session_id TEXT REFERENCES authentication_sessions(session_id),
              login_attempts INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            )''')
        db.execute('''INSERT INTO authentication_checkpoints(
              checkpoint_id,task_id,provider,account_context,interrupted_state,interrupted_role,
              candidate_revision,execution_id,evidence_refs_json,candidate_identity_json,status,
              login_session_id,login_attempts,created_at,updated_at)
              SELECT checkpoint_id,task_id,provider,account_context,interrupted_state,interrupted_role,
              candidate_revision,execution_id,evidence_refs_json,'{}',status,login_session_id,
              login_attempts,created_at,updated_at FROM authentication_checkpoints_v2''')
        db.execute('DROP TABLE authentication_checkpoints_v2')
        db.execute('''CREATE UNIQUE INDEX one_active_authentication_checkpoint
                      ON authentication_checkpoints(task_id)
                      WHERE status IN ('waiting','ready','login_reconciliation_required')''')

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

    def _artifact_intact(self, digest):
        if (not isinstance(digest, str) or len(digest) != 64 or
                any(character not in '0123456789abcdef' for character in digest)):
            return False
        target = self.artifact_root / digest[:2] / digest
        return (target.is_file() and not target.is_symlink() and
                hashlib.sha256(target.read_bytes()).hexdigest() == digest)

    def artifact_intact(self, digest):
        """Read-only integrity check for a controller content-addressed artifact."""
        return self._artifact_intact(digest)

    def create_task(self, task_id, objective, dependencies=(), *, implementer=('codex', None),
                    reviewer=('claude', None), max_repairs=2, max_calls=6,
                    max_elapsed_seconds=300, max_concurrency=1,
                    max_timeout_seconds=90, verification_reserve=2, review_reserve=0,
                    max_provider_calls=None, max_planning_calls=0):
        max_provider_calls = max_calls if max_provider_calls is None else max_provider_calls
        if (not isinstance(task_id, str) or not task_id or len(task_id) > 128 or
                not task_id.replace('-', '').replace('_', '').isalnum()):
            raise ControllerError('invalid task id')
        if type(max_repairs) is not int or max_repairs < 0 or max_repairs > 2:
            raise ControllerError('Phase 3 allows at most two repairs')
        if (type(max_calls) is not int or max_calls < 1 or
                type(verification_reserve) is not int or verification_reserve < 1 or
                type(review_reserve) is not int or review_reserve < 0 or
                verification_reserve + review_reserve >= max_calls or
                type(max_concurrency) is not int or max_concurrency < 1 or
                type(max_provider_calls) is not int or max_provider_calls < 1 or
                max_provider_calls > max_calls or type(max_planning_calls) is not int or
                max_planning_calls < 0 or max_planning_calls > max_provider_calls or
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
              max_timeout_seconds,verification_reserve,review_reserve,max_provider_calls,
              max_planning_calls) VALUES(?,?,?,?,?,?,?,?,?)''',
              (task_id, max_calls, max_elapsed_seconds, max_concurrency,
               max_timeout_seconds, verification_reserve, review_reserve,
               max_provider_calls, max_planning_calls))
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

    def set_next_action(self, task_id, expected_state, next_action, event_type, *, authority=None):
        self._require(authority)
        if (not isinstance(next_action, str) or not next_action.strip() or len(next_action) > 1024 or
                not isinstance(event_type, str) or not event_type.strip() or len(event_type) > 128):
            raise ControllerError('bounded next action and event type are required')
        with self.transaction() as db:
            row = db.execute('SELECT state FROM tasks WHERE task_id=?', (task_id,)).fetchone()
            if not row or row['state'] != expected_state:
                raise ControllerError('task state changed before next-action update')
            db.execute('UPDATE tasks SET next_action=?,version=version+1,updated_at=? WHERE task_id=?',
                       (next_action, _now(), task_id))
            self._append(db, task_id, task_id + '-' + event_type + '-' + str(uuid.uuid4()),
                         event_type, {'state': expected_state, 'next_action': next_action})

    def reserve_execution(self, task_id, role, engine, model, timeout_seconds, *, effort=None,
                          authority=None):
        self._require(authority)
        if role not in ROLE_STATES:
            raise ControllerError('invalid execution role')
        if (type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds) or
                timeout_seconds <= 0):
            raise ControllerError('execution timeout must be a finite positive number')
        if effort is not None and (not isinstance(effort, str) or not effort or len(effort) > 32):
            raise ControllerError('execution effort must be a bounded string or unknown')
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
            provider_call = engine in ('codex', 'claude')
            planning_call = role == 'planning'
            if provider_call and (budget['provider_completed_calls'] +
                                  budget['provider_reserved_calls'] >=
                                  budget['max_provider_calls']):
                raise BudgetExceeded('provider execution limit reached')
            if provider_call and role in ('planning', 'implementer', 'repair'):
                provider_remaining_after = (budget['max_provider_calls'] -
                                            budget['provider_completed_calls'] -
                                            budget['provider_reserved_calls'] - 1)
                provider_protected = budget['review_reserve'] + (1 if role == 'planning' else 0)
                if provider_remaining_after < provider_protected:
                    raise BudgetExceeded('provider review reserve protected')
            if planning_call and (budget['planning_completed_calls'] +
                                  budget['planning_reserved_calls'] >=
                                  budget['max_planning_calls']):
                raise BudgetExceeded('planning call limit reached')
            consumed = budget['completed_calls'] + budget['reserved_calls']
            remaining_after = budget['max_calls'] - consumed - 1
            if remaining_after < 0:
                raise BudgetExceeded('call limit reached')
            protected_calls = 0
            if role == 'planning':
                protected_calls = budget['verification_reserve'] + budget['review_reserve'] + 1
            elif role in ('implementer', 'repair'):
                protected_calls = budget['verification_reserve'] + budget['review_reserve']
            elif role == 'verification':
                protected_calls = budget['review_reserve']
            if remaining_after < protected_calls:
                raise BudgetExceeded('verification or review reserve protected')
            if (budget['elapsed_seconds'] + budget['reserved_elapsed_seconds'] + timeout_seconds >
                    budget['max_elapsed_seconds']):
                raise BudgetExceeded('elapsed-time allocation exhausted')
            db.execute('''UPDATE budgets SET reserved_calls=reserved_calls+1,active_calls=active_calls+1,
                          reserved_elapsed_seconds=reserved_elapsed_seconds+?,
                          provider_reserved_calls=provider_reserved_calls+?,
                          planning_reserved_calls=planning_reserved_calls+? WHERE task_id=?''',
                       (timeout_seconds, int(provider_call), int(planning_call), task_id))
            db.execute('''INSERT INTO executions(execution_id,task_id,role,engine,model,effort,
                          allocation_seconds,status) VALUES(?,?,?,?,?,?,?,?)''',
                       (execution_id, task_id, role, engine, model, effort, timeout_seconds, 'reserved'))
            self._append(db, task_id, 'reserve-' + execution_id, 'execution_reserved',
                         {'execution_id': execution_id, 'role': role, 'timeout_seconds': timeout_seconds,
                          'requested_configuration': {'model': model, 'effort': effort}})
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
            row = db.execute('SELECT status,task_id,allocation_seconds,engine,role FROM executions WHERE execution_id=?',
                             (execution_id,)).fetchone()
            if not row or row['status'] not in ('reserved', 'running', 'cancel_requested'):
                raise ControllerError('execution is not active')
            db.execute('''UPDATE executions SET status=?,finished_at=?,elapsed_seconds=?,usage_json=?,
                          result_json=? WHERE execution_id=?''',
                       (status, _now(), elapsed_seconds, _json(asdict(usage)), _json(result or {}), execution_id))
            db.execute('''UPDATE budgets SET reserved_calls=reserved_calls-1,active_calls=active_calls-1,
                          completed_calls=completed_calls+1,elapsed_seconds=elapsed_seconds+?,
                          reserved_elapsed_seconds=reserved_elapsed_seconds-?,
                          provider_reserved_calls=provider_reserved_calls-?,
                          provider_completed_calls=provider_completed_calls+?,
                          planning_reserved_calls=planning_reserved_calls-?,
                          planning_completed_calls=planning_completed_calls+?
                          WHERE task_id=?''',
                       (elapsed_seconds, row['allocation_seconds'],
                        int(row['engine'] in ('codex', 'claude')),
                        int(row['engine'] in ('codex', 'claude')),
                        int(row['role'] == 'planning'), int(row['role'] == 'planning'),
                        row['task_id']))
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
            row = db.execute('''SELECT execution_id,task_id,status,allocation_seconds,engine,role FROM executions
                              WHERE execution_id=?''', (execution_id,)).fetchone()
            if not row or row['status'] != 'reconciliation_required':
                raise ReconciliationRequired('execution has no outstanding uncertainty')
            final_status = 'reconciled_' + resolution
            db.execute('''UPDATE executions SET status=?,finished_at=?,reconciliation_note=?
                          WHERE execution_id=?''',
                       (final_status, _now(), note, execution_id))
            db.execute('''UPDATE budgets SET reserved_calls=reserved_calls-1,
                          active_calls=active_calls-1,completed_calls=completed_calls+1,
                          reserved_elapsed_seconds=reserved_elapsed_seconds-?,
                          provider_reserved_calls=provider_reserved_calls-?,
                          provider_completed_calls=provider_completed_calls+?,
                          planning_reserved_calls=planning_reserved_calls-?,
                          planning_completed_calls=planning_completed_calls+?
                          WHERE task_id=?''',
                       (row['allocation_seconds'],
                        int(row['engine'] in ('codex', 'claude')),
                        int(row['engine'] in ('codex', 'claude')),
                        int(row['role'] == 'planning'), int(row['role'] == 'planning'),
                        row['task_id']))
            self._append(db, row['task_id'], 'resolve-' + execution_id,
                         'execution_uncertainty_resolved',
                         {'execution_id': execution_id, 'resolution': resolution, 'note': note})
        return final_status

    def checkpoint_authentication(self, task_id, execution_id, provider, *,
                                  account_context='default-subscription', evidence_refs=(),
                                  auth_reason='missing_or_expired', candidate_identity=None,
                                  authority=None):
        """Pause only a provider stage that ended with a classified auth failure."""
        self._require(authority)
        if provider not in ('codex', 'claude'):
            raise AuthenticationRecoveryError('unsupported authentication provider')
        if (not isinstance(account_context, str) or not account_context.strip() or
                len(account_context) > 128 or auth_reason not in ('missing', 'expired', 'missing_or_expired')):
            raise AuthenticationRecoveryError('invalid authentication checkpoint metadata')
        refs = tuple(evidence_refs)
        if any(not isinstance(item, str) or not item for item in refs):
            raise AuthenticationRecoveryError('evidence references must be nonempty strings')
        identity = _validated_candidate_identity(candidate_identity)
        checkpoint_id = str(uuid.uuid4())
        now = _now()
        with self.transaction() as db:
            task = db.execute('SELECT state,head_revision FROM tasks WHERE task_id=?', (task_id,)).fetchone()
            execution = db.execute('SELECT * FROM executions WHERE execution_id=? AND task_id=?',
                                   (execution_id, task_id)).fetchone()
            if not task or task['state'] not in ('implementing', 'repairing', 'reviewing'):
                raise AuthenticationRecoveryError('authentication recovery is invalid for this task state')
            expected_role = {'implementing': 'implementer', 'repairing': 'repair',
                             'reviewing': 'reviewer'}[task['state']]
            if (not execution or execution['role'] != expected_role or execution['engine'] != provider or
                    execution['status'] not in ('failed', 'blocked')):
                raise AuthenticationRecoveryError('interrupted execution is not a completed provider stage')
            try:
                result = json.loads(execution['result_json'] or '{}')
            except (TypeError, ValueError):
                result = {}
            if result.get('error_class') != 'authentication':
                raise AuthenticationRecoveryError('only classified authentication failures are recoverable')
            if db.execute("SELECT 1 FROM executions WHERE task_id=? AND status IN "
                          "('reserved','running','cancel_requested','reconciliation_required') LIMIT 1",
                          (task_id,)).fetchone():
                raise ReconciliationRequired('execution uncertainty must be resolved before authentication recovery')
            if (identity['revision'] != task['head_revision'] or
                    identity['branch'] != db.execute('SELECT branch FROM tasks WHERE task_id=?',
                                                     (task_id,)).fetchone()['branch']):
                raise StaleEvidence('authentication checkpoint candidate does not match controller state')
            active_checkpoint = db.execute('''SELECT 1 FROM authentication_checkpoints
                WHERE task_id=? AND status IN ('waiting','ready','login_reconciliation_required') LIMIT 1''',
                                           (task_id,)).fetchone()
            if active_checkpoint:
                raise AuthenticationRecoveryError('task already has an active authentication checkpoint')
            for evidence_id in refs:
                evidence = db.execute('''SELECT artifact_sha256 FROM evidence WHERE evidence_id=? AND task_id=?
                                      AND revision=? AND stale=0''',
                                      (evidence_id, task_id, task['head_revision'])).fetchone()
                if not evidence or not self._artifact_intact(evidence['artifact_sha256']):
                    raise StaleEvidence('authentication checkpoint references stale or absent evidence')
            session = db.execute('''SELECT session_id FROM authentication_sessions
                                  WHERE provider=? AND account_context=?
                                  AND status IN ('waiting','in_progress','reconciliation_required')''',
                                 (provider, account_context)).fetchone()
            if session:
                session_id = session['session_id']
            else:
                session_id = str(uuid.uuid4())
                db.execute('''INSERT INTO authentication_sessions(session_id,provider,account_context,status,
                              owner_task_id,attempt,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)''',
                           (session_id, provider, account_context, 'waiting', task_id, 0, now, now))
            db.execute('''INSERT INTO authentication_checkpoints(checkpoint_id,task_id,provider,
                          account_context,interrupted_state,interrupted_role,candidate_revision,
                          execution_id,evidence_refs_json,candidate_identity_json,status,
                          login_session_id,created_at,updated_at)
                          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                       (checkpoint_id, task_id, provider, account_context, task['state'], expected_role,
                        task['head_revision'], execution_id, _json(list(refs)), _json(identity),
                        'waiting', session_id, now, now))
            self._append(db, task_id, task_id + '-authentication-required-' + checkpoint_id,
                         'authentication_required', {
                             'checkpoint_id': checkpoint_id, 'provider': provider,
                             'interrupted_state': task['state'], 'interrupted_role': expected_role,
                             'candidate_revision': task['head_revision'], 'evidence_refs': list(refs),
                             'reason': auth_reason,
                         })
            db.execute('''UPDATE tasks SET state='authentication_required',next_action=?,
                          version=version+1,updated_at=? WHERE task_id=?''',
                       ('complete official ' + provider + ' subscription login', now, task_id))
        return self.authentication_checkpoint(task_id)

    def claim_authentication_login(self, task_id, provider, *, owner_pid=None, owner_nonce=None,
                                   authority=None):
        """Atomically elect one interactive login owner for a provider/account context."""
        self._require(authority)
        owner_pid = os.getpid() if owner_pid is None else owner_pid
        owner_nonce = str(uuid.uuid4()) if owner_nonce is None else owner_nonce
        if (type(owner_pid) is not int or owner_pid <= 0 or not isinstance(owner_nonce, str) or
                not owner_nonce or len(owner_nonce) > 256):
            raise AuthenticationRecoveryError('invalid login owner identity')
        now = _now()
        with self.transaction() as db:
            checkpoint = db.execute('''SELECT * FROM authentication_checkpoints WHERE task_id=?
                AND status IN ('waiting','ready','login_reconciliation_required')
                ORDER BY rowid DESC LIMIT 1''', (task_id,)).fetchone()
            task = db.execute('SELECT state FROM tasks WHERE task_id=?', (task_id,)).fetchone()
            if (not checkpoint or not task or task['state'] != 'authentication_required' or
                    checkpoint['provider'] != provider or checkpoint['status'] == 'resumed'):
                raise AuthenticationRecoveryError('no matching recoverable authentication checkpoint')
            session = db.execute('SELECT * FROM authentication_sessions WHERE session_id=?',
                                 (checkpoint['login_session_id'],)).fetchone()
            if session and session['status'] == 'in_progress':
                return {'claimed': False, 'session_id': session['session_id'], 'status': 'in_progress',
                        'ownership': 'still_running_or_uncertain', 'reconciliation_required': True}
            if session and session['status'] == 'reconciliation_required':
                raise ReconciliationRequired('login ownership is uncertain and must be explicitly reconciled')
            if session and session['status'] == 'succeeded':
                return {'claimed': False, 'session_id': session['session_id'], 'status': 'succeeded'}
            attempts = checkpoint['login_attempts']
            if attempts >= 2:
                raise AuthenticationRecoveryError('authentication login attempt limit reached')
            if not session or session['status'] != 'waiting':
                active = db.execute('''SELECT * FROM authentication_sessions WHERE provider=?
                                    AND account_context=?
                                    AND status IN ('waiting','in_progress','reconciliation_required')''',
                                    (provider, checkpoint['account_context'])).fetchone()
                if active:
                    session = active
                else:
                    session_id = str(uuid.uuid4())
                    db.execute('''INSERT INTO authentication_sessions(session_id,provider,account_context,status,
                                  owner_task_id,attempt,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)''',
                               (session_id, provider, checkpoint['account_context'], 'waiting', task_id,
                                attempts, now, now))
                    session = db.execute('SELECT * FROM authentication_sessions WHERE session_id=?',
                                         (session_id,)).fetchone()
                db.execute('''UPDATE authentication_checkpoints SET login_session_id=?,updated_at=?
                              WHERE checkpoint_id=?''',
                           (session['session_id'], now, checkpoint['checkpoint_id']))
            if session['status'] == 'in_progress':
                return {'claimed': False, 'session_id': session['session_id'], 'status': 'in_progress',
                        'ownership': 'still_running_or_uncertain', 'reconciliation_required': True}
            if session['status'] == 'reconciliation_required':
                raise ReconciliationRequired('login ownership is uncertain and must be explicitly reconciled')
            claimed = db.execute("UPDATE authentication_sessions SET status='in_progress',owner_task_id=?,"
                                 "owner_pid=?,owner_nonce=?,attempt=attempt+1,updated_at=? "
                                 "WHERE session_id=? AND status='waiting'",
                                 (task_id, owner_pid, owner_nonce, now, session['session_id']))
            if claimed.rowcount != 1:
                return {'claimed': False, 'session_id': session['session_id'], 'status': 'in_progress'}
            db.execute('''UPDATE authentication_checkpoints SET login_attempts=login_attempts+1,
                          updated_at=? WHERE provider=? AND account_context=? AND status='waiting' ''',
                       (now, provider, checkpoint['account_context']))
            self._append(db, task_id, task_id + '-authentication-login-claimed-' + session['session_id'],
                         'authentication_login_claimed', {'provider': provider,
                                                          'session_id': session['session_id']})
            return {'claimed': True, 'session_id': session['session_id'], 'status': 'in_progress',
                    'owner_nonce': owner_nonce}

    def finish_authentication_login(self, session_id, outcome, *, auth_mode='unknown',
                                    reason='unknown', owner_nonce=None, authority=None):
        """Record only a sanitized login outcome; raw terminal output is never accepted."""
        self._require(authority)
        if outcome not in ('succeeded', 'failed', 'cancelled', 'timed_out'):
            raise AuthenticationRecoveryError('invalid login outcome')
        if outcome == 'succeeded' and auth_mode != 'subscription':
            raise AuthenticationRecoveryError('recovery requires verified subscription authentication')
        if reason not in ('authenticated', 'status_unavailable', 'cli_failed', 'cancelled',
                          'timed_out', 'not_subscription'):
            raise AuthenticationRecoveryError('invalid sanitized login reason')
        now = _now()
        with self.transaction() as db:
            session = db.execute('SELECT * FROM authentication_sessions WHERE session_id=?',
                                 (session_id,)).fetchone()
            if (not session or session['status'] != 'in_progress' or not owner_nonce or
                    session['owner_nonce'] != owner_nonce):
                raise AuthenticationRecoveryError('authentication session is not in progress')
            db.execute('''UPDATE authentication_sessions SET status=?,auth_mode=?,result_reason=?,
                          owner_pid=NULL,owner_nonce=NULL,updated_at=? WHERE session_id=?''',
                       (outcome, auth_mode, reason, now, session_id))
            checkpoint_status = 'ready' if outcome == 'succeeded' else 'waiting'
            rows = db.execute('''SELECT task_id,checkpoint_id FROM authentication_checkpoints
                               WHERE login_session_id=? AND status='waiting' ''', (session_id,)).fetchall()
            db.execute('''UPDATE authentication_checkpoints SET status=?,updated_at=?
                          WHERE login_session_id=? AND status='waiting' ''',
                       (checkpoint_status, now, session_id))
            for row in rows:
                self._append(db, row['task_id'], row['task_id'] + '-authentication-login-' +
                             outcome + '-' + session_id, 'authentication_login_' + outcome,
                             {'provider': session['provider'], 'session_id': session_id,
                              'auth_mode': auth_mode, 'reason': reason})

    def reconcile_authentication_login(self, session_id, resolution, reason, *, owner_nonce=None,
                                       authority=None):
        """Resolve login ownership from process evidence; elapsed time alone is never sufficient."""
        self._require(authority)
        if resolution not in ('still_running', 'confirmed_ended', 'uncertain'):
            raise AuthenticationRecoveryError('invalid login ownership resolution')
        allowed_reasons = {
            'still_running': {'owner_reports_running'},
            'confirmed_ended': {'process_exit_confirmed'},
            'uncertain': {'process_termination_unconfirmed', 'controller_interrupted',
                          'launcher_exception'},
        }
        if reason not in allowed_reasons[resolution]:
            raise AuthenticationRecoveryError('invalid sanitized login reconciliation reason')
        now = _now()
        with self.transaction() as db:
            session = db.execute('SELECT * FROM authentication_sessions WHERE session_id=?',
                                 (session_id,)).fetchone()
            if not session or session['status'] not in ('in_progress', 'reconciliation_required'):
                raise ReconciliationRequired('login session has no outstanding ownership uncertainty')
            if resolution == 'still_running':
                if session['status'] != 'in_progress' or owner_nonce != session['owner_nonce']:
                    raise ReconciliationRequired('only the current login owner can confirm it is still running')
                status = 'in_progress'
                checkpoint_status = None
            elif resolution == 'uncertain':
                status = 'reconciliation_required'
                checkpoint_status = 'login_reconciliation_required'
            else:
                status = 'abandoned'
                checkpoint_status = 'waiting'
            db.execute('''UPDATE authentication_sessions SET status=?,result_reason=?,
                          owner_pid=?,owner_nonce=?,updated_at=? WHERE session_id=?''',
                       (status, 'ownership_' + resolution,
                        session['owner_pid'] if status == 'in_progress' else None,
                        session['owner_nonce'] if status == 'in_progress' else None,
                        now, session_id))
            rows = db.execute('''SELECT task_id,checkpoint_id FROM authentication_checkpoints
                                 WHERE login_session_id=? AND status IN
                                 ('waiting','login_reconciliation_required')''',
                              (session_id,)).fetchall()
            if checkpoint_status:
                db.execute('''UPDATE authentication_checkpoints SET status=?,updated_at=?
                              WHERE login_session_id=? AND status IN
                              ('waiting','login_reconciliation_required')''',
                           (checkpoint_status, now, session_id))
            for row in rows:
                self._append(db, row['task_id'], row['task_id'] + '-authentication-login-' +
                             resolution + '-' + str(uuid.uuid4()),
                             'authentication_login_' + resolution,
                             {'provider': session['provider'], 'session_id': session_id,
                              'resolution': resolution, 'reason': reason})
        return status

    def resume_after_authentication(self, task_id, *, candidate_identity=None, authority=None):
        """Restore exactly the interrupted stage after all revision/lifecycle checks pass."""
        self._require(authority)
        identity = _validated_candidate_identity(candidate_identity)
        now = _now()
        with self.transaction() as db:
            task = db.execute('SELECT * FROM tasks WHERE task_id=?', (task_id,)).fetchone()
            checkpoint = db.execute('''SELECT * FROM authentication_checkpoints WHERE task_id=?
                AND status IN ('waiting','ready','login_reconciliation_required')
                ORDER BY rowid DESC LIMIT 1''', (task_id,)).fetchone()
            if not task or task['state'] != 'authentication_required' or not checkpoint:
                raise AuthenticationRecoveryError('task is not waiting for authentication')
            session = db.execute('SELECT * FROM authentication_sessions WHERE session_id=?',
                                 (checkpoint['login_session_id'],)).fetchone()
            if (checkpoint['status'] != 'ready' or not session or session['status'] != 'succeeded' or
                    session['auth_mode'] != 'subscription'):
                raise AuthenticationRecoveryError('subscription login has not been verified')
            if task['head_revision'] != checkpoint['candidate_revision']:
                raise StaleEvidence('candidate changed while authentication was pending')
            recorded_identity = json.loads(checkpoint['candidate_identity_json'])
            if (identity != recorded_identity or identity['repository'] != recorded_identity.get('repository') or
                    identity['worktree'] != task['worktree'] or identity['branch'] != task['branch'] or
                    identity['revision'] != task['head_revision']):
                raise StaleEvidence('actual repository, branch, HEAD, cleanliness, or manifest changed')
            if db.execute("SELECT 1 FROM executions WHERE task_id=? AND status IN "
                          "('reserved','running','cancel_requested','reconciliation_required') LIMIT 1",
                          (task_id,)).fetchone():
                raise ReconciliationRequired('execution uncertainty must be resolved before resume')
            execution = db.execute('SELECT status FROM executions WHERE execution_id=?',
                                   (checkpoint['execution_id'],)).fetchone()
            if not execution or execution['status'] not in ('failed', 'blocked'):
                raise AuthenticationRecoveryError('interrupted execution is not durably finished')
            for evidence_id in json.loads(checkpoint['evidence_refs_json']):
                evidence = db.execute('''SELECT artifact_sha256 FROM evidence WHERE evidence_id=? AND task_id=?
                                      AND revision=? AND stale=0''',
                                      (evidence_id, task_id, task['head_revision'])).fetchone()
                if not evidence or not self._artifact_intact(evidence['artifact_sha256']):
                    raise StaleEvidence('checkpoint evidence became stale')
            target = checkpoint['interrupted_state']
            if target not in ('implementing', 'repairing', 'reviewing'):
                raise AuthenticationRecoveryError('checkpoint stage is not resumable')
            db.execute("UPDATE authentication_checkpoints SET status='resumed',updated_at=? WHERE checkpoint_id=?",
                       (now, checkpoint['checkpoint_id']))
            db.execute('UPDATE tasks SET state=?,next_action=?,version=version+1,updated_at=? WHERE task_id=?',
                       (target, 'resume interrupted ' + checkpoint['interrupted_role'] + ' stage', now, task_id))
            self._append(db, task_id, task_id + '-authentication-resumed-' + checkpoint['checkpoint_id'],
                         'authentication_resumed', {'checkpoint_id': checkpoint['checkpoint_id'],
                                                    'provider': checkpoint['provider'],
                                                    'state': target,
                                                    'candidate_revision': task['head_revision']})
        return self.task(task_id)

    def authentication_checkpoint(self, task_id):
        with self._connect() as db:
            row = db.execute('''SELECT * FROM authentication_checkpoints WHERE task_id=?
                AND status IN ('waiting','ready','login_reconciliation_required')
                ORDER BY rowid DESC LIMIT 1''', (task_id,)).fetchone()
        if not row:
            return None
        result = dict(row)
        result['evidence_refs'] = json.loads(result.pop('evidence_refs_json'))
        result['candidate_identity'] = json.loads(result.pop('candidate_identity_json'))
        return result

    def authentication_checkpoint_history(self, task_id):
        with self._connect() as db:
            rows = db.execute('''SELECT * FROM authentication_checkpoints WHERE task_id=?
                                 ORDER BY rowid''', (task_id,)).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item['evidence_refs'] = json.loads(item.pop('evidence_refs_json'))
            item['candidate_identity'] = json.loads(item.pop('candidate_identity_json'))
            result.append(item)
        return result

    def recover_review_format_failure(self, task_id, execution_id, evidence_id, revision, *,
                                      authority=None):
        """Recover one verified provider-success review rejected only for JSON presentation."""
        self._require(authority)
        now = _now()
        with self.transaction() as db:
            task = db.execute('SELECT state,head_revision FROM tasks WHERE task_id=?',
                              (task_id,)).fetchone()
            execution = db.execute('SELECT * FROM executions WHERE execution_id=? AND task_id=?',
                                   (execution_id, task_id)).fetchone()
            evidence = db.execute('''SELECT 1 FROM evidence WHERE evidence_id=? AND task_id=?
                                  AND revision=? AND kind='independent-review' AND status='passed'
                                  AND stale=0''', (evidence_id, task_id, revision)).fetchone()
            last = db.execute('''SELECT event_type,payload_json FROM events WHERE task_id=?
                              AND event_type='transition' ORDER BY sequence DESC LIMIT 1''',
                              (task_id,)).fetchone()
            if not task or task['state'] != 'blocked' or task['head_revision'] != revision:
                raise ControllerError('review format recovery requires the unchanged blocked candidate')
            if (not execution or execution['role'] != 'reviewer' or execution['status'] != 'failed'):
                raise ControllerError('review format recovery requires the failed reviewer execution')
            details = json.loads(execution['result_json'] or '{}')
            if (details.get('error_class') is not None or
                    details.get('parse_error') != 'reviewer did not return a JSON object'):
                raise ControllerError('review failure is not the narrow recoverable format case')
            if not evidence:
                raise ControllerError('validated current review evidence is required')
            if (not last or last['event_type'] != 'transition' or
                    json.loads(last['payload_json']).get('from') != 'reviewing' or
                    json.loads(last['payload_json']).get('to') != 'blocked'):
                raise ControllerError('task was not blocked by the rejected review')
            if db.execute("SELECT 1 FROM executions WHERE task_id=? AND status IN "
                          "('reserved','running','cancel_requested','reconciliation_required') LIMIT 1",
                          (task_id,)).fetchone():
                raise ReconciliationRequired('execution uncertainty prevents review recovery')
            self._append(db, task_id, task_id + '-review-format-recovered-' + execution_id,
                         'review_format_recovered', {'execution_id': execution_id,
                                                     'evidence_id': evidence_id,
                                                     'revision': revision})
            db.execute("UPDATE tasks SET state='review_complete',next_action=?,version=version+1,"
                       "updated_at=? WHERE task_id=?",
                       ('prepare local approval package', now, task_id))
        return self.task(task_id)

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
            if not task or task['state'] not in ('verifying', 'reviewing', 'review_complete'):
                raise ControllerError('repair findings require a quality-stage state')
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
            authentication = db.execute('''SELECT * FROM authentication_checkpoints
                                          WHERE task_id=? ORDER BY rowid''', (task_id,)).fetchall()
        return {'task': dict(task), 'budget': dict(budget), 'events': [dict(x) for x in events],
                'executions': [dict(x) for x in executions], 'evidence': [dict(x) for x in evidence],
                'approvals': [dict(x) for x in approvals],
                'authentication_checkpoints': [dict(x) for x in authentication]}

    @property
    def authority(self):
        """Controller-process capability. Never serialize or pass into worker input."""
        return self._authority
