"""Prompt inspection, literal substitution, and qualification tests."""

import pytest

from conftest import runtime


def make_catalog(tmp_path, complete, file_data, write_file, load_catalog, **action_updates):
    """Create and load one temporary complete action."""
    source = tmp_path / "source"
    write_file(source, file_data(actions={"test": {"agnostic": complete(**action_updates)}}))
    return load_catalog(source), source


def test_no_variables_and_no_qualification(tmp_path, complete, file_data, write_file, load_catalog):
    catalog, _source = make_catalog(tmp_path, complete, file_data, write_file, load_catalog)
    rendered = catalog.render("test[agnostic]", {})
    assert rendered.prompt == "Perform the test action."
    assert rendered.qualification is None


def test_one_multiple_and_repeated_variables(tmp_path, complete, file_data, write_file, load_catalog):
    catalog, _source = make_catalog(
        tmp_path,
        complete,
        file_data,
        write_file,
        load_catalog,
        prompt_vars={"%Input%": "Input", "%Kind%": "Kind"},
        prompt="Read %Input%, make %Kind%, cite %Input%.",
    )
    rendered = catalog.render("test[agnostic]", {"%Input%": "a b.txt", "%Kind%": "a report"})
    assert rendered.prompt == "Read a b.txt, make a report, cite a b.txt."


@pytest.mark.parametrize(
    "value",
    [
        "spaces and = equals",
        "quotes ' \" and percent %",
        "`backticks` $(touch /tmp/never) ; $HOME",
        "backslash \\\\ path",
        "Unicode \u03bb",
        "embedded\nnewline",
    ],
)
def test_complex_binding_values_remain_literal_data(tmp_path, complete, file_data, write_file, load_catalog, value):
    catalog, _source = make_catalog(tmp_path, complete, file_data, write_file, load_catalog, prompt_vars={"%Value%": "Value"}, prompt="Value=%Value%")
    assert catalog.render("test[agnostic]", {"%Value%": value}).prompt == "Value=" + value


def test_substitution_is_one_pass_and_does_not_expand_introduced_placeholder(tmp_path, complete, file_data, write_file, load_catalog):
    catalog, _source = make_catalog(
        tmp_path,
        complete,
        file_data,
        write_file,
        load_catalog,
        prompt_vars={"%A%": "A", "%B%": "B"},
        prompt="%A% then %B%",
    )
    rendered = catalog.render("test[agnostic]", {"%A%": "%B%", "%B%": "done"})
    assert rendered.prompt == "%B% then done"


@pytest.mark.parametrize(
    ("variables", "status"),
    [
        ({}, "missing_variables"),
        ({"%X%": "x", "%Extra%": "extra"}, "extra_variables"),
        ({"%X%": ""}, "invalid_variable_value"),
        ({"%X%": 1}, "invalid_variable_value"),
    ],
)
def test_missing_extra_and_invalid_bindings(tmp_path, complete, file_data, write_file, load_catalog, variables, status):
    catalog, _source = make_catalog(tmp_path, complete, file_data, write_file, load_catalog, prompt_vars={"%X%": "X"}, prompt="Use %X%.")
    with pytest.raises(runtime.CatalogRequestError, match="variable") as error:
        catalog.render("test[agnostic]", variables)
    assert error.value.status == status


def test_no_edits_prefix_is_shared_by_inspection_and_rendering(tmp_path, complete, file_data, write_file, load_catalog):
    catalog, _source = make_catalog(tmp_path, complete, file_data, write_file, load_catalog, no_edits=True, prompt="Inspect this.")
    inspection = catalog.inspect("test[agnostic]")
    assert inspection.base_prompt == "No edits. Inspect this."
    assert catalog.render("test[agnostic]", {}).prompt == inspection.base_prompt


def test_no_prefix_when_no_edits_is_false(tmp_path, complete, file_data, write_file, load_catalog):
    catalog, _source = make_catalog(tmp_path, complete, file_data, write_file, load_catalog, no_edits=False, prompt="Edit this.")
    assert catalog.inspect("test[agnostic]").base_prompt == "Edit this."


def test_qualification_is_trimmed_and_appended_with_exact_structure(tmp_path, complete, file_data, write_file, load_catalog):
    catalog, _source = make_catalog(tmp_path, complete, file_data, write_file, load_catalog)
    rendered = catalog.render("test[agnostic]", {}, qualification="  Restrict the scope.  ")
    assert rendered.qualification == "Restrict the scope."
    assert rendered.prompt == "Perform the test action.\n\nBUT: Restrict the scope."


@pytest.mark.parametrize("qualification", ["BUT: Restrict the scope.", "  BUT:Restrict the scope.  "])
def test_qualification_but_prefix_is_silently_normalized(tmp_path, complete, file_data, write_file, load_catalog, qualification):
    catalog, _source = make_catalog(tmp_path, complete, file_data, write_file, load_catalog)
    rendered = catalog.render("test[agnostic]", {}, qualification=qualification)
    assert rendered.qualification == "Restrict the scope."
    assert rendered.prompt == "Perform the test action.\n\nBUT: Restrict the scope."


@pytest.mark.parametrize("qualification", ["", "   ", "line one\nline two", "line\rbreak", "\x00control", "\x1fcontrol", "BUT:", "  BUT:  ", 1])
def test_invalid_qualification_structure_is_rejected(tmp_path, complete, file_data, write_file, load_catalog, qualification):
    catalog, _source = make_catalog(tmp_path, complete, file_data, write_file, load_catalog)
    with pytest.raises(runtime.CatalogRequestError) as error:
        catalog.render("test[agnostic]", {}, qualification=qualification)
    assert error.value.status == "invalid_qualification"


def test_qualification_placeholder_text_is_literal_and_notes_never_enter_prompt(tmp_path, complete, file_data, write_file, load_catalog):
    catalog, _source = make_catalog(tmp_path, complete, file_data, write_file, load_catalog, prompt_vars={"%X%": "X"}, prompt="Use %X%.", notes="Follow-up %X%.")
    rendered = catalog.render("test[agnostic]", {"%X%": "value"}, qualification="Keep %X% literal.")
    assert rendered.prompt == "Use value.\n\nBUT: Keep %X% literal."
    assert "Follow-up" not in rendered.prompt
    assert rendered.to_dict()["notes"] == "Follow-up %X%."


def test_goal_mode_final_prompt_includes_every_rendering_transformation(tmp_path, complete, file_data, write_file, load_catalog):
    catalog, _source = make_catalog(
        tmp_path,
        complete,
        file_data,
        write_file,
        load_catalog,
        goal_mode=True,
        no_edits=True,
        prompt_vars={"%Target%": "Target"},
        prompt="Inspect %Target%.",
        notes="Keep this separate.",
    )
    inspection = catalog.inspect("test[agnostic]")
    rendered = catalog.render(
        "test[agnostic]",
        {"%Target%": "src/"},
        qualification="Only report confirmed findings.",
    )
    assert inspection.to_dict()["goal_mode"] is True
    assert rendered.prompt == "No edits. Inspect src/.\n\nBUT: Only report confirmed findings."
    assert "Keep this separate." not in rendered.prompt


def test_unrelated_diagnostics_never_enter_inspection_or_rendered_prompt(tmp_path, complete, file_data, write_file, load_catalog):
    source = tmp_path / "source"
    bad = complete()
    bad["unknown"] = True
    write_file(source, file_data(actions={"good": {"agnostic": complete()}, "bad": {"agnostic": bad}}))
    catalog = load_catalog(source)
    inspection = catalog.inspect("good[agnostic]")
    rendered = catalog.render("good[agnostic]", {})
    assert catalog.diagnostics
    assert "unknown_action_field" not in inspection.base_prompt
    assert "unknown_action_field" not in rendered.prompt
