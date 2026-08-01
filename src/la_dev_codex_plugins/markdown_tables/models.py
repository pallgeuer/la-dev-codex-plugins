"""Immutable public models for Markdown table inspection and formatting."""

import collections
import typing


class MarkdownTableRow(collections.namedtuple("MarkdownTableRowBase", "line_number raw cells")):
    """One physical table row and its structurally trimmed cells."""

    __slots__ = ()

    def __new__(cls, line_number, raw, cells):
        return super(MarkdownTableRow, cls).__new__(cls, line_number, raw, tuple(cells))


class MarkdownTable(collections.namedtuple("MarkdownTableBase", "start_line end_line raw container_prefix indentation rows alignments")):
    """One safely parsed Markdown table with inclusive physical positions."""

    __slots__ = ()

    def __new__(cls, start_line, end_line, raw, container_prefix, indentation, rows, alignments):
        return super(MarkdownTable, cls).__new__(cls, start_line, end_line, raw, container_prefix, indentation, tuple(rows), tuple(alignments))


class MarkdownTableChange(collections.namedtuple("MarkdownTableChangeBase", "kind message line_number path boundary_position")):
    """One proposed safe table or boundary change."""

    __slots__ = ()

    def __new__(cls, kind, message, line_number, path=None, boundary_position=None):
        return super(MarkdownTableChange, cls).__new__(cls, kind, message, line_number, path, boundary_position)


class MarkdownTableIssue(collections.namedtuple("MarkdownTableIssueBase", "kind message line_number path")):
    """One unresolved malformed or pending-format diagnostic."""

    __slots__ = ()

    def __new__(cls, kind, message, line_number, path=None):
        return super(MarkdownTableIssue, cls).__new__(cls, kind, message, line_number, path)


class MarkdownTableFormatResult:
    """Partial formatting output with safe tables, changes, and issues."""

    __slots__ = ("_changed", "changes", "issues", "tables", "text")
    _changed: bool
    changes: tuple
    issues: tuple
    tables: tuple
    text: str

    def __init__(self, text, tables=(), changes=(), issues=(), changed=False):
        """Store normalized text, immutable collections, and explicit change state."""
        if type(changed) is not bool:
            raise TypeError("changed must be a Boolean")
        object.__setattr__(self, "text", text)
        object.__setattr__(self, "tables", tuple(tables))
        object.__setattr__(self, "changes", tuple(changes))
        object.__setattr__(self, "issues", tuple(issues))
        object.__setattr__(self, "_changed", changed)

    def __setattr__(self, _name, _value):
        raise AttributeError("MarkdownTableFormatResult is immutable")

    def __repr__(self):
        return "MarkdownTableFormatResult(text={!r}, tables={!r}, changes={!r}, issues={!r}, changed={!r})".format(self.text, self.tables, self.changes, self.issues, self.changed)

    def __eq__(self, other):
        if not isinstance(other, MarkdownTableFormatResult):
            return NotImplemented
        return (self.text, self.tables, self.changes, self.issues, self.changed) == (other.text, other.tables, other.changes, other.issues, other.changed)

    def __hash__(self):
        return hash((self.text, self.tables, self.changes, self.issues, self.changed))

    @property
    def changed(self):
        """Whether normalized text is recorded as differing from its source."""
        return self._changed

    @property
    def has_errors(self):
        """Whether unresolved parser issues remain."""
        return bool(self.issues)


class MarkdownTableError(Exception):
    """Strict normalization or operational failure with structured context."""

    result: typing.Optional[MarkdownTableFormatResult]

    def __init__(self, message, path=None, line_number=None, issues=(), result=None):
        """Store a concise message plus optional path, line, issues, and result."""
        super().__init__(message)
        self.message = message
        self.path = None if path is None else str(path)
        self.line_number = line_number
        self.issues = tuple(issues)
        self.result = result

    def __str__(self):
        location = self.path or ""
        if self.line_number is not None:
            location = "{}:{}".format(location, self.line_number) if location else str(self.line_number)
        return "{}: {}".format(location, self.message) if location else self.message
