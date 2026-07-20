"""Conventional local filesystem, environment, and bounded Git discovery tests."""

import importlib
import io
import os
from pathlib import Path

import pytest

from conftest import runtime

discovery_module = importlib.import_module("toolkit_perform_runtime.discovery")


def git_result(root=None, returncode=0, **overrides):
    """Return a synthetic bounded Git result."""
    stdout = b"" if root is None else (str(root) + "\n").encode("utf-8")
    return runtime.GitCommandResult(returncode=returncode, stdout=stdout, **overrides)


def no_repository(_cwd):
    """Return the normal Git non-work-tree result."""
    return git_result(returncode=128)


class HermeticFilesystem(runtime.FilesystemView):
    """Hide ambient VCS markers above one temporary-test boundary."""

    def __init__(self, boundary):
        self.boundary = Path(boundary).resolve()

    def exists(self, path):
        """Ignore supported markers outside the temporary fixture tree."""
        candidate = Path(path)
        if candidate.name in (".git", ".hg", ".sl"):
            try:
                candidate.resolve().relative_to(self.boundary)
            except ValueError:
                return False
        return super().exists(path)


def discover(bundled, cwd, env=None, git_runner=no_repository, filesystem=None):
    """Run discovery with deterministic test defaults."""
    if filesystem is None:
        filesystem = HermeticFilesystem(Path(bundled).parent)
    return runtime.discover_action_directories(str(bundled), cwd=str(cwd), env={} if env is None else env, git_runner=git_runner, filesystem=filesystem)


def kinds(result):
    """Return ordered source kinds."""
    return [source.kind for source in result.sources]


def test_explicit_valid_codex_home_and_user_actions_without_config(tmp_path):
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    codex_home = tmp_path / "codex-home"
    (codex_home / "toolkit_perform_actions").mkdir(parents=True)
    result = discover(bundled, tmp_path, env={"CODEX_HOME": str(codex_home)})
    assert kinds(result) == ["bundled", "user"]
    assert result.precedence_incomplete is False


@pytest.mark.parametrize("value", [None, ""])
def test_absent_or_empty_codex_home_defaults_to_dot_codex(tmp_path, monkeypatch, value):
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    home = tmp_path / "home"
    (home / ".codex" / "toolkit_perform_actions").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    env = {} if value is None else {"CODEX_HOME": value}
    result = discover(bundled, tmp_path, env=env)
    assert kinds(result) == ["bundled", "user"]
    assert result.sources[-1].normalized_path == str((home / ".codex" / "toolkit_perform_actions").resolve())


def test_relative_codex_home_resolves_against_requested_cwd(tmp_path):
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    cwd = tmp_path / "work"
    (cwd / "relative" / "toolkit_perform_actions").mkdir(parents=True)
    (cwd / "nested").mkdir()
    result = discover(bundled, cwd, env={"CODEX_HOME": "nested/../relative"})
    assert result.sources[-1].normalized_path == str((cwd / "relative" / "toolkit_perform_actions").resolve())
    assert ".." not in Path(result.sources[-1].display_path).parts


@pytest.mark.parametrize("kind", ["missing", "file"])
def test_explicit_invalid_codex_home_is_fatal_without_default_fallback(tmp_path, monkeypatch, kind):
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    default_home = tmp_path / "home"
    (default_home / ".codex" / "toolkit_perform_actions").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(default_home))
    configured = tmp_path / kind
    if kind == "file":
        configured.write_text("not a directory", encoding="ascii")
    result = discover(bundled, tmp_path, env={"CODEX_HOME": str(configured)})
    assert kinds(result) == ["bundled"]
    assert result.precedence_incomplete is True
    assert [diagnostic.code for diagnostic in result.diagnostics] == ["invalid_codex_home"]


class DenyDirectoryFilesystem(runtime.FilesystemView):
    """Filesystem view that makes one existing directory inaccessible."""

    def __init__(self, denied):
        self.denied = os.path.realpath(str(denied))

    def accessible_directory(self, path):
        """Deny the configured resolved directory only."""
        return os.path.realpath(path) != self.denied


def test_inaccessible_explicit_codex_home_is_fatal(tmp_path):
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    filesystem = DenyDirectoryFilesystem(codex_home)
    result = discover(bundled, tmp_path, env={"CODEX_HOME": str(codex_home)}, filesystem=filesystem)
    assert result.precedence_incomplete is True
    assert any(diagnostic.code == "invalid_codex_home" for diagnostic in result.diagnostics)


class MappedSystemFilesystem(runtime.FilesystemView):
    """Map documented system paths to temporary test paths without touching /etc."""

    def __init__(self, mapped_actions, config_present=True):
        self.mapped_actions = str(mapped_actions)
        self.config_present = config_present

    def _map(self, path):
        if path == "/etc/codex/toolkit_perform_actions":
            return self.mapped_actions
        return path

    def exists(self, path):
        """Map system action existence into the temporary directory."""
        return super().exists(self._map(path))

    def is_file(self, path):
        """Represent only the documented system config activation file."""
        if path == "/etc/codex/config.toml":
            return self.config_present
        return super().is_file(self._map(path))

    def is_dir(self, path):
        """Map system action directory checks."""
        return super().is_dir(self._map(path))

    def accessible_directory(self, path):
        """Map system action accessibility checks."""
        return super().accessible_directory(self._map(path))

    def realpath(self, path):
        """Map system source identity to its temporary directory."""
        return super().realpath(self._map(path))


def test_documented_unix_system_source_requires_exact_config_activation(tmp_path):
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    system_actions = tmp_path / "system-actions"
    system_actions.mkdir()
    present = discover(bundled, tmp_path, filesystem=MappedSystemFilesystem(system_actions, config_present=True))
    absent = discover(bundled, tmp_path, filesystem=MappedSystemFilesystem(system_actions, config_present=False))
    assert kinds(present) == ["bundled", "system"]
    assert kinds(absent) == ["bundled"]


def test_successful_git_resolution_activates_only_root_repository_actions(tmp_path):
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    repository = tmp_path / "repository"
    cwd = repository / "nested" / "work"
    cwd.mkdir(parents=True)
    (repository / ".codex" / "toolkit_perform_actions").mkdir(parents=True)
    (repository / ".codex" / "config.toml").write_text("", encoding="ascii")
    (cwd / ".codex" / "toolkit_perform_actions").mkdir(parents=True)
    (cwd / ".codex" / "config.toml").write_text("", encoding="ascii")
    result = discover(bundled, cwd, git_runner=lambda _cwd: git_result(repository))
    assert result.repository_resolution == "git"
    assert result.repository_root == str(repository.resolve())
    assert kinds(result) == ["bundled", "repository"]
    assert result.sources[-1].normalized_path == str((repository / ".codex" / "toolkit_perform_actions").resolve())


def test_repository_actions_require_root_config(tmp_path):
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    repository = tmp_path / "repository"
    actions = repository / ".codex" / "toolkit_perform_actions"
    actions.mkdir(parents=True)
    result = discover(bundled, repository, git_runner=lambda _cwd: git_result(repository))
    assert kinds(result) == ["bundled"]


@pytest.mark.parametrize("marker", [".git", ".hg", ".sl"])
def test_git_failure_falls_back_to_supported_marker_walk(tmp_path, marker):
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    repository = tmp_path / "repository"
    cwd = repository / "nested"
    cwd.mkdir(parents=True)
    (repository / marker).mkdir()
    result = discover(bundled, cwd)
    assert result.repository_resolution == "marker_walk"
    assert result.repository_root == str(repository.resolve())


def test_nested_repository_marker_selects_closest_containing_root(tmp_path):
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    outer = tmp_path / "outer"
    inner = outer / "inner"
    cwd = inner / "work"
    cwd.mkdir(parents=True)
    (outer / ".git").mkdir()
    (inner / ".hg").mkdir()
    result = discover(bundled, cwd)
    assert result.repository_root == str(inner.resolve())


def test_no_vcs_root_loads_no_repository_source(tmp_path):
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    result = discover(bundled, tmp_path)
    assert result.repository_resolution == "none"
    assert result.repository_root is None
    assert kinds(result) == ["bundled"]


@pytest.mark.parametrize(
    ("result", "code"),
    [
        (runtime.GitCommandResult(launch_error="missing"), "git_unavailable"),
        (runtime.GitCommandResult(timed_out=True), "git_timeout"),
        (runtime.GitCommandResult(returncode=0, stdout=b"one\ntwo\n"), "git_malformed_output"),
        (runtime.GitCommandResult(returncode=0, stdout=b"relative-root\n"), "git_malformed_output"),
        (runtime.GitCommandResult(returncode=0, stdout=b"\xff"), "git_invalid_utf8"),
        (runtime.GitCommandResult(returncode=0, stdout=b"/missing\n"), "git_invalid_root"),
        (runtime.GitCommandResult(returncode=0, stdout=b"x", stdout_truncated=True), "git_output_too_large"),
    ],
)
def test_git_problem_diagnostics_fall_back_without_accepting_invalid_root(tmp_path, result, code):
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    discovered = discover(bundled, tmp_path, git_runner=lambda _cwd: result)
    assert discovered.repository_resolution == "none"
    assert any(diagnostic.code == code for diagnostic in discovered.diagnostics)


def test_git_non_work_tree_status_is_normal_and_silent(tmp_path):
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    result = discover(bundled, tmp_path, git_runner=lambda _cwd: git_result(returncode=128))
    assert result.diagnostics == []


def test_symlink_normalization_deduplicates_at_highest_precedence(tmp_path):
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    (codex_home / "toolkit_perform_actions").symlink_to(bundled, target_is_directory=True)
    result = discover(bundled, tmp_path, env={"CODEX_HOME": str(codex_home)})
    assert kinds(result) == ["user"]
    assert result.sources[0].normalized_path == str(bundled.resolve())
    assert any(diagnostic.code == "source_deduplicated" for diagnostic in result.diagnostics)


def test_missing_optional_sources_are_normal(tmp_path, monkeypatch):
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "empty-home"))
    result = discover(bundled, tmp_path)
    assert kinds(result) == ["bundled"]
    assert result.diagnostics == []


def test_existing_inaccessible_action_source_makes_precedence_incomplete(tmp_path):
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    codex_home = tmp_path / "codex-home"
    user_actions = codex_home / "toolkit_perform_actions"
    user_actions.mkdir(parents=True)
    filesystem = DenyDirectoryFilesystem(user_actions)
    result = discover(bundled, tmp_path, env={"CODEX_HOME": str(codex_home)}, filesystem=filesystem)
    assert result.precedence_incomplete is True
    assert any(diagnostic.code == "action_source_inaccessible" and diagnostic.fatal for diagnostic in result.diagnostics)


def test_invalid_working_directory_is_fatal(tmp_path):
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    missing = tmp_path / "missing"
    result = discover(bundled, missing)
    assert result.precedence_incomplete is True
    assert any(diagnostic.code == "invalid_cwd" for diagnostic in result.diagnostics)


class FakeProcess:
    """Small Popen test double supporting bounded pipe collection."""

    def __init__(self, stdout=b"", stderr=b"", returncode=0, timeout_once=False):
        self.stdout = io.BytesIO(stdout)
        self.stderr = io.BytesIO(stderr)
        self.returncode = returncode
        self.timeout_once = timeout_once
        self.wait_calls = 0
        self.terminated = False
        self.killed = False

    def wait(self, timeout=None):
        """Return completion or synthesize one initial timeout."""
        self.wait_calls += 1
        if self.timeout_once and self.wait_calls == 1:
            raise discovery_module.subprocess.TimeoutExpired("git", timeout)
        return self.returncode

    def terminate(self):
        """Record graceful termination."""
        self.terminated = True

    def kill(self):
        """Record forced termination."""
        self.killed = True


def test_bounded_git_launches_only_exact_read_only_command_without_shell(tmp_path):
    calls = []
    process = FakeProcess(stdout=(str(tmp_path) + "\n").encode("utf-8"))

    def popen(command, **kwargs):
        calls.append((command, kwargs))
        return process

    result = runtime.run_bounded_git_root(str(tmp_path), popen_factory=popen)
    assert result.returncode == 0
    assert calls == [
        (
            ["git", "-C", str(tmp_path), "rev-parse", "--show-toplevel"],
            {
                "stdin": discovery_module.subprocess.DEVNULL,
                "stdout": discovery_module.subprocess.PIPE,
                "stderr": discovery_module.subprocess.PIPE,
                "shell": False,
            },
        )
    ]
    assert all("codex" not in part and "uv" not in part for part in calls[0][0])


def test_bounded_git_caps_both_output_streams(tmp_path):
    process = FakeProcess(stdout=b"x" * (discovery_module.GIT_OUTPUT_LIMIT + 10), stderr=b"y" * (discovery_module.GIT_OUTPUT_LIMIT + 20))
    result = runtime.run_bounded_git_root(str(tmp_path), popen_factory=lambda _command, **_kwargs: process)
    assert len(result.stdout) == discovery_module.GIT_OUTPUT_LIMIT
    assert len(result.stderr) == discovery_module.GIT_OUTPUT_LIMIT
    assert result.stdout_truncated is True
    assert result.stderr_truncated is True


def test_bounded_git_terminates_on_timeout(tmp_path):
    process = FakeProcess(timeout_once=True)
    result = runtime.run_bounded_git_root(str(tmp_path), popen_factory=lambda _command, **_kwargs: process, timeout=0.01)
    assert result.timed_out is True
    assert process.terminated is True


def test_explicit_ordered_directories_bypass_conventional_discovery(tmp_path, complete, file_data, write_file):
    first = tmp_path / "first"
    second = tmp_path / "second"
    write_file(first, file_data(actions={"test": {"agnostic": complete(gloss="first")}}))
    write_file(second, file_data(actions={"test": {"agnostic": complete(gloss="second")}}))
    catalog = runtime.load_action_catalog(action_directories=[str(first), str(second)], bundled_dir="/missing", cwd="/missing")
    assert catalog.discovery.repository_resolution == "none"
    assert [source.source_order for source in catalog.discovery.sources] == [0, 1]
    assert catalog.inspect("test[agnostic]").action.fields["gloss"] == "second"
