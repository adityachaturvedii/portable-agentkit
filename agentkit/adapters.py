"""Separate CLI wire adapters and bounded managed subscription smoke execution."""

from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import uuid

from .doctor import (COMPATIBLE, REQUIRED, clean_environment, detect_engine,
                     native_sandbox_capability, owned_code_profile, readonly_profile)
from .process import run_process
from .redaction import redact, redacted_stream
from .runtime_contracts import ExecutionBoundary, ExecutionResult, LivePolicy, UsageObservation
from .validation import _pairs, _depth


def error_class(text):
    text = text.lower()
    for label, needles in [
        ("usage_limit", ("usage limit", "quota exceeded", "insufficient_quota", "credit balance", "payment required", "additional payment", "extra usage", "out of credits")),
        ("authentication", ("unauthorized", "authentication", "invalid api key", "not logged in", "login required", "401")),
        ("rate_limit", ("rate limit", "rate_limit", "429", "overloaded")),
        ("sandbox_unavailable", ("sandbox_apply", "sandbox unavailable", "failed to initialize sandbox", "sandbox initialization")),
        ("guard_denied", ("operation not permitted", "permission denied")),
        ("network", ("connection", "dns", "network", "timed out", "unreachable")),
    ]:
        if any(n in text for n in needles):
            return label
    return "provider_error"


def _count(value):
    return value if type(value) is int and value >= 0 else None


def _usage(data, source, final=True):
    if not isinstance(data, dict):
        return UsageObservation()
    return UsageObservation(input_tokens=_count(data.get("input_tokens")), output_tokens=_count(data.get("output_tokens")),
                            cached_input_tokens=_count(data.get("cached_input_tokens", data.get("cache_read_input_tokens"))),
                            cache_creation_tokens=_count(data.get("cache_creation_input_tokens")),
                            reasoning_tokens=_count(data.get("reasoning_output_tokens")),
                            source=source, final=final, provider_details=redact(data))


class IncompleteStream(ValueError):
    """A typed stream ended without its required terminal record."""


class CodexAdapter:
    engine = "codex"

    def argv(self, executable, request, runtime, boundary=None, session_id=None):
        settings = {'forced_login_method': '"chatgpt"', 'approval_policy': '"never"',
                    'model_provider': '"openai"', 'web_search': '"disabled"', 'project_doc_max_bytes': '0',
                    'shell_environment_policy.inherit': '"none"', 'sqlite_home': json.dumps(str(runtime)),
                    'history.persistence': '"none"', 'log_dir': json.dumps(str(runtime)),
                    'skills.max_context_tokens': '1', 'apps._default.enabled': 'false'}
        disabled = ['hooks', 'plugins', 'apps', 'browser_use', 'browser_use_external',
                     'computer_use', 'image_generation', 'multi_agent', 'multi_agent_v2', 'memories',
                     'shell_snapshot', 'skill_mcp_dependency_install', 'skill_search']
        if request.mode == 'model-only':
            disabled.append('shell_tool')
        for name in disabled:
            settings['features.' + name] = 'false'
        argv = [executable, 'exec', '--json', '--ephemeral', '--ignore-user-config', '--ignore-rules',
                # A nested native macOS sandbox cannot initialize inside the
                # whole-process Seatbelt guard. Owned-code commands therefore
                # use that stricter outer path boundary as the sole OS sandbox.
                '--sandbox', 'danger-full-access' if request.mode == 'owned-code' else 'read-only',
                '--skip-git-repo-check', '--color', 'never', '-C', request.cwd]
        for key, value in settings.items():
            argv.extend(['-c', key + '=' + value])
        if request.model:
            argv.extend(['--model', request.model])
        argv.append('-')
        return argv

    def parse(self, events, result, allow_tools=False):
        finals = []
        for event in events:
            kind = event.get('type')
            if kind == 'thread.started':
                result.session_id = event.get('thread_id')
            elif kind == 'item.completed':
                item = event.get('item', {})
                if not isinstance(item, dict):
                    raise ValueError('invalid item')
                if item.get('type') == 'agent_message':
                    result.final_text = item.get('text')
                elif item.get('type') not in (('reasoning', 'error', 'command_execution', 'file_change') if allow_tools else ('reasoning', 'error')):
                    result.status, result.error_class = 'failed', 'unexpected_tools'
            elif kind in ('turn.completed', 'turn.failed'):
                finals.append(event)
            elif kind == 'error':
                result.error_class = error_class(json.dumps(event))
        if not finals:
            raise IncompleteStream('missing terminal turn event')
        if len(finals) != 1:
            raise ValueError('duplicate terminal turn event')
        final = finals[0]
        if final['type'] == 'turn.failed':
            result.status = 'failed'
            result.error_class = error_class(json.dumps(final))
        else:
            result.usage = _usage(final.get('usage'), 'codex.turn.completed')
        result.provider_details['terminal_type'] = final['type']


class ClaudeAdapter:
    engine = "claude"

    def argv(self, executable, request, runtime, boundary=None, session_id=None):
        owned = request.mode == 'owned-code'
        filesystem = {'disabled': False}
        if owned:
            filesystem['denyRead'] = list(boundary.denied_read_paths)
        settings = {'disableAllHooks': True,
                    # Native macOS sandboxing is disabled only for owned-code,
                    # which is already inside the whole-process Seatbelt guard.
                    'sandbox': {'enabled': not owned, 'failIfUnavailable': not owned, 'allowUnsandboxedCommands': False,
                                'excludedCommands': [], 'filesystem': filesystem,
                                'network': {'allowedDomains': [], 'allowLocalBinding': False}},
                    'permissions': ({'defaultMode': 'dontAsk', 'blockReadsOutsideWorkingDirectories': True,
                                     'allow': ['Read', 'Edit', 'Bash(python3 -B -m unittest -v)'],
                                     'deny': ['Write', 'WebFetch', 'WebSearch', 'Agent']}
                                    if owned else
                                    {'defaultMode': 'dontAsk', 'deny': ['Bash', 'Read', 'Write', 'Edit', 'WebFetch', 'WebSearch', 'Agent']})}
        argv = [executable, '--print', '--output-format', 'stream-json', '--verbose', '--safe-mode',
                '--setting-sources', '', '--settings', json.dumps(settings), '--tools', '',
                '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}', '--disable-slash-commands',
                '--no-session-persistence', '--no-chrome', '--permission-mode', 'dontAsk']
        if owned:
            argv[argv.index('--tools') + 1] = 'Read,Edit,Bash'
            argv.extend(['--session-id', session_id])
        if request.model:
            argv.extend(['--model', request.model])
        return argv

    def parse(self, events, result, allow_tools=False):
        finals = []
        for event in events:
            if event.get('type') == 'assistant':
                message = event.get('message', {})
                if isinstance(message, dict) and isinstance(message.get('content'), list):
                    tool_names = [part.get('name') for part in message['content'] if isinstance(part, dict) and part.get('type') in ('tool_use', 'server_tool_use')]
                    if tool_names and (not allow_tools or any(name not in ('Read', 'Edit', 'Bash') for name in tool_names)):
                        result.status, result.error_class = 'failed', 'unexpected_tools'
            if event.get('type') == 'system' and event.get('subtype') == 'init':
                result.session_id = event.get('session_id')
                result.model = event.get('model')
                # Record actual advertised runtime surfaces, not just requested flags.
                result.provider_details['tools'] = event.get('tools')
                result.provider_details['mcp_servers'] = event.get('mcp_servers')
                allowed_advertised = set(event.get('tools') or ()) <= {'Read', 'Edit', 'Bash'}
                if event.get('mcp_servers') or (event.get('tools') and (not allow_tools or not allowed_advertised)):
                    result.status, result.error_class = 'failed', 'unexpected_tools'
            if event.get('type') == 'result':
                finals.append(event)
        if not finals:
            raise IncompleteStream('missing terminal result')
        if len(finals) != 1:
            raise ValueError('duplicate terminal result')
        final = finals[0]
        result.session_id = final.get('session_id', result.session_id)
        if final.get('is_error') is True or final.get('subtype') != 'success':
            result.status = 'failed'
            result.error_class = error_class(json.dumps(final))
        result.final_text = final.get('result')
        if isinstance(final.get('structured_output'), dict):
            result.structured_output = final['structured_output']
        result.usage = _usage(final.get('usage'), 'claude.result')
        cost = final.get('total_cost_usd')
        if type(cost) in (int, float) and cost >= 0:
            result.usage.estimated_cost_usd = cost
            result.usage.source = 'claude.result'
            result.usage.final = True
        result.usage.provider_details['model_usage'] = redact(final.get('modelUsage'))
        result.provider_details['terminal_type'] = final.get('subtype')


ADAPTERS = {'codex': CodexAdapter(), 'claude': ClaudeAdapter()}


def normalize(request, outcome):
    result = ExecutionResult(request.engine, request.task_id, 'succeeded', None, outcome.exit_code,
                             outcome.elapsed_seconds, model=request.model, cancellation=outcome.cancellation)
    if outcome.stop_reason:
        result.status = 'cancelled' if outcome.stop_reason in ('cancelled', 'interrupted') else 'failed'
        result.error_class = outcome.stop_reason
    text = ''
    events = []
    try:
        text = outcome.stdout.decode('utf-8', 'strict') if outcome.stdout else ''
        if text and not text.endswith('\n'):
            raise IncompleteStream('unterminated JSONL record')
        for line in text.splitlines():
            if not line.strip():
                continue
            value = json.loads(line, object_pairs_hook=_pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite')))
            _depth(value)
            if not isinstance(value, dict) or not isinstance(value.get('type'), str):
                raise ValueError('event must be typed object')
            events.append(value)
        if not outcome.stop_reason:
            ADAPTERS[request.engine].parse(events, result, allow_tools=request.mode == 'owned-code')
    except IncompleteStream:
        if not outcome.stop_reason:
            result.status, result.error_class = 'failed', 'truncated_output'
    except (ValueError, KeyError, TypeError, RecursionError):
        if not outcome.stop_reason:
            result.status = 'failed'
            result.error_class = 'malformed_output' if outcome.stdout else 'truncated_output'
    if not outcome.stop_reason and outcome.exit_code != 0:
        result.status = 'failed'
        result.error_class = error_class(outcome.stderr.decode('utf-8', 'replace') + '\n' + text)
    if result.error_class and result.status == 'succeeded':
        result.status = 'failed'
    if result.final_text is not None and not isinstance(result.final_text, str):
        result.status, result.error_class = 'failed', 'malformed_output'
        result.final_text = None
    if result.structured_output is None and result.final_text:
        try:
            value = json.loads(result.final_text, object_pairs_hook=_pairs)
            _depth(value)
            if isinstance(value, dict):
                result.structured_output = value
        except (ValueError, RecursionError):
            pass
    result.limitations = ['Provider events and final text are claims; fixture acceptance is independently computed.',
                          'Usage counts are provider-reported. Missing fields stay null. Cost estimates are not billing.',
                          'Process groups cannot prove detached-descendant or remote cancellation.']
    # No unredacted provider content leaves the normalization boundary.
    result.final_text = redact(result.final_text)
    result.structured_output = redact(result.structured_output)
    result.provider_details = redact(result.provider_details)
    for name in ('session_id', 'model'):
        value = getattr(result, name)
        if value is not None and not isinstance(value, str):
            result.status, result.error_class = 'failed', 'malformed_output'
            setattr(result, name, None)
        else:
            setattr(result, name, redact(value))
    return result


def stop_on_limit(stdout, stderr, allow_tools=False):
    """Stop explicit failure events, not benign rate-limit metadata or IDs."""
    diagnostic = stderr.decode('utf-8', 'replace')
    category = error_class(diagnostic)
    if category in ('usage_limit', 'rate_limit', 'authentication'):
        return category
    if 'reconnecting' in diagnostic.lower() or 'retrying' in diagnostic.lower():
        return 'retry_requested'
    # Only complete JSONL records; a chunk may end midway through a string.
    for line in stdout.split(b'\n')[:-1]:
        try:
            event = json.loads(line)
        except (ValueError, UnicodeError, RecursionError):
            continue
        if not isinstance(event, dict):
            continue
        kind = event.get('type')
        if kind == 'rate_limit_event':
            info = event.get('rate_limit_info', {})
            if isinstance(info, dict) and info.get('status') == 'rejected':
                return 'usage_limit'
            continue
        if kind == 'system' and event.get('subtype') == 'init' and (event.get('mcp_servers') or
                (event.get('tools') and (not allow_tools or not set(event.get('tools', ())) <= {'Read', 'Edit', 'Bash'}))):
            return 'unexpected_tools'
        if kind in ('item.started', 'item.completed') and isinstance(event.get('item'), dict):
            allowed = ('agent_message', 'reasoning', 'error', 'command_execution', 'file_change') if allow_tools else ('agent_message', 'reasoning', 'error')
            if event['item'].get('type') not in allowed:
                return 'unexpected_tools'
        if kind == 'assistant' and isinstance(event.get('message'), dict):
            content = event['message'].get('content')
            names = [part.get('name') for part in content or () if isinstance(part, dict) and part.get('type') in ('tool_use', 'server_tool_use')]
            if names and (not allow_tools or any(name not in ('Read', 'Edit', 'Bash') for name in names)):
                return 'unexpected_tools'
        if kind in ('error', 'turn.failed') or (kind == 'result' and event.get('is_error')):
            description = json.dumps(event)
            category = error_class(description)
            if category in ('usage_limit', 'rate_limit', 'authentication'):
                return category
            if 'reconnecting' in description.lower() or 'retrying' in description.lower():
                return 'retry_requested'
    return None


def persist_result(directory, request, result, outcome=None):
    path = Path(directory)
    if path.exists() or path.is_symlink():
        raise ValueError('result directory must be fresh; refusing overwrite or symlink')
    path.mkdir(mode=0o700)
    summary = asdict(request)
    summary.pop('prompt')
    summary['prompt_sha256'] = hashlib.sha256(request.prompt.encode()).hexdigest()
    summary['prompt_bytes'] = len(request.prompt.encode())
    files = {'request.json': json.dumps(summary, indent=2) + '\n'}
    if outcome is not None:
        files['stdout.redacted.jsonl'] = redacted_stream(outcome.stdout, outcome.stop_reason == 'output_limit')
        files['stderr.redacted.txt'] = redacted_stream(outcome.stderr, outcome.stop_reason == 'output_limit')
    for name, content in files.items():
        target = path / name
        with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
            stream.write(content)
        result.artifacts[name] = hashlib.sha256(target.read_bytes()).hexdigest()
    with os.fdopen(os.open(path / 'result.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        json.dump(result.to_dict(), stream, indent=2, allow_nan=False)
        stream.write('\n')
    return result


def execute(request, directory, *, policy=LivePolicy(), cancel_event=None):
    """Managed model-only smoke execution. Other modes visibly fail closed."""
    # Fail before even diagnostics/inference if evidence could not be retained.
    output = Path(directory)
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise ValueError('result directory must be fresh with an existing parent')
    def blocked(reason, detail):
        result = ExecutionResult(request.engine, request.task_id, 'blocked', reason, None, 0)
        result.limitations = [detail]
        return persist_result(directory, request, result)

    if not policy.subscription_smoke_authorized:
        return blocked('billing_policy', 'No trusted authorization for an existing-subscription smoke. No process launched.')
    if request.mode != 'model-only':
        return blocked('unsupported_isolation', 'Owned-code and untrusted tool execution remain unsupported until effective credential/tool boundaries are proven.')
    sandbox = native_sandbox_capability()
    if sandbox.state != 'verified':
        return blocked('sandbox_unavailable', sandbox.evidence)
    cap = detect_engine(request.engine, sandbox)
    if not cap.executable:
        return blocked('missing_executable', 'CLI executable absent. No install or alternate engine fallback.')
    if cap.version != COMPATIBLE[request.engine] or any(cap.features.get(f).state != 'verified' for f in REQUIRED[request.engine]):
        return blocked('incompatible_cli', 'Installed version or required flags not verified. No fallback or install.')
    if cap.authentication.state != 'verified' or cap.authentication_mode != 'subscription':
        return blocked('authentication', 'Existing subscription auth is unavailable or unknown. No auth changes or fallback.')
    # Caller must provide a fresh synthetic directory. No project discovery is performed.
    cwd = Path(request.cwd).resolve()
    if not cwd.is_dir() or any(cwd.iterdir()):
        return blocked('fixture_not_empty', 'Managed smoke requires an empty disposable cwd; prompt carries synthetic input.')
    import tempfile
    with tempfile.TemporaryDirectory(prefix='agentkit-managed-') as tmp:
        runtime = Path(tmp)
        argv = ADAPTERS[request.engine].argv(cap.executable, request, runtime)
        env = clean_environment()
        env['TMPDIR'] = tmp
        if request.engine == 'claude':
            env.update(CLAUDE_CODE_MAX_RETRIES='0', CLAUDE_CODE_MAX_TURNS='1',
                       CLAUDE_CODE_MAX_OUTPUT_TOKENS='512')
        # Whole CLI: deny global writes. Native tools disabled; this does NOT isolate
        # the authenticated process from credentials it must read for its own login.
        startup_write = ()
        installation_before = None
        if request.engine == 'codex':
            install_id = Path.home() / '.codex' / 'installation_id'
            if not install_id.is_file() or install_id.is_symlink():
                return blocked('startup_state_unavailable', 'Codex installation_id is absent, non-regular, or a symlink; no broad write fallback.')
            installation_before = _file_fingerprint(install_id)
            startup_write = (install_id,)
        prefix = ['/usr/bin/sandbox-exec', '-p', readonly_profile(runtime, network=True,
                                                                  literal_write_paths=startup_write)]
        outcome = run_process(prefix + argv, cwd=str(cwd), env=env, stdin=request.prompt.encode(),
                              timeout=request.timeout_seconds, max_bytes=request.max_output_bytes,
                              cancel_event=cancel_event, stop_predicate=stop_on_limit)
        result = normalize(request, outcome)
        result.provider_details.update(version=cap.version, executable_sha256=cap.executable_sha256,
                                       authentication='subscription-reported', paid_overflow='unknown',
                                       authorization=policy.evidence, managed_mode='model-only')
        if startup_write:
            installation_after = _file_fingerprint(startup_write[0])
            result.provider_details['installation_id_integrity'] = {
                'before': installation_before, 'after': installation_after,
                'unchanged': installation_before == installation_after,
                'path': str(startup_write[0])}
            if installation_before != installation_after:
                result.status, result.error_class = 'failed', 'startup_state_changed'
        result.limitations.extend(['Whole-process guard denies global writes; parent provider network and auth access remain available.',
                                  'Tool-enabled execution is unsupported. Tool disabling is not OS credential isolation.',
                                  'No API keys, paid-mode fallback, purchase or billing-setting change is performed. Stop on reported limits; no controller retry.'])
        if request.engine == 'codex':
            result.limitations.append('Codex built-in transport retries cannot be set to zero without changing provider; wall time bounds the process and reported retries terminate it. Hidden attempts remain unknown.')
        return persist_result(directory, request, result, outcome)


def _file_fingerprint(path):
    path = Path(path)
    return {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'size': path.stat().st_size, 'mode': oct(path.stat().st_mode & 0o777)}


def execute_owned_code(request, directory, boundary, *, policy=LivePolicy(), cancel_event=None):
    """Run one bounded task in a caller-created disposable workspace."""
    output = Path(directory)
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise ValueError('result directory must be fresh with an existing parent')
    if not isinstance(boundary, ExecutionBoundary):
        raise TypeError('trusted ExecutionBoundary required')
    def blocked(reason, detail):
        result = ExecutionResult(request.engine, request.task_id, 'blocked', reason, None, 0)
        result.limitations = [detail]
        return persist_result(directory, request, result)
    if not policy.subscription_smoke_authorized:
        return blocked('billing_policy', 'No trusted authorization for an existing-subscription smoke. No process launched.')
    if request.mode != 'owned-code':
        return blocked('unsupported_isolation', 'This entry point only supports disposable owned-code mode.')
    requested_workspace = Path(request.cwd)
    workspace = requested_workspace.resolve()
    if (workspace != Path(boundary.workspace).resolve() or not workspace.is_dir() or
            requested_workspace.is_symlink() or any(path.is_symlink() for path in workspace.rglob('*'))):
        return blocked('invalid_boundary', 'Request cwd must be the real, existing disposable boundary workspace.')
    denied = tuple(Path(p).resolve() for p in boundary.denied_read_paths)
    if any(workspace == path or workspace in path.parents or path in workspace.parents for path in denied):
        return blocked('invalid_boundary', 'Denied paths cannot contain the workspace.')
    if output.resolve() == workspace or workspace in output.resolve().parents:
        return blocked('invalid_boundary', 'Result evidence cannot be stored inside the agent workspace.')
    sandbox = native_sandbox_capability()
    if sandbox.state != 'verified':
        return blocked('sandbox_unavailable', sandbox.evidence)
    cap = detect_engine(request.engine, sandbox)
    if not cap.executable:
        return blocked('missing_executable', 'CLI executable absent. No install or alternate engine fallback.')
    if cap.version != COMPATIBLE[request.engine] or any(cap.features.get(f).state != 'verified' for f in REQUIRED[request.engine]):
        return blocked('incompatible_cli', 'Installed version or required flags not verified. No fallback or install.')
    if cap.authentication.state != 'verified' or cap.authentication_mode != 'subscription':
        return blocked('authentication', 'Existing subscription auth is unavailable or unknown. No auth changes or fallback.')
    import tempfile
    with tempfile.TemporaryDirectory(prefix='agentkit-owned-runtime-') as tmp:
        runtime = Path(tmp).resolve()
        write_exceptions = ()
        installation_before = None
        claude_session_path = None
        if request.engine == 'codex':
            install_id = Path.home() / '.codex' / 'installation_id'
            if not install_id.is_file() or install_id.is_symlink():
                return blocked('startup_state_unavailable', 'Codex installation_id is absent, non-regular, or a symlink; no broad write fallback.')
            installation_before = _file_fingerprint(install_id)
            write_exceptions = (install_id,)
        else:
            session_parent = Path.home() / '.claude' / 'session-env'
            if not session_parent.is_dir() or session_parent.is_symlink():
                return blocked('startup_state_unavailable', 'Claude session-env parent is absent, non-directory, or a symlink; no broad write fallback.')
            session_id = str(uuid.uuid4())
            claude_session_path = session_parent / session_id
            if claude_session_path.exists() or claude_session_path.is_symlink():
                return blocked('startup_state_unavailable', 'Fresh Claude session state path unexpectedly exists.')
            write_exceptions = (claude_session_path,)
        argv = ADAPTERS[request.engine].argv(cap.executable, request, runtime, boundary,
                                             session_id=session_id if request.engine == 'claude' else None)
        env = clean_environment()
        env.update(TMPDIR=str(runtime), PYTHONDONTWRITEBYTECODE='1')
        if request.engine == 'codex':
            env['CODEX_INSTALL_DIR'] = str(runtime / 'install')
        else:
            env.update(CLAUDE_CODE_TMPDIR=str(runtime), CLAUDE_TMPDIR=str(runtime),
                       CLAUDE_CODE_MAX_RETRIES='0', CLAUDE_CODE_MAX_TURNS='8',
                       CLAUDE_CODE_MAX_OUTPUT_TOKENS='2048')
        profile = owned_code_profile(runtime, workspace, denied, write_exceptions, network=True)
        predicate = lambda stdout, stderr: stop_on_limit(stdout, stderr, allow_tools=True)
        outcome = run_process(['/usr/bin/sandbox-exec', '-p', profile] + argv,
                              cwd=str(workspace), env=env, stdin=request.prompt.encode(),
                              timeout=request.timeout_seconds, max_bytes=request.max_output_bytes,
                              cancel_event=cancel_event, stop_predicate=predicate)
        result = normalize(request, outcome)
        result.provider_details.update(version=cap.version, executable_sha256=cap.executable_sha256,
                                       authentication='subscription-reported', paid_overflow='unknown',
                                       authorization=policy.evidence, managed_mode='external-seatbelt-owned-code',
                                       denied_read_paths=[str(p) for p in denied])
        if request.engine == 'codex':
            installation_after = _file_fingerprint(write_exceptions[0])
            result.provider_details['installation_id_integrity'] = {
                'before': installation_before, 'after': installation_after,
                'unchanged': installation_before == installation_after,
                'path': str(write_exceptions[0])}
            if installation_before != installation_after:
                result.status, result.error_class = 'failed', 'startup_state_changed'
        elif claude_session_path is not None:
            result.provider_details['claude_session_state'] = {
                'path': str(claude_session_path), 'fresh_path_only': True,
                'created': claude_session_path.exists()}
            if claude_session_path.exists():
                shutil.rmtree(claude_session_path)
            result.provider_details['claude_session_state']['removed_after_run'] = not claude_session_path.exists()
        write_scope = ('Whole-process guard permits writes only in the disposable workspace/runtime plus the preselected fresh Claude session path.'
                       if request.engine == 'claude' else
                       'Whole-process guard permits writes only in the disposable workspace/runtime plus the literal Codex startup lock file.')
        result.limitations.extend([
            write_scope,
            'Explicit disposable read canaries are denied; comprehensive parent credential isolation is not established.',
            'Provider and tool traffic share the parent network boundary; tool network isolation is unsupported in this mode.',
            'No API keys, paid-mode fallback, purchase or billing-setting change is performed. Stop on reported limits; no controller retry.'
        ])
        if request.engine == 'codex':
            result.limitations.append('Codex built-in transport retries cannot be configured to zero with its built-in subscription provider; reported reconnects stop the run and wall time bounds it. Hidden attempts remain unknown.')
        return persist_result(directory, request, result, outcome)
