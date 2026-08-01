"""Explicit pytest-isolation plugin loading and dispatch tests."""

import importlib.util
import pathlib
import typing

import la_dev_codex_plugins.pytest_isolation.plugin as isolation_plugin


def test_plugin_import_does_not_require_typing_noreturn(monkeypatch):
    monkeypatch.delattr(typing, "NoReturn", raising=False)
    path = pathlib.Path(isolation_plugin.__file__)
    specification = importlib.util.spec_from_file_location("pytest_isolation_without_noreturn", str(path))
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)


def test_plugin_absent_leaves_marker_and_fixture_unavailable(run_isolation):
    result = run_isolation(
        """
import pytest

@pytest.mark.isolated_cwd
def test_marker_without_plugin():
    pass

def test_fixture_without_plugin(isolated_cwd):
    pass
""",
        "--strict-markers",
        load_plugin=False,
    )
    assert result.ret != 0
    result.stdout.fnmatch_lines(["*isolated_cwd*not found*"])


def test_explicit_p_option_loads_markers_and_fixtures(run_isolation):
    result = run_isolation(
        """
from pathlib import Path
import os

def test_fixture(isolated_cwd):
    assert Path.cwd() == isolated_cwd
    assert isolated_cwd.name == "cwd"
    assert Path(os.environ["TMPDIR"]).name == "tmp"
"""
    )
    result.assert_outcomes(passed=1)


def test_explicit_pytest_plugins_loading_works_without_p_option(run_isolation):
    result = run_isolation(
        """
from pathlib import Path

pytest_plugins = ("la_dev_codex_plugins.pytest_isolation.plugin",)

def test_fixture(isolated_cwd):
    assert Path.cwd() == isolated_cwd
""",
        load_plugin=False,
    )
    result.assert_outcomes(passed=1)


def test_unmarked_test_has_no_cwd_environment_or_tempdir_mutation(run_isolation):
    result = run_isolation(
        """
import os
import tempfile

ORIGINAL_CWD = os.getcwd()
ORIGINAL_ENV = {name: os.environ.get(name) for name in ("TMPDIR", "TEMP", "TMP")}
ORIGINAL_TEMPDIR = tempfile.tempdir

def test_unmarked():
    assert os.getcwd() == ORIGINAL_CWD
    assert {name: os.environ.get(name) for name in ORIGINAL_ENV} == ORIGINAL_ENV
    assert tempfile.tempdir is ORIGINAL_TEMPDIR
"""
    )
    result.assert_outcomes(passed=1)


def test_unmarked_test_does_not_allocate_isolation_boundary(run_isolation):
    result = run_isolation(
        """
def test_unmarked():
    assert True
""",
        conftest="""
import la_dev_codex_plugins.pytest_isolation.plugin as isolation_plugin

def forbidden_create_boundary(*args, **kwargs):
    raise AssertionError("unmarked test allocated an isolation boundary")

isolation_plugin._create_boundary = forbidden_create_boundary
""",
    )
    result.assert_outcomes(passed=1)


def test_opposite_modes_and_invalid_isolated_marker_arguments_fail_setup(run_isolation):
    result = run_isolation(
        """
import pytest

@pytest.mark.guarded_cwd
@pytest.mark.isolated_cwd
def test_both_markers():
    pass

def test_both_fixtures(guarded_cwd, isolated_cwd):
    pass

@pytest.mark.guarded_cwd
def test_guarded_marker_isolated_fixture(isolated_cwd):
    pass

@pytest.mark.isolated_cwd
def test_isolated_marker_guarded_fixture(guarded_cwd):
    pass

@pytest.mark.isolated_cwd("unexpected")
def test_isolated_argument():
    pass
"""
    )
    result.assert_outcomes(errors=5)
    result.stdout.fnmatch_lines(["*guarded_cwd and isolated_cwd cannot be applied*", "*isolated_cwd accepts no positional or keyword arguments*"])


def test_partial_boundary_setup_failure_restores_process_state(run_isolation):
    result = run_isolation(
        """
import os
import tempfile

ORIGINAL_CWD = os.getcwd()
ORIGINAL_ENV = {name: os.environ.get(name) for name in ("TMPDIR", "TEMP", "TMP")}
ORIGINAL_TEMPDIR = tempfile.tempdir

def test_setup_failure(isolated_cwd):
    pass

def test_restored_after_setup_failure():
    assert os.getcwd() == ORIGINAL_CWD
    assert {name: os.environ.get(name) for name in ORIGINAL_ENV} == ORIGINAL_ENV
    assert tempfile.tempdir is ORIGINAL_TEMPDIR
""",
        conftest="""
import la_dev_codex_plugins.pytest_isolation.plugin as isolation_plugin

original_create_boundary = isolation_plugin._create_boundary

def fail_after_boundary_creation(state, poison_files):
    original_create_boundary(state, poison_files)
    raise RuntimeError("partial boundary setup failed")

isolation_plugin._create_boundary = fail_after_boundary_creation
""",
    )
    result.assert_outcomes(passed=1, errors=1)
    result.stdout.fnmatch_lines(["*partial boundary setup failed*"])


def test_chdir_setup_failure_restores_redirected_environment(run_isolation):
    result = run_isolation(
        """
import os
import tempfile

ORIGINAL_CWD = os.getcwd()
ORIGINAL_ENV = {name: os.environ.get(name) for name in ("TMPDIR", "TEMP", "TMP")}
ORIGINAL_TEMPDIR = tempfile.tempdir

def test_setup_failure(isolated_cwd):
    pass

def test_restored_after_setup_failure():
    assert os.getcwd() == ORIGINAL_CWD
    assert {name: os.environ.get(name) for name in ORIGINAL_ENV} == ORIGINAL_ENV
    assert tempfile.tempdir is ORIGINAL_TEMPDIR
""",
        conftest="""
import os
import la_dev_codex_plugins.pytest_isolation.plugin as isolation_plugin

original_chdir = isolation_plugin.os.chdir
failed = [False]

def fail_boundary_chdir(path):
    if not failed[0] and os.path.basename(path) == "cwd":
        failed[0] = True
        raise OSError("boundary chdir failed")
    return original_chdir(path)

isolation_plugin.os.chdir = fail_boundary_chdir
""",
    )
    result.assert_outcomes(passed=1, errors=1)
    result.stdout.fnmatch_lines(["*boundary chdir failed*"])


def test_dispatcher_precedes_and_outlives_ordinary_function_fixtures(run_isolation):
    result = run_isolation(
        """
from pathlib import Path
import pytest

@pytest.fixture
def ordinary_fixture():
    cwd = Path.cwd()
    assert cwd.name == "cwd"
    yield cwd
    assert Path.cwd() == cwd
    (cwd / "teardown.txt").write_text("ok", encoding="utf-8")

def test_order(isolated_cwd, ordinary_fixture):
    assert ordinary_fixture == isolated_cwd
"""
    )
    result.assert_outcomes(passed=1)
