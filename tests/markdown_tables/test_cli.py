"""Markdown table command-line interface tests."""

import pathlib
import subprocess

import pytest

import la_dev_codex_plugins._filesystem as filesystem
import la_dev_codex_plugins.markdown_tables.cli as markdown_cli
import la_dev_codex_plugins.markdown_tables.files as markdown_files
import la_dev_codex_plugins.markdown_tables.selection as markdown_selection


def _git(repository, *arguments):
    subprocess.run(("git", *arguments), cwd=str(repository), check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def test_check_reports_changes_without_mutation_and_uses_status_one(tmp_path, capsys):
    path = tmp_path / "table.md"
    source = "| A|B |\n|-|-|\n"
    path.write_text(source, encoding="utf-8")

    assert markdown_cli.main(["--check", str(path)]) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("la-dev-markdown-tables: ")
    assert ":1: Repair Markdown table structure\n" in captured.err
    assert path.read_text(encoding="utf-8") == source


def test_fix_prints_changed_path_and_is_quiet_when_clean(tmp_path, capsys):
    path = tmp_path / "table.md"
    path.write_text("| A|B |\n|-|-|\n", encoding="utf-8")

    assert markdown_cli.main([str(path)]) == 0
    captured = capsys.readouterr()
    assert captured.out == "Formatted Markdown tables: {}\n".format(path.as_posix())
    assert captured.err == ""

    assert markdown_cli.main([str(path)]) == 0
    assert capsys.readouterr() == ("", "")


def test_human_output_escapes_paths_to_one_physical_line(tmp_path, capsys):
    path = tmp_path / "line\nreturn\rtab\tback\\slash-\u03bb.md"
    path.write_text("| A|B |\n|-|-|\n", encoding="utf-8")

    assert markdown_cli.main([str(path)]) == 0
    captured = capsys.readouterr()
    assert captured.out == "Formatted Markdown tables: {}\n".format(filesystem.escape_display_text(path.as_posix()))
    assert captured.out.count("\n") == 1
    assert captured.err == ""

    missing = tmp_path / "missing\nback\\slash.md"
    assert markdown_cli.main(["--check", str(missing)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.count("\n") == 1
    assert filesystem.escape_display_text(missing.as_posix()) in captured.err


def test_display_text_preserves_printable_unicode_and_escapes_unsafe_characters():
    source = "print-\u03bb\\\a\b\t\n\v\f\r\x1f\x7f\x85\u200e\u2028\u2029\udcff"
    expected = "print-\u03bb\\\\\\a\\b\\t\\n\\v\\f\\r\\x1f\\x7f\\x85\\u200e\\u2028\\u2029\\udcff"
    assert filesystem.escape_display_text(source) == expected


def test_explicit_multi_file_fix_preserves_command_line_order(tmp_path, capsys):
    first = tmp_path / "first.txt"
    second = tmp_path / "second.markdown"
    for path in (first, second):
        path.write_text("| A|B |\n|-|-|\n", encoding="utf-8")

    assert markdown_cli.main([str(second), str(first)]) == 0

    output = capsys.readouterr().out.splitlines()
    assert output == ["Formatted Markdown tables: {}".format(second), "Formatted Markdown tables: {}".format(first)]
    assert first.read_text(encoding="utf-8") == second.read_text(encoding="utf-8") == "| A | B |\n|---|---|\n"


def test_malformed_status_two_takes_precedence_over_check_changes(tmp_path, capsys):
    changed = tmp_path / "changed.md"
    malformed = tmp_path / "malformed.md"
    changed.write_text("| A|B |\n|-|-|\n", encoding="utf-8")
    malformed.write_text("| C | D |\n|---|---|\n| 1 | 2 | 3 |\n", encoding="utf-8")

    assert markdown_cli.main(["--check", str(changed), str(malformed)]) == 2

    captured = capsys.readouterr()
    assert "Repair Markdown table structure" in captured.err
    assert "Body row has 3 cells; expected 2" in captured.err


def test_check_interleaves_changes_and_issues_in_same_file_source_order(tmp_path, capsys):
    path = tmp_path / "mixed.md"
    path.write_text("| A | B |\n|---|---|\n| 1 | 2 | 3 |\n\n| C|D |\n|---|---|\n", encoding="utf-8")

    assert markdown_cli.main(["--check", str(path)]) == 2

    diagnostics = capsys.readouterr().err.splitlines()
    assert ":3: Body row has 3 cells; expected 2" in diagnostics[0]
    assert ":5: Format Markdown table style" in diagnostics[1]


def test_fix_writes_safe_changes_then_returns_two_for_malformed_table(tmp_path, capsys):
    path = tmp_path / "mixed.md"
    path.write_text("| A|B |\n|-|-|\n\n| C | D |\n|---|---|\n| 1 | 2 | 3 |\n", encoding="utf-8")

    assert markdown_cli.main([str(path)]) == 2

    captured = capsys.readouterr()
    assert captured.out == "Formatted Markdown tables: {}\n".format(path.as_posix())
    assert "Body row has 3 cells; expected 2" in captured.err


def test_duplicate_explicit_paths_are_processed_once(tmp_path, monkeypatch, capsys):
    path = tmp_path / "table.txt"
    path.write_text("| A|B |\n|-|-|\n", encoding="utf-8")
    calls = []
    original = markdown_files.format_markdown_tables_file

    def record(selected, check=False):
        calls.append((selected, check))
        return original(selected, check=check)

    monkeypatch.setattr(markdown_files, "format_markdown_tables_file", record)
    assert markdown_cli.main(["--check", str(path), str(pathlib.Path(str(path.parent)) / "." / path.name)]) == 1
    capsys.readouterr()
    assert len(calls) == 1


def test_operational_errors_continue_to_later_files(tmp_path, capsys):
    missing = tmp_path / "missing.md"
    clean = tmp_path / "clean.md"
    clean.write_text("| A | B |\n|---|---|\n", encoding="utf-8")

    assert markdown_cli.main([str(missing), str(clean)]) == 2
    captured = capsys.readouterr()
    assert "Cannot inspect file" in captured.err


@pytest.mark.parametrize("check", [False, True])
def test_cli_refuses_outside_directory_and_final_symlink_in_both_modes(tmp_path, capsys, check):
    target = tmp_path / "target.md"
    target.write_text("| A |\n|---|\n", encoding="utf-8")
    link = tmp_path / "link.md"
    link.symlink_to(target)
    arguments = [str(tmp_path), str(link)]
    if check:
        arguments.insert(0, "--check")

    assert markdown_cli.main(arguments) == 2

    diagnostics = capsys.readouterr().err
    assert "Directory must be inside the active Git worktree" in diagnostics
    assert "symbolic link" in diagnostics


def test_no_paths_uses_tracked_discovery(monkeypatch, tmp_path, capsys):
    path = tmp_path / "table.md"
    path.write_text("| A|B |\n|-|-|\n", encoding="utf-8")
    discoveries = []

    def discover(_start=None):
        discoveries.append(True)
        return tmp_path

    monkeypatch.setattr(markdown_selection, "_discover_git_root", discover)
    monkeypatch.setattr(markdown_selection, "_git_markdown_entries", lambda _root, **_kwargs: (("table.md", path),))

    assert markdown_cli.main(["--check"]) == 1
    assert "table.md:1" in capsys.readouterr().err
    assert discoveries == [True]


@pytest.mark.parametrize("option", ["--help", "--version"])
def test_help_and_version_exit_zero(option, capsys):
    with pytest.raises(SystemExit) as caught:
        markdown_cli.main([option])
    assert caught.value.code == 0
    assert capsys.readouterr().out


def test_cli_applies_root_config_to_pre_commit_style_explicit_paths_and_can_bypass_it(tmp_path, monkeypatch, capsys):
    repository = tmp_path / "repo"
    repository.mkdir()
    _git(repository, "init")
    path = repository / "generated.md"
    path.write_text("| A|B |\n|-|-|\n", encoding="utf-8")
    (repository / ".la-dev-markdown-tables.json").write_text('{"version": 1, "exclude": ["^generated\\\\.md$"]}\n', encoding="utf-8")
    monkeypatch.chdir(repository)

    assert markdown_cli.main(["--check", str(path)]) == 0
    assert capsys.readouterr() == ("", "")
    assert markdown_cli.main(["--check", "--no-exclude", str(path)]) == 1
    assert "generated.md:1" in capsys.readouterr().err


def test_cli_exclusions_are_additive_and_no_config_disables_root_config(tmp_path, monkeypatch, capsys):
    repository = tmp_path / "repo"
    repository.mkdir()
    _git(repository, "init")
    configured = repository / "configured.md"
    command_line = repository / "command-line.md"
    for path in (configured, command_line):
        path.write_text("| A|B |\n|-|-|\n", encoding="utf-8")
    (repository / ".la-dev-markdown-tables.json").write_text('{"version": 1, "exclude": ["^configured\\\\.md$"]}\n', encoding="utf-8")
    monkeypatch.chdir(repository)

    assert markdown_cli.main(["--check", "--exclude", "^command-line\\.md$", str(configured), str(command_line)]) == 0
    assert capsys.readouterr() == ("", "")
    assert markdown_cli.main(["--check", "--no-config", str(configured)]) == 1
    assert "configured.md:1" in capsys.readouterr().err


def test_cli_directory_discovery_adds_only_nonignored_untracked_files(tmp_path, monkeypatch, capsys):
    repository = tmp_path / "repo"
    docs = repository / "docs"
    docs.mkdir(parents=True)
    _git(repository, "init")
    tracked = docs / "tracked.md"
    untracked = docs / "untracked.md"
    ignored = docs / "ignored.md"
    for path in (tracked, untracked, ignored):
        path.write_text("| A|B |\n|-|-|\n", encoding="utf-8")
    (repository / ".gitignore").write_text("docs/ignored.md\n", encoding="utf-8")
    _git(repository, "add", "--", "docs/tracked.md", ".gitignore")
    monkeypatch.chdir(repository)

    assert markdown_cli.main(["--check", str(docs)]) == 1
    diagnostics = capsys.readouterr().err
    assert "docs/tracked.md:1" in diagnostics
    assert "untracked.md" not in diagnostics
    assert markdown_cli.main(["--check", "--include-untracked", str(docs)]) == 1
    diagnostics = capsys.readouterr().err
    assert "docs/tracked.md:1" in diagnostics
    assert "docs/untracked.md:1" in diagnostics
    assert "ignored.md" not in diagnostics


def test_cli_invalid_config_fails_before_fixing_any_file(tmp_path, monkeypatch, capsys):
    repository = tmp_path / "repo"
    repository.mkdir()
    _git(repository, "init")
    path = repository / "table.md"
    source = "| A|B |\n|-|-|\n"
    path.write_text(source, encoding="utf-8")
    (repository / ".la-dev-markdown-tables.json").write_text('{"version": 1, "exclude": ["["]}\n', encoding="utf-8")
    monkeypatch.chdir(repository)

    assert markdown_cli.main([str(path)]) == 2
    assert "Invalid exclusion regular expression" in capsys.readouterr().err
    assert path.read_text(encoding="utf-8") == source


def test_cli_operational_git_failure_stops_before_writing_explicit_file(tmp_path, monkeypatch, capsys):
    repository = tmp_path / "repo"
    repository.mkdir()
    _git(repository, "init")
    path = repository / "table.md"
    source = "| A|B |\n|-|-|\n"
    path.write_text(source, encoding="utf-8")
    (repository / ".la-dev-markdown-tables.json").write_text('{"version": 1, "exclude": ["^table\\\\.md$"]}\n', encoding="utf-8")
    monkeypatch.chdir(repository)
    monkeypatch.setenv("PATH", "")

    assert markdown_cli.main([str(path)]) == 2
    assert "Git launch failed" in capsys.readouterr().err
    assert path.read_text(encoding="utf-8") == source


def test_cli_directory_error_does_not_prevent_later_file_fix(tmp_path, monkeypatch, capsys):
    repository = tmp_path / "repo"
    outside = tmp_path / "outside"
    repository.mkdir()
    outside.mkdir()
    _git(repository, "init")
    path = repository / "table.md"
    path.write_text("| A|B |\n|-|-|\n", encoding="utf-8")
    monkeypatch.chdir(repository)

    assert markdown_cli.main([str(outside), str(path)]) == 2
    captured = capsys.readouterr()
    assert "Directory must be inside the active Git worktree" in captured.err
    assert captured.out == "Formatted Markdown tables: table.md\n"
    assert path.read_text(encoding="utf-8") == "| A | B |\n|---|---|\n"


def test_cli_input_inspection_error_does_not_prevent_later_file_fix(tmp_path, monkeypatch, capsys):
    denied = tmp_path / "denied.md"
    selected = tmp_path / "selected.md"
    denied.write_text("denied\n", encoding="utf-8")
    selected.write_text("| A|B |\n|-|-|\n", encoding="utf-8")
    original_lstat = pathlib.Path.lstat

    def inspect(path):
        if path == denied:
            raise PermissionError("denied")
        return original_lstat(path)

    monkeypatch.setattr(pathlib.Path, "lstat", inspect)

    assert markdown_cli.main([str(denied), str(selected)]) == 2
    captured = capsys.readouterr()
    assert "Cannot inspect input path: denied" in captured.err
    assert captured.out == "Formatted Markdown tables: {}\n".format(selected.as_posix())
    assert denied.read_text(encoding="utf-8") == "denied\n"
    assert selected.read_text(encoding="utf-8") == "| A | B |\n|---|---|\n"


@pytest.mark.parametrize(
    "arguments",
    [
        ["--no-exclude", "--exclude", "docs"],
        ["--config", "config.json", "--no-config"],
        ["--no-exclude", "--config", "config.json"],
        ["--no-exclude", "--no-config"],
    ],
)
def test_cli_rejects_contradictory_selection_controls(arguments):
    with pytest.raises(SystemExit) as caught:
        markdown_cli.main(arguments)
    assert caught.value.code == 2
