"""Guided first-party CLI login without capturing interactive authentication output."""

from dataclasses import asdict, dataclass
import math
import os
import platform
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time

from .doctor import (auth_summary, clean_environment, native_sandbox_capability,
                     readonly_profile)
from .process import run_process


@dataclass(frozen=True)
class AuthenticationStatus:
    provider: str
    state: str
    mode: str
    reason: str
    executable: object = None

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class LoginResult:
    provider: str
    status: str
    authentication: AuthenticationStatus
    command: str
    machine: str
    termination: str = 'not_started'

    def to_dict(self):
        return {**asdict(self), 'authentication': self.authentication.to_dict()}


def _require_provider(provider):
    if provider not in ('codex', 'claude'):
        raise ValueError('provider must be codex or claude')
    return provider


def status_argv(provider, executable):
    _require_provider(provider)
    if provider == 'codex':
        return [executable, 'login', 'status']
    return [executable, '--safe-mode', '--setting-sources', '', 'auth', 'status', '--json']


def login_argv(provider, executable, method='browser'):
    _require_provider(provider)
    if provider == 'codex':
        if method not in ('browser', 'device'):
            raise ValueError('Codex login method must be browser or device')
        argv = [executable, 'login', '-c', 'forced_login_method="chatgpt"']
        if method == 'device':
            argv.append('--device-auth')
        return argv
    if method != 'browser':
        raise ValueError('Claude Code uses its browser flow with a manual code prompt fallback')
    return [executable, 'auth', 'login', '--claudeai']


def probe_authentication(provider, *, executable=None, runner=run_process,
                         capability_check=native_sandbox_capability):
    """Return only a sanitized status; raw CLI status bytes are discarded."""
    provider = _require_provider(provider)
    executable = executable or shutil.which(provider)
    if not executable:
        return AuthenticationStatus(provider, 'unavailable', 'none', 'missing_executable', None)
    sandbox = capability_check()
    if sandbox.state != 'verified':
        return AuthenticationStatus(provider, 'unknown', 'unknown', 'status_unavailable', executable)
    with tempfile.TemporaryDirectory(prefix='agentkit-auth-status-') as tmp:
        env = clean_environment()
        env['TMPDIR'] = tmp
        prefix = ['/usr/bin/sandbox-exec', '-p', readonly_profile(tmp)]
        outcome = runner(prefix + status_argv(provider, executable), cwd=tmp,
                         env=env, timeout=15, max_bytes=65536)
    capability, mode, _ = auth_summary(provider, outcome)
    reason = 'authenticated' if capability.state == 'verified' and mode == 'subscription' else (
        'not_subscription' if capability.state == 'verified' else
        'missing_or_expired' if capability.state == 'unavailable' else 'status_unavailable')
    return AuthenticationStatus(provider, capability.state, mode, reason, executable)


@dataclass(frozen=True)
class LoginLaunchResult:
    status: str
    termination: str


def _terminate_login_process(process):
    """Try to terminate and reap the whole official-login process group."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    except OSError:
        return 'uncertain'
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except OSError:
            return 'uncertain'
        try:
            process.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            return 'uncertain'
    except OSError:
        return 'uncertain'
    return 'confirmed_ended' if process.poll() is not None else 'uncertain'


def _interactive_launch(argv, env, cwd, timeout, cancel_event=None):
    """Attach the official CLI directly to the terminal; never pipe or retain its output."""
    try:
        process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=None, stdout=None, stderr=None,
                                   start_new_session=True)
    except OSError:
        return LoginLaunchResult('failed', 'not_started')
    deadline = time.monotonic() + timeout
    outcome = 'failed'
    try:
        while process.poll() is None:
            if cancel_event is not None and cancel_event.is_set():
                outcome = 'cancelled'
                break
            if time.monotonic() >= deadline:
                outcome = 'timed_out'
                break
            time.sleep(.1)
        else:
            return LoginLaunchResult('succeeded' if process.returncode == 0 else 'failed',
                                     'confirmed_ended')
    except KeyboardInterrupt:
        outcome = 'cancelled'
    except Exception:
        outcome = 'failed'
    termination = _terminate_login_process(process)
    return LoginLaunchResult(outcome, termination)


def guided_login(provider, method='browser', *, timeout_seconds=600, cancel_event=None,
                 terminal_available=None, launcher=_interactive_launch, executable=None,
                 status_probe=probe_authentication):
    """Reuse valid auth or run an official interactive login with uncaptured terminal I/O."""
    provider = _require_provider(provider)
    if (type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds) or
            not 1 <= timeout_seconds <= 1800):
        raise ValueError('login timeout must be finite and between 1 and 1800 seconds')
    current = status_probe(provider, executable=executable)
    resolved = current.executable or executable or shutil.which(provider)
    if current.state == 'verified' and current.mode == 'subscription':
        command = shlex.join(login_argv(provider, resolved, method))
        return LoginResult(provider, 'already_authenticated', current, command, platform.node(),
                           'not_started')
    if not resolved:
        return LoginResult(provider, 'failed', current, provider, platform.node(), 'not_started')
    argv = login_argv(provider, resolved, method)
    command = shlex.join([provider] + argv[1:])
    if terminal_available is None:
        terminal_available = sys.stdin.isatty() and sys.stdout.isatty() and sys.stderr.isatty()
    if not terminal_available:
        return LoginResult(provider, 'handoff_required', current, command, platform.node(), 'not_started')
    print('Authenticating ' + provider + ' subscription on ' + platform.node() + '.', flush=True)
    if provider == 'claude':
        print('Complete the official Claude page. If it shows a code, paste it only into the CLI prompt.', flush=True)
    elif method == 'device':
        print('Open the official URL shown by Codex and enter its one-time device code there.', flush=True)
    else:
        print('Complete the official ChatGPT browser flow; passwords and MFA stay in the browser.', flush=True)
    try:
        launch = launcher(argv, clean_environment(), '/private/tmp', timeout_seconds, cancel_event)
    except KeyboardInterrupt:
        return LoginResult(provider, 'cancelled', current, command, platform.node(), 'uncertain')
    except Exception:
        return LoginResult(provider, 'failed', current, command, platform.node(), 'uncertain')
    if isinstance(launch, str):
        launch = LoginLaunchResult(launch, 'confirmed_ended')
    if (not isinstance(launch, LoginLaunchResult) or
            launch.termination not in ('confirmed_ended', 'uncertain', 'not_started')):
        return LoginResult(provider, 'failed', current, command, platform.node(), 'uncertain')
    if launch.status in ('cancelled', 'timed_out'):
        return LoginResult(provider, launch.status, current, command, platform.node(), launch.termination)
    try:
        verified = status_probe(provider, executable=resolved)
    except Exception:
        return LoginResult(provider, 'failed', current, command, platform.node(), launch.termination)
    final = ('succeeded' if launch.status == 'succeeded' and verified.state == 'verified' and
             verified.mode == 'subscription' else 'failed')
    return LoginResult(provider, final, verified, command, platform.node(), launch.termination)


def safe_login_reason(result):
    if result.status in ('cancelled', 'timed_out'):
        return result.status
    if result.status in ('succeeded', 'already_authenticated'):
        return 'authenticated'
    if result.authentication.reason == 'not_subscription':
        return 'not_subscription'
    if result.authentication.reason == 'status_unavailable':
        return 'status_unavailable'
    return 'cli_failed'
