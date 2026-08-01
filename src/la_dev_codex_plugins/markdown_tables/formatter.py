"""Canonical Markdown table rendering and whole-document replacement."""

from . import models, parser


def _render_data_cell(cell, width, alignment):
    padding = width - len(cell)
    if alignment in {"none", "left"}:
        left = 0
        right = padding
    elif alignment == "right":
        left = padding
        right = 0
    else:
        left = padding // 2
        right = padding - left
    return " " + " " * left + cell + " " * right + " "


def _render_delimiter_cell(slot_width, alignment):
    if alignment == "left":
        return ":" + "-" * (slot_width - 1)
    if alignment == "right":
        return "-" * (slot_width - 1) + ":"
    if alignment == "center":
        return ":" + "-" * (slot_width - 2) + ":"
    return "-" * slot_width


def _render_candidate(candidate):
    data_rows = (candidate.row_cells[0], *candidate.row_cells[2:])
    slot_widths = []
    content_widths = []
    for column, alignment in enumerate(candidate.alignments):
        intrinsic = max(len(row[column]) for row in data_rows)
        colon_count = 2 if alignment == "center" else 1 if alignment in {"left", "right"} else 0
        slot_width = max(intrinsic + 2, 3 + colon_count)
        slot_widths.append(slot_width)
        content_widths.append(slot_width - 2)

    prefix = candidate.table.container_prefix + candidate.table.indentation
    rendered = []
    for row_index, cells in enumerate(candidate.row_cells):
        if row_index == 1:
            row_text = prefix + "|" + "|".join(_render_delimiter_cell(slot_widths[column], candidate.alignments[column]) for column in range(len(cells))) + "|"
        else:
            row_text = prefix + "|" + "|".join(_render_data_cell(cell, content_widths[column], candidate.alignments[column]) for column, cell in enumerate(cells)) + "|"
        if row_index == 0 and candidate.bom:
            row_text = "\ufeff" + row_text
        rendered.append(row_text)

    source_lines = parser._split_lines(candidate.table.raw)
    return "".join(row + source_lines[index].ending for index, row in enumerate(rendered))


def _line_is_blank(line, quote_table=False):
    if quote_table:
        _depth, _prefix, remainder = parser._peel_blockquotes(line.text)
        return not remainder.strip(" \t")
    return not line.text.strip(" \t")


def _boundary_text(candidate, ending):
    if candidate.quote_prefix:
        return candidate.quote_prefix.rstrip(" \t") + ending
    return ending


def _preferred_ending(primary, secondary):
    return primary or secondary or "\n"


def format_markdown_tables(text, path=None):
    """Return partial canonical formatting while preserving unsafe tables."""
    supplied_path = None if path is None else str(path)
    scan = parser._scan_markdown_tables(text, path=supplied_path)
    replacements = []
    insertions = {}
    insertion_changes = {}
    table_changes = []

    for candidate in scan.candidates:
        rendered = _render_candidate(candidate)
        source = text[candidate.start_offset : candidate.end_offset]
        if rendered != source:
            replacements.append((candidate.start_offset, candidate.end_offset, rendered))
            kind = "repair" if candidate.structural_repair else "style"
            message = "Repair Markdown table structure" if kind == "repair" else "Format Markdown table style"
            table_changes.append((candidate.start_offset, models.MarkdownTableChange(kind, message, candidate.table.start_line, supplied_path)))

        if candidate.list_contained:
            continue
        quote_table = bool(candidate.quote_prefix)
        if candidate.start_index > 0 and not candidate.boundary_before_ambiguous:
            previous = scan.lines[candidate.start_index - 1]
            if not _line_is_blank(previous, quote_table=quote_table):
                offset = candidate.start_offset
                ending = _preferred_ending(previous.ending, candidate.first_ending)
                if offset not in insertions:
                    insertions[offset] = _boundary_text(candidate, ending)
                    insertion_changes[offset] = models.MarkdownTableChange("boundary", "Insert blank line before Markdown table", candidate.table.start_line, supplied_path, "before")
        if candidate.end_index < len(scan.lines) and not candidate.boundary_after_ambiguous:
            following = scan.lines[candidate.end_index]
            if not _line_is_blank(following, quote_table=quote_table):
                offset = candidate.end_offset
                ending = _preferred_ending(candidate.last_ending, following.ending)
                if offset not in insertions:
                    insertions[offset] = _boundary_text(candidate, ending)
                    insertion_changes[offset] = models.MarkdownTableChange("boundary", "Insert blank line after Markdown table", candidate.table.end_line, supplied_path, "after")

    events = []
    for offset, insertion in insertions.items():
        events.append((offset, 0, offset, insertion))
    for start, end, replacement in replacements:
        events.append((start, 1, end, replacement))
    events.sort(key=lambda event: (event[0], event[1]))
    pieces = []
    cursor = 0
    for start, event_kind, end, replacement in events:
        if event_kind == 0:
            if start < cursor:
                continue
            pieces.append(text[cursor:start])
            pieces.append(replacement)
            cursor = start
        else:
            if start < cursor:
                continue
            pieces.append(text[cursor:start])
            pieces.append(replacement)
            cursor = end
    pieces.append(text[cursor:])
    normalized = "".join(pieces)

    change_records = [(offset, 0, change) for offset, change in insertion_changes.items()]
    change_records.extend((offset, 1, change) for offset, change in table_changes)
    change_records.sort(key=lambda record: (record[0], record[1]))
    changes = tuple(record[2] for record in change_records)
    return models.MarkdownTableFormatResult(normalized, scan.tables, changes, scan.issues, changed=normalized != text)


def normalize_markdown_tables(text):
    """Return strict canonical text or raise with the partial format result."""
    result = format_markdown_tables(text)
    if result.issues:
        first = result.issues[0]
        raise models.MarkdownTableError("Malformed Markdown table", line_number=first.line_number, issues=result.issues, result=result)
    return result.text


def markdown_table_issues(text, path=None):
    """Return pending format changes and malformed issues in source order."""
    result = format_markdown_tables(text, path=path)
    return _ordered_result_issues(result)


def _ordered_result_issues(result):
    records = []
    for index, change in enumerate(result.changes):
        if change.boundary_position == "before":
            priority = 0
        elif change.boundary_position == "after":
            priority = 2
        else:
            priority = 1
        issue = models.MarkdownTableIssue("format", change.message, change.line_number, change.path)
        records.append((change.line_number, priority, index, issue))
    issue_offset = len(records)
    for index, issue in enumerate(result.issues):
        records.append((issue.line_number, 3, issue_offset + index, issue))
    records.sort(key=lambda record: (record[0], record[1], record[2]))
    return tuple(record[3] for record in records)
