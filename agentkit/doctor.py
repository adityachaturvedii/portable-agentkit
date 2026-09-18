"""Read-only diagnostics: no inference, auth extraction, or global config writes."""

from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import tempfile

from .process import run_process
from .runtime_contracts import Capability, EngineCapabilities


COMPATIBLE = {"codex": "0.154.0", "claude": "2.1.220"}
REQUIRED = {
    "codex": ["--json", "--output-schema", "--ephemeral", "--ignore-user-config", "--ignore-rules", "--sandbox"],
    "claude": ["--print", "--output-format", "--json-schema", "--safe-mode", "--setting-sources", "--settings", "--strict-mcp-config", "--tools", "--no-session-persistence"],
}


def clean_environment():
    # Whitelist instead of chasing every possible API key/helper/loader variable.
    env = {k: v for k, v in os.environ.items() if k in ("HOME", "PATH", "LANG", "LC_ALL", "USER", "LOGNAME", "TMPDIR")}
    env.update(DISABLE_AUTOUPDATER="1", CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1",
               CLAUDE_CODE_SAFE_MODE="1", GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1")
    return env


def readonly_profile(runtime, network=False, literal_write_paths=()):
    text = '(version 1)(allow default)(deny file-write*)'
    if not network:
        text += '(deny network*)'
    text += '(allow file-write* (subpath ' + json.dumps(str(Path(runtime).resolve())) + '))'
    for path in literal_write_paths:
        text += '(allow file-write* (literal ' + json.dumps(str(Path(path).resolve())) + '))'
    return text


def owned_code_profile(runtime, workspace, denied_read_paths, startup_write_paths=(), network=True):
    """Whole-process guard for a disposable workspace.

    Startup exceptions exist for a literal file or preselected fresh directory.
    Callers must independently verify or remove that state after execution.
    """
    runtime = Path(runtime).resolve()
    workspace = Path(workspace).resolve()
    text = '(version 1)(allow default)(deny file-write*)'
    if not network:
        text += '(deny network*)'
    text += '(allow file-write* (subpath ' + json.dumps(str(runtime)) + '))'
    text += '(allow file-write* (subpath ' + json.dumps(str(workspace)) + '))'
    for path in startup_write_paths:
        resolved = Path(path).resolve()
        selector = 'literal' if resolved.is_file() else 'subpath'
        text += '(allow file-write* (' + selector + ' ' + json.dumps(str(resolved)) + '))'
    for path in denied_read_paths:
        resolved = Path(path).resolve()
        selector = 'literal' if resolved.is_file() else 'subpath'
        text += '(deny file-read* (' + selector + ' ' + json.dumps(str(resolved)) + '))'
    return text


def native_sandbox_capability():
    if platform.system() != "Darwin" or not Path("/usr/bin/sandbox-exec").is_file():
        return Capability("unavailable", "This release has no verified whole-process diagnostic guard for this platform.")
    probe = run_process(["/usr/bin/sandbox-exec", "-p", '(version 1)(allow default)(deny file-write*)(deny network*)', "/usr/bin/true"],
                        cwd="/private/tmp", env=clean_environment(), timeout=3)
    if probe.exit_code == 0 and probe.stop_reason is None:
        return Capability("verified", "Seatbelt successfully initialized for a no-write/no-network true process; not a complete isolation proof.")
    return Capability("unavailable", "Seatbelt initialization failed in this execution context; nested sandboxes may prohibit sandbox_apply. No unrestricted retry.")


def auth_summary(engine, outcome):
    text = (outcome.stdout + outcome.stderr).decode("utf-8", "replace")
    if outcome.stop_reason or "sandbox_apply" in text:
        return Capability("unknown", "Authentication status probe could not complete under the read-only guard."), "unknown", {}
    if engine == "codex":
        if outcome.exit_code == 0 and "Logged in using ChatGPT" in text:
            return Capability("verified", "Official CLI reports ChatGPT login; no credential content read by toolkit."), "subscription", {}
        if "API key" in text:
            return Capability("verified", "Official CLI reports API-key authentication; managed execution is blocked."), "api-key", {}
        if "Not logged in" in text:
            return Capability("unavailable", "Official CLI reports no login in this context."), "none", {}
    else:
        try:
            data = json.loads(outcome.stdout)
            if not isinstance(data, dict) or outcome.exit_code != 0:
                raise ValueError("auth status failed or is not an object")
            if data.get("loggedIn") is True and data.get("authMethod") == "claude.ai" and data.get("apiProvider") == "firstParty":
                return Capability("verified", "Official CLI reports first-party Claude subscription login."), "subscription", {"subscription_type": data.get("subscriptionType")}
            if data.get("loggedIn") is False:
                return Capability("unavailable", "No authentication visible to the CLI in this execution context; Keychain restrictions may hide an existing login."), "none", {}
            if data.get("loggedIn") is True:
                return Capability("verified", "Non-subscription authentication reported; managed execution blocked."), "other", {}
        except (ValueError, TypeError):
            pass
    return Capability("unknown", "Unrecognized auth status; no credential files or values inspected."), "unknown", {}


def detect_engine(engine, sandbox):
    executable = shutil.which(engine)
    unknown = Capability("unknown", "Not probed")
    cap = EngineCapabilities(engine, executable, None, None, {}, unknown)
    if not executable:
        cap.authentication = Capability("unavailable", "Executable absent from PATH")
        cap.features = {x: Capability("unavailable", "Executable missing") for x in REQUIRED[engine]}
        return cap
    digest = hashlib.sha256()
    with Path(executable).resolve().open('rb') as binary:
        for chunk in iter(lambda: binary.read(1024 * 1024), b''):
            digest.update(chunk)
    cap.executable_sha256 = digest.hexdigest()
    cap.provider_details['hash_scope'] = 'Resolved launcher file; nested native components are not attested by this hash.' if engine == 'codex' else 'Resolved executable file.'
    with tempfile.TemporaryDirectory(prefix="agentkit-doctor-") as tmp:
        env = clean_environment()
        env.update(CODEX_HOME=tmp, CLAUDE_CONFIG_DIR=tmp, XDG_CACHE_HOME=tmp, TMPDIR=tmp)
        # With no OS guard, fake HOME prevents any real user-state access for help/version.
        if sandbox.state != "verified":
            env["HOME"] = tmp
        prefix = ["/usr/bin/sandbox-exec", "-p", readonly_profile(tmp)] if sandbox.state == "verified" else []
        version = run_process(prefix + [executable, "--version"], cwd=tmp, env=env, timeout=5)
        match = re.search(r"\b(\d+\.\d+\.\d+)\b", version.stdout.decode("utf-8", "replace"))
        if version.exit_code == 0 and match:
            cap.version = match.group(1)
        args = [executable, "exec", "--help"] if engine == "codex" else [executable, "--help"]
        help_result = run_process(prefix + args, cwd=tmp, env=env, timeout=5)
        help_text = help_result.stdout.decode("utf-8", "replace")
        for flag in REQUIRED[engine]:
            cap.features[flag] = Capability("verified" if help_result.exit_code == 0 and flag in help_text else "unknown",
                                            "Advertised by installed CLI help; effective behavior requires separate integration evidence.")
        cap.features["tested_version"] = Capability("verified" if cap.version == COMPATIBLE[engine] else "unknown",
                                                   "Compatibility target " + COMPATIBLE[engine] + "; different versions fail managed preflight.")
        cap.features['credential_isolation'] = Capability('unavailable', 'Managed parent retains its authentication and broad read access. Tool-enabled modes are blocked.')
        cap.features['tool_sandbox_effectiveness'] = Capability('unknown', 'Requires separate per-platform canary evidence; CLI flags are not an isolation proof.')
        cap.features['usage_reporting'] = Capability('unknown', 'Doctor performs no inference. Events may omit usage; missing quantities remain unknown.')
        cap.features['zero_native_retries'] = Capability('unavailable' if engine == 'codex' else 'unknown',
            'Codex 0.154.0 rejects built-in provider retry overrides; managed wall time and observed-retry stop bound execution.' if engine == 'codex' else
            'Adapter requests CLAUDE_CODE_MAX_RETRIES=0; adverse behavior tested with fixtures, not quota-consuming live failures.')
        if sandbox.state == "verified":
            auth_env = clean_environment()
            auth_env["TMPDIR"] = tmp
            args = [executable, "login", "status"] if engine == "codex" else [executable, "--safe-mode", "--setting-sources", "", "auth", "status"]
            auth = run_process(prefix + args, cwd=tmp, env=auth_env, timeout=10)
            cap.authentication, cap.authentication_mode, details = auth_summary(engine, auth)
            cap.provider_details.update(details)
        else:
            cap.authentication = Capability("unknown", "Real authentication not probed: no effective no-write diagnostic guard. No fallback.")
    cap.billing_mode = "subscription-reported" if cap.authentication_mode == "subscription" else "unknown"
    cap.provider_details["authentication_probe_network"] = "disabled"
    cap.provider_details["paid_overflow"] = "unknown; status commands do not establish account billing settings"
    return cap


def doctor():
    sandbox = native_sandbox_capability()
    return {"schema_version": 1, "platform": {"system": platform.system(), "release": platform.release(), "machine": platform.machine()},
            "sandbox_initialization": asdict(sandbox),
            "sandbox_executables": {name: bool(shutil.which(name)) for name in ("sandbox-exec", "bwrap", "docker", "podman")},
            "engines": {name: asdict(detect_engine(name, sandbox)) for name in ("codex", "claude")},
            "limitations": ["Doctor never invokes inference or changes global settings. Temporary diagnostic files may be created and removed.",
                            "Presence, advertised features, and successful initialization are distinct from effective isolation.",
                            "Authentication is CLI-reported, not proof of remaining quota or paid-overflow configuration.",
                            "No credential contents or account identifiers are emitted."]}
