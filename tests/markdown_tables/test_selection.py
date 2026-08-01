"""Markdown path selection and Git discovery tests."""

import os
import pathlib
import re
import subprocess

import pytest

import la_dev_codex_plugins._process as process
import la_dev_codex_plugins.markdown_tables as markdown_tables
import la_dev_codex_plugins.markdown_tables.files as markdown_files
import la_dev_codex_plugins.markdown_tables.selection as markdown_selection


def _git(repository, *arguments):
    subprocess.run(("git", *arguments), cwd=str(repository), check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def test_tracked_paths_use_nearest_root_case_insensitive_suffixes_and_nul_output(tmp_path, monkeypatch):
    repository = tmp_path / "repo"
    nested = repository / "nested" / "deeper"
    nested.mkdir(parents=True)
    _git(repository, "init")
    paths = [repository / "a.md", repository / "B.MARKDOWN", repository / "line\nbreak.md", repository / "skip.txt"]
    for path in paths:
        path.write_text("text\n", encoding="utf-8")
    _git(repository, "add", "--", ".")
    monkeypatch.chdir(nested)

    discovered = markdown_tables.tracked_markdown_paths()

    assert discovered == (repository / "B.MARKDOWN", repository / "a.md", repository / "line\nbreak.md")
    assert all(path.is_absolute() for path in discovered)


def test_tracked_paths_decode_non_utf8_filename_with_filesystem_surrogateescape(tmp_path):
    repository = tmp_path / "repo"
    repository.mkdir()
    _git(repository, "init")
    raw_name = b"non-utf8-\xff.md"
    raw_path = os.fsencode(str(repository)) + b"/" + raw_name
    descriptor = os.open(raw_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    decoded_name = os.fsdecode(raw_name)
    _git(repository, "add", "--", decoded_name)

    discovered = markdown_tables.tracked_markdown_paths(repository)

    assert len(discovered) == 1
    assert os.fsencode(discovered[0].name) == raw_name


def test_tracked_paths_ignore_absent_files_but_return_tracked_symlinks_for_validation(tmp_path):
    repository = tmp_path / "repo"
    repository.mkdir()
    _git(repository, "init")
    present = repository / "present.md"
    absent = repository / "absent.md"
    target = repository / "target.txt"
    link = repository / "link.md"
    present.write_text("text\n", encoding="utf-8")
    absent.write_text("text\n", encoding="utf-8")
    target.write_text("text\n", encoding="utf-8")
    link.symlink_to(target)
    _git(repository, "add", "--", ".")
    absent.unlink()

    discovered = markdown_tables.tracked_markdown_paths(repository)

    assert present in discovered
    assert absent not in discovered
    assert link in discovered


def test_empty_git_discovery_succeeds(tmp_path):
    repository = tmp_path / "repo"
    repository.mkdir()
    _git(repository, "init")
    assert markdown_tables.tracked_markdown_paths(repository) == ()


@pytest.mark.parametrize("suffix", ["\r", "\n"])
def test_git_root_preserves_trailing_path_line_characters(tmp_path, suffix):
    repository = tmp_path / ("repository" + suffix)
    repository.mkdir()
    _git(repository, "init")

    assert markdown_selection._discover_git_root(repository) == repository.absolute()


def test_select_paths_loads_strict_root_config_and_adds_cli_exclusions(tmp_path):
    repository = tmp_path / "repo"
    docs = repository / "docs"
    generated = docs / "generated"
    generated.mkdir(parents=True)
    _git(repository, "init")
    keep = docs / "keep.md"
    configured = generated / "configured.md"
    command_line = docs / "command-line.md"
    for path in (keep, configured, command_line):
        path.write_text("text\n", encoding="utf-8")
    (repository / ".la-dev-markdown-tables.json").write_text('{"version": 1, "exclude": ["^docs/generated/"]}\n', encoding="utf-8")
    _git(repository, "add", "--", ".")

    selected = markdown_tables.select_markdown_paths(root=repository, exclude="command-line\\.md$")

    assert selected == (keep,)
    assert markdown_tables.select_markdown_paths(root=repository, apply_excludes=False) == (command_line, configured, keep)


def test_select_paths_can_include_only_nonignored_untracked_markdown(tmp_path):
    repository = tmp_path / "repo"
    repository.mkdir()
    _git(repository, "init")
    tracked = repository / "tracked.md"
    untracked = repository / "untracked.MARKDOWN"
    ignored = repository / "ignored.md"
    unrelated = repository / "notes.txt"
    tracked.write_text("tracked\n", encoding="utf-8")
    untracked.write_text("untracked\n", encoding="utf-8")
    ignored.write_text("ignored\n", encoding="utf-8")
    unrelated.write_text("notes\n", encoding="utf-8")
    (repository / ".gitignore").write_text("ignored.md\n", encoding="utf-8")
    _git(repository, "add", "--", "tracked.md", ".gitignore")

    assert markdown_tables.select_markdown_paths(root=repository, use_config=False) == (tracked,)
    assert markdown_tables.select_markdown_paths(root=repository, include_untracked=True, use_config=False) == (tracked, untracked)
    assert markdown_tables.select_markdown_paths(ignored, root=repository, use_config=False) == (ignored,)


def test_select_paths_expands_git_scoped_directories_in_input_order(tmp_path):
    repository = tmp_path / "repo"
    docs = repository / "docs"
    nested = docs / "nested"
    elsewhere = repository / "elsewhere"
    nested.mkdir(parents=True)
    elsewhere.mkdir()
    _git(repository, "init")
    first = docs / "a.md"
    second = nested / "b.MD"
    untracked = docs / "c.md"
    ignored = docs / "ignored.md"
    explicit_text = elsewhere / "table.txt"
    for path in (first, second, untracked, ignored, explicit_text):
        path.write_text("text\n", encoding="utf-8")
    (repository / ".gitignore").write_text("docs/ignored.md\n", encoding="utf-8")
    _git(repository, "add", "--", "docs/a.md", "docs/nested/b.MD", "elsewhere/table.txt", ".gitignore")

    selected = markdown_tables.select_markdown_paths((explicit_text, docs, first), root=repository, include_untracked=True, use_config=False)

    assert selected == (explicit_text, first, untracked, second)
    assert ignored not in selected


def test_directory_entry_index_preserves_sorted_descendants_for_each_ancestor(tmp_path):
    entries = (("a.md", tmp_path / "a.md"), ("docs/a.md", tmp_path / "docs" / "a.md"), ("docs/nested/b.md", tmp_path / "docs" / "nested" / "b.md"))

    indexed = markdown_selection._index_entries_by_directory(entries)

    assert indexed["."] == tuple(item[1] for item in entries)
    assert indexed["docs"] == tuple(item[1] for item in entries[1:])
    assert indexed["docs/nested"] == (entries[2][1],)


def test_select_paths_rejects_directory_outside_active_worktree(tmp_path):
    repository = tmp_path / "repo"
    outside = tmp_path / "outside"
    repository.mkdir()
    outside.mkdir()
    _git(repository, "init")

    with pytest.raises(markdown_tables.MarkdownTableError, match="inside the active Git worktree"):
        markdown_tables.select_markdown_paths(outside, root=repository, use_config=False)


def test_select_paths_match_external_files_by_absolute_posix_path(tmp_path):
    repository = tmp_path / "repo"
    outside = tmp_path / "outside.md"
    repository.mkdir()
    outside.write_text("text\n", encoding="utf-8")
    _git(repository, "init")

    assert markdown_tables.select_markdown_paths(outside, root=repository, exclude=re.escape(outside.as_posix()) + "$", use_config=False) == ()
    assert markdown_tables.select_markdown_paths(outside, root=repository, use_config=False) == (outside,)


def test_explicit_file_outside_worktree_uses_named_repository_free_result(tmp_path, monkeypatch):
    path = tmp_path / "table.md"
    path.write_text("text\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    result = markdown_selection._select_markdown_paths(path, use_config=False)

    assert result.paths == (path,)
    assert result.repository is None
    assert result.input_errors == ()


@pytest.mark.parametrize(
    ("result", "message"),
    [
        (process.BoundedProcessResult(launch_error="missing executable"), "Git launch failed"),
        (process.BoundedProcessResult(returncode=-9, timed_out=True), "timed out"),
        (process.BoundedProcessResult(returncode=0, capture_incomplete=True), "capture limit"),
        (process.BoundedProcessResult(returncode=0, stdout_truncated=True), "capture limit"),
        (process.BoundedProcessResult(returncode=128, stderr=b"fatal: invalid gitfile format: .git\n"), "invalid gitfile"),
        (process.BoundedProcessResult(returncode=128, stderr=b"fatal: not a git repository: '/broken'\n"), "not a git repository"),
    ],
)
def test_explicit_files_propagate_operational_git_discovery_failures(tmp_path, monkeypatch, result, message):
    path = tmp_path / "table.md"
    path.write_text("text\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(markdown_selection.process, "run_bounded_process", lambda *_args, **_kwargs: result)

    with pytest.raises(markdown_tables.MarkdownTableError, match=message):
        markdown_tables.select_markdown_paths(path, use_config=False)


def test_git_discovery_forces_c_locale_and_only_expected_not_worktree_falls_back(tmp_path, monkeypatch):
    path = tmp_path / "table.md"
    path.write_text("text\n", encoding="utf-8")
    captured_environments = []

    def not_worktree(_command, _cwd, environment, _timeout, _limit):
        captured_environments.append(environment)
        return process.BoundedProcessResult(returncode=128, stderr=b"fatal: not a git repository (or any of the parent directories): .git\n")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(markdown_selection.process, "run_bounded_process", not_worktree)

    assert markdown_tables.select_markdown_paths(path, use_config=False) == (path,)
    assert captured_environments[0]["LC_ALL"] == "C"


@pytest.mark.parametrize("explicit", [False, True])
def test_configuration_fifo_is_opened_nonblocking_and_rejected(tmp_path, monkeypatch, explicit):
    repository = tmp_path / "repo"
    repository.mkdir()
    _git(repository, "init")
    config = repository / ".la-dev-markdown-tables.json"
    os.mkfifo(str(config))
    original_open = markdown_files.os.open

    def checked_open(path, flags, *arguments):
        if path == str(config):
            assert flags & os.O_NONBLOCK
        return original_open(path, flags, *arguments)

    monkeypatch.setattr(markdown_files.os, "open", checked_open)

    with pytest.raises(markdown_tables.MarkdownTableError, match="regular file"):
        markdown_tables.select_markdown_paths(root=repository, config_path=config if explicit else None)


@pytest.mark.parametrize(
    ("contents", "message"),
    [
        ("{", "Invalid JSON configuration"),
        ("[]", "root must be an object"),
        ('{"version": 1}', "missing required field"),
        ('{"version": true, "exclude": []}', "version must be 1"),
        ('{"version": 2, "exclude": []}', "version must be 1"),
        ('{"version": 1, "exclude": [], "extra": true}', "unknown field"),
        ('{"version": 1, "exclude": "docs"}', "array of strings"),
        ('{"version": 1, "exclude": [1]}', "array of strings"),
        ('{"version": 1, "exclude": ["["]}', "Invalid exclusion regular expression"),
    ],
)
def test_select_paths_rejects_invalid_configuration(tmp_path, contents, message):
    repository = tmp_path / "repo"
    repository.mkdir()
    _git(repository, "init")
    (repository / ".la-dev-markdown-tables.json").write_text(contents, encoding="utf-8")

    with pytest.raises(markdown_tables.MarkdownTableError, match=message):
        markdown_tables.select_markdown_paths(root=repository)


def test_select_paths_explicit_config_and_argument_contracts(tmp_path):
    repository = tmp_path / "repo"
    repository.mkdir()
    _git(repository, "init")
    path = repository / "table.md"
    path.write_text("text\n", encoding="utf-8")
    config = tmp_path / "selection.json"
    config.write_text('{"version": 1, "exclude": ["table\\\\.md$"]}\n', encoding="utf-8")

    assert markdown_tables.select_markdown_paths(path, root=repository, config_path=config) == ()
    with pytest.raises(markdown_tables.MarkdownTableError, match="config_path cannot"):
        markdown_tables.select_markdown_paths(path, root=repository, config_path=config, use_config=False)
    with pytest.raises(markdown_tables.MarkdownTableError, match="apply_excludes is false"):
        markdown_tables.select_markdown_paths(path, root=repository, exclude="table", apply_excludes=False)
    with pytest.raises(markdown_tables.MarkdownTableError, match="does not exist"):
        markdown_tables.select_markdown_paths(path, root=repository, config_path=tmp_path / "missing.json")


def test_select_paths_configuration_requires_regular_utf8_file(tmp_path):
    repository = tmp_path / "repo"
    repository.mkdir()
    _git(repository, "init")
    config = repository / ".la-dev-markdown-tables.json"
    config.write_bytes(b"\xff")

    with pytest.raises(markdown_tables.MarkdownTableError, match="valid UTF-8"):
        markdown_tables.select_markdown_paths(root=repository)

    config.unlink()
    target = repository / "actual-config.json"
    target.write_text('{"version": 1, "exclude": []}\n', encoding="utf-8")
    config.symlink_to(target)
    with pytest.raises(markdown_tables.MarkdownTableError, match="symbolic link"):
        markdown_tables.select_markdown_paths(root=repository)


def test_select_paths_rejects_unexpected_input_inspection_failure(tmp_path, monkeypatch):
    path = tmp_path / "table.md"
    path.write_text("text\n", encoding="utf-8")
    original_lstat = pathlib.Path.lstat

    def denied(selected):
        if selected == path:
            raise PermissionError("denied")
        return original_lstat(selected)

    monkeypatch.setattr(pathlib.Path, "lstat", denied)

    with pytest.raises(markdown_tables.MarkdownTableError, match="Cannot inspect input path: denied"):
        markdown_tables.select_markdown_paths(path, use_config=False)


def test_select_paths_retains_not_a_directory_input_as_file_candidate(tmp_path):
    parent = tmp_path / "not-a-directory"
    parent.write_text("text\n", encoding="utf-8")
    path = parent / "table.md"

    assert markdown_tables.select_markdown_paths(path, use_config=False) == (path.absolute(),)
