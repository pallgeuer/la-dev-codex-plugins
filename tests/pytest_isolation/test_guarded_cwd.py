"""Read-only poisoned guarded working-directory behavior tests."""


def test_symlinked_temporary_root_is_the_same_guarded_directory(run_isolation, monkeypatch, tmp_path):
    real = tmp_path / "real-temporary-root"
    real.mkdir()
    link = tmp_path / "linked-temporary-root"
    link.symlink_to(real, target_is_directory=True)
    monkeypatch.setenv("TMPDIR", str(link))

    result = run_isolation(
        """
import os

def test_guard(guarded_cwd):
    assert os.path.samefile(os.getcwd(), str(guarded_cwd))
"""
    )

    result.assert_outcomes(passed=1)


def test_default_poison_permissions_and_separate_writable_tmp(run_isolation):
    result = run_isolation(
        """
from pathlib import Path
import os
import stat

def test_guard(guarded_cwd):
    poison = guarded_cwd / "pyproject.toml"
    assert poison.read_bytes() == b"[tool.la_dev_cwd_guard\\n"
    assert stat.S_IMODE(guarded_cwd.stat().st_mode) == 0o500
    assert stat.S_IMODE(poison.stat().st_mode) == 0o400
    tmp = Path(os.environ["TMPDIR"])
    assert tmp == guarded_cwd.parent / "tmp"
    (tmp / "writable").write_text("ok", encoding="utf-8")
"""
    )
    result.assert_outcomes(passed=1)


def test_marker_only_custom_merge_override_disable_and_nested_parents(run_isolation):
    result = run_isolation(
        """
import pytest

@pytest.mark.guarded_cwd(poison_files={"nested/config.ini": "exact", "pyproject.toml": "override"})
def test_merge(request):
    cwd = getattr(request.node, "_la_dev_pytest_isolation_state").cwd
    assert (cwd / "nested/config.ini").read_bytes() == b"exact"
    assert (cwd / "pyproject.toml").read_bytes() == b"override"

@pytest.mark.guarded_cwd(poison_files={"only.txt": "no newline"}, include_default_poison=False)
def test_disable_default(request):
    cwd = getattr(request.node, "_la_dev_pytest_isolation_state").cwd
    assert not (cwd / "pyproject.toml").exists()
    assert (cwd / "only.txt").read_bytes() == b"no newline"

@pytest.mark.guarded_cwd(poison_files=None)
def test_none_uses_default(guarded_cwd):
    assert (guarded_cwd / "pyproject.toml").is_file()

@pytest.mark.guarded_cwd(poison_files=None, include_default_poison=False)
def test_none_without_default(guarded_cwd):
    assert list(guarded_cwd.iterdir()) == []
"""
    )
    result.assert_outcomes(passed=4)


def test_closest_same_mode_marker_configuration_wins(run_isolation):
    result = run_isolation(
        """
import pytest

pytestmark = pytest.mark.guarded_cwd(poison_files={"scope.txt": "module"}, include_default_poison=False)

class TestScoped:
    pytestmark = pytest.mark.guarded_cwd(poison_files={"scope.txt": "class"}, include_default_poison=False)

    def test_class(self, guarded_cwd):
        assert (guarded_cwd / "scope.txt").read_text(encoding="utf-8") == "class"

    @pytest.mark.guarded_cwd(poison_files={"scope.txt": "function"}, include_default_poison=False)
    def test_function(self, guarded_cwd):
        assert (guarded_cwd / "scope.txt").read_text(encoding="utf-8") == "function"
"""
    )
    result.assert_outcomes(passed=2)


def test_invalid_guarded_marker_configurations_fail_directly(run_isolation):
    result = run_isolation(
        """
import pytest

@pytest.mark.guarded_cwd("positional")
def test_positional(): pass

@pytest.mark.guarded_cwd(unknown=True)
def test_unknown(): pass

@pytest.mark.guarded_cwd(include_default_poison=1)
def test_boolean(): pass

@pytest.mark.guarded_cwd(poison_files=[])
def test_mapping(): pass

@pytest.mark.guarded_cwd(poison_files={1: "value"})
def test_path_type(): pass

@pytest.mark.guarded_cwd(poison_files={"value": b"bytes"})
def test_content_type(): pass

@pytest.mark.guarded_cwd(poison_files={"/absolute": "value"})
def test_absolute(): pass

@pytest.mark.guarded_cwd(poison_files={"": "value"})
def test_empty(): pass

@pytest.mark.guarded_cwd(poison_files={".": "value"})
def test_dot(): pass

@pytest.mark.guarded_cwd(poison_files={"a/../b": "value"})
def test_parent(): pass

@pytest.mark.guarded_cwd(poison_files={"a/b": "one", "a//b": "two"})
def test_duplicate(): pass

@pytest.mark.guarded_cwd(poison_files={"a": "file", "a/b": "child"})
def test_collision(): pass
"""
    )
    result.assert_outcomes(errors=12)
    result.stdout.fnmatch_lines(["*guarded_cwd*"])


def test_guarded_accessible_and_deleted_cwd_leaks_fail_after_restoration(run_isolation):
    result = run_isolation(
        """
import os
import shutil

def test_accessible_escape(guarded_cwd):
    os.chdir(str(guarded_cwd.parent / "tmp"))

def test_deleted_escape(guarded_cwd):
    child = guarded_cwd / "deleted"
    os.chmod(str(guarded_cwd), 0o700)
    child.mkdir()
    os.chdir(str(child))
    shutil.rmtree(str(guarded_cwd))

def test_restored_after_leaks():
    assert os.getcwd()
"""
    )
    result.assert_outcomes(passed=3, errors=2)
    result.stdout.fnmatch_lines(["*guarded_cwd test escaped its guarded working directory*", "*could not inspect the test's final working directory*"])


def test_root_aware_guard_retains_poison_and_leak_detection(run_isolation):
    result = run_isolation(
        """
import os
import stat
import pytest

def test_root_aware_guard(guarded_cwd):
    poison = guarded_cwd / "pyproject.toml"
    assert poison.read_bytes() == b"[tool.la_dev_cwd_guard\\n"
    assert stat.S_IMODE(guarded_cwd.stat().st_mode) == 0o500
    assert stat.S_IMODE(poison.stat().st_mode) == 0o400
    if getattr(os, "geteuid", lambda: -1)() != 0:
        with pytest.raises(PermissionError):
            poison.write_text("unexpected", encoding="utf-8")
    os.chdir(str(guarded_cwd.parent / "tmp"))
"""
    )
    result.assert_outcomes(passed=1, errors=1)
    result.stdout.fnmatch_lines(["*guarded_cwd test escaped its guarded working directory*"])


def test_permission_restoration_uses_verified_directories_without_following_links(run_isolation):
    result = run_isolation(
        """
import os
import pathlib

def test_restore_safely(guarded_cwd):
    outside = pathlib.Path(os.environ["GUARD_RESTORE_OUTSIDE"])
    os.chmod(str(guarded_cwd), 0o700)
    nested = guarded_cwd / "nested"
    nested.mkdir()
    nested.chmod(0o500)
    (guarded_cwd / "file-link").symlink_to(outside / "file")
    (guarded_cwd / "directory-link").symlink_to(outside / "directory", target_is_directory=True)
    os.link(str(outside / "file"), str(guarded_cwd / "hard-link"))
""",
        conftest="""
import os
import pathlib
import stat
import la_dev_codex_plugins.pytest_isolation.plugin as isolation_plugin

outside = pathlib.Path.cwd() / "guard-restore-outside"
outside.mkdir()
(outside / "directory").mkdir()
(outside / "file").write_text("external", encoding="ascii")
(outside / "directory").chmod(0o500)
(outside / "file").chmod(0o400)
os.environ["GUARD_RESTORE_OUTSIDE"] = str(outside)
original_restore_permissions = isolation_plugin._restore_permissions

def observe_restoration(state, failures):
    original_restore_permissions(state, failures)
    assert failures == []
    assert stat.S_IMODE(state.cwd.stat().st_mode) == 0o700
    assert stat.S_IMODE((state.cwd / "nested").stat().st_mode) == 0o700
    assert stat.S_IMODE((state.cwd / "pyproject.toml").stat().st_mode) == 0o400
    assert stat.S_IMODE((outside / "file").stat().st_mode) == 0o400
    assert stat.S_IMODE((outside / "directory").stat().st_mode) == 0o500

isolation_plugin._restore_permissions = observe_restoration
""",
    )
    result.assert_outcomes(passed=1)


def test_replaced_guarded_directory_fails_closed_without_touching_target(run_isolation):
    result = run_isolation(
        """
import os
import pathlib

def test_replace_guard(guarded_cwd):
    outside = pathlib.Path(os.environ["GUARD_REPLACEMENT_OUTSIDE"])
    boundary = guarded_cwd.parent
    os.chdir(str(boundary / "tmp"))
    os.chmod(str(guarded_cwd), 0o700)
    guarded_cwd.rename(boundary / "original-cwd")
    guarded_cwd.symlink_to(outside, target_is_directory=True)
""",
        conftest="""
import os
import pathlib

outside = pathlib.Path.cwd() / "guard-replacement-outside"
outside.mkdir()
outside.chmod(0o500)
os.environ["GUARD_REPLACEMENT_OUTSIDE"] = str(outside)
""",
    )
    result.assert_outcomes(passed=1, errors=1)
    result.stdout.fnmatch_lines(["*could not safely open guarded working directory*"])


def test_original_cwd_restore_failure_still_restores_environment_and_permissions(run_isolation):
    result = run_isolation(
        """
def test_restore_failure(guarded_cwd):
    assert (guarded_cwd / "pyproject.toml").is_file()
""",
        conftest="""
import os
import pathlib
import stat
import tempfile
import la_dev_codex_plugins.pytest_isolation.plugin as isolation_plugin

original_cwd = os.getcwd()
original_environment = {name: os.environ.get(name) for name in ("TMPDIR", "TEMP", "TMP")}
original_tempdir = tempfile.tempdir
original_chdir = isolation_plugin.os.chdir
original_restore_permissions = isolation_plugin._restore_permissions
failed = [False]

def fail_original_restore(path):
    if not failed[0] and path == original_cwd and pathlib.Path.cwd().name == "cwd":
        failed[0] = True
        raise OSError("original cwd restore failed")
    return original_chdir(path)

def observe_restoration(state, failures):
    assert {name: os.environ.get(name) for name in original_environment} == original_environment
    assert tempfile.tempdir is original_tempdir
    original_restore_permissions(state, failures)
    assert stat.S_IMODE(state.cwd.stat().st_mode) == 0o700
    assert stat.S_IMODE((state.cwd / "pyproject.toml").stat().st_mode) == 0o400
    original_chdir(original_cwd)

isolation_plugin.os.chdir = fail_original_restore
isolation_plugin._restore_permissions = observe_restoration
""",
    )
    result.assert_outcomes(passed=1, errors=1)
    result.stdout.fnmatch_lines(["*could not restore the original working directory*original cwd restore failed*"])
