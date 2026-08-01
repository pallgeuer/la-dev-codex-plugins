"""Markdown table file and Git discovery tests."""

import os
import stat
import subprocess

import pytest

import la_dev_codex_plugins._filesystem as filesystem
import la_dev_codex_plugins.markdown_tables as markdown_tables
import la_dev_codex_plugins.markdown_tables.files as markdown_files


def _git(repository, *arguments):
    subprocess.run(("git", *arguments), cwd=str(repository), check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def test_format_file_check_does_not_write_and_fix_preserves_mode(tmp_path):
    path = tmp_path / "table.md"
    source = b"\xef\xbb\xbf| A|B |\r\n|-|-|\n"
    path.write_bytes(source)
    path.chmod(0o640)

    checked = markdown_tables.format_markdown_tables_file(path, check=True)
    assert checked.changed
    assert path.read_bytes() == source

    fixed = markdown_tables.format_markdown_tables_file(path)
    assert fixed.changed
    assert path.read_bytes() == b"\xef\xbb\xbf| A | B |\r\n|---|---|\n"
    assert stat.S_IMODE(path.stat().st_mode) == 0o640


def test_fix_preserves_special_mode_bits_after_writing(tmp_path):
    path = tmp_path / "table.md"
    path.write_text("| A|B |\n|-|-|\n", encoding="utf-8")
    path.chmod(0o4755)

    markdown_tables.format_markdown_tables_file(path)

    assert stat.S_IMODE(path.stat().st_mode) == 0o4755


def test_fix_writes_safe_table_before_reporting_independent_malformed_table(tmp_path):
    path = tmp_path / "table.md"
    path.write_text("| A|B |\n|-|-|\n\n| C | D |\n|---|---|\n| 1 | 2 | 3 |\n", encoding="utf-8")

    result = markdown_tables.format_markdown_tables_file(path)

    assert result.changed
    assert result.has_errors
    assert path.read_text(encoding="utf-8").startswith("| A | B |\n|---|---|")


def test_strict_file_api_refuses_partial_write_for_malformed_input(tmp_path):
    path = tmp_path / "table.md"
    source = "| A|B |\n|-|-|\n\n| C | D |\n|---|---|\n| 1 | 2 | 3 |\n"
    path.write_text(source, encoding="utf-8")

    with pytest.raises(markdown_tables.MarkdownTableError):
        markdown_tables.normalize_markdown_tables_file(path)

    assert path.read_text(encoding="utf-8") == source


def test_invalid_utf8_directory_and_final_symlink_are_refused(tmp_path):
    invalid = tmp_path / "invalid.md"
    invalid.write_bytes(b"\xff")
    with pytest.raises(markdown_tables.MarkdownTableError, match="valid UTF-8"):
        markdown_tables.format_markdown_tables_file(invalid, check=True)

    with pytest.raises(markdown_tables.MarkdownTableError, match="regular file"):
        markdown_tables.format_markdown_tables_file(tmp_path, check=True)

    real = tmp_path / "real.md"
    real.write_text("| A |\n|---|\n", encoding="utf-8")
    link = tmp_path / "link.md"
    link.symlink_to(real)
    with pytest.raises(markdown_tables.MarkdownTableError, match="symbolic link"):
        markdown_tables.format_markdown_tables_file(link, check=True)


def test_atomic_replacement_failure_cleans_temporary_and_preserves_original(tmp_path, monkeypatch):
    path = tmp_path / "table.md"
    source = "| A|B |\n|-|-|\n"
    path.write_text(source, encoding="utf-8")

    def fail_replace(_source, _target):
        raise OSError("replacement failed")

    monkeypatch.setattr(filesystem.os, "replace", fail_replace)
    with pytest.raises(markdown_tables.MarkdownTableError, match="replacement failed"):
        markdown_tables.format_markdown_tables_file(path)

    assert path.read_text(encoding="utf-8") == source
    assert list(tmp_path.glob(".la-dev-markdown-tables-*")) == []


def test_descriptor_read_and_fix_reject_symlink_swap(tmp_path, monkeypatch):
    path = tmp_path / "table.md"
    target = tmp_path / "target.md"
    source = "| A|B |\n|-|-|\n"
    target_source = "target contents\n"
    path.write_text(source, encoding="utf-8")
    target.write_text(target_source, encoding="utf-8")
    original_fstat = markdown_files.os.fstat
    swapped = []

    def swap_after_open(descriptor):
        metadata = original_fstat(descriptor)
        if not swapped:
            path.unlink()
            path.symlink_to(target)
            swapped.append(True)
        return metadata

    monkeypatch.setattr(markdown_files.os, "fstat", swap_after_open)
    with pytest.raises(markdown_tables.MarkdownTableError, match="changed after it was read"):
        markdown_tables.format_markdown_tables_file(path)

    assert path.is_symlink()
    assert target.read_text(encoding="utf-8") == target_source
    assert list(tmp_path.glob(".la-dev-markdown-tables-*")) == []


def test_fix_rejects_concurrent_regular_file_replacement(tmp_path, monkeypatch):
    path = tmp_path / "table.md"
    replacement = tmp_path / "replacement.md"
    path.write_text("| A|B |\n|-|-|\n", encoding="utf-8")
    replacement.write_text("concurrent replacement\n", encoding="utf-8")
    original_format = markdown_files.formatter.format_markdown_tables

    def replace_during_format(text, path=None):
        replacement.replace(path)
        return original_format(text, path=path)

    monkeypatch.setattr(markdown_files.formatter, "format_markdown_tables", replace_during_format)
    with pytest.raises(markdown_tables.MarkdownTableError, match="changed after it was read"):
        markdown_tables.format_markdown_tables_file(path)

    assert path.read_text(encoding="utf-8") == "concurrent replacement\n"
    assert list(tmp_path.glob(".la-dev-markdown-tables-*")) == []


def test_noop_file_is_not_replaced(tmp_path):
    path = tmp_path / "table.md"
    path.write_text("| A | B |\n|---|---|\n", encoding="utf-8")
    before = path.stat()

    result = markdown_tables.format_markdown_tables_file(path)

    after = path.stat()
    assert not result.changed
    assert (after.st_ino, after.st_mtime_ns) == (before.st_ino, before.st_mtime_ns)


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

    assert markdown_files._discover_git_root(repository) == repository.absolute()
