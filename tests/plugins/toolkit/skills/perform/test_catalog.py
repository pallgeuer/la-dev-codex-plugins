"""Catalog schema, validation, diagnostics, and isolation tests."""

import json

import pytest

from conftest import runtime


def selectors(catalog, name=None):
    """Return canonical selectors from one catalog listing."""
    return [summary.selector for summary in catalog.list_actions(name=name)]


def diagnostic_codes(catalog):
    """Return stable diagnostic codes from one catalog."""
    return [diagnostic.code for diagnostic in catalog.diagnostics]


def test_complete_agnostic_and_complete_language_only(tmp_path, complete, file_data, write_file, load_catalog):
    actions = {
        "general": {"agnostic": complete(gloss="General")},
        "language-only": {"python": complete(gloss="Python only", prompt="Check Python.")},
    }
    source = tmp_path / "source"
    write_file(source, file_data(actions=actions))
    catalog = load_catalog(source)
    assert selectors(catalog) == ["general[agnostic]", "help[agnostic]", "language-only[python]"]
    assert catalog.inspect("language-only[python]").action.fields["gloss"] == "Python only"
    assert catalog.diagnostics == []


def test_empty_root_actions_is_valid_but_empty_language_object_is_not(tmp_path, file_data, write_file, load_catalog):
    source = tmp_path / "source"
    write_file(source, file_data(actions={"empty": {}}))
    catalog = load_catalog(source)
    assert selectors(catalog) == ["help[agnostic]"]
    assert "invalid_action_languages" in diagnostic_codes(catalog)


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("[]", "invalid_root"),
        ('{"version": true, "actions": {}}', "invalid_version"),
        ('{"version": 2, "actions": {}}', "unsupported_version"),
        ('{"version": 1}', "invalid_actions_root"),
        ('{"version": 1, "actions": [], "ignore_actions": []}', "invalid_actions_root"),
        ('{"version": 1, "actions": {}, "ignore_actions": {}}', "invalid_ignore_actions"),
        ('{"version": 1, "actions": {}, "ignore_action": []}', "unknown_root_field"),
    ],
)
def test_file_fatal_root_validation(tmp_path, write_raw, load_catalog, text, code):
    source = tmp_path / code
    write_raw(source, text)
    catalog = load_catalog(source)
    assert selectors(catalog) == ["help[agnostic]"]
    assert diagnostic_codes(catalog) == [code]
    assert catalog.diagnostics[0].fatality == "file_fatal"


@pytest.mark.parametrize(
    "text",
    [
        '{"version": 1, "version": 1, "actions": {}}',
        '{"version": 1, "actions": {"test": {}, "test": {}}}',
        '{"version": 1, "actions": {"test": {"agnostic": {}, "agnostic": {}}}}',
        '{"version": 1, "actions": {"test": {"agnostic": {"prompt_vars": {"%X%": "one", "%X%": "two"}}}}}',
    ],
)
def test_duplicate_keys_at_every_object_depth_are_file_fatal(tmp_path, write_raw, load_catalog, text):
    source = tmp_path / "duplicate"
    write_raw(source, text)
    catalog = load_catalog(source)
    assert diagnostic_codes(catalog) == ["duplicate_key"]
    assert catalog.diagnostics[0].fatality == "file_fatal"


@pytest.mark.parametrize("action_name", ["UPPER", "-leading", "space name", "bad[name]", "comma,name", "caf\u00e9"])
def test_invalid_action_names_are_isolated(tmp_path, complete, file_data, write_file, load_catalog, action_name):
    source = tmp_path / "source"
    write_file(source, file_data(actions={action_name: {"agnostic": complete()}, "valid": {"agnostic": complete()}}))
    catalog = load_catalog(source)
    assert selectors(catalog) == ["help[agnostic]", "valid[agnostic]"]
    assert "invalid_action_name" in diagnostic_codes(catalog)


@pytest.mark.parametrize("language", ["UPPER", ".leading", "space name", "json,yaml", "bad[lang]", "caf\u00e9"])
def test_invalid_language_names_are_isolated(tmp_path, complete, file_data, write_file, load_catalog, language):
    source = tmp_path / "source"
    write_file(source, file_data(actions={"test": {language: complete(), "python": complete()}}))
    catalog = load_catalog(source)
    assert selectors(catalog, "test") == ["test[python]"]
    assert "invalid_language_name" in diagnostic_codes(catalog)


def test_reserved_help_definition_and_ignore_do_not_affect_builtin(tmp_path, complete, file_data, write_file, load_catalog):
    source = tmp_path / "source"
    write_file(source, file_data(actions={"help": {"agnostic": complete(gloss="Mutable")}}, ignore_actions=["help", "help[agnostic]"]))
    catalog = load_catalog(source)
    help_summary = catalog.list_actions(name="help")
    assert len(help_summary) == 1
    assert help_summary[0].built_in is True
    assert help_summary[0].gloss == runtime.HELP_GLOSS
    assert sorted(diagnostic_codes(catalog)) == ["reserved_help_definition", "reserved_help_ignore", "reserved_help_ignore"]


def test_unknown_action_field_is_variant_local_and_unknown_root_is_file_fatal(tmp_path, complete, file_data, write_file, load_catalog):
    source = tmp_path / "source"
    invalid_variant = complete()
    invalid_variant["promt"] = invalid_variant.pop("prompt")
    write_file(source, file_data(actions={"bad": {"agnostic": invalid_variant}, "good": {"agnostic": complete()}}), "10-variants.json")
    root = file_data(actions={"lost": {"agnostic": complete()}})
    root["typo"] = True
    write_file(source, root, "20-root.json")
    catalog = load_catalog(source)
    assert selectors(catalog) == ["good[agnostic]", "help[agnostic]"]
    by_code = {diagnostic.code: diagnostic for diagnostic in catalog.diagnostics}
    assert by_code["unknown_action_field"].fatality == "variant_fatal"
    assert by_code["unknown_root_field"].fatality == "file_fatal"


@pytest.mark.parametrize(
    ("field", "bad_value", "expected_code"),
    [
        ("gloss", 1, "invalid_gloss"),
        ("model", 1, "invalid_model"),
        ("reasoning_effort", 1, "invalid_effort"),
        ("goal_mode", 0, "invalid_boolean"),
        ("plan_mode", 0, "invalid_boolean"),
        ("plan_reasoning_effort", 1, "invalid_effort"),
        ("no_edits", 0, "invalid_boolean"),
        ("prompt_vars", [], "invalid_prompt_vars"),
        ("prompt", 1, "invalid_prompt"),
        ("prefer_interactive", 1, "invalid_boolean"),
        ("custom_codex_args", ["ok", 1], "invalid_custom_codex_args"),
        ("notes", 1, "invalid_notes"),
    ],
)
def test_each_action_field_rejects_wrong_type(tmp_path, complete, file_data, write_file, load_catalog, field, bad_value, expected_code):
    source = tmp_path / field
    action = complete()
    action[field] = bad_value
    write_file(source, file_data(actions={"test": {"agnostic": action}}))
    catalog = load_catalog(source)
    assert selectors(catalog, "test") == []
    assert expected_code in diagnostic_codes(catalog)


@pytest.mark.parametrize("model", ["default", "gpt-5", "gpt_5.1", "gpt:5+fast/max", "A0"])
def test_model_identifier_accepts_exact_ascii_grammar(tmp_path, complete, file_data, write_file, load_catalog, model):
    source = tmp_path / "accepted"
    write_file(source, file_data(actions={"test": {"agnostic": complete(model=model)}}))
    assert selectors(load_catalog(source), "test") == ["test[agnostic]"]


@pytest.mark.parametrize("model", ["", " gpt-5", "gpt-5 ", "-gpt", "gpt 5", "gpt\n", "gpt\x00", "m\u00f6del"])
def test_model_identifier_rejects_whitespace_control_and_non_ascii(tmp_path, complete, file_data, write_file, load_catalog, model):
    source = tmp_path / "rejected"
    write_file(source, file_data(actions={"test": {"agnostic": complete(model=model)}}))
    catalog = load_catalog(source)
    assert selectors(catalog, "test") == []
    assert "invalid_model" in diagnostic_codes(catalog)


@pytest.mark.parametrize("bad_args", [[""], ["has\x00nul"]])
def test_custom_codex_arguments_reject_empty_and_nul_entries(tmp_path, complete, file_data, write_file, load_catalog, bad_args):
    source = tmp_path / "source"
    write_file(source, file_data(actions={"test": {"agnostic": complete(custom_codex_args=bad_args)}}))
    catalog = load_catalog(source)
    assert selectors(catalog, "test") == []
    assert "invalid_custom_codex_args" in diagnostic_codes(catalog)


@pytest.mark.parametrize(
    "conflicting_args",
    [
        ["-m", "gpt-5"],
        ["-mgpt-5"],
        ["-m=gpt-5"],
        ["--model", "gpt-5"],
        ["--model=gpt-5"],
        ["-c", 'model="gpt-5"'],
        ['-cmodel="gpt-5"'],
        ['-c=model="gpt-5"'],
        ["--config", 'model_reasoning_effort="high"'],
        ['--config=plan_mode_reasoning_effort="high"'],
        ["--config", "model.provider=openai"],
    ],
)
def test_custom_codex_arguments_reject_structured_policy_overrides(tmp_path, complete, file_data, write_file, load_catalog, conflicting_args):
    source = tmp_path / "source"
    write_file(source, file_data(actions={"test": {"agnostic": complete(custom_codex_args=conflicting_args)}}))
    catalog = load_catalog(source)
    assert selectors(catalog, "test") == []
    assert "conflicting_custom_codex_args" in diagnostic_codes(catalog)


@pytest.mark.parametrize("malformed_args", [["-c"], ["--config"], ["-cnot-an-assignment"], ["--config=missing-assignment"], ["--config", "=value"]])
def test_custom_codex_arguments_reject_malformed_config_overrides(tmp_path, complete, file_data, write_file, load_catalog, malformed_args):
    source = tmp_path / "source"
    write_file(source, file_data(actions={"test": {"agnostic": complete(custom_codex_args=malformed_args)}}))
    catalog = load_catalog(source)
    assert selectors(catalog, "test") == []
    assert "invalid_custom_codex_args" in diagnostic_codes(catalog)


@pytest.mark.parametrize(
    "custom_args",
    [
        ["--search"],
        ["-c", 'sandbox_mode="read-only"'],
        ["-cfeatures.example=true"],
        ['--config=shell_environment_policy.inherit="all"'],
    ],
)
def test_custom_codex_arguments_allow_unrelated_nonempty_arguments(tmp_path, complete, file_data, write_file, load_catalog, custom_args):
    source = tmp_path / "source"
    write_file(source, file_data(actions={"test": {"agnostic": complete(custom_codex_args=custom_args)}}))
    catalog = load_catalog(source)
    assert selectors(catalog, "test") == ["test[agnostic]"]
    assert catalog.diagnostics == []


@pytest.mark.parametrize("bad_text", ["two\nlines", "has\ttab", "has\x00nul", "has\x7fdel", "has\x85next", "has\u2028line", "has\u2029paragraph"])
@pytest.mark.parametrize(("field", "expected_code"), [("gloss", "invalid_gloss"), ("description", "invalid_placeholder_description")])
def test_short_display_metadata_rejects_controls_and_separators(tmp_path, complete, file_data, write_file, load_catalog, bad_text, field, expected_code):
    source = tmp_path / "source"
    action = complete(gloss=bad_text) if field == "gloss" else complete(prompt_vars={"%VALUE%": bad_text}, prompt="Use %VALUE%.")
    write_file(source, file_data(actions={"test": {"agnostic": action}}))
    catalog = load_catalog(source)
    assert selectors(catalog, "test") == []
    assert expected_code in diagnostic_codes(catalog)


def test_short_display_metadata_preserves_ordinary_unicode(tmp_path, complete, file_data, write_file, load_catalog):
    source = tmp_path / "source"
    action = complete(gloss="R\u00e9sum\u00e9 review", prompt_vars={"%VALUE%": "Cr\u00e8me br\u00fbl\u00e9e"}, prompt="Use %VALUE%.")
    write_file(source, file_data(actions={"test": {"agnostic": action}}))
    catalog = load_catalog(source)
    assert selectors(catalog, "test") == ["test[agnostic]"]
    assert catalog.inspect("test[agnostic]").action.fields["gloss"] == "R\u00e9sum\u00e9 review"


@pytest.mark.parametrize(
    ("updates", "code"),
    [
        ({"goal_mode": True, "plan_mode": True}, "conflicting_modes"),
        ({"reasoning_effort": "high", "plan_reasoning_effort": "medium", "plan_mode": False}, "unequal_efforts_without_plan"),
        ({"no_edits": True, "prompt": "No edits. Check this."}, "manual_no_edits_prefix"),
        ({"gloss": "  "}, "invalid_gloss"),
        ({"prompt": "\n"}, "invalid_prompt"),
        ({"reasoning_effort": "High", "plan_reasoning_effort": "High"}, "invalid_effort"),
    ],
)
def test_cross_field_and_nonempty_validation(tmp_path, complete, file_data, write_file, load_catalog, updates, code):
    source = tmp_path / code
    write_file(source, file_data(actions={"test": {"agnostic": complete(**updates)}}))
    catalog = load_catalog(source)
    assert selectors(catalog, "test") == []
    assert code in diagnostic_codes(catalog)


def test_plan_mode_allows_distinct_default_and_planning_efforts(tmp_path, complete, file_data, write_file, load_catalog):
    source = tmp_path / "source"
    write_file(source, file_data(actions={"test": {"agnostic": complete(reasoning_effort="medium", plan_mode=True, plan_reasoning_effort="high")}}))
    catalog = load_catalog(source)
    assert selectors(catalog, "test") == ["test[agnostic]"]
    assert catalog.diagnostics == []


@pytest.mark.parametrize("prompt", ["No edits.", "No edits. Next", "No edits.\tNext", "No edits.\nNext", "No edits.\u2003Next"])
def test_no_edits_rejects_manual_sentence_followed_by_end_or_whitespace(tmp_path, complete, file_data, write_file, load_catalog, prompt):
    source = tmp_path / "source"
    write_file(source, file_data(actions={"test": {"agnostic": complete(no_edits=True, prompt=prompt)}}))
    catalog = load_catalog(source)
    assert selectors(catalog, "test") == []
    assert "manual_no_edits_prefix" in diagnostic_codes(catalog)


@pytest.mark.parametrize("prompt", [" No edits. Next", "no edits. Next", "No edits: Next", "No edits.Next"])
def test_no_edits_allows_nonprefix_near_matches(tmp_path, complete, file_data, write_file, load_catalog, prompt):
    source = tmp_path / "source"
    write_file(source, file_data(actions={"test": {"agnostic": complete(no_edits=True, prompt=prompt)}}))
    catalog = load_catalog(source)
    assert selectors(catalog, "test") == ["test[agnostic]"]
    assert catalog.diagnostics == []


def test_prompt_variable_declarations_must_match_materialized_prompt(tmp_path, complete, file_data, write_file, load_catalog):
    source = tmp_path / "source"
    actions = {
        "unused": {"agnostic": complete(prompt_vars={"%X%": "Value"})},
        "undeclared": {"agnostic": complete(prompt="Use %X%.")},
        "bad-key": {"agnostic": complete(prompt_vars={"%1X%": "Value"}, prompt="Use %1X%.")},
        "bad-description": {"agnostic": complete(prompt_vars={"%X%": "  "}, prompt="Use %X%.")},
    }
    write_file(source, file_data(actions=actions))
    catalog = load_catalog(source)
    assert selectors(catalog) == ["help[agnostic]"]
    assert set(diagnostic_codes(catalog)) >= {"unused_prompt_variable", "undeclared_prompt_variable", "invalid_placeholder", "invalid_placeholder_description"}


def test_invalid_ignore_selector_does_not_block_independent_definitions(tmp_path, complete, file_data, write_file, load_catalog):
    source = tmp_path / "source"
    write_file(source, file_data(actions={"good": {"agnostic": complete()}}, ignore_actions=[1, "bad[python,rust]", "no-op"]))
    catalog = load_catalog(source)
    assert selectors(catalog, "good") == ["good[agnostic]"]
    assert diagnostic_codes(catalog).count("invalid_ignore_selector") == 2


def test_invalid_json_file_does_not_invalidate_valid_sibling_file(tmp_path, complete, file_data, write_file, write_raw, load_catalog):
    source = tmp_path / "source"
    write_raw(source, "{", "10-bad.json")
    write_file(source, file_data(actions={"good": {"agnostic": complete()}}), "20-good.json")
    catalog = load_catalog(source)
    assert selectors(catalog, "good") == ["good[agnostic]"]
    assert "invalid_json" in diagnostic_codes(catalog)
    assert catalog.precedence_incomplete is False


def test_json_round_trip_preserves_prompt_content(tmp_path, complete, file_data, write_file, load_catalog):
    prompt = "Line one.\n\n- Unicode: \u03bb\n- Quotes: `x` and $() and \\\\"
    source = tmp_path / "source"
    write_file(source, file_data(actions={"test": {"agnostic": complete(prompt=prompt)}}))
    catalog = load_catalog(source)
    assert catalog.inspect("test[agnostic]").action.fields["prompt"] == prompt
    assert json.loads(json.dumps(catalog.inspect("test[agnostic]").to_dict()))["base_prompt"] == prompt
