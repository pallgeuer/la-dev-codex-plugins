"""Read-only poisoned guarded working-directory behavior tests."""

import pathlib
import stat


def test_symlinked_temporary_root_is_the_same_guarded_directory(run_isolation, monkeypatch, tmp_path):
    real = tmp_path / "real-temporary-root"
    real.mkdir()
    link = tmp_path / "linked-temporary-root"
    link.symlink_to(real, target_is_directory=True)
    monkeypatch.setenv("TMPDIR", str(link))

    result = run_isolation(
        """
import os
from pathlib import Path

def test_guard(guarded_cwd):
    assert Path.cwd() == guarded_cwd
    assert Path(os.environ["TMPDIR"]).parent == guarded_cwd.parent
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
from pathlib import Path

import pytest

@pytest.mark.guarded_cwd(poison_files={"nested/config.ini": "exact", "pyproject.toml": "override"})
def test_merge():
    cwd = Path.cwd()
    assert (cwd / "nested/config.ini").read_bytes() == b"exact"
    assert (cwd / "pyproject.toml").read_bytes() == b"override"

@pytest.mark.guarded_cwd(poison_files={"only.txt": "no newline"}, include_default_poison=False)
def test_disable_default():
    cwd = Path.cwd()
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


def test_cleanup_restores_permissions_without_following_links(run_isolation, monkeypatch, tmp_path):
    outside = tmp_path / "guard-cleanup-outside"
    outside.mkdir()
    (outside / "directory").mkdir()
    (outside / "file").write_text("external", encoding="ascii")
    (outside / "directory").chmod(0o500)
    (outside / "file").chmod(0o400)
    record = tmp_path / "guard-cleanup-record.txt"
    monkeypatch.setenv("GUARD_CLEANUP_OUTSIDE", str(outside))
    monkeypatch.setenv("GUARD_CLEANUP_RECORD", str(record))
    result = run_isolation(
        """
import os
import pathlib

def test_cleanup_safely(guarded_cwd):
    outside = pathlib.Path(os.environ["GUARD_CLEANUP_OUTSIDE"])
    pathlib.Path(os.environ["GUARD_CLEANUP_RECORD"]).write_text(str(guarded_cwd.parent), encoding="ascii")
    os.chmod(str(guarded_cwd), 0o700)
    nested = guarded_cwd / "nested"
    nested.mkdir()
    nested.chmod(0o500)
    (guarded_cwd / "file-link").symlink_to(outside / "file")
    (guarded_cwd / "directory-link").symlink_to(outside / "directory", target_is_directory=True)
    os.link(str(outside / "file"), str(guarded_cwd / "hard-link"))
""",
    )
    result.assert_outcomes(passed=1)
    assert not pathlib.Path(record.read_text(encoding="ascii")).exists()
    assert (outside / "file").read_text(encoding="ascii") == "external"
    assert stat.S_IMODE((outside / "file").stat().st_mode) == 0o400
    assert stat.S_IMODE((outside / "directory").stat().st_mode) == 0o500


def test_replaced_guarded_directory_fails_closed_without_touching_target(run_isolation, monkeypatch, tmp_path, remove_preserved_boundary):
    record = tmp_path / "guard-replacement-boundary.txt"
    monkeypatch.setenv("GUARD_REPLACEMENT_RECORD", str(record))
    result = run_isolation(
        """
import os
import pathlib

def test_replace_guard(guarded_cwd):
    outside = pathlib.Path(os.environ["GUARD_REPLACEMENT_OUTSIDE"])
    boundary = guarded_cwd.parent
    pathlib.Path(os.environ["GUARD_REPLACEMENT_RECORD"]).write_text(str(boundary), encoding="ascii")
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
    result.stdout.fnmatch_lines(["*could not safely open recorded working directory*"])
    boundary = pathlib.Path(record.read_text(encoding="ascii"))
    assert boundary.is_dir()
    assert (boundary / "cwd").is_symlink()
    assert (boundary / "original-cwd").is_dir()
    remove_preserved_boundary(boundary)


def test_private_cleanup_preserves_identity_replaced_cwd_and_tmp(run_isolation, monkeypatch, tmp_path, remove_preserved_boundary):
    for fixture_name in ("isolated_cwd", "guarded_cwd"):
        for child_name in ("cwd", "tmp"):
            label = "{}-{}".format(fixture_name, child_name)
            external = tmp_path / (label + "-external")
            external.mkdir()
            (external / "sentinel.txt").write_text("keep", encoding="ascii")
            record = tmp_path / (label + "-boundary.txt")
            monkeypatch.setenv("PRIVATE_REPLACEMENT_EXTERNAL", str(external))
            monkeypatch.setenv("PRIVATE_REPLACEMENT_RECORD", str(record))
            result = run_isolation(
                """
import os
import pathlib

def test_replace({fixture_name}):
    boundary = {fixture_name}.parent
    target = boundary / {child_name!r}
    pathlib.Path(os.environ["PRIVATE_REPLACEMENT_RECORD"]).write_text(str(boundary), encoding="ascii")
    if pathlib.Path.cwd() == target:
        os.chdir(str(boundary))
    target.rename(boundary / ({child_name!r} + "-original"))
    pathlib.Path(os.environ["PRIVATE_REPLACEMENT_EXTERNAL"]).rename(target)
""".format(fixture_name=fixture_name, child_name=child_name)
            )
            result.assert_outcomes(passed=1, errors=1)
            boundary = pathlib.Path(record.read_text(encoding="ascii"))
            assert (boundary / child_name / "sentinel.txt").read_text(encoding="ascii") == "keep"
            assert (boundary / (child_name + "-original")).is_dir()
            remove_preserved_boundary(boundary)


def test_private_cleanup_restores_unreadable_temporary_descendants(run_isolation, monkeypatch, tmp_path):
    for fixture_name in ("isolated_cwd", "guarded_cwd"):
        record = tmp_path / (fixture_name + "-unreadable-boundary.txt")
        monkeypatch.setenv("UNREADABLE_PRIVATE_RECORD", str(record))
        result = run_isolation(
            """
import os
import pathlib

def test_unreadable_tmp({fixture_name}):
    boundary = {fixture_name}.parent
    pathlib.Path(os.environ["UNREADABLE_PRIVATE_RECORD"]).write_text(str(boundary), encoding="ascii")
    locked = boundary / "tmp" / "locked"
    locked.mkdir()
    nested = locked / "nested"
    nested.mkdir()
    (nested / "sentinel.txt").write_text("remove", encoding="ascii")
    nested.chmod(0o300)
    locked.chmod(0o000)
""".format(fixture_name=fixture_name)
        )
        result.assert_outcomes(passed=1)
        assert not pathlib.Path(record.read_text(encoding="ascii")).exists()


def test_cleanup_descriptor_exhaustion_is_reported_and_preserved(run_isolation, monkeypatch, tmp_path, remove_preserved_boundary):
    record = tmp_path / "descriptor-exhaustion-boundary.txt"
    monkeypatch.setenv("DESCRIPTOR_EXHAUSTION_RECORD", str(record))
    result = run_isolation(
        """
import os
import pathlib

def test_descriptor_exhaustion(isolated_cwd):
    boundary = isolated_cwd.parent
    pathlib.Path(os.environ["DESCRIPTOR_EXHAUSTION_RECORD"]).write_text(str(boundary), encoding="ascii")
    nested = boundary / "tmp" / "nested"
    nested.mkdir()
    (nested / "sentinel.txt").write_text("keep", encoding="ascii")
""",
        conftest="""
import errno
import la_dev_codex_plugins.pytest_isolation.plugin as isolation_plugin

original_open = isolation_plugin.os.open

def fail_nested_open(path, flags, *args, **kwargs):
    if path == "nested" and kwargs.get("dir_fd") is not None:
        raise OSError(errno.EMFILE, "injected descriptor exhaustion")
    return original_open(path, flags, *args, **kwargs)

isolation_plugin.os.open = fail_nested_open
""",
    )
    result.assert_outcomes(passed=1, errors=1)
    output = "\n".join(result.stdout.lines + result.stderr.lines)
    assert "injected descriptor exhaustion" in output
    boundary = pathlib.Path(record.read_text(encoding="ascii"))
    assert (boundary / "tmp" / "nested" / "sentinel.txt").read_text(encoding="ascii") == "keep"
    remove_preserved_boundary(boundary)


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
original_cleanup_boundary = isolation_plugin._cleanup_boundary
failed = [False]

def fail_original_restore(path):
    if not failed[0] and path == original_cwd and pathlib.Path.cwd().name == "cwd":
        failed[0] = True
        raise OSError("original cwd restore failed")
    return original_chdir(path)

def observe_cleanup(state, failures):
    assert {name: os.environ.get(name) for name in original_environment} == original_environment
    assert tempfile.tempdir is original_tempdir
    assert stat.S_IMODE(state.cwd.stat().st_mode) == 0o500
    assert stat.S_IMODE((state.cwd / "pyproject.toml").stat().st_mode) == 0o400
    original_chdir(original_cwd)
    original_cleanup_boundary(state, failures)

isolation_plugin.os.chdir = fail_original_restore
isolation_plugin._cleanup_boundary = observe_cleanup
""",
    )
    result.assert_outcomes(passed=1, errors=1)
    result.stdout.fnmatch_lines(["*could not restore the original working directory*original cwd restore failed*"])
