"""Canonical Markdown table formatter tests."""

import pytest

import la_dev_codex_plugins.markdown_tables as markdown_tables
import la_dev_codex_plugins.markdown_tables.formatter as markdown_formatter

# Representative fixtures adapted from pallgeuer/pydocformatter's current tools/fix_markdown_tables.py and tests/test_markdown_tables.py behavior.
PYDOCFORMATTER_CASES = (
    (
        "| Name  | Value |\n|-------|-------|\n| one   | two   |\n",
        "| Name | Value |\n|------|-------|\n| one  | two   |\n",
    ),
    (
        "  | Name  | Value |\n|-------|-------|\n   | one   | two   |\n",
        "  | Name | Value |\n  |------|-------|\n  | one  | two   |\n",
    ),
)

# Static fixtures adapted from the GFM table-extension examples at https://github.github.com/gfm/#tables-extension-.
GFM_CASES = (
    (
        "| foo | bar |\n| --- | --- |\n| baz | bim |\n",
        "| foo | bar |\n|-----|-----|\n| baz | bim |\n",
    ),
    (
        "foo | bar\n--- | ---\nbaz | bim\n",
        "| foo | bar |\n|-----|-----|\n| baz | bim |\n",
    ),
    (
        "| f\\|oo | b `\\|` az |\n| --- | --- |\n| bim | baz |\n",
        "| f\\|oo | b `\\|` az |\n|-------|-----------|\n| bim   | baz       |\n",
    ),
)

# PyCharm documents fully bordered pipe tables with source-aligned columns; this fixture locks in that presentation.
PYCHARM_CASE = (
    "| Header 1 | Header 2 |\n|----------|----------|\n| Cell 1 | Cell 2 |\n",
    "| Header 1 | Header 2 |\n|----------|----------|\n| Cell 1   | Cell 2   |\n",
)


@pytest.mark.parametrize(("source", "expected"), PYDOCFORMATTER_CASES)
def test_attributed_pydocformatter_style_fixtures(source, expected):
    assert markdown_tables.normalize_markdown_tables(source) == expected


@pytest.mark.parametrize(("source", "expected"), GFM_CASES)
def test_attributed_gfm_table_extension_fixtures(source, expected):
    assert markdown_tables.normalize_markdown_tables(source) == expected


def test_documented_pycharm_style_fixture():
    assert markdown_tables.normalize_markdown_tables(PYCHARM_CASE[0]) == PYCHARM_CASE[1]


def test_gfm_cardinality_and_termination_cases_follow_documented_safe_subset():
    short = markdown_tables.format_markdown_tables("| A | B |\n|---|---|\n| x |\n")
    assert short.text == "| A | B |\n|---|---|\n| x |   |\n"
    assert short.issues == ()

    excess_source = "| A | B |\n|---|---|\n| x | y | z |\n"
    excess = markdown_tables.format_markdown_tables(excess_source)
    assert excess.text == excess_source
    assert excess.issues[0].line_number == 3

    mismatch_source = "| A | B |\n|---|---|---|\n"
    mismatch = markdown_tables.format_markdown_tables(mismatch_source)
    assert mismatch.text == mismatch_source
    assert mismatch.issues[0].line_number == 2

    terminated = markdown_tables.format_markdown_tables("| A | B |\n|---|---|\n| x | y |\nafter\n")
    assert terminated.tables[0].end_line == 3
    assert terminated.text.endswith("\nafter\n")


def test_all_alignments_apply_to_header_and_body_with_odd_center_padding_after():
    source = "| Default | Left | Center | Right |\n|---|:---|:---:|---:|\n| a | bb | c | d |\n"
    expected = "| Default | Left | Center | Right |\n|---------|:-----|:------:|------:|\n| a       | bb   |   c    |     d |\n"
    assert markdown_tables.normalize_markdown_tables(source) == expected


def test_short_aligned_columns_expand_for_three_dashes_and_colons():
    source = "| a | b | c | d |\n|-|:-|:-:|-:|\n"
    expected = "| a | b  |  c  |  d |\n|---|:---|:---:|---:|\n"
    assert markdown_tables.normalize_markdown_tables(source) == expected


def test_safe_repairs_add_borders_delimiters_and_trailing_body_cells():
    source = "A | B | C\n-|--\nx | y\n"
    result = markdown_tables.format_markdown_tables(source)
    assert result.text == "| A | B | C |\n|---|---|---|\n| x | y |   |\n"
    assert result.changes[0].kind == "repair"
    assert not result.has_errors


def test_unescaped_pipes_inside_backticks_remain_structural():
    source = "| A | B | C |\n|---|---|---|\n| `x | y` | z |\n"
    result = markdown_tables.format_markdown_tables(source)

    assert result.text == "| A  | B  | C |\n|----|----|---|\n| `x | y` | z |\n"
    assert result.tables[0].rows[2].cells == ("`x", "y`", "z")
    assert "\\|" not in result.text


def test_escaped_pipes_inside_backticks_remain_cell_content():
    source = "| A | B |\n|---|---|\n| `x \\| y` | value |\n"
    result = markdown_tables.format_markdown_tables(source)

    assert result.text == "| A        | B     |\n|----------|-------|\n| `x \\| y` | value |\n"
    assert result.tables[0].rows[2].cells == ("`x \\| y`", "value")


def test_backtick_run_width_and_backslashes_do_not_hide_structural_pipes():
    source = "| A | B | C |\n|---|---|---|\n| ``x ` y | z`` | value |\n| \\`x | y\\` | z |\n| `x | y\\` | z |\n"
    result = markdown_tables.format_markdown_tables(source)

    assert result.issues == ()
    assert result.tables[0].rows[2].cells == ("``x ` y", "z``", "value")
    assert result.tables[0].rows[3].cells == ("\\`x", "y\\`", "z")
    assert result.tables[0].rows[4].cells == ("`x", "y\\`", "z")


def test_malformed_table_is_preserved_while_later_safe_table_changes():
    source = "| A | B |\n|---|---|\n| 1 | 2 | 3 |\n\n| C|D |\n|---|---|\n|x|y|\n"
    result = markdown_tables.format_markdown_tables(source, path="doc.md")
    assert result.text.startswith("| A | B |\n|---|---|\n| 1 | 2 | 3 |")
    assert "| C | D |\n|---|---|\n| x | y |" in result.text
    assert [(issue.kind, issue.line_number, issue.path) for issue in result.issues] == [("malformed", 3, "doc.md")]
    assert result.changed
    assert result.has_errors


def test_strict_normalization_raises_with_partial_format_result():
    source = "| A | B |\n|---|---|\n| 1 | 2 | 3 |\n\n| C|D |\n|---|---|\n"
    with pytest.raises(markdown_tables.MarkdownTableError) as caught:
        markdown_tables.normalize_markdown_tables(source)
    assert caught.value.result is not None
    assert caught.value.result.changed
    assert caught.value.result.text != source


def test_adjacent_strong_tables_split_with_one_boundary_but_weak_rows_remain_data():
    strong = "|A|B|\n|---|---|\n|x|y|\n|C|D|\n|---|---|\n|p|q|\n"
    formatted = markdown_tables.format_markdown_tables(strong)
    assert "| x | y |\n\n| C | D |" in formatted.text
    assert [change.kind for change in formatted.changes].count("boundary") == 1

    weak = "| A | B |\n|---|---|\n| C | D |\n| - | - |\n"
    assert len(markdown_tables.format_markdown_tables(weak).tables) == 1

    one_column = "| A |\n|---|\n| x |\n| B |\n|---|\n| y |\n"
    one_column_result = markdown_tables.format_markdown_tables(one_column)
    assert len(one_column_result.tables) == 1
    assert one_column_result.tables[0].end_line == 6

    separated = "| A | B |\n|---|---|\n\n| C | D |\n|---|---|\n"
    separated_result = markdown_tables.format_markdown_tables(separated)
    assert len(separated_result.tables) == 2
    assert all(change.kind != "boundary" for change in separated_result.changes)


def test_top_level_and_blockquote_boundaries_are_inserted_but_list_spacing_is_untouched():
    top = markdown_tables.normalize_markdown_tables("before\n| A | B |\n|---|---|\nafter\n")
    assert top == "before\n\n| A | B |\n|---|---|\n\nafter\n"

    quote = markdown_tables.normalize_markdown_tables("> before\n> | A | B |\n> |---|---|\n> after\n")
    assert quote == "> before\n>\n> | A | B |\n> |---|---|\n>\n> after\n"

    listed = "- item\n  | A|B |\n  |---|---|\n  |x|y|\nnext\n"
    assert markdown_tables.normalize_markdown_tables(listed) == "- item\n  | A | B |\n  |---|---|\n  | x | y |\nnext\n"


@pytest.mark.parametrize("prefix", ["- item\n", "- item\nlazy continuation\n", "> - item\n> lazy continuation\n"])
def test_possible_lazy_list_blocks_do_not_gain_a_pre_table_boundary(prefix):
    quote = "> " if prefix.startswith(">") else ""
    source = prefix + quote + "| A|B |\n" + quote + "|-|-|\n"
    expected = prefix + quote + "| A | B |\n" + quote + "|---|---|\n"
    assert markdown_tables.normalize_markdown_tables(source) == expected


def test_pipe_less_one_column_row_makes_post_table_boundary_ambiguous():
    source = "before\n| A|\n|-|\nbody without pipes\n"
    expected = "before\n\n| A |\n|---|\nbody without pipes\n"
    assert markdown_tables.normalize_markdown_tables(source) == expected


def test_boundary_changes_expose_position_and_drive_diagnostic_ordering():
    result = markdown_tables.format_markdown_tables("before\n| A|B |\n|-|-|\nafter\n")
    assert [change.boundary_position for change in result.changes] == ["before", None, "after"]
    assert markdown_tables.MarkdownTableChange("style", "wording", 1, "doc.md").boundary_position is None

    changes = (
        markdown_tables.MarkdownTableChange("style", "style wording", 2, "doc.md"),
        markdown_tables.MarkdownTableChange("boundary", "unrelated wording", 2, "doc.md", "before"),
    )
    synthetic = markdown_tables.MarkdownTableFormatResult("", changes=changes)
    assert [issue.message for issue in markdown_formatter._ordered_result_issues(synthetic)] == ["unrelated wording", "style wording"]


def test_existing_blank_counts_document_edges_and_final_newline_are_preserved():
    source = "| A|B |\r\n|-|-|\n\n\ntext\r| C|D |\r|---|---|"
    formatted = markdown_tables.normalize_markdown_tables(source)
    assert formatted.startswith("| A | B |\r\n|---|---|\n\n\ntext\r\r| C | D |\r|---|---|")
    assert not formatted.endswith(("\n", "\r"))


def test_bom_and_mixed_physical_line_endings_are_preserved():
    source = "\ufeff| A|B |\r\n|-|-|\n|x|y|\r"
    assert markdown_tables.normalize_markdown_tables(source) == "\ufeff| A | B |\r\n|---|---|\n| x | y |\r"


def test_non_ascii_edge_whitespace_and_code_point_width_are_preserved():
    source = "| A | B |\n|---|---|\n| \u00a0x\u00a0 | \u754c |\n"
    result = markdown_tables.normalize_markdown_tables(source)
    assert "\u00a0x\u00a0" in result
    assert "\u754c" in result
    assert markdown_tables.normalize_markdown_tables(result) == result


def test_internal_tabs_and_unicode_sequences_use_unnormalized_code_point_width():
    values = ("a\tb", "e\u0301", "x\ufe0f", "a\u200db", "\U0001f469\u200d\U0001f4bb", "\uff21")
    source = "| Value | Other |\n|---|---|\n" + "".join("| {} | x |\n".format(value) for value in values)
    result = markdown_tables.normalize_markdown_tables(source)
    for value in values:
        assert value in result
    assert markdown_tables.normalize_markdown_tables(result) == result


def test_inserted_boundaries_use_neighboring_local_line_endings():
    source = "before\r\n| A | B |\r\n|---|---|\r\nafter\n"
    assert markdown_tables.normalize_markdown_tables(source) == "before\r\n\r\n| A | B |\r\n|---|---|\r\n\r\nafter\n"


@pytest.mark.parametrize(("preceding_ending", "table_ending"), [("\r", "\n"), ("\r", "\r\n"), ("\n", "\r"), ("\r\n", "\n")])
def test_inserted_pre_table_boundary_duplicates_preceding_ending_in_one_pass(preceding_ending, table_ending):
    source = "before" + preceding_ending + "| A | B |" + table_ending + "|---|---|" + table_ending
    formatted = markdown_tables.normalize_markdown_tables(source)

    assert formatted.startswith("before" + preceding_ending + preceding_ending + "| A | B |")
    assert markdown_tables.normalize_markdown_tables(formatted) == formatted


def test_markdown_table_issues_combines_format_and_malformed_diagnostics():
    source = "| A|B |\n|---|---|\n\n| C | D |\n|---|---|\n| 1 | 2 | 3 |\n"
    issues = markdown_tables.markdown_table_issues(source, path="memory.md")
    assert [(issue.kind, issue.line_number, issue.path) for issue in issues] == [("format", 1, "memory.md"), ("malformed", 6, "memory.md")]


def test_result_collections_are_immutable_and_changed_is_exact_text_difference():
    result = markdown_tables.format_markdown_tables("plain\n")
    assert not result.changed
    assert result.tables == result.changes == result.issues == ()
    with pytest.raises(AttributeError):
        result.text = "changed"


def test_result_changed_state_participates_in_representation_equality_and_hashing():
    unchanged = markdown_tables.MarkdownTableFormatResult("text")
    changed = markdown_tables.MarkdownTableFormatResult("text", changed=True)

    assert unchanged.changed is False
    assert changed.changed is True
    assert unchanged != changed
    assert hash(unchanged) != hash(changed)
    assert "changed=False" in repr(unchanged)
    assert "changed=True" in repr(changed)
    for invalid in (None, 0, 1, "yes"):
        with pytest.raises(TypeError, match="changed must be a Boolean"):
            markdown_tables.MarkdownTableFormatResult("text", changed=invalid)
