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


def test_partial_boundary_creation_failure_removes_identified_components(run_isolation, monkeypatch, tmp_path):
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    for method_name, target_name in (("chmod", "boundary"), ("mkdir", "cwd"), ("chmod", "cwd"), ("mkdir", "tmp"), ("chmod", "tmp")):
        result = run_isolation(
            """
def test_setup_failure(isolated_cwd):
    pass
""",
            conftest="""
import la_dev_codex_plugins.pytest_isolation.plugin as isolation_plugin

method_name = {method_name!r}
target_name = {target_name!r}
original = getattr(isolation_plugin.pathlib.Path, method_name)

def fail_creation_step(path, *args, **kwargs):
    is_boundary = path.name.startswith("la-dev-pytest-isolation-")
    if (target_name == "boundary" and is_boundary) or (target_name != "boundary" and path.name == target_name and path.parent.name.startswith("la-dev-pytest-isolation-")):
        raise OSError("injected {{}} {{}} failure".format(target_name, method_name))
    return original(path, *args, **kwargs)

setattr(isolation_plugin.pathlib.Path, method_name, fail_creation_step)
""".format(method_name=method_name, target_name=target_name),
        )
        result.assert_outcomes(errors=1)
        result.stdout.fnmatch_lines(["*injected {} {} failure*".format(target_name, method_name)])
        assert not list(tmp_path.glob("la-dev-pytest-isolation-*"))


def test_private_setup_restoration_failure_preserves_keyboard_interrupt(run_isolation):
    result = run_isolation(
        """
def test_interrupt(isolated_cwd):
    pass
""",
        conftest="""
import la_dev_codex_plugins.pytest_isolation.plugin as isolation_plugin

def interrupt_setup(*args, **kwargs):
    raise KeyboardInterrupt("injected setup interrupt")

def fail_cleanup(state, failures):
    state.cleanup_complete = False
    failures.append("injected restoration failure")

isolation_plugin._create_boundary = interrupt_setup
isolation_plugin._cleanup_boundary = fail_cleanup
""",
    )
    assert result.ret == 2
    output = "\n".join(result.stdout.lines + result.stderr.lines)
    assert "injected setup interrupt" in output
    assert "injected restoration failure" in output
    assert "Isolation setup failed" not in output


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


def test_dispatcher_precedes_and_outlives_downstream_autouse_function_fixtures(run_isolation):
    result = run_isolation(
        """
from pathlib import Path
import pytest

@pytest.fixture(autouse=True)
def downstream_autouse_fixture():
    cwd = Path.cwd()
    assert cwd.name == "cwd"
    yield cwd
    assert Path.cwd() == cwd

@pytest.mark.isolated_cwd
def test_order():
    assert Path.cwd().name == "cwd"
"""
    )
    result.assert_outcomes(passed=1)


def test_custom_items_without_fixture_metadata_work_in_both_unmarked_modes(run_isolation):
    for mode in ("none", "shared_guarded"):
        result = run_isolation(
            None,
            config="[pytest]\nla_dev_cwd_isolation_unmarked = {}\n".format(mode),
            conftest="""
import pathlib
import pytest

EXPECTED_SHARED = {expected_shared}

class BareItem(pytest.Item):
    def runtest(self):
        assert (pathlib.Path.cwd().name == "cwd") is EXPECTED_SHARED

    def reportinfo(self):
        return self.path, 0, self.name

class BareFile(pytest.File):
    def collect(self):
        yield BareItem.from_parent(self, name="bare")

def pytest_collect_file(file_path, parent):
    if file_path.suffix == ".custom":
        return BareFile.from_parent(parent, path=file_path)
""".format(expected_shared=mode == "shared_guarded"),
            files={"case.custom": "custom\n"},
        )
        result.assert_outcomes(passed=1)


def test_force_outcome_exception_supports_modern_and_pluggy_1_0_results():
    exception = RuntimeError("forced")

    class ModernOutcome:
        def __init__(self):
            self.exception = None

        def force_exception(self, forced):
            self.exception = forced

    modern = ModernOutcome()
    isolation_plugin._force_outcome_exception(modern, exception)
    assert modern.exception is exception

    class LegacyOutcome:
        def __init__(self):
            self._excinfo = None

    legacy = LegacyOutcome()
    isolation_plugin._force_outcome_exception(legacy, exception)
    assert legacy._excinfo == (RuntimeError, exception, exception.__traceback__)
