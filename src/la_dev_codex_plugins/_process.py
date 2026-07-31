"""Bounded subprocess execution for installed-package features."""

import contextlib
import os
import signal
import subprocess
import threading


class BoundedProcessResult:
    """Captured bounded subprocess state."""

    __slots__ = ("capture_incomplete", "launch_error", "returncode", "stderr", "stderr_truncated", "stdout", "stdout_truncated", "timed_out")

    def __init__(self, returncode=None, stdout=b"", stderr=b"", timed_out=False, stdout_truncated=False, stderr_truncated=False, capture_incomplete=False, launch_error=None):
        """Store completion, capped streams, timeout state, and launch failure."""
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.timed_out = timed_out
        self.stdout_truncated = stdout_truncated
        self.stderr_truncated = stderr_truncated
        self.capture_incomplete = capture_incomplete
        self.launch_error = launch_error


def _capture_pipe(pipe, limit, result):
    """Drain one pipe while retaining no more than the requested byte limit."""
    retained = bytearray()
    truncated = False
    complete = True
    try:
        while True:
            chunk = pipe.read(8192)
            if not chunk:
                break
            remaining = limit - len(retained)
            if remaining > 0:
                retained.extend(chunk[:remaining])
            if len(chunk) > remaining:
                truncated = True
    except (OSError, ValueError):
        complete = False
    finally:
        try:
            pipe.close()
        except (OSError, ValueError):
            complete = False
        result.append((bytes(retained), truncated, complete))


def _signal_process_tree(process, force, graceful_signal=None):
    """Signal an isolated process tree, falling back to its direct child."""
    try:
        signal_number = signal.SIGKILL if force else signal.SIGTERM if graceful_signal is None else graceful_signal
        os.killpg(process.pid, signal_number)
        return True
    except (AttributeError, OSError):
        pass
    try:
        if force:
            process.kill()
        else:
            process.terminate()
    except OSError:
        pass
    return False


def stop_process_tree(process, graceful_signal=None):
    """Stop one isolated process tree with a short graceful interval."""
    tree_signaled = _signal_process_tree(process, force=False, graceful_signal=graceful_signal)
    still_running = False
    try:
        process.wait(timeout=0.25)
    except subprocess.TimeoutExpired:
        still_running = True
    if tree_signaled or still_running:
        _signal_process_tree(process, force=True)
    if still_running:
        process.wait()


def _finish_pipe_capture(process, threads, pipes, results):
    """Finish pipe readers after cleaning descendants that retained handles."""
    for thread in threads:
        thread.join(timeout=0.1)
    if any(thread.is_alive() for thread in threads):
        stop_process_tree(process)
        for thread in threads:
            thread.join(timeout=1)
    if any(thread.is_alive() for thread in threads):
        for pipe in pipes:
            with contextlib.suppress(OSError, ValueError):
                pipe.close()
        for thread in threads:
            thread.join(timeout=0.1)
    captures = [result[0] if result else (b"", False, False) for result in results]
    incomplete = any(thread.is_alive() for thread in threads) or any(not capture[2] for capture in captures)
    return captures, incomplete


def run_bounded_process(command, cwd, env, timeout, output_limit, popen_factory=None):
    """Run one command with exact environment, capped streams, and timeout."""
    if popen_factory is None:
        popen_factory = subprocess.Popen
    try:
        process = popen_factory(command, cwd=cwd, env=dict(env), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False, start_new_session=True)
    except OSError as exc:
        return BoundedProcessResult(launch_error=str(exc))

    stdout_result = []
    stderr_result = []
    stdout_thread = threading.Thread(target=_capture_pipe, args=(process.stdout, output_limit, stdout_result))
    stderr_thread = threading.Thread(target=_capture_pipe, args=(process.stderr, output_limit, stderr_result))
    stdout_thread.daemon = True
    stderr_thread.daemon = True
    stdout_thread.start()
    stderr_thread.start()

    timed_out = False
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        stop_process_tree(process)
    captures, capture_incomplete = _finish_pipe_capture(process, (stdout_thread, stderr_thread), (process.stdout, process.stderr), (stdout_result, stderr_result))
    stdout, stderr = captures
    return BoundedProcessResult(
        returncode=process.returncode,
        stdout=stdout[0],
        stderr=stderr[0],
        timed_out=timed_out,
        stdout_truncated=stdout[1],
        stderr_truncated=stderr[1],
        capture_incomplete=capture_incomplete,
    )
