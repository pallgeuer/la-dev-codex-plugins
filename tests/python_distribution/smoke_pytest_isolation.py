#!/usr/bin/env python3
"""Smoke checks for the explicitly loaded installed pytest-isolation plugin."""

import argparse
import os
import pathlib
import shutil
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


def remove_retained_tree(path):
    """Restore owner permissions and remove one intentional smoke fixture."""
    for root, directories, files in os.walk(str(path)):
        root_path = pathlib.Path(root)
        root_path.chmod(0o700)
        for name in directories:
            child = root_path / name
            if not child.is_symlink():
                child.chmod(0o700)
        for name in files:
            child = root_path / name
            if not child.is_symlink():
                child.chmod(0o600)
    shutil.rmtree(str(path))


def smoke_plugin(expected_pytest_version):
    """Run temporary suites covering default, explicit, and shared isolation."""
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

        shared_record = suite_root / "shared-boundary.txt"
        restored_record = suite_root / "shared-restored.txt"
        pytest_temp_record = suite_root / "pytest-temp-record.txt"
        (suite_root / "pytest.ini").write_text("[pytest]\nla_dev_cwd_isolation_unmarked = shared_guarded\n", encoding="ascii")
        (suite_root / "conftest.py").write_text(
            """import os
import pathlib
import tempfile

INITIAL_CWD = os.getcwd()
INITIAL_ENVIRONMENT = {{name: (name in os.environ, os.environ.get(name)) for name in ("TMPDIR", "TEMP", "TMP")}}
INITIAL_TEMPDIR = tempfile.tempdir
RECORD = pathlib.Path({record})
RESTORED = pathlib.Path({restored})


def pytest_la_dev_cwd_isolation_shared_policy(config):
    return {{"boundary_files": {{"neutral.toml": "[tool.project]\\n"}}}}


def pytest_unconfigure(config):
    assert os.getcwd() == INITIAL_CWD
    for name, previous in INITIAL_ENVIRONMENT.items():
        assert (name in os.environ, os.environ.get(name)) == previous
    assert tempfile.tempdir is INITIAL_TEMPDIR
    boundary = pathlib.Path(RECORD.read_text(encoding="ascii"))
    assert not boundary.exists()
    RESTORED.write_text("restored", encoding="ascii")
""".format(record=repr(str(shared_record)), restored=repr(str(restored_record))),
            encoding="ascii",
        )
        shared_path = suite_root / "test_shared_guard.py"
        shared_path.write_text(
            """import os
import pathlib
import stat
import tempfile

import pytest

EXPECTED_POISON = "[tool.la_dev_cwd_guard\\n"
RECORD = pathlib.Path({record})
PYTEST_TEMP_RECORD = pathlib.Path({pytest_temp_record})
SHARED_CWD = None
SHARED_TMP = None


@pytest.fixture(scope="session", autouse=True)
def stable_session_fixture():
    cwd = pathlib.Path.cwd()
    resource = pathlib.Path(os.environ["TMPDIR"]) / "session-resource"
    resource.write_text("session", encoding="ascii")
    yield
    assert pathlib.Path.cwd() == cwd
    assert resource.read_text(encoding="ascii") == "session"


@pytest.fixture(scope="module", autouse=True)
def stable_module_fixture():
    cwd = pathlib.Path.cwd()
    resource = pathlib.Path(os.environ["TMPDIR"]) / "module-resource"
    resource.write_text("module", encoding="ascii")
    yield
    assert pathlib.Path.cwd() == cwd
    assert resource.read_text(encoding="ascii") == "module"


@pytest.fixture(autouse=True)
def assert_downstream_fixture_is_contained():
    active_cwd = pathlib.Path.cwd()
    assert active_cwd.name == "cwd"
    yield
    assert pathlib.Path.cwd() == active_cwd


def _assert_shared():
    cwd = pathlib.Path.cwd()
    tmp = pathlib.Path(os.environ["TMPDIR"])
    assert cwd == SHARED_CWD
    assert tmp == SHARED_TMP
    assert os.environ["TEMP"] == os.environ["TMP"] == str(tmp)
    assert pathlib.Path(tempfile.gettempdir()) == tmp


def test_01_first_shared_guard(tmp_path):
    global SHARED_CWD, SHARED_TMP
    SHARED_CWD = pathlib.Path.cwd()
    SHARED_TMP = pathlib.Path(os.environ["TMPDIR"])
    poison = SHARED_CWD / "pyproject.toml"
    assert poison.read_text(encoding="utf-8") == EXPECTED_POISON
    assert stat.S_IMODE(SHARED_CWD.stat().st_mode) == 0o500
    assert stat.S_IMODE(poison.stat().st_mode) == 0o400
    assert stat.S_IMODE(SHARED_TMP.stat().st_mode) == 0o700
    neutral = SHARED_CWD.parent / "neutral.toml"
    assert neutral.read_text(encoding="utf-8") == "[tool.project]\\n"
    assert stat.S_IMODE(neutral.stat().st_mode) == 0o400
    retained = tmp_path / "retained.txt"
    retained.write_text("retained", encoding="ascii")
    assert SHARED_CWD.parent not in retained.parents
    PYTEST_TEMP_RECORD.write_text(str(retained), encoding="ascii")
    RECORD.write_text(str(SHARED_CWD.parent), encoding="ascii")
    _assert_shared()


def test_02_second_test_reuses_shared_guard():
    _assert_shared()


@pytest.mark.isolated_cwd
def test_03_explicit_isolated_override():
    private_cwd = pathlib.Path.cwd()
    assert private_cwd != SHARED_CWD
    assert pathlib.Path(os.environ["TMPDIR"]) == private_cwd.parent / "tmp"
    (private_cwd / "writable").write_text("ok", encoding="ascii")


def test_04_returns_to_shared_guard():
    _assert_shared()
""".format(record=repr(str(shared_record)), pytest_temp_record=repr(str(pytest_temp_record))),
            encoding="ascii",
        )
        shared_stdout, _shared_stderr = run(
            [sys.executable, "-m", "pytest", "-p", "la_dev_codex_plugins.pytest_isolation.plugin", "-q", str(shared_path)],
            str(suite_root),
        )
        if "4 passed" not in shared_stdout:
            raise AssertionError("Shared pytest suite did not report four passing tests: {!r}".format(shared_stdout))
        if not shared_record.is_file():
            raise AssertionError("Shared pytest suite did not create its boundary record")
        shared_boundary_value = shared_record.read_text(encoding="ascii")
        if shared_boundary_value == "":
            raise AssertionError("Shared pytest suite did not record its boundary")
        if pathlib.Path(shared_boundary_value).exists():
            raise AssertionError("Shared pytest boundary remained after session teardown")
        if not pytest_temp_record.is_file():
            raise AssertionError("Shared pytest suite did not record its pytest temporary artifact")
        retained = pathlib.Path(pytest_temp_record.read_text(encoding="ascii"))
        if retained.read_text(encoding="ascii") != "retained":
            raise AssertionError("Shared pytest suite did not preserve its pytest temporary artifact")
        if restored_record.read_text(encoding="ascii") != "restored":
            raise AssertionError("Shared pytest suite did not verify session restoration")

        retained_record = suite_root / "retained-boundaries.txt"
        retained_restored = suite_root / "retained-restored.txt"
        (suite_root / "pytest.ini").write_text(
            "[pytest]\nla_dev_cwd_isolation_unmarked = shared_guarded\nla_dev_cwd_isolation_cleanup = pytest_retained\n",
            encoding="ascii",
        )
        (suite_root / "conftest.py").write_text(
            """import os
import pathlib
import tempfile

INITIAL_CWD = os.getcwd()
INITIAL_ENVIRONMENT = {{name: (name in os.environ, os.environ.get(name)) for name in ("TMPDIR", "TEMP", "TMP")}}
INITIAL_TEMPDIR = tempfile.tempdir
RECORD = pathlib.Path({record})
RESTORED = pathlib.Path({restored})

def pytest_unconfigure(config):
    assert os.getcwd() == INITIAL_CWD
    assert {{name: (name in os.environ, os.environ.get(name)) for name in INITIAL_ENVIRONMENT}} == INITIAL_ENVIRONMENT
    assert tempfile.tempdir is INITIAL_TEMPDIR
    boundaries = [pathlib.Path(value) for value in RECORD.read_text(encoding="ascii").splitlines()]
    assert all(boundary.is_dir() for boundary in boundaries)
    RESTORED.write_text("restored", encoding="ascii")
""".format(record=repr(str(retained_record)), restored=repr(str(retained_restored))),
            encoding="ascii",
        )
        retained_path = suite_root / "test_retained_guard.py"
        retained_path.write_text(
            """import pathlib

RECORD = pathlib.Path({record})
SHARED = None

def test_01_shared_retained():
    global SHARED
    SHARED = pathlib.Path.cwd().parent
    RECORD.write_text(str(SHARED) + "\\n", encoding="ascii")

def test_02_nested_private_retained(isolated_cwd):
    private = isolated_cwd.parent
    assert private.parent == SHARED / "tmp"
    with RECORD.open("a", encoding="ascii") as handle:
        handle.write(str(private) + "\\n")
""".format(record=repr(str(retained_record))),
            encoding="ascii",
        )
        retained_stdout, retained_stderr = run(
            [sys.executable, "-m", "pytest", "-p", "la_dev_codex_plugins.pytest_isolation.plugin", "-q", str(retained_path)],
            str(suite_root),
        )
        if "2 passed" not in retained_stdout:
            raise AssertionError("Retained pytest suite did not report two passing tests: {!r}".format(retained_stdout))
        if "incomplete" in retained_stdout + retained_stderr:
            raise AssertionError("Retained pytest suite reported incomplete cleanup: {!r}".format(retained_stdout + retained_stderr))
        retained_boundaries = [pathlib.Path(value) for value in retained_record.read_text(encoding="ascii").splitlines()]
        if len(retained_boundaries) != 2 or not all(boundary.is_dir() for boundary in retained_boundaries):
            raise AssertionError("Retained pytest suite did not preserve shared and private boundaries")
        if retained_boundaries[1].parent != retained_boundaries[0] / "tmp":
            raise AssertionError("Retained private boundary was not nested below the shared temporary directory")
        if retained_restored.read_text(encoding="ascii") != "restored":
            raise AssertionError("Retained pytest suite did not verify session restoration")
        remove_retained_tree(retained_boundaries[0])
        (suite_root / "pytest.ini").unlink()
        (suite_root / "conftest.py").unlink()

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
            [sys.executable, "-m", "pytest", "-p", "la_dev_codex_plugins.pytest_isolation.plugin", "-q", "-o", "la_dev_cwd_isolation_unmarked=none", str(leak_path)],
            str(suite_root),
            expected_returncode=1,
        )
        leak_output = leak_stdout + leak_stderr
        if "guarded_cwd test escaped its guarded working directory" not in leak_output:
            raise AssertionError("Guarded leak smoke did not report the expected protection: {!r}".format(leak_output))
        if "AttributeError" in leak_output or "force_exception" in leak_output:
            raise AssertionError("Guarded leak smoke used an incompatible Pluggy outcome API: {!r}".format(leak_output))


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
