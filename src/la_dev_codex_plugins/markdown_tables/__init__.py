"""Public library API for canonical Markdown table handling."""

from .files import format_markdown_tables_file, normalize_markdown_tables_file, tracked_markdown_paths
from .formatter import format_markdown_tables, markdown_table_issues, normalize_markdown_tables
from .models import MarkdownTable, MarkdownTableChange, MarkdownTableError, MarkdownTableFormatResult, MarkdownTableIssue, MarkdownTableRow
from .parser import parse_markdown_tables

__all__ = (
    "MarkdownTable",
    "MarkdownTableChange",
    "MarkdownTableError",
    "MarkdownTableFormatResult",
    "MarkdownTableIssue",
    "MarkdownTableRow",
    "format_markdown_tables",
    "format_markdown_tables_file",
    "markdown_table_issues",
    "normalize_markdown_tables",
    "normalize_markdown_tables_file",
    "parse_markdown_tables",
    "tracked_markdown_paths",
)
