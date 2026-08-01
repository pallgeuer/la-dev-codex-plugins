"""Markdown table command-line interface tests."""

import pathlib

import pytest

import la_dev_codex_plugins._filesystem as filesystem
import la_dev_codex_plugins.markdown_tables.cli as markdown_cli
import la_dev_codex_plugins.markdown_tables.files as markdown_files


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
def test_cli_refuses_directory_and_final_symlink_in_both_modes(tmp_path, capsys, check):
    target = tmp_path / "target.md"
    target.write_text("| A |\n|---|\n", encoding="utf-8")
    link = tmp_path / "link.md"
    link.symlink_to(target)
    arguments = [str(tmp_path), str(link)]
    if check:
        arguments.insert(0, "--check")

    assert markdown_cli.main(arguments) == 2

    diagnostics = capsys.readouterr().err
    assert "Expected a regular file" in diagnostics
    assert "symbolic link" in diagnostics


def test_no_paths_uses_tracked_discovery(monkeypatch, tmp_path, capsys):
    path = tmp_path / "table.md"
    path.write_text("| A|B |\n|-|-|\n", encoding="utf-8")
    discoveries = []

    def discover(_start=None):
        discoveries.append(True)
        return tmp_path

    monkeypatch.setattr(markdown_files, "_discover_git_root", discover)
    monkeypatch.setattr(markdown_files, "_tracked_markdown_paths", lambda _root: (path,))

    assert markdown_cli.main(["--check"]) == 1
    assert "table.md:1" in capsys.readouterr().err
    assert discoveries == [True]


@pytest.mark.parametrize("option", ["--help", "--version"])
def test_help_and_version_exit_zero(option, capsys):
    with pytest.raises(SystemExit) as caught:
        markdown_cli.main([option])
    assert caught.value.code == 0
    assert capsys.readouterr().out
