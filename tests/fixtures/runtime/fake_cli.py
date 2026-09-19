"""Disposable provider simulator. Never imports providers or contacts a network."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

engine, scenario = sys.argv[1:3]
def emit(value):
    print(json.dumps(value), flush=True)

if scenario in ('hang', 'children', 'orphan'):
    if scenario != 'hang':
        child = subprocess.Popen([sys.executable, '-c',
            'import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(60)'])
        Path('child.pid').write_text(str(child.pid))
        if scenario == 'orphan':
            sys.exit(0)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    time.sleep(60)
if scenario == 'flood':
    print('x' * 100000, flush=True)
    time.sleep(60)
if scenario == 'invalid_utf8':
    os.write(1, b'\xff\n')
    sys.exit(0)
if scenario == 'malformed':
    print('{no-json}')
    sys.exit(0)
if scenario == 'truncated':
    print('{"type":"result"', end='', flush=True)
    sys.exit(0)
if scenario in ('authentication', 'rate_limit', 'usage_limit'):
    message = {'authentication': 'Not logged in: authentication required',
               'rate_limit': 'Rate limit exceeded', 'usage_limit': 'Usage limit: additional payment required'}[scenario]
    print(message, file=sys.stderr, flush=True)
    if len(sys.argv) > 3:
        time.sleep(60)
    sys.exit(1)
if scenario == 'secrets':
    for chunk in ('authorization: Bear', 'er fake-secret-value\n', 'api_key=sk-fake-split-value\n'):
        os.write(2, chunk.encode())
        time.sleep(.01)
usage = {'input_tokens': 12, 'output_tokens': 4}
answer = '{"sum":42}' if scenario != 'wrong' else '{"sum":43}'
if engine == 'codex':
    emit({'type': 'thread.started', 'thread_id': 'fixture-session'})
    emit({'type': 'item.completed', 'item': {'type': 'agent_message', 'text': answer}})
    if scenario != 'no_terminal':
        final = {'type': 'turn.completed'}
        if scenario != 'no_usage':
            final['usage'] = usage
        emit(final)
        if scenario == 'duplicate':
            emit(final)
else:
    emit({'type': 'system', 'subtype': 'init', 'tools': ['Bash'] if scenario == 'tools' else [], 'mcp_servers': [], 'model': 'fixture'})
    if scenario != 'no_terminal':
        final = {'type': 'result', 'subtype': 'success', 'is_error': False, 'result': answer}
        if scenario != 'no_usage':
            final.update(usage=usage, total_cost_usd=0.001)
        emit(final)
        if scenario == 'duplicate':
            emit(final)
