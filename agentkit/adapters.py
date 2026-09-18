"""Separate CLI wire adapters and bounded managed subscription smoke execution."""

from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path

from .doctor import COMPATIBLE, REQUIRED, clean_environment, detect_engine, native_sandbox_capability, readonly_profile
from .process import run_process
from .redaction import redact, redacted_stream
from .runtime_contracts import ExecutionResult, LivePolicy, UsageObservation
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

    def argv(self, executable, request, runtime):
        settings = {'forced_login_method': '"chatgpt"', 'approval_policy': '"never"',
                    'model_provider': '"openai"', 'web_search': '"disabled"', 'project_doc_max_bytes': '0',
                    'shell_environment_policy.inherit': '"none"', 'sqlite_home': json.dumps(str(runtime)),
                    'history.persistence': '"none"', 'log_dir': json.dumps(str(runtime)),
                    'skills.max_context_tokens': '1', 'apps._default.enabled': 'false'}
        for name in ('shell_tool', 'hooks', 'plugins', 'apps', 'browser_use', 'browser_use_external',
                     'computer_use', 'image_generation', 'multi_agent', 'multi_agent_v2', 'memories',
                     'shell_snapshot', 'skill_mcp_dependency_install', 'skill_search'):
            settings['features.' + name] = 'false'
        argv = [executable, 'exec', '--json', '--ephemeral', '--ignore-user-config', '--ignore-rules',
                '--sandbox', 'read-only', '--skip-git-repo-check', '--color', 'never', '-C', request.cwd]
        for key, value in settings.items():
            argv.extend(['-c', key + '=' + value])
        if request.model:
            argv.extend(['--model', request.model])
        argv.append('-')
        return argv

    def parse(self, events, result):
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
                elif item.get('type') not in ('reasoning', 'error'):
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

    def argv(self, executable, request, runtime):
        settings = {'disableAllHooks': True,
                    'sandbox': {'enabled': True, 'failIfUnavailable': True, 'allowUnsandboxedCommands': False,
                                'excludedCommands': [], 'filesystem': {'disabled': False},
                                'network': {'allowedDomains': [], 'allowLocalBinding': False}},
                    'permissions': {'defaultMode': 'dontAsk', 'deny': ['Bash', 'Read', 'Write', 'Edit', 'WebFetch', 'WebSearch', 'Agent']}}
        argv = [executable, '--print', '--output-format', 'stream-json', '--verbose', '--safe-mode',
                '--setting-sources', '', '--settings', json.dumps(settings), '--tools', '',
                '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}', '--disable-slash-commands',
                '--no-session-persistence', '--no-chrome', '--permission-mode', 'dontAsk']
        if request.model:
            argv.extend(['--model', request.model])
        return argv

    def parse(self, events, result):
        finals = []
        for event in events:
            if event.get('type') == 'assistant':
                message = event.get('message', {})
                if isinstance(message, dict) and isinstance(message.get('content'), list):
                    if any(isinstance(part, dict) and part.get('type') in ('tool_use', 'server_tool_use') for part in message['content']):
                        result.status, result.error_class = 'failed', 'unexpected_tools'
            if event.get('type') == 'system' and event.get('subtype') == 'init':
                result.session_id = event.get('session_id')
                result.model = event.get('model')
                # Record actual advertised runtime surfaces, not just requested flags.
                result.provider_details['tools'] = event.get('tools')
                result.provider_details['mcp_servers'] = event.get('mcp_servers')
                if event.get('tools') or event.get('mcp_servers'):
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
            ADAPTERS[request.engine].parse(events, result)
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


def stop_on_limit(stdout, stderr):
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
        if kind == 'system' and event.get('subtype') == 'init' and (event.get('tools') or event.get('mcp_servers')):
            return 'unexpected_tools'
        if kind in ('item.started', 'item.completed') and isinstance(event.get('item'), dict):
            if event['item'].get('type') not in ('agent_message', 'reasoning', 'error'):
                return 'unexpected_tools'
        if kind == 'assistant' and isinstance(event.get('message'), dict):
            content = event['message'].get('content')
            if isinstance(content, list) and any(isinstance(part, dict) and part.get('type') in ('tool_use', 'server_tool_use') for part in content):
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
        prefix = ['/usr/bin/sandbox-exec', '-p', readonly_profile(runtime, network=True)]
        outcome = run_process(prefix + argv, cwd=str(cwd), env=env, stdin=request.prompt.encode(),
                              timeout=request.timeout_seconds, max_bytes=request.max_output_bytes,
                              cancel_event=cancel_event, stop_predicate=stop_on_limit)
        result = normalize(request, outcome)
        result.provider_details.update(version=cap.version, executable_sha256=cap.executable_sha256,
                                       authentication='subscription-reported', paid_overflow='unknown',
                                       authorization=policy.evidence, managed_mode='model-only')
        result.limitations.extend(['Whole-process guard denies global writes; parent provider network and auth access remain available.',
                                  'Tool-enabled execution is unsupported. Tool disabling is not OS credential isolation.',
                                  'No API keys, paid-mode fallback, purchase or billing-setting change is performed. Stop on reported limits; no controller retry.'])
        if request.engine == 'codex':
            result.limitations.append('Codex built-in transport retries cannot be set to zero without changing provider; wall time bounds the process and reported retries terminate it. Hidden attempts remain unknown.')
        return persist_result(directory, request, result, outcome)
