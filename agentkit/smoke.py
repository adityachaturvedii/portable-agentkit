"""One synthetic task, one launch, independent controller acceptance oracle."""

import json
import os
from pathlib import Path
import tempfile

from .adapters import execute
from .runtime_contracts import ExecutionRequest, LivePolicy


def acceptance(result, values):
    expected = {'sum': sum(values)}
    output = result.structured_output
    return {'expected': expected, 'passed': result.status == 'succeeded' and
            isinstance(output, dict) and set(output) == {'sum'} and
            type(output['sum']) is int and output == expected,
            'oracle': 'controller integer sum and exact shape; independent of provider success claim'}


def smoke_test(engine, directory, authorized=False):
    values = [17, 25]
    prompt = 'Return only a JSON object with one integer property "sum", the sum of ' + json.dumps(values) + '. No tools or explanation.'
    with tempfile.TemporaryDirectory(prefix='agentkit-smoke-') as tmp:
        request = ExecutionRequest(engine, 'phase2-subscription-smoke', prompt, str(Path(tmp).resolve()), timeout_seconds=45)
        result = execute(request, directory, policy=LivePolicy(authorized,
                         'Operator authorized one existing-subscription smoke; stop on usage/payment limits; no billing/auth changes.'))
        observed = acceptance(result, values)
        observed['disposable_cwd_remained_empty'] = not any(Path(tmp).iterdir())
        observed['passed'] = observed['passed'] and observed['disposable_cwd_remained_empty']
        path = Path(directory) / 'acceptance.json'
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
            json.dump(observed, stream, indent=2)
            stream.write('\n')
        return {'result': result.to_dict(), 'acceptance': observed}
