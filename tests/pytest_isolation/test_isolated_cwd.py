"""Writable isolated working-directory behavior tests."""


def test_marker_fixture_and_matching_combination_each_activate_once(run_isolation):
    result = run_isolation(
        """
from pathlib import Path
import os
import pytest

SEEN = set()

def assert_isolated(path):
    assert Path.cwd() == path
    assert path.parent.name.startswith("la-dev-pytest-isolation-")
    assert path.parent not in SEEN
    SEEN.add(path.parent)
    tmp = Path(os.environ["TMPDIR"])
    assert tmp == path.parent / "tmp"
    assert os.environ["TEMP"] == os.environ["TMP"] == str(tmp)
    assert path.is_dir() and os.access(str(path), os.W_OK)
    assert tmp.is_dir() and os.access(str(tmp), os.W_OK)

@pytest.mark.isolated_cwd
def test_marker_only():
    assert_isolated(Path.cwd())

def test_fixture_only(isolated_cwd):
    assert_isolated(isolated_cwd)

@pytest.mark.isolated_cwd
def test_marker_and_fixture(isolated_cwd):
    assert_isolated(isolated_cwd)
"""
    )
    result.assert_outcomes(passed=3)


def test_isolation_directories_are_usable_under_restrictive_umask(run_isolation):
    result = run_isolation(
        """
from pathlib import Path
import os
import stat
import pytest

PREVIOUS_UMASK = os.umask(0o777)

def teardown_module():
    os.umask(PREVIOUS_UMASK)

def test_isolated(isolated_cwd):
    boundary = isolated_cwd.parent
    tmp = boundary / "tmp"
    assert stat.S_IMODE(boundary.stat().st_mode) == 0o700
    assert stat.S_IMODE(isolated_cwd.stat().st_mode) == 0o700
    assert stat.S_IMODE(tmp.stat().st_mode) == 0o700
    (isolated_cwd / "created.txt").write_text("ok", encoding="utf-8")
    (tmp / "created.txt").write_text("ok", encoding="utf-8")

@pytest.mark.guarded_cwd(poison_files={"nested/deeper/config.ini": "exact"})
def test_guarded(guarded_cwd):
    boundary = guarded_cwd.parent
    tmp = boundary / "tmp"
    assert stat.S_IMODE(boundary.stat().st_mode) == 0o700
    assert stat.S_IMODE(guarded_cwd.stat().st_mode) == 0o500
    assert stat.S_IMODE((guarded_cwd / "nested").stat().st_mode) == 0o500
    assert stat.S_IMODE((guarded_cwd / "nested/deeper").stat().st_mode) == 0o500
    assert stat.S_IMODE((guarded_cwd / "nested/deeper/config.ini").stat().st_mode) == 0o400
    assert stat.S_IMODE(tmp.stat().st_mode) == 0o700
    (tmp / "created.txt").write_text("ok", encoding="utf-8")
"""
    )
    result.assert_outcomes(passed=2)


def test_accessible_chdir_is_allowed_and_deleted_final_cwd_fails_after_restoration(run_isolation):
    result = run_isolation(
        """
import os
import shutil

def test_accessible_chdir(isolated_cwd):
    os.chdir(str(isolated_cwd.parent / "tmp"))

def test_deleted_cwd(isolated_cwd):
    child = isolated_cwd / "deleted"
    child.mkdir()
    os.chdir(str(child))
    shutil.rmtree(str(isolated_cwd))

def test_later_unmarked_still_runs():
    assert os.getcwd()
"""
    )
    result.assert_outcomes(passed=3, errors=1)
    result.stdout.fnmatch_lines(["*could not inspect the test's final working directory*"])


def test_process_state_restores_after_pass_failure_skip_and_fixture_failures(run_isolation):
    result = run_isolation(
        """
import os
import tempfile
import pytest

ORIGINAL_CWD = os.getcwd()
ORIGINAL_ENV = {name: os.environ.get(name) for name in ("TMPDIR", "TEMP", "TMP")}
ORIGINAL_TEMPDIR = tempfile.tempdir

@pytest.fixture
def setup_failure():
    raise RuntimeError("setup failure")

@pytest.fixture
def teardown_failure():
    yield
    raise RuntimeError("teardown failure")

def test_pass(isolated_cwd):
    assert tempfile.tempdir is None

def test_assertion_failure(isolated_cwd):
    assert False

def test_skip(isolated_cwd):
    pytest.skip("skip")

def test_setup_failure(isolated_cwd, setup_failure):
    pass

def test_teardown_failure(isolated_cwd, teardown_failure):
    pass

def test_restored():
    assert os.getcwd() == ORIGINAL_CWD
    assert {name: os.environ.get(name) for name in ORIGINAL_ENV} == ORIGINAL_ENV
    assert tempfile.tempdir is ORIGINAL_TEMPDIR
"""
    )
    result.assert_outcomes(passed=3, failed=1, skipped=1, errors=2)


def test_exact_prior_environment_and_tempfile_cache_are_restored(run_isolation):
    result = run_isolation(
        """
import os
import tempfile

os.environ["TMPDIR"] = "prior-tmpdir"
os.environ.pop("TEMP", None)
os.environ["TMP"] = "prior-tmp"
tempfile.tempdir = "prior-cache"

def test_isolated(isolated_cwd):
    assert tempfile.tempdir is None
    assert all(os.environ[name].endswith("/tmp") for name in ("TMPDIR", "TEMP", "TMP"))

def test_restored():
    assert os.environ["TMPDIR"] == "prior-tmpdir"
    assert "TEMP" not in os.environ
    assert os.environ["TMP"] == "prior-tmp"
    assert tempfile.tempdir == "prior-cache"
"""
    )
    result.assert_outcomes(passed=2)
