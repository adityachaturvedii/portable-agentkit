"""Offline macOS boundary experiment; exclusively disposable fake credentials.

The probe is trusted test code, not a provider/model assertion. No real secret
path is opened. The parent verifies canary integrity and write outcomes.
"""
import json
from pathlib import Path
import shutil
import socket
import sys
import tempfile

from .doctor import clean_environment, native_sandbox_capability, readonly_profile
from .process import run_process
from .redaction import redacted_stream


CHILD = r'''
import json,os,pathlib,socket,subprocess,sys
root=pathlib.Path(sys.argv[1]); port=int(sys.argv[2]); observed={}
def attempt(name, operation):
    try:
        observed[name]={'allowed':bool(operation())}
    except OSError as exc:
        observed[name]={'allowed':False,'errno':exc.errno}
attempt('read_workspace', lambda:(root/'cwd/input').read_text()=='synthetic')
attempt('read_fake_credential', lambda:(root/'fake-home/credential').read_text()=='FAKE-CANARY-NOT-A-CREDENTIAL')
attempt('read_symlink_to_fake_credential', lambda:(root/'cwd/secret-link').read_text()=='FAKE-CANARY-NOT-A-CREDENTIAL')
attempt('write_workspace', lambda:(root/'cwd/written').write_text('probe')>0)
attempt('write_sibling', lambda:(root/'sibling/written').write_text('probe')>0)
attempt('write_common_git_metadata', lambda:(root/'common.git/config').write_text('overwritten')>0)
attempt('write_runtime', lambda:(root/'runtime/written').write_text('probe')>0)
attempt('overwrite_fake_credential', lambda:(root/'fake-home/credential').write_text('overwritten')>0)
def connect():
    with socket.create_connection(('127.0.0.1',port),timeout=.5): return True
attempt('loopback_network',connect)
attempt('spawn_process',lambda:subprocess.run(['/usr/bin/true'],timeout=2).returncode==0)
observed['fake_env_visible']={'allowed':os.environ.get('CANARY_FAKE_SECRET')=='fake-env-value'}
print(json.dumps(observed))
'''


def probe():
    sandbox = native_sandbox_capability()
    report = {'schema_version': 1, 'platform': sys.platform, 'initialization': sandbox.state,
              'evidence': sandbox.evidence, 'cases': {},
              'limitations': ['Only synthetic canaries; no real credentials opened.',
                              'Loopback only, not every network family or tool path.',
                              'Process spawn allowed; process groups are lifecycle controls, not isolation.',
                              'Claude native Bash sandbox not exercised by this offline OS/Codex probe.']}
    if sandbox.state != 'verified':
        return report
    for name in ('whole-process-offline', 'whole-process-live-policy', 'codex-native-read-only', 'codex-native-deny-canary'):
        with tempfile.TemporaryDirectory(prefix='agentkit-canary-') as tmp:
            root = Path(tmp).resolve()
            for sub in ('cwd', 'sibling', 'runtime', 'fake-home', 'common.git'):
                (root / sub).mkdir()
            (root / 'cwd/input').write_text('synthetic')
            credential = root / 'fake-home/credential'
            credential.write_text('FAKE-CANARY-NOT-A-CREDENTIAL')
            (root / 'common.git/config').write_text('fake-git-metadata')
            (root / 'cwd/secret-link').symlink_to(credential)
            env = clean_environment()
            env.update(HOME=str(root / 'fake-home'), CODEX_HOME=str(root / 'fake-home'),
                       TMPDIR=str(root / 'runtime'), PYTHONDONTWRITEBYTECODE='1', CANARY_FAKE_SECRET='fake-env-value')
            with socket.socket() as listener:
                listener.bind(('127.0.0.1', 0))
                listener.listen(4)
                command = [sys.executable, '-c', CHILD, str(root), str(listener.getsockname()[1])]
                if name.startswith('whole-process'):
                    argv = ['/usr/bin/sandbox-exec', '-p', readonly_profile(root / 'runtime', network=name.endswith('live-policy'))] + command
                else:
                    executable = shutil.which('codex')
                    if not executable:
                        report['cases'][name] = {'status': 'unavailable', 'reason': 'codex absent'}
                        continue
                    argv = [executable, 'sandbox', '-C', str(root / 'cwd'), '-c', 'sandbox_mode="read-only"',
                            '-c', 'approval_policy="never"']
                    if name == 'codex-native-read-only':
                        argv += ['-P', 'canary', '-c', 'permissions.canary.filesystem={"/"="read"}',
                                 '-c', 'permissions.canary.network.enabled=false']
                    if name.endswith('deny-canary'):
                        # Current Codex permissions profile. A rejected config is unsupported,
                        # never retried without its deny rule.
                        argv += ['-P', 'canary', '--sandbox-state-disable-network', '-c', 'permissions.canary.filesystem={"/"="read",' +
                                 json.dumps(str(root / 'fake-home')) + '="deny"}',
                                 '-c', 'permissions.canary.network.enabled=false']
                    argv += command
                outcome = run_process(argv, cwd=str(root / 'cwd'), env=env, timeout=8)
            try:
                child = json.loads(outcome.stdout)
            except ValueError:
                child = None
            report['cases'][name] = {
                'status': 'observed' if outcome.exit_code == 0 and child is not None else 'unsupported',
                'exit_code': outcome.exit_code, 'stop_reason': outcome.stop_reason,
                'observed': child, 'stderr': redacted_stream(outcome.stderr),
                'parent_verification': {'canary_unchanged': credential.read_text() == 'FAKE-CANARY-NOT-A-CREDENTIAL',
                                        'common_git_metadata_unchanged': (root / 'common.git/config').read_text() == 'fake-git-metadata',
                                        'workspace_write_exists': (root / 'cwd/written').exists(),
                                        'sibling_write_exists': (root / 'sibling/written').exists(),
                                        'runtime_write_exists': (root / 'runtime/written').exists()},
                'process_group_gone': outcome.cancellation.process_group_gone}
    return report


if __name__ == '__main__':
    print(json.dumps(probe(), indent=2))
