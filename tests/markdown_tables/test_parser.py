"""Markdown table parser tests."""

import pytest

import la_dev_codex_plugins.markdown_tables as markdown_tables
import la_dev_codex_plugins.markdown_tables.parser as markdown_parser


def test_physical_line_splitter_searches_original_text_from_absolute_offsets(monkeypatch):
    source = "one\ntwo\r\nthree\rfour"
    original = markdown_parser._LINE_ENDING
    calls = []

    class Searcher:
        def search(self, text, offset):
            calls.append((text, offset))
            return original.search(text, offset)

    monkeypatch.setattr(markdown_parser, "_LINE_ENDING", Searcher())
    lines = markdown_parser._split_lines(source)

    assert [line.text for line in lines] == ["one", "two", "three", "four"]
    assert [line.ending for line in lines] == ["\n", "\r\n", "\r", ""]
    assert [offset for _text, offset in calls] == [0, 4, 9, 15]
    assert all(text is source for text, _offset in calls)


def test_parse_returns_public_positions_raw_text_cells_and_alignments():
    source = "Intro\r\n\r\n  | A | B |\r\n  |:--|--:|\n  | x | y |"

    table = markdown_tables.parse_markdown_tables(source)[0]

    assert (table.start_line, table.end_line) == (3, 5)
    assert table.raw == "  | A | B |\r\n  |:--|--:|\n  | x | y |"
    assert table.container_prefix == ""
    assert table.indentation == "  "
    assert table.alignments == ("left", "right")
    assert table.rows[0].line_number == 3
    assert table.rows[0].raw == "  | A | B |"
    assert table.rows[0].cells == ("A", "B")


@pytest.mark.parametrize(
    "source",
    [
        "A | B\n---|---\nx | y\n",
        "| A | B\n---|---|\nx | y |\n",
        "A | B |\n|---|---\n| x | y\n",
    ],
)
def test_multi_column_tables_allow_missing_or_inconsistent_outer_borders(source):
    assert len(markdown_tables.parse_markdown_tables(source)) == 1


@pytest.mark.parametrize("source", ["A\n---\nx\n", "| A\n|---\n| x\n", "A |\n--- |\nx |\n"])
def test_one_column_tables_require_both_outer_borders(source):
    assert markdown_tables.parse_markdown_tables(source) == ()


def test_one_column_table_with_borders_is_recognized():
    table = markdown_tables.parse_markdown_tables("| A |\n|---|\n| x |\n")[0]
    assert table.rows[0].cells == ("A",)


def test_invalid_delimiter_like_prose_is_not_a_candidate():
    assert markdown_tables.parse_markdown_tables("A | B\nnot | a delimiter\n") == ()


def test_strict_parse_raises_with_all_source_ordered_malformed_issues():
    source = "| A | B |\n|---|---|---|\n\n| C | D |\n|---|---|\n| 1 | 2 | 3 |\n"

    with pytest.raises(markdown_tables.MarkdownTableError) as caught:
        markdown_tables.parse_markdown_tables(source)

    assert [issue.line_number for issue in caught.value.issues] == [2, 6]
    assert caught.value.result is not None
    assert caught.value.result.text == source


@pytest.mark.parametrize("fence", ["```", "~~~~"])
def test_fenced_content_and_unclosed_fences_are_protected(fence):
    source = "{0}\n| A | B |\n|---|---|\n| x | y |\n".format(fence)
    assert markdown_tables.parse_markdown_tables(source) == ()


def test_invalid_backtick_info_string_does_not_open_fence():
    source = "``` info `\n| A | B |\n|---|---|\n"
    assert len(markdown_tables.parse_markdown_tables(source)) == 1


@pytest.mark.parametrize(
    ("opening", "closing"),
    [
        ("<!--", "-->"),
        ("<?target", "?>"),
        ("<!DOCTYPE html", ">"),
        ("<![CDATA[", "]] >".replace(" ", "")),
        ("<script>", "</script>"),
        ("<div>", ""),
        ('<custom attr="value">', ""),
    ],
)
def test_all_commonmark_html_block_classes_protect_tables(opening, closing):
    source = opening + "\n| A | B |\n|---|---|\n| x | y |\n" + closing + "\n\n| C | D |\n|---|---|\n"
    tables = markdown_tables.parse_markdown_tables(source)
    assert len(tables) == 1
    assert tables[0].rows[0].cells == ("C", "D")


@pytest.mark.parametrize("opening", ["<!--", "<script>"])
@pytest.mark.parametrize(
    "container",
    [
        "> {opening}\n> protected\n",
        "- item\n  {opening}\n  protected\n",
        "- {opening}\n  protected\n",
        "> - item\n>   {opening}\n>   protected\n",
    ],
)
def test_unclosed_html_ends_when_its_container_ends(opening, container):
    source = container.format(opening=opening) + "| A|B |\n|-|-|\n"
    result = markdown_tables.format_markdown_tables(source)

    assert len(result.tables) == 1
    assert result.tables[0].rows[0].cells == ("A", "B")
    assert result.changed
    assert result.text.endswith("| A | B |\n|---|---|\n")


@pytest.mark.parametrize(("opening", "closing"), [("<!--", "-->"), ("<script>", "</script>")])
def test_html_terminator_inside_list_releases_following_list_table(opening, closing):
    source = "- item\n  {0}\n  protected\n  {1}\n  | A|B |\n  |-|-|\n".format(opening, closing)
    result = markdown_tables.format_markdown_tables(source)

    assert len(result.tables) == 1
    assert result.tables[0].container_prefix == "  "
    assert result.text.endswith("  | A | B |\n  |---|---|\n")


@pytest.mark.parametrize("marker", ["---", "+++"])
def test_leading_front_matter_and_unclosed_front_matter_are_protected(marker):
    closed = marker + "\ntable: |\n  A | B\n  ---|---\n" + marker + "\n\n| C | D |\n|---|---|\n"
    assert markdown_tables.parse_markdown_tables(closed)[0].rows[0].cells == ("C", "D")
    assert markdown_tables.parse_markdown_tables(marker + "\n| A | B |\n|---|---|\n") == ()


@pytest.mark.parametrize("marker", ["---", "+++"])
def test_bom_before_front_matter_is_protected(marker):
    source = "\ufeff" + marker + "\nA | B\n---|---\n" + marker + "\n\n| C | D |\n|---|---|\n"
    tables = markdown_tables.parse_markdown_tables(source)
    assert len(tables) == 1
    assert tables[0].start_line == 6


def test_bom_is_preserved_but_excluded_from_first_header_cell():
    table = markdown_tables.parse_markdown_tables("\ufeff| A | B |\n|---|---|\n")[0]
    assert table.raw.startswith("\ufeff")
    assert table.rows[0].cells == ("A", "B")


def test_repeated_blockquote_and_explicit_list_containers_are_recognized():
    quote = markdown_tables.parse_markdown_tables("> > | A | B |\n> > |---|---|\n> > | x | y |\n")[0]
    assert quote.container_prefix == "> > "

    listed = markdown_tables.parse_markdown_tables("- item\n  | A | B |\n  |---|---|\n  | x | y |\n")[0]
    assert listed.container_prefix == "  "

    nested = markdown_tables.parse_markdown_tables("- outer\n  - inner\n    | A | B |\n    |---|---|\n")[0]
    assert nested.container_prefix == "    "

    quoted_list = markdown_tables.parse_markdown_tables("> - item\n>   | A | B |\n>   |---|---|\n>   | x | y |\n")[0]
    assert quoted_list.container_prefix == ">   "


def test_lazy_or_tab_derived_list_continuation_is_not_guessed():
    assert markdown_tables.parse_markdown_tables("- item\n| A | B |\n|---|---|\n") != ()
    assert markdown_tables.parse_markdown_tables("- item\n\t| A | B |\n\t|---|---|\n") == ()


@pytest.mark.parametrize("header", ["- | A | B |", "+ | A | B |", "1. | A | B |", "# | A | B |", "###### | A | B |"])
def test_same_line_list_markers_and_atx_headings_are_not_table_headers(header):
    source = header + "\n  |---|---|\n"
    assert markdown_tables.parse_markdown_tables(source) == ()
    assert markdown_tables.normalize_markdown_tables(source) == source


def test_four_space_and_tab_indented_top_level_tables_are_code():
    assert markdown_tables.parse_markdown_tables("    | A | B |\n    |---|---|\n") == ()
    assert markdown_tables.parse_markdown_tables("\t| A | B |\n\t|---|---|\n") == ()


def test_mixed_space_tab_header_and_inconsistent_container_are_malformed():
    with pytest.raises(markdown_tables.MarkdownTableError, match="Malformed") as mixed:
        markdown_tables.parse_markdown_tables(" \t| A | B |\n \t|---|---|\n")
    assert mixed.value.issues[0].message == "Table header has mixed space/tab indentation"

    with pytest.raises(markdown_tables.MarkdownTableError, match="Malformed") as container:
        markdown_tables.parse_markdown_tables("> | A | B |\n|---|---|\n")
    assert container.value.issues[0].message == "Delimiter row has inconsistent container ownership"


def test_body_stops_before_bare_prose_or_new_block_structure():
    source = "| A | B |\n|---|---|\n| x | y |\nprose\n# Heading | still heading\n"
    table = markdown_tables.parse_markdown_tables(source)[0]
    assert table.end_line == 3


def test_odd_and_even_backslash_runs_control_structural_pipes():
    escaped = markdown_tables.parse_markdown_tables("| A | B |\n|---|---|\n| x\\|y | z |\n")[0]
    assert escaped.rows[2].cells == ("x\\|y", "z")

    with pytest.raises(markdown_tables.MarkdownTableError):
        markdown_tables.parse_markdown_tables("| A | B |\n|---|---|\n| x\\\\|y | z |\n")


def test_commonmark_fence_width_and_closing_rules_protect_only_the_fenced_region():
    source = "```` info\n| A | B |\n|---|---|\n```\n| still | fenced |\n````   \n\n| C | D |\n|---|---|\n"
    tables = markdown_tables.parse_markdown_tables(source)
    assert len(tables) == 1
    assert tables[0].rows[0].cells == ("C", "D")


@pytest.mark.parametrize("fence", ["```", "~~~~"])
def test_explicit_list_fences_use_list_relative_indentation(fence):
    sources = (
        "- item\n    {0}\n    | A|B |\n    |-|-|\n    {0}\n".format(fence),
        "- {0}\n  | A|B |\n  |-|-|\n  {0}\n".format(fence),
    )
    for source in sources:
        assert markdown_tables.parse_markdown_tables(source) == ()
        assert markdown_tables.normalize_markdown_tables(source) == source


def test_fence_closers_must_belong_to_the_opening_container():
    source = "> ```\n> quoted code\n```\n| A|B |\n|-|-|\n"
    assert markdown_tables.parse_markdown_tables(source) == ()
    assert markdown_tables.normalize_markdown_tables(source) == source


@pytest.mark.parametrize(
    "source",
    [
        "```\n> |a|b|\n> |-|-|\n```\n",
        "> ```\n> > |a|b|\n> > |-|-|\n> ```\n",
        "- ```\n  > |a|b|\n  > |-|-|\n  ```\n",
    ],
)
def test_fences_preserve_literal_extra_blockquote_markers(source):
    assert markdown_tables.parse_markdown_tables(source) == ()
    assert markdown_tables.normalize_markdown_tables(source) == source


def test_list_context_discovery_is_linear_for_many_tables(monkeypatch):
    calls = []
    original = markdown_parser._peel_blockquotes

    def record(text):
        calls.append(text)
        return original(text)

    monkeypatch.setattr(markdown_parser, "_peel_blockquotes", record)
    table_count = 1000
    source = "ordinary prose\n\n" + "\nordinary prose\n\n".join("| A | B |\n|---|---|\n| x | y |" for _unused in range(table_count)) + "\n"

    assert len(markdown_tables.parse_markdown_tables(source)) == table_count
    assert len(calls) < 20 * len(source.splitlines())


def test_table_model_alignment_cardinality_and_raw_line_endings_are_exact():
    source = "| A | B |\r\n|:--|--:|\r| x | y |"
    table = markdown_tables.parse_markdown_tables(source)[0]
    assert len(table.alignments) == len(table.rows[0].cells) == 2
    assert table.alignments == ("left", "right")
    assert table.raw == source
    assert (table.start_line, table.end_line) == (1, 3)
