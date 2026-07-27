"""Shared behavioral contract for bounded subprocess implementations."""

import importlib
import io
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from la_dev_codex_plugins.cli import _perform_runtime as perform_runtime

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PERFORM_SCRIPTS = REPOSITORY_ROOT / "plugins" / "toolkit" / "skills" / "perform" / "scripts"
sys.path.insert(0, str(PERFORM_SCRIPTS))
discovery_module = importlib.import_module("toolkit_perform_runtime.discovery")


class FakeProcess:
    """Popen test double with controllable waits and bounded pipes."""

    def __init__(self, stdout=b"", stderr=b"", returncode=0, timeout_count=0, stdout_pipe=None, stderr_pipe=None):
        self.stdout = io.BytesIO(stdout) if stdout_pipe is None else stdout_pipe
        self.stderr = io.BytesIO(stderr) if stderr_pipe is None else stderr_pipe
        self.returncode = returncode
        self.timeout_count = timeout_count
        self.wait_calls = 0
        self.terminated = False
        self.killed = False

    def wait(self, timeout=None):
        """Return completion after the configured number of timeouts."""
        self.wait_calls += 1
        if self.wait_calls <= self.timeout_count:
            raise subprocess.TimeoutExpired("bounded-process", 0 if timeout is None else timeout)
        return self.returncode

    def terminate(self):
        """Record graceful termination."""
        self.terminated = True

    def kill(self):
        """Record forced termination."""
        self.killed = True


class BrokenPipe:
    """Pipe double whose contents cannot be captured completely."""

    def read(self, _size):
        """Fail every read."""
        raise OSError("broken pipe")

    def close(self):
        """Accept cleanup."""


class SourceRuntimeAdapter:
    """Adapt source launcher plugin discovery to the shared contract."""

    module = perform_runtime
    output_limit = 4096

    def run(self, cwd, popen_factory, timeout=0.1):
        """Run one bounded source-launcher command."""
        return perform_runtime._run_bounded_command(["codex", "plugin", "list"], str(cwd), {}, popen_factory=popen_factory, timeout=timeout, output_limit=self.output_limit)

    def run_real(self, cwd, command, timeout):
        """Run one real bounded source-launcher command."""
        return perform_runtime._run_bounded_command(command, str(cwd), os.environ, timeout=timeout, output_limit=self.output_limit)


class PluginRuntimeAdapter:
    """Adapt toolkit Git discovery to the shared contract."""

    module = discovery_module
    output_limit = discovery_module.GIT_OUTPUT_LIMIT

    def run(self, cwd, popen_factory, timeout=0.1):
        """Run one bounded toolkit Git command."""
        return discovery_module.run_bounded_git_root(str(cwd), popen_factory=popen_factory, timeout=timeout, env={})

    def run_real(self, cwd, command, timeout):
        """Run one real process through the bounded toolkit Git path."""

        def popen(_git_command, **kwargs):
            return subprocess.Popen(command, **kwargs)

        return discovery_module.run_bounded_git_root(str(cwd), popen_factory=popen, timeout=timeout, env=os.environ)


@pytest.fixture(params=(SourceRuntimeAdapter, PluginRuntimeAdapter), ids=("source-launcher", "toolkit-git"))
def bounded_process(request):
    """Return one bounded-process implementation adapter."""
    return request.param()


def test_bounded_process_caps_both_output_streams(tmp_path, bounded_process):
    process = FakeProcess(stdout=b"x" * (bounded_process.output_limit + 10), stderr=b"y" * (bounded_process.output_limit + 20))
    result = bounded_process.run(tmp_path, lambda _command, **_kwargs: process)
    assert len(result.stdout) == bounded_process.output_limit
    assert len(result.stderr) == bounded_process.output_limit
    assert result.stdout_truncated is True
    assert result.stderr_truncated is True
    assert result.capture_incomplete is False


def test_bounded_process_reports_launch_failures(tmp_path, bounded_process):
    def fail_launch(*_args, **_kwargs):
        raise OSError("missing executable")

    result = bounded_process.run(tmp_path, fail_launch)
    assert result.launch_error == "missing executable"
    assert result.returncode is None


def test_bounded_process_terminates_after_timeout(tmp_path, bounded_process):
    process = FakeProcess(timeout_count=1)
    result = bounded_process.run(tmp_path, lambda _command, **_kwargs: process, timeout=0.01)
    assert result.timed_out is True
    assert process.terminated is True
    assert process.killed is False


def test_bounded_process_kills_a_child_that_ignores_termination(tmp_path, bounded_process):
    process = FakeProcess(timeout_count=2)
    result = bounded_process.run(tmp_path, lambda _command, **_kwargs: process, timeout=0.01)
    assert result.timed_out is True
    assert process.terminated is True
    assert process.killed is True


def test_bounded_process_marks_incomplete_pipe_capture(tmp_path, bounded_process):
    process = FakeProcess(stdout_pipe=BrokenPipe())
    result = bounded_process.run(tmp_path, lambda _command, **_kwargs: process)
    assert result.capture_incomplete is True


def test_bounded_process_kills_descendants_that_retain_pipes(tmp_path, bounded_process):
    child_code = "import time; time.sleep(60)"
    parent_code = "import subprocess, sys, time; subprocess.Popen([sys.executable, '-c', {!r}]); time.sleep(60)".format(child_code)
    started = time.monotonic()
    result = bounded_process.run_real(tmp_path, [sys.executable, "-c", parent_code], timeout=0.1)
    elapsed = time.monotonic() - started
    assert result.timed_out is True
    assert result.capture_incomplete is False
    assert result.stdout_truncated is False
    assert result.stderr_truncated is False
    assert elapsed < 3
