"""Core configured session-shared working-directory behavior tests."""

import pathlib

import pytest

SHARED_CONFIG = """[pytest]
la_dev_cwd_isolation_unmarked = shared_guarded
"""


@pytest.mark.parametrize("configured", [None, "none"])
def test_default_modes_leave_unmarked_tests_untouched_without_requesting_policy(run_isolation, configured):
    arguments = () if configured is None else ("-o", "la_dev_cwd_isolation_unmarked={}".format(configured))
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
""",
        *arguments,
        conftest="""
import la_dev_codex_plugins.pytest_isolation.plugin as isolation_plugin

def pytest_la_dev_cwd_isolation_shared_policy(config):
    raise AssertionError("inactive shared poison policy was requested")

def forbidden_create_boundary(*args, **kwargs):
    raise AssertionError("inactive shared mode allocated a boundary")

isolation_plugin._create_boundary = forbidden_create_boundary
""",
    )
    result.assert_outcomes(passed=1)


def test_shared_session_reuses_guard_and_tmp_then_restores_and_cleans(run_isolation, monkeypatch, tmp_path):
    record = tmp_path / "shared-record.txt"
    restored = tmp_path / "restored.txt"
    pytest_temp_record = tmp_path / "pytest-temp-record.txt"
    monkeypatch.setenv("SHARED_RECORD", str(record))
    monkeypatch.setenv("SHARED_RESTORED", str(restored))
    monkeypatch.setenv("PYTEST_TEMP_RECORD", str(pytest_temp_record))
    result = run_isolation(
        """
import os
import pathlib
import stat
import tempfile

SHARED_CWD = None
SHARED_TMP = None

def test_01_first_shared_test(tmp_path):
    global SHARED_CWD, SHARED_TMP
    SHARED_CWD = pathlib.Path.cwd()
    SHARED_TMP = pathlib.Path(os.environ["TMPDIR"])
    assert os.environ["TEMP"] == os.environ["TMP"] == str(SHARED_TMP)
    assert SHARED_CWD.parent == SHARED_TMP.parent
    assert stat.S_IMODE(SHARED_CWD.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(SHARED_CWD.stat().st_mode) == 0o500
    assert stat.S_IMODE(SHARED_TMP.stat().st_mode) == 0o700
    poison = SHARED_CWD / "pyproject.toml"
    assert poison.read_bytes() == b"[tool.la_dev_cwd_guard\\n"
    assert stat.S_IMODE(poison.stat().st_mode) == 0o400
    with tempfile.NamedTemporaryFile(delete=False) as handle:
        temporary_file = pathlib.Path(handle.name)
    assert SHARED_TMP in temporary_file.parents
    retained = tmp_path / "retained.txt"
    retained.write_text("retained", encoding="ascii")
    assert SHARED_CWD.parent not in retained.parents
    pathlib.Path(os.environ["PYTEST_TEMP_RECORD"]).write_text(str(retained), encoding="ascii")
    pathlib.Path(os.environ["SHARED_RECORD"]).write_text(str(SHARED_CWD.parent), encoding="ascii")

def test_02_second_shared_test():
    assert pathlib.Path.cwd() == SHARED_CWD
    assert pathlib.Path(os.environ["TMPDIR"]) == SHARED_TMP
    assert tempfile.tempdir is None
    assert pathlib.Path(tempfile.gettempdir()) == SHARED_TMP
""",
        config=SHARED_CONFIG,
        conftest="""
import os
import pathlib
import tempfile

ORIGINAL = {}
_MISSING = object()

def pytest_sessionstart(session):
    ORIGINAL["cwd"] = os.getcwd()
    ORIGINAL["environment"] = {name: os.environ.get(name, _MISSING) for name in ("TMPDIR", "TEMP", "TMP")}
    ORIGINAL["tempdir"] = tempfile.tempdir

def pytest_unconfigure(config):
    assert os.getcwd() == ORIGINAL["cwd"]
    for name, previous in ORIGINAL["environment"].items():
        if previous is _MISSING:
            assert name not in os.environ
        else:
            assert os.environ[name] == previous
    assert tempfile.tempdir is ORIGINAL["tempdir"]
    boundary = pathlib.Path(pathlib.Path(os.environ["SHARED_RECORD"]).read_text(encoding="ascii"))
    assert not boundary.exists()
    pathlib.Path(os.environ["SHARED_RESTORED"]).write_text("restored", encoding="ascii")
""",
    )
    result.assert_outcomes(passed=2)
    assert not pathlib.Path(record.read_text(encoding="ascii")).exists()
    assert restored.read_text(encoding="ascii") == "restored"
    retained = pathlib.Path(pytest_temp_record.read_text(encoding="ascii"))
    assert retained.read_text(encoding="ascii") == "retained"


def test_pytest_temp_factory_initialization_preserves_tempfile_cache(run_isolation):
    result = run_isolation(
        """
import tempfile

def test_shared_state_redirects_only_after_collection():
    assert tempfile.tempdir is None
""",
        config=SHARED_CONFIG,
        conftest="""
import tempfile
import pytest

@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session):
    tempfile.tempdir = None

@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(session, config, items):
    assert tempfile.tempdir is None

@pytest.hookimpl(tryfirst=True)
def pytest_unconfigure(config):
    assert tempfile.tempdir is None
""",
    )
    result.assert_outcomes(passed=1)


def test_shared_boundary_exists_before_an_explicit_first_test(run_isolation):
    result = run_isolation(
        """
import os
import pathlib
import stat
import pytest

SHARED_BOUNDARY = None

@pytest.mark.isolated_cwd
def test_01_private_runs_after_shared_session_setup(isolated_cwd):
    global SHARED_BOUNDARY
    candidates = [parent for parent in isolated_cwd.parents if (parent / "session-anchor.txt").is_file()]
    assert len(candidates) == 1
    SHARED_BOUNDARY = candidates[0]
    anchor = SHARED_BOUNDARY / "session-anchor.txt"
    assert anchor.read_text(encoding="utf-8") == "anchor"
    assert stat.S_IMODE(anchor.stat().st_mode) == 0o400
    assert isolated_cwd.parent.parent == SHARED_BOUNDARY / "tmp"

def test_02_unmarked_uses_existing_shared_boundary():
    assert pathlib.Path.cwd().parent == SHARED_BOUNDARY
    assert pathlib.Path(os.environ["TMPDIR"]) == SHARED_BOUNDARY / "tmp"
""",
        config=SHARED_CONFIG,
        conftest="""
def pytest_la_dev_cwd_isolation_shared_policy(config):
    return {"boundary_files": {"session-anchor.txt": "anchor"}}
""",
    )
    result.assert_outcomes(passed=2)


def test_explicit_private_modes_override_shared_default_and_restore_it(run_isolation):
    result = run_isolation(
        """
import os
import pathlib
import tempfile
import pytest

SHARED = None
SHARED_TMP = None
PRIVATE = set()

def _assert_private(path):
    assert path != SHARED
    assert path.parent not in PRIVATE
    PRIVATE.add(path.parent)
    state_tmp = pathlib.Path(os.environ["TMPDIR"])
    assert state_tmp == path.parent / "tmp"
    assert state_tmp != SHARED_TMP

def test_01_shared():
    global SHARED, SHARED_TMP
    SHARED = pathlib.Path.cwd()
    SHARED_TMP = pathlib.Path(os.environ["TMPDIR"])

@pytest.mark.isolated_cwd
def test_02_isolated_marker():
    cwd = pathlib.Path.cwd()
    _assert_private(cwd)
    (cwd / "writable").write_text("ok", encoding="ascii")

def test_03_isolated_fixture(isolated_cwd):
    _assert_private(isolated_cwd)

def test_04_shared_again():
    assert pathlib.Path.cwd() == SHARED
    assert pathlib.Path(os.environ["TMPDIR"]) == SHARED_TMP
    assert tempfile.tempdir is None

def test_05_guarded_fixture(guarded_cwd):
    _assert_private(guarded_cwd)
    assert (guarded_cwd / "pyproject.toml").is_file()

@pytest.mark.guarded_cwd(poison_files={"only.ini": "exact"}, include_default_poison=False)
def test_06_guarded_marker():
    cwd = pathlib.Path.cwd()
    _assert_private(cwd)
    assert not (cwd / "pyproject.toml").exists()
    assert (cwd / "only.ini").read_text(encoding="utf-8") == "exact"

@pytest.mark.guarded_cwd(poison_files={"custom.ini": "merged"})
def test_07_guarded_marker_merge():
    cwd = pathlib.Path.cwd()
    _assert_private(cwd)
    assert (cwd / "pyproject.toml").is_file()
    assert (cwd / "custom.ini").read_text(encoding="utf-8") == "merged"

@pytest.mark.guarded_cwd
def test_08_matching_marker_fixture(guarded_cwd):
    _assert_private(guarded_cwd)

@pytest.mark.guarded_cwd
@pytest.mark.isolated_cwd
def test_09_explicit_conflict_still_fails():
    pass

def test_10_shared_finally():
    assert pathlib.Path.cwd() == SHARED
    assert pathlib.Path(os.environ["TMPDIR"]) == SHARED_TMP
""",
        config=SHARED_CONFIG,
    )
    result.assert_outcomes(passed=9, errors=1)
    result.stdout.fnmatch_lines(["*guarded_cwd and isolated_cwd cannot be applied to the same test*"])


def test_shared_boundary_modes_survive_restrictive_collection_umask_without_basetemp_chmod(run_isolation):
    result = run_isolation(
        """
import os
import pathlib
import stat

PREVIOUS_UMASK = os.umask(0o777)

def teardown_module():
    os.umask(PREVIOUS_UMASK)

def test_shared_modes_and_writable_tmp():
    cwd = pathlib.Path.cwd()
    tmp = pathlib.Path(os.environ["TMPDIR"])
    assert stat.S_IMODE(cwd.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(cwd.stat().st_mode) == 0o500
    assert stat.S_IMODE(tmp.stat().st_mode) == 0o700
    (tmp / "writable").write_text("ok", encoding="ascii")
""",
        config=SHARED_CONFIG,
    )
    result.assert_outcomes(passed=1)
