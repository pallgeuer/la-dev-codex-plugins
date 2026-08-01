"""Command-line interface for canonical Markdown table formatting."""

import argparse
import pathlib
import sys

from .. import __version__
from .. import _filesystem as filesystem
from . import files, formatter, models, selection

_PREFIX = "la-dev-markdown-tables:"


def _display_path(path, repository):
    return filesystem.escape_display_text(selection._path_text(path, repository))


def _diagnostic(path, line_number, message, repository):
    display = _display_path(path, repository)
    display_message = filesystem.escape_display_text(message)
    if line_number is None:
        return "{} {}: {}".format(_PREFIX, display, display_message)
    return "{} {}:{}: {}".format(_PREFIX, display, line_number, display_message)


def main(argv=None):
    """Format selected Markdown files and return a CLI status."""
    argument_parser = argparse.ArgumentParser(prog="la-dev-markdown-tables", description="Format Markdown pipe tables to one canonical bordered and aligned style.")
    argument_parser.add_argument("--check", action="store_true", help="Report required formatting without writing files.")
    argument_parser.add_argument("--include-untracked", action="store_true", help="Include untracked, nonignored Markdown during Git discovery.")
    exclusion_group = argument_parser.add_mutually_exclusive_group()
    exclusion_group.add_argument("--exclude", action="append", default=[], metavar="REGEX", help="Exclude matching paths; repeat to add patterns.")
    exclusion_group.add_argument("--no-exclude", action="store_true", help="Disable all configured exclusion filtering.")
    configuration_group = argument_parser.add_mutually_exclusive_group()
    configuration_group.add_argument("--config", type=pathlib.Path, metavar="PATH", help="Use this configuration instead of the Git-root default.")
    configuration_group.add_argument("--no-config", action="store_true", help="Do not load Markdown-table configuration.")
    argument_parser.add_argument("--version", action="version", version="%(prog)s {}".format(__version__))
    argument_parser.add_argument("paths", metavar="PATH", nargs="*", type=pathlib.Path, help="Files or Git-scoped directories; defaults to tracked Markdown files.")
    arguments = argument_parser.parse_args(argv)
    if arguments.no_exclude and (arguments.config is not None or arguments.no_config):
        argument_parser.error("--no-exclude cannot be combined with --config or --no-config")

    try:
        selection_result = selection._select_markdown_paths(
            paths=arguments.paths,
            include_untracked=arguments.include_untracked,
            exclude=arguments.exclude,
            config_path=arguments.config,
            use_config=not arguments.no_config,
            apply_excludes=not arguments.no_exclude,
            collect_input_errors=True,
        )
    except models.MarkdownTableError as exc:
        print("{} {}".format(_PREFIX, filesystem.escape_display_text(exc)), file=sys.stderr)
        return 2

    changed = False
    failed = bool(selection_result.input_errors)
    for error in selection_result.input_errors:
        print(_diagnostic(pathlib.Path(error.path), error.line_number, error.message, selection_result.repository), file=sys.stderr)
    for path in selection_result.paths:
        try:
            result = files.format_markdown_tables_file(path, check=arguments.check)
        except models.MarkdownTableError as exc:
            print(_diagnostic(path, exc.line_number, exc.message, selection_result.repository), file=sys.stderr)
            failed = True
            continue
        if result.changed:
            changed = True
            if not arguments.check:
                print("Formatted Markdown tables: {}".format(_display_path(path, selection_result.repository)))
        if result.issues:
            failed = True
        diagnostics = (
            tuple((issue.line_number, issue.message) for issue in formatter._ordered_result_issues(result)) if arguments.check else tuple((issue.line_number, issue.message) for issue in result.issues)
        )
        for line_number, message in diagnostics:
            print(_diagnostic(path, line_number, message, selection_result.repository), file=sys.stderr)

    if failed:
        return 2
    if arguments.check and changed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
