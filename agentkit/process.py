"""Bounded POSIX process transport. A process group is not a sandbox."""

from dataclasses import dataclass
import os
import selectors
import signal
import subprocess
import time

from .runtime_contracts import CancellationStatus


@dataclass
class ProcessOutcome:
    stdout: bytes
    stderr: bytes
    exit_code: object
    elapsed_seconds: float
    stop_reason: object
    cancellation: CancellationStatus


def group_exists(pgid):
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def run_process(argv, *, cwd, env, stdin=b"", timeout=30.0,
                max_bytes=1048576, cancel_event=None, grace=0.2, stop_predicate=None):
    """Never retry; capture bounded bytes without persisting raw unredacted data."""
    if os.name != "posix":
        return ProcessOutcome(b"", b"POSIX process control unavailable", None, 0,
                              "unsupported_platform", CancellationStatus())
    if not argv or not all(isinstance(x, str) and "\0" not in x for x in argv):
        raise ValueError("argv must be explicit strings")
    if not 0.05 <= timeout <= 300 or not 1024 <= max_bytes <= 4194304 or len(stdin) > 32768:
        raise ValueError("invalid transport limits")
    cancellation = CancellationStatus()
    started = time.monotonic()
    if cancel_event is not None and cancel_event.is_set():
        cancellation.requested = True
        cancellation.reason = "cancelled-before-launch"
        cancellation.process_group_gone = True
        return ProcessOutcome(b"", b"", None, 0.0, "cancelled", cancellation)
    try:
        proc = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                start_new_session=True, close_fds=True)
    except FileNotFoundError:
        return ProcessOutcome(b"", b"executable or working directory unavailable", None,
                              time.monotonic() - started, "missing_executable", cancellation)
    except OSError as exc:
        return ProcessOutcome(b"", ("launch error: " + str(exc)).encode(), None,
                              time.monotonic() - started, "launch_error", cancellation)
    selector = selectors.DefaultSelector()
    streams = {"stdout": bytearray(), "stderr": bytearray()}
    total = 0
    offset = 0
    stop = None
    deadline = started + timeout
    term_at = None
    kill_at = None

    def terminate(reason):
        nonlocal term_at
        cancellation.reason = reason
        cancellation.requested = reason != "leader-exited"
        if term_at is None:
            term_at = time.monotonic()
            try:
                os.killpg(proc.pid, signal.SIGTERM)
                cancellation.term_sent = True
            except ProcessLookupError:
                pass

    for name in ("stdout", "stderr"):
        stream = getattr(proc, name)
        os.set_blocking(stream.fileno(), False)
        selector.register(stream, selectors.EVENT_READ, name)
    if stdin:
        os.set_blocking(proc.stdin.fileno(), False)
        selector.register(proc.stdin, selectors.EVENT_WRITE, "stdin")
    else:
        proc.stdin.close()
    try:
        while selector.get_map() or proc.poll() is None:
            now = time.monotonic()
            if stop is None and cancel_event is not None and cancel_event.is_set():
                stop = "cancelled"
            if stop is None and now >= deadline:
                stop = "timeout"
            if stop is not None:
                terminate(stop)
            # Also clean remaining group members after a normally exiting leader.
            if proc.poll() is not None:
                terminate(stop or "leader-exited")
            if term_at is not None and now - term_at >= grace and kill_at is None:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                    cancellation.kill_sent = True
                except ProcessLookupError:
                    pass
                kill_at = now
            if kill_at is not None and now - kill_at > 1.0:
                break  # A detached pipe holder cannot make collection unbounded.
            for key, mask in selector.select(0.02):
                stream, name = key.fileobj, key.data
                if name == "stdin":
                    try:
                        offset += os.write(stream.fileno(), stdin[offset:offset + 4096])
                    except BrokenPipeError:
                        offset = len(stdin)
                    except BlockingIOError:
                        continue
                    if offset == len(stdin):
                        selector.unregister(stream)
                        stream.close()
                    continue
                try:
                    chunk = os.read(stream.fileno(), 8192)
                except BlockingIOError:
                    continue
                if not chunk:
                    selector.unregister(stream)
                    stream.close()
                    continue
                remaining = max_bytes - total
                streams[name].extend(chunk[:remaining])
                total += min(len(chunk), remaining)
                if len(chunk) > remaining:
                    stop = "output_limit"
                if stop is None and stop_predicate is not None:
                    stop = stop_predicate(bytes(streams['stdout']), bytes(streams['stderr']))
    except (KeyboardInterrupt, SystemExit):
        stop = "interrupted"
        terminate(stop)
    finally:
        # Always signal the group, including when the leader already closed its pipes.
        terminate(stop or "leader-exited")
        until = time.monotonic() + grace
        while group_exists(proc.pid) and time.monotonic() < until:
            proc.poll()
            time.sleep(0.01)
        if group_exists(proc.pid):
            try:
                os.killpg(proc.pid, signal.SIGKILL)
                cancellation.kill_sent = True
            except ProcessLookupError:
                pass
        try:
            proc.wait(timeout=1)
            cancellation.leader_reaped = True
        except subprocess.TimeoutExpired:
            pass
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            stream.close()
        selector.close()
        until = time.monotonic() + 0.3
        while group_exists(proc.pid) and time.monotonic() < until:
            time.sleep(0.01)
        cancellation.process_group_gone = not group_exists(proc.pid)
    return ProcessOutcome(bytes(streams["stdout"]), bytes(streams["stderr"]), proc.returncode,
                          round(time.monotonic() - started, 6), stop, cancellation)
