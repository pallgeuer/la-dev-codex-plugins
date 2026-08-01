#!/usr/bin/env python3
"""Smoke checks for the explicitly loaded installed pytest-isolation plugin."""

import argparse
import pathlib
import subprocess
import sys
import tempfile


def run(command, cwd, expected_returncode=0):
    """Run one command and return decoded output after requiring one status."""
    completed = subprocess.run(
        command,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=False,
    )
    stdout = completed.stdout.decode("utf-8", errors="replace")
    stderr = completed.stderr.decode("utf-8", errors="replace")
    if completed.returncode != expected_returncode:
        raise AssertionError("Command returned exit code {}, expected {}: {!r}\nstdout:\n{}\nstderr:\n{}".format(completed.returncode, expected_returncode, command, stdout, stderr))
    return stdout, stderr


def smoke_plugin(expected_pytest_version):
    """Run a temporary suite covering marker-only and fixture-only opt-in."""
    with tempfile.TemporaryDirectory(prefix="la-dev-pytest-isolation-smoke-") as temporary_directory:
        suite_root = pathlib.Path(temporary_directory).resolve()
        test_path = suite_root / "test_installed_plugin.py"
        test_path.write_text(
            """import os
import pathlib
import stat
import tempfile

import pytest

EXPECTED_CWD = {expected_cwd}
EXPECTED_POISON = "[tool.la_dev_cwd_guard\\n"


def _assert_redirected_tmp(cwd):
    values = {{os.environ[name] for name in ("TMPDIR", "TEMP", "TMP")}}
    assert len(values) == 1
    tmp = pathlib.Path(values.pop())
    assert tmp == pathlib.Path(tempfile.gettempdir())
    assert tmp.name == "tmp"
    assert tmp.parent == cwd.parent
    assert tmp != cwd
    (tmp / "writable").write_text("ok", encoding="ascii")


def test_unmarked_keeps_normal_cwd():
    assert os.getcwd() == EXPECTED_CWD


@pytest.mark.isolated_cwd
def test_marker_only_isolated_mode():
    cwd = pathlib.Path.cwd()
    assert cwd.name == "cwd"
    (cwd / "writable").write_text("ok", encoding="ascii")
    _assert_redirected_tmp(cwd)


def test_fixture_only_isolated_mode(isolated_cwd):
    assert pathlib.Path.cwd() == isolated_cwd
    assert isolated_cwd.name == "cwd"
    _assert_redirected_tmp(isolated_cwd)


@pytest.mark.guarded_cwd
def test_marker_only_guarded_mode():
    cwd = pathlib.Path.cwd()
    poison = cwd / "pyproject.toml"
    assert poison.read_text(encoding="utf-8") == EXPECTED_POISON
    assert stat.S_IMODE(cwd.stat().st_mode) == 0o500
    assert stat.S_IMODE(poison.stat().st_mode) == 0o400
    _assert_redirected_tmp(cwd)


def test_fixture_only_guarded_mode(guarded_cwd):
    assert pathlib.Path.cwd() == guarded_cwd
    poison = guarded_cwd / "pyproject.toml"
    assert poison.read_text(encoding="utf-8") == EXPECTED_POISON
    assert stat.S_IMODE(guarded_cwd.stat().st_mode) == 0o500
    assert stat.S_IMODE(poison.stat().st_mode) == 0o400
    _assert_redirected_tmp(guarded_cwd)
""".format(expected_cwd=repr(str(suite_root))),
            encoding="ascii",
        )
        version_stdout, version_stderr = run([sys.executable, "-m", "pytest", "--version"], str(suite_root))
        expected_prefix = "pytest {}".format(expected_pytest_version)
        if not version_stdout.startswith(expected_prefix) or version_stderr:
            raise AssertionError("Unexpected pytest version output: stdout={!r}, stderr={!r}".format(version_stdout, version_stderr))
        stdout, _stderr = run(
            [sys.executable, "-m", "pytest", "-p", "la_dev_codex_plugins.pytest_isolation.plugin", "-q", str(test_path)],
            str(suite_root),
        )
        if "5 passed" not in stdout:
            raise AssertionError("Temporary pytest suite did not report five passing tests: {!r}".format(stdout))

        leak_path = suite_root / "test_guarded_leak.py"
        leak_path.write_text(
            """import os

import pytest


@pytest.mark.guarded_cwd
def test_guarded_leak_is_detected():
    os.chdir(os.environ["TMPDIR"])
""",
            encoding="ascii",
        )
        leak_stdout, leak_stderr = run(
            [sys.executable, "-m", "pytest", "-p", "la_dev_codex_plugins.pytest_isolation.plugin", "-q", str(leak_path)],
            str(suite_root),
            expected_returncode=1,
        )
        leak_output = leak_stdout + leak_stderr
        if "guarded_cwd test escaped its guarded working directory" not in leak_output:
            raise AssertionError("Guarded leak smoke did not report the expected protection: {!r}".format(leak_output))


def main(argv=None):
    """Run installed pytest-isolation smoke checks."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-pytest-version", required=True)
    args = parser.parse_args(argv)
    if sys.version_info < (3, 6):
        raise AssertionError("Python 3.6+ is required")
    smoke_plugin(args.expected_pytest_version)
    print("Installed pytest-isolation smoke checks passed on Python {}.{}.{}.".format(*sys.version_info[:3]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
