"""Command-line interface for canonical Markdown table formatting."""

import argparse
import os
import pathlib
import sys

from .. import __version__
from .. import _filesystem as filesystem
from . import files, formatter, models

_PREFIX = "la-dev-markdown-tables:"


def _absolute_paths(raw_paths):
    selected = []
    seen = set()
    for raw_path in raw_paths:
        path = pathlib.Path(os.path.abspath(str(raw_path)))  # noqa: PTH100 - lexical normalization must not resolve symlinks
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        selected.append(path)
    return tuple(selected)


def _display_path(path, repository):
    if repository is not None:
        try:
            return filesystem.escape_display_text(path.relative_to(repository).as_posix())
        except ValueError:
            pass
    return filesystem.escape_display_text(path.as_posix())


def _diagnostic(path, line_number, message, repository):
    display = _display_path(path, repository)
    display_message = filesystem.escape_display_text(message)
    if line_number is None:
        return "{} {}: {}".format(_PREFIX, display, display_message)
    return "{} {}:{}: {}".format(_PREFIX, display, line_number, display_message)


def main(argv=None):
    """Format explicit files or tracked Markdown files and return a CLI status."""
    argument_parser = argparse.ArgumentParser(prog="la-dev-markdown-tables", description="Format Markdown pipe tables to one canonical bordered and aligned style.")
    argument_parser.add_argument("--check", action="store_true", help="Report required formatting without writing files.")
    argument_parser.add_argument("--version", action="version", version="%(prog)s {}".format(__version__))
    argument_parser.add_argument("paths", metavar="PATH", nargs="*", type=pathlib.Path, help="Files to inspect; defaults to tracked Markdown files.")
    arguments = argument_parser.parse_args(argv)

    try:
        if arguments.paths:
            selected = _absolute_paths(arguments.paths)
            try:
                repository = files._discover_git_root()
            except models.MarkdownTableError:
                repository = None
        else:
            repository = files._discover_git_root()
            selected = files._tracked_markdown_paths(repository)
    except models.MarkdownTableError as exc:
        print("{} {}".format(_PREFIX, filesystem.escape_display_text(exc)), file=sys.stderr)
        return 2

    changed = False
    failed = False
    for path in selected:
        try:
            result = files.format_markdown_tables_file(path, check=arguments.check)
        except models.MarkdownTableError as exc:
            print(_diagnostic(path, exc.line_number, exc.message, repository), file=sys.stderr)
            failed = True
            continue
        if result.changed:
            changed = True
            if not arguments.check:
                print("Formatted Markdown tables: {}".format(_display_path(path, repository)))
        if result.issues:
            failed = True
        diagnostics = (
            tuple((issue.line_number, issue.message) for issue in formatter._ordered_result_issues(result)) if arguments.check else tuple((issue.line_number, issue.message) for issue in result.issues)
        )
        for line_number, message in diagnostics:
            print(_diagnostic(path, line_number, message, repository), file=sys.stderr)

    if failed:
        return 2
    if arguments.check and changed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
