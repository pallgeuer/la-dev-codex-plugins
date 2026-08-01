"""Conservative Markdown table scanning and structural parsing."""

import collections
import re

from . import models

_Line = collections.namedtuple("_Line", "number text ending start end")
_LineContext = collections.namedtuple("_LineContext", "quote_depth list_column lazy_list_boundary")
_Context = collections.namedtuple("_Context", "quote_depth quote_prefix list_column indentation container_prefix")
_Fence = collections.namedtuple("_Fence", "marker width quote_depth list_column")
_Html = collections.namedtuple("_Html", "kind end quote_depth list_column")
_ParsedRow = collections.namedtuple("_ParsedRow", "cells leading_border trailing_border repaired pipe_count")
_Candidate = collections.namedtuple(
    "_Candidate",
    "table start_offset end_offset row_cells alignments structural_repair list_contained quote_prefix first_ending last_ending start_index end_index bom boundary_before_ambiguous boundary_after_ambiguous",
)
_IssueRecord = collections.namedtuple("_IssueRecord", "issue offset")
_ScanResult = collections.namedtuple("_ScanResult", "lines tables candidates issues")

_DELIMITER_CELL = re.compile(r":?-+:?\Z")
_LIST_MARKER = re.compile(r"^( *)([*+-]|[0-9]{1,9}[.)])( {1,4})(.*)$")
_NEW_BLOCK = re.compile(r"(?:#{1,6}(?:[ \t]+|$)|(?:[*+-]|[0-9]{1,9}[.)])[ \t]+|(?:`{3,}|~{3,})|(?:[*_-][ \t]*){3,}$)")
_HTML_RAW_START = re.compile(r"<(script|pre|style|textarea)(?:[ \t>]|$)", re.IGNORECASE)
_HTML_BLOCK_TAGS = "address|article|aside|base|basefont|blockquote|body|caption|center|col|colgroup|dd|details|dialog|dir|div|dl|dt|fieldset|figcaption|figure|footer|form|frame|frameset|h1|h2|h3|h4|h5|h6|head|header|hr|html|iframe|legend|li|link|main|menu|menuitem|nav|noframes|ol|optgroup|option|p|param|search|section|summary|table|tbody|td|tfoot|th|thead|title|tr|track|ul"
_HTML_BLOCK_START = re.compile(r"</?(?:" + _HTML_BLOCK_TAGS + r")(?:[ \t\n/>]|$)", re.IGNORECASE)
_HTML_COMPLETE_TAG = re.compile(r"</?[A-Za-z][A-Za-z0-9-]*(?:[ \t]+[A-Za-z_:][A-Za-z0-9_.:-]*(?:[ \t]*=[ \t]*(?:[^ \t\"'=<>`]+|'[^']*'|\"[^\"]*\"))?)*[ \t]*/?>[ \t]*\Z")
_LINE_ENDING = re.compile(r"\r\n|\r|\n")


def _split_lines(text):
    lines = []
    offset = 0
    number = 1
    while offset < len(text):
        match = _LINE_ENDING.search(text, offset)
        end = len(text) if match is None else match.end()
        physical = text[offset:end]
        if physical.endswith("\r\n"):
            content = physical[:-2]
            ending = "\r\n"
        elif physical.endswith(("\n", "\r")):
            content = physical[:-1]
            ending = physical[-1:]
        else:
            content = physical
            ending = ""
        end = offset + len(physical)
        lines.append(_Line(number, content, ending, offset, end))
        offset = end
        number += 1
    return tuple(lines)


def _is_escaped(text, index):
    count = 0
    index -= 1
    while index >= 0 and text[index] == "\\":
        count += 1
        index -= 1
    return count % 2 == 1


def _run_width(text, index, character):
    end = index
    while end < len(text) and text[end] == character:
        end += 1
    return end - index


def _parse_row(source):
    stripped = source.strip(" \t")
    structural = tuple(index for index, character in enumerate(stripped) if character == "|" and not _is_escaped(stripped, index))
    if not structural:
        return _ParsedRow((), False, False, False, 0)
    leading = structural[0] == 0
    trailing = structural[-1] == len(stripped) - 1
    start = 1 if leading else 0
    end = len(stripped) - 1 if trailing else len(stripped)
    boundaries = tuple(index for index in structural if start <= index < end)
    cells = []
    cursor = start
    for boundary in boundaries:
        cells.append(stripped[cursor:boundary].strip(" \t"))
        cursor = boundary + 1
    cells.append(stripped[cursor:end].strip(" \t"))
    repaired = not (leading and trailing)
    return _ParsedRow(tuple(cells), leading, trailing, repaired, len(structural))


def _peel_blockquotes(text):
    position = 0
    depth = 0
    while position < len(text):
        match = re.match(r" {0,3}>[ \t]?", text[position:])
        if match is None:
            break
        position += match.end()
        depth += 1
    return depth, text[:position], text[position:]


def _leading_spaces(text):
    return len(text) - len(text.lstrip(" "))


def _is_new_block(source):
    stripped = source.strip(" \t")
    return bool(stripped and (_NEW_BLOCK.match(stripped) or stripped.startswith((">", "<!--", "<?", "<![CDATA[")) or _HTML_BLOCK_START.match(stripped)))


def _line_contexts(lines):
    contexts = []
    active_quote_depth = None
    active_list_columns = []
    lazy_quote_depth = None
    lazy_list_boundary = False
    previous_nonblank = False
    for index, line in enumerate(lines):
        text = line.text[1:] if index == 0 and line.text.startswith("\ufeff") else line.text
        quote_depth, _quote_prefix, remainder = _peel_blockquotes(text)
        leading = _leading_spaces(remainder)
        list_column = None
        if active_quote_depth == quote_depth and not remainder.startswith("\t"):
            for candidate in reversed(active_list_columns):
                if candidate <= leading <= candidate + 3:
                    list_column = candidate
                    break
        contexts.append(_LineContext(quote_depth, list_column, previous_nonblank and lazy_quote_depth == quote_depth and lazy_list_boundary))

        if not remainder.strip(" \t"):
            lazy_quote_depth = None
            lazy_list_boundary = False
            previous_nonblank = False
            continue
        if remainder.startswith("\t"):
            active_quote_depth = None
            active_list_columns = []
        else:
            if active_quote_depth != quote_depth:
                active_quote_depth = quote_depth
                active_list_columns = []
            else:
                while active_list_columns and active_list_columns[-1] > leading:
                    active_list_columns.pop()
            marker = _LIST_MARKER.match(remainder)
            if marker is not None:
                active_list_columns.append(len(marker.group(1)) + len(marker.group(2)) + len(marker.group(3)))

        if lazy_quote_depth != quote_depth or not previous_nonblank:
            lazy_list_boundary = False
        marker = _LIST_MARKER.match(remainder)
        if marker is not None:
            lazy_list_boundary = True
        elif _is_new_block(remainder.lstrip(" \t")):
            lazy_list_boundary = False
        lazy_quote_depth = quote_depth
        previous_nonblank = True
    return tuple(contexts)


def _derive_context(lines, line_contexts, index):
    text = lines[index].text
    if index == 0 and text.startswith("\ufeff"):
        text = text[1:]
    depth, quote_prefix, remainder = _peel_blockquotes(text)
    leading = _leading_spaces(remainder)
    indentation_prefix = remainder[:leading]
    if remainder[leading:].startswith("\t") or "\t" in indentation_prefix:
        return None
    list_column = line_contexts[index].list_column
    table_indent_width = leading - list_column if list_column is not None else leading
    if table_indent_width < 0 or table_indent_width > 3:
        return None
    indentation = " " * table_indent_width
    continuation = " " * list_column if list_column is not None else ""
    return _Context(depth, quote_prefix, list_column, indentation, quote_prefix + continuation)


def _source_for_context(text, context, allow_bom=False):
    if allow_bom and text.startswith("\ufeff"):
        text = text[1:]
    depth, _quote_prefix, remainder = _peel_blockquotes(text)
    if depth != context.quote_depth or remainder.startswith("\t"):
        return None
    if context.list_column is not None:
        continuation = " " * context.list_column
        if not remainder.startswith(continuation):
            return None
        remainder = remainder[context.list_column :]
    leading = _leading_spaces(remainder)
    if leading > 3 or remainder[leading:].startswith("\t"):
        return None
    return remainder[leading:]


def _block_content(text):
    _depth, _prefix, remainder = _peel_blockquotes(text)
    if remainder.startswith("\t"):
        return None
    leading = _leading_spaces(remainder)
    if leading > 3:
        return None
    return remainder[leading:]


def _rough_content(text, allow_bom=False):
    if allow_bom and text.startswith("\ufeff"):
        text = text[1:]
    _depth, _prefix, remainder = _peel_blockquotes(text)
    return remainder.lstrip(" \t")


def _after_quote_depth(text, quote_depth):
    position = 0
    for _unused in range(quote_depth):
        match = re.match(r" {0,3}>[ \t]?", text[position:])
        if match is None:
            return None
        position += match.end()
    return text[position:]


def _opening_fence(content):
    match = re.match(r"([`~])\1{2,}", content)
    if match is None:
        return None
    marker = match.group(1)
    width = match.end()
    if marker == "`" and "`" in content[width:]:
        return None
    return marker, width


def _closing_fence(content, fence):
    marker, width = fence.marker, fence.width
    if not content.startswith(marker * width):
        return False
    marker_width = _run_width(content, 0, marker)
    return marker_width >= width and not content[marker_width:].strip(" \t")


def _content_for_container(text, quote_depth, list_column):
    remainder = _after_quote_depth(text, quote_depth)
    if remainder is None or remainder.startswith("\t"):
        return None
    if list_column is not None:
        if not remainder.strip(" \t"):
            return ""
        if _leading_spaces(remainder) < list_column:
            return None
        remainder = remainder[list_column:]
    leading = _leading_spaces(remainder)
    if leading > 3 or remainder[leading:].startswith("\t"):
        return None
    return remainder[leading:]


def _line_remains_in_fence_container(text, fence):
    remainder = _after_quote_depth(text, fence.quote_depth)
    if remainder is None:
        return False
    if fence.list_column is None or not remainder.strip(" \t"):
        return True
    return not remainder.startswith("\t") and _leading_spaces(remainder) >= fence.list_column


def _opening_fence_for_line(lines, line_contexts, index):
    text = lines[index].text[1:] if index == 0 and lines[index].text.startswith("\ufeff") else lines[index].text
    quote_depth, _quote_prefix, remainder = _peel_blockquotes(text)
    list_match = _LIST_MARKER.match(remainder)
    if list_match is not None:
        opening = _opening_fence(list_match.group(4))
        if opening is not None:
            list_column = len(list_match.group(1)) + len(list_match.group(2)) + len(list_match.group(3))
            return _Fence(opening[0], opening[1], quote_depth, list_column)
    rough = _rough_content(lines[index].text, allow_bom=index == 0)
    if _opening_fence(rough) is None:
        return None
    context = _derive_context(lines, line_contexts, index)
    if context is None:
        return None
    content = _source_for_context(lines[index].text, context, allow_bom=index == 0)
    opening = None if content is None else _opening_fence(content)
    if opening is None:
        return None
    return _Fence(opening[0], opening[1], context.quote_depth, context.list_column)


def _html_start(content):
    raw = _HTML_RAW_START.match(content)
    if raw is not None:
        return "raw", re.compile(r"</" + re.escape(raw.group(1)) + r">", re.IGNORECASE)
    if content.startswith("<!--"):
        return "token", "-->"
    if content.startswith("<?"):
        return "token", "?>"
    if re.match(r"<![A-Z]", content):
        return "token", ">"
    if content.startswith("<![CDATA["):
        return "token", "]]" + ">"
    if _HTML_BLOCK_START.match(content):
        return "blank", None
    if _HTML_COMPLETE_TAG.fullmatch(content):
        return "blank", None
    return None


def _opening_html_for_line(lines, line_contexts, index):
    text = lines[index].text[1:] if index == 0 and lines[index].text.startswith("\ufeff") else lines[index].text
    quote_depth, _quote_prefix, remainder = _peel_blockquotes(text)
    list_match = _LIST_MARKER.match(remainder)
    if list_match is not None:
        content = list_match.group(4)
        opening = _html_start(content)
        if opening is not None:
            list_column = len(list_match.group(1)) + len(list_match.group(2)) + len(list_match.group(3))
            return _Html(opening[0], opening[1], quote_depth, list_column), content
    context = _derive_context(lines, line_contexts, index)
    if context is None:
        return None
    content = _source_for_context(lines[index].text, context, allow_bom=index == 0)
    opening = None if content is None else _html_start(content)
    if opening is None:
        return None
    return _Html(opening[0], opening[1], context.quote_depth, context.list_column), content


def _html_ends(html, content):
    if html.kind == "raw":
        return html.end.search(content) is not None
    if html.kind == "token":
        return html.end in content
    return False


def _protected_line_indexes(lines, line_contexts):
    protected = set()
    if lines:
        first = lines[0].text[1:] if lines[0].text.startswith("\ufeff") else lines[0].text
        if first in {"---", "+++"}:
            marker = first
            close = None
            for index in range(1, len(lines)):
                if lines[index].text == marker:
                    close = index
                    break
            final = len(lines) - 1 if close is None else close
            protected.update(range(final + 1))

    fence = None
    html = None
    for index, line in enumerate(lines):
        if index in protected:
            continue
        if fence is not None:
            if _line_remains_in_fence_container(line.text, fence):
                protected.add(index)
                content = _content_for_container(line.text, fence.quote_depth, fence.list_column)
                if content is not None and _closing_fence(content, fence):
                    fence = None
                continue
            fence = None
        if html is not None:
            active_content = _content_for_container(line.text, html.quote_depth, html.list_column)
            if active_content is None or (html.kind == "blank" and not active_content.strip(" \t")):
                html = None
            else:
                protected.add(index)
                if _html_ends(html, active_content):
                    html = None
                continue
        fence = _opening_fence_for_line(lines, line_contexts, index)
        if fence is not None:
            protected.add(index)
            continue
        html_start = _opening_html_for_line(lines, line_contexts, index)
        if html_start is not None:
            protected.add(index)
            html, content = html_start
            if _html_ends(html, content):
                html = None
    return protected


def _delimiter_alignment(cell):
    if cell.startswith(":") and cell.endswith(":"):
        return "center"
    if cell.startswith(":"):
        return "left"
    if cell.endswith(":"):
        return "right"
    return "none"


def _delimiter_is_strong(row):
    return bool(row.cells) and all(_DELIMITER_CELL.fullmatch(cell) is not None and len(cell.strip(":")) >= 3 for cell in row.cells)


def _looks_like_table_pair(first, second):
    first_row = _parse_row(first.strip(" \t"))
    second_row = _parse_row(second.strip(" \t"))
    return bool(first_row.pipe_count and second_row.cells and all(_DELIMITER_CELL.fullmatch(cell) is not None for cell in second_row.cells))


def _adjacent_strong_table(lines, index, context, protected):
    if index + 1 >= len(lines) or index in protected or index + 1 in protected:
        return False
    first_source = _source_for_context(lines[index].text, context)
    second_source = _source_for_context(lines[index + 1].text, context)
    if first_source is None or second_source is None:
        return False
    first = _parse_row(first_source)
    second = _parse_row(second_source)
    return len(first.cells) >= 2 and len(first.cells) == len(second.cells) and _delimiter_is_strong(second)


def _candidate_for(lines, start_index, context, path, protected, boundary_before_ambiguous):
    bom = start_index == 0 and lines[start_index].text.startswith("\ufeff")
    header_source = _source_for_context(lines[start_index].text, context, allow_bom=bom)
    delimiter_source = _source_for_context(lines[start_index + 1].text, context)
    if header_source is None:
        return None
    if _is_new_block(header_source):
        return None
    header = _parse_row(header_source)
    if delimiter_source is None:
        rough_delimiter = _parse_row(_rough_content(lines[start_index + 1].text))
        if header.pipe_count and rough_delimiter.cells and all(_DELIMITER_CELL.fullmatch(cell) is not None for cell in rough_delimiter.cells):
            issue = models.MarkdownTableIssue("malformed", "Delimiter row has inconsistent container ownership", lines[start_index + 1].number, path)
            return None, start_index + 2, (_IssueRecord(issue, lines[start_index + 1].start),)
        return None
    delimiter = _parse_row(delimiter_source)
    if not header.pipe_count or not delimiter.cells or not all(_DELIMITER_CELL.fullmatch(cell) is not None for cell in delimiter.cells):
        return None
    if len(header.cells) == 1 and not (header.leading_border and header.trailing_border and delimiter.leading_border and delimiter.trailing_border):
        return None
    if len(header.cells) < 2 and len(header.cells) != 1:
        return None

    issues = []
    structural_repair = header.repaired or delimiter.repaired or any(len(cell.strip(":")) < 3 for cell in delimiter.cells)
    alignments = [_delimiter_alignment(cell) for cell in delimiter.cells]
    delimiter_cells = list(delimiter.cells)
    if len(delimiter_cells) > len(header.cells):
        issues.append(
            _IssueRecord(
                models.MarkdownTableIssue("malformed", "Delimiter row has {} cells; expected {}".format(len(delimiter_cells), len(header.cells)), lines[start_index + 1].number, path),
                lines[start_index + 1].start,
            )
        )
    elif len(delimiter_cells) < len(header.cells):
        structural_repair = True
        delimiter_cells.extend("---" for _unused in range(len(header.cells) - len(delimiter_cells)))
        alignments.extend("none" for _unused in range(len(header.cells) - len(alignments)))

    parsed_rows = [header, _ParsedRow(tuple(delimiter_cells), delimiter.leading_border, delimiter.trailing_border, delimiter.repaired, delimiter.pipe_count)]
    end_index = start_index + 2
    while end_index < len(lines) and end_index not in protected:
        source = _source_for_context(lines[end_index].text, context)
        if source is not None and not source.strip(" \t"):
            break
        if _adjacent_strong_table(lines, end_index, context, protected):
            break
        if source is None:
            rough = _block_content(lines[end_index].text)
            if rough is not None and _parse_row(rough).pipe_count:
                issues.append(_IssueRecord(models.MarkdownTableIssue("malformed", "Table row has inconsistent container ownership", lines[end_index].number, path), lines[end_index].start))
                end_index += 1
                continue
            break
        if _is_new_block(source):
            break
        row = _parse_row(source)
        if not row.pipe_count:
            break
        parsed_rows.append(row)
        structural_repair = structural_repair or row.repaired
        if len(row.cells) > len(header.cells):
            issues.append(
                _IssueRecord(
                    models.MarkdownTableIssue("malformed", "Body row has {} cells; expected {}".format(len(row.cells), len(header.cells)), lines[end_index].number, path), lines[end_index].start
                )
            )
        end_index += 1

    if issues:
        return None, end_index, tuple(issues)

    normalized_cells = [tuple(header.cells), tuple(delimiter_cells)]
    for row in parsed_rows[2:]:
        cells = list(row.cells)
        if len(cells) < len(header.cells):
            cells.extend("" for _unused in range(len(header.cells) - len(cells)))
            structural_repair = True
        normalized_cells.append(tuple(cells))

    public_rows = []
    for offset, cells in enumerate(normalized_cells):
        source_line = lines[start_index + offset]
        public_rows.append(models.MarkdownTableRow(source_line.number, source_line.text, cells))
    start_offset = lines[start_index].start
    end_offset = lines[end_index - 1].end
    raw = "".join(line.text + line.ending for line in lines[start_index:end_index])
    table = models.MarkdownTable(lines[start_index].number, lines[end_index - 1].number, raw, context.container_prefix, context.indentation, public_rows, tuple(alignments))
    boundary_after_ambiguous = _ambiguous_pipe_less_row(lines, end_index, context, protected, len(header.cells))
    candidate = _Candidate(
        table,
        start_offset,
        end_offset,
        tuple(normalized_cells),
        tuple(alignments),
        structural_repair,
        context.list_column is not None,
        context.quote_prefix,
        lines[start_index].ending,
        lines[end_index - 1].ending,
        start_index,
        end_index,
        bom,
        boundary_before_ambiguous,
        boundary_after_ambiguous,
    )
    return candidate, end_index, ()


def _ambiguous_pipe_less_row(lines, end_index, context, protected, column_count):
    if column_count != 1 or end_index >= len(lines) or end_index in protected:
        return False
    source = _source_for_context(lines[end_index].text, context)
    if source is None or not source.strip(" \t") or _is_new_block(source):
        return False
    return not _parse_row(source).pipe_count


def _scan_markdown_tables(text, path=None):
    supplied_path = None if path is None else str(path)
    lines = _split_lines(text)
    line_contexts = _line_contexts(lines)
    protected = _protected_line_indexes(lines, line_contexts)
    candidates = []
    issue_records = []
    index = 0
    while index + 1 < len(lines):
        if index in protected or index + 1 in protected:
            index += 1
            continue
        first = _rough_content(lines[index].text, allow_bom=index == 0)
        second = _rough_content(lines[index + 1].text)
        if not _looks_like_table_pair(first, second):
            index += 1
            continue
        context = _derive_context(lines, line_contexts, index)
        if context is None:
            first_text = lines[index].text[1:] if index == 0 and lines[index].text.startswith("\ufeff") else lines[index].text
            _depth, _prefix, first_remainder = _peel_blockquotes(first_text)
            leading = first_remainder[: len(first_remainder) - len(first_remainder.lstrip(" \t"))]
            if " " in leading and "\t" in leading and _looks_like_table_pair(first, second):
                issue_records.append(_IssueRecord(models.MarkdownTableIssue("malformed", "Table header has mixed space/tab indentation", lines[index].number, supplied_path), lines[index].start))
                index += 2
                continue
            index += 1
            continue
        boundary_before_ambiguous = context.list_column is None and line_contexts[index].lazy_list_boundary
        candidate_result = _candidate_for(lines, index, context, supplied_path, protected, boundary_before_ambiguous)
        if candidate_result is None:
            index += 1
            continue
        candidate, next_index, issues = candidate_result
        if candidate is not None:
            candidates.append(candidate)
        issue_records.extend(issues)
        index = max(index + 1, next_index)

    issue_records.sort(key=lambda record: record.offset)
    tables = tuple(candidate.table for candidate in candidates)
    issues = tuple(record.issue for record in issue_records)
    return _ScanResult(lines, tables, tuple(candidates), issues)


def parse_markdown_tables(text):
    """Return safely parsed tables or raise for any malformed candidate."""
    scan = _scan_markdown_tables(text)
    if scan.issues:
        result = models.MarkdownTableFormatResult(text, scan.tables, (), scan.issues, changed=False)
        first = scan.issues[0]
        raise models.MarkdownTableError("Malformed Markdown table", line_number=first.line_number, issues=scan.issues, result=result)
    return scan.tables
