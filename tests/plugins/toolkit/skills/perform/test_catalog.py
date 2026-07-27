"""Catalog schema, validation, diagnostics, and isolation tests."""

import importlib
import json

import pytest

catalog_module = importlib.import_module("toolkit_perform_runtime.catalog")
discovery_module = importlib.import_module("toolkit_perform_runtime.discovery")
validation_module = importlib.import_module("toolkit_perform_runtime.validation")


def selectors(catalog, name=None):
    """Return canonical selectors from one catalog listing."""
    return [summary.selector for summary in catalog.list_actions(name=name)]


def diagnostic_codes(catalog):
    """Return stable diagnostic codes from one catalog."""
    return [diagnostic.code for diagnostic in catalog.diagnostics]


def test_field_validator_registry_exactly_covers_the_action_schema():
    assert frozenset(catalog_module._FIELD_VALIDATORS) == validation_module.ACTION_FIELD_SET


def test_materialization_groups_patches_in_one_input_traversal(complete):
    class CountingPatches(dict):
        def __init__(self):
            super().__init__()
            self.item_traversals = 0
            self.key_traversals = 0

        def items(self):
            self.item_traversals += 1
            return super().items()

        def __iter__(self):
            self.key_traversals += 1
            return super().__iter__()

    source = discovery_module.SourceDirectory("bundled", "/actions", source_order=0)
    origin = catalog_module._FieldOrigin(source, "actions.json", "/actions")
    fields = complete()
    field_origins = dict.fromkeys(fields, origin)
    patches = CountingPatches()
    for action, language in (("second", "python"), ("first", "rust"), ("first", "agnostic"), ("second", "agnostic")):
        patches[(action, language)] = catalog_module.VariantPatch(fields=fields, field_origins=field_origins, definition_origin=origin)
    diagnostics = []
    actions = catalog_module._materialize(patches, diagnostics)
    assert patches.item_traversals == 1
    assert patches.key_traversals == 0
    assert diagnostics == []
    assert list(actions) == [("first", "agnostic"), ("first", "rust"), ("second", "agnostic"), ("second", "python")]


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
        '{"version": 1, "actions": {"test": {"agnostic": {"prompt_vars": {"X": "one", "X": "two"}}}}}',
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
    assert help_summary[0].gloss == catalog_module.HELP_GLOSS
    assert help_summary[0].to_dict() == {"selector": "help[agnostic]", "gloss": catalog_module.HELP_GLOSS}
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


def test_lone_surrogates_in_json_keys_remain_isolated_and_sortable(tmp_path, complete, file_data, write_file, load_catalog):
    source = tmp_path / "source"
    surrogate = chr(0xD800)
    invalid_field = complete()
    invalid_field[surrogate] = True
    write_file(
        source,
        file_data(
            actions={
                "bad-field": {"agnostic": invalid_field},
                "bad-language": {surrogate: complete()},
                surrogate: {"agnostic": complete()},
                "good": {"agnostic": complete()},
            }
        ),
        "10-variants.json",
    )
    invalid_root = file_data(actions={"lost": {"agnostic": complete()}})
    invalid_root[surrogate] = True
    write_file(source, invalid_root, "20-root.json")
    catalog = load_catalog(source)
    assert selectors(catalog) == ["good[agnostic]", "help[agnostic]"]
    assert set(diagnostic_codes(catalog)) == {"invalid_action_name", "invalid_language_name", "unknown_action_field", "unknown_root_field"}
    assert any(surrogate in (diagnostic.json_path or "") for diagnostic in catalog.diagnostics)


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
        ("interactive", True, "invalid_interactivity"),
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


@pytest.mark.parametrize("field", ["model", "reasoning_effort", "plan_reasoning_effort", "interactive", "custom_codex_args"])
def test_structured_launcher_fields_remain_required(tmp_path, complete, file_data, write_file, load_catalog, field):
    source = tmp_path / field
    action = complete()
    del action[field]
    write_file(source, file_data(actions={"test": {"agnostic": action}}))
    catalog = load_catalog(source)
    assert selectors(catalog, "test") == []
    assert "incomplete_action" in diagnostic_codes(catalog)


@pytest.mark.parametrize("interactive", ["allowed", "preferred", "required"])
def test_interactivity_accepts_exact_policy_values(tmp_path, complete, file_data, write_file, load_catalog, interactive):
    source = tmp_path / interactive
    write_file(source, file_data(actions={"test": {"agnostic": complete(interactive=interactive)}}))
    catalog = load_catalog(source)
    assert selectors(catalog, "test") == ["test[agnostic]"]
    assert catalog.inspect("test[agnostic]").action.fields["interactive"] == interactive


@pytest.mark.parametrize("interactive", ["", "optional", "Preferred", "required ", 0, None, [], {}])
def test_interactivity_rejects_values_outside_exact_policy(tmp_path, complete, file_data, write_file, load_catalog, interactive):
    source = tmp_path / "source"
    write_file(source, file_data(actions={"test": {"agnostic": complete(interactive=interactive)}}))
    catalog = load_catalog(source)
    assert selectors(catalog, "test") == []
    assert "invalid_interactivity" in diagnostic_codes(catalog)


def test_removed_prefer_interactive_field_is_unknown(tmp_path, complete, file_data, write_file, load_catalog):
    source = tmp_path / "source"
    action = complete()
    action["prefer_interactive"] = True
    write_file(source, file_data(actions={"test": {"agnostic": action}}))
    catalog = load_catalog(source)
    assert selectors(catalog, "test") == []
    assert "unknown_action_field" in diagnostic_codes(catalog)


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


@pytest.mark.parametrize("bad_args", [[""], ["has\x00nul"], ["--future=\ud800"]])
def test_custom_codex_arguments_reject_empty_and_nul_entries(tmp_path, complete, file_data, write_file, load_catalog, bad_args):
    source = tmp_path / "source"
    write_file(source, file_data(actions={"test": {"agnostic": complete(custom_codex_args=bad_args)}}))
    catalog = load_catalog(source)
    assert selectors(catalog, "test") == []
    assert "invalid_custom_codex_args" in diagnostic_codes(catalog)


@pytest.mark.parametrize(
    "conflicting_args",
    [
        ["--model=gpt-5"],
        ['--config=plan_mode_reasoning_effort="high"'],
        ["--cd=/tmp"],
        ["--sandbox=danger-full-access"],
        ["--add-dir=/"],
        ["--ask-for-approval=never"],
        ["--profile=unsafe"],
        ["--remote=ws://example.invalid"],
        ["--ignore-rules"],
        ["--image=/secret"],
        ["--enable=unsafe-feature"],
        ["--local-provider=remote"],
        ["--dangerously-future-unsafe"],
        ["--future-option=42"],
        ["--future-boolean"],
        ["--yolo"],
        ["--ephemeral"],
        ["--ephemeral=1"],
        ["--help"],
        ["--version"],
    ],
)
def test_custom_codex_arguments_reject_structured_policy_overrides(tmp_path, complete, file_data, write_file, load_catalog, conflicting_args):
    source = tmp_path / "source"
    write_file(source, file_data(actions={"test": {"agnostic": complete(custom_codex_args=conflicting_args)}}))
    catalog = load_catalog(source)
    assert selectors(catalog, "test") == []
    assert "conflicting_custom_codex_args" in diagnostic_codes(catalog)


def test_goal_action_rejects_action_defined_ephemeral_during_catalog_validation(tmp_path, complete, file_data, write_file, load_catalog):
    source = tmp_path / "source"
    write_file(source, file_data(actions={"test": {"agnostic": complete(goal_mode=True, custom_codex_args=["--ephemeral"])}}))
    catalog = load_catalog(source)
    assert selectors(catalog, "test") == []
    assert "conflicting_custom_codex_args" in diagnostic_codes(catalog)


@pytest.mark.parametrize("malformed_args", [["-s"], ["--"], ["resume"], ["--color", "never"], ["--bad_name=value"], ["--bad name=value"]])
def test_custom_codex_arguments_require_self_contained_long_options(tmp_path, complete, file_data, write_file, load_catalog, malformed_args):
    source = tmp_path / "source"
    write_file(source, file_data(actions={"test": {"agnostic": complete(custom_codex_args=malformed_args)}}))
    catalog = load_catalog(source)
    assert selectors(catalog, "test") == []
    assert "invalid_custom_codex_args" in diagnostic_codes(catalog)


@pytest.mark.parametrize(
    "custom_args",
    [
        ["--search"],
        ["--no-alt-screen"],
        ["--strict-config"],
    ],
)
def test_custom_codex_arguments_allow_curated_flag_only_options(tmp_path, complete, file_data, write_file, load_catalog, custom_args):
    source = tmp_path / "source"
    write_file(source, file_data(actions={"test": {"agnostic": complete(custom_codex_args=custom_args)}}))
    catalog = load_catalog(source)
    assert selectors(catalog, "test") == ["test[agnostic]"]
    assert catalog.diagnostics == []


@pytest.mark.parametrize("custom_arg", ["--search=true", "--no-alt-screen=false", "--strict-config=yes"])
def test_custom_codex_arguments_reject_values_for_allowed_flags(tmp_path, complete, file_data, write_file, load_catalog, custom_arg):
    source = tmp_path / "source"
    write_file(source, file_data(actions={"test": {"agnostic": complete(custom_codex_args=[custom_arg])}}))
    catalog = load_catalog(source)
    assert selectors(catalog, "test") == []
    assert "invalid_custom_codex_args" in diagnostic_codes(catalog)


@pytest.mark.parametrize("bad_text", ["two\nlines", "has\ttab", "has\x00nul", "has\x7fdel", "has\x85next", "has\u2028line", "has\u2029paragraph", "has\u202eoverride", "has\ud800surrogate"])
@pytest.mark.parametrize(("field", "expected_code"), [("gloss", "invalid_gloss"), ("description", "invalid_variable_description")])
def test_short_display_metadata_rejects_controls_and_separators(tmp_path, complete, file_data, write_file, load_catalog, bad_text, field, expected_code):
    source = tmp_path / "source"
    action = complete(gloss=bad_text) if field == "gloss" else complete(prompt_vars={"VALUE": bad_text}, prompt="Use %VALUE%.")
    write_file(source, file_data(actions={"test": {"agnostic": action}}))
    catalog = load_catalog(source)
    assert selectors(catalog, "test") == []
    assert expected_code in diagnostic_codes(catalog)


def test_short_display_metadata_preserves_ordinary_unicode(tmp_path, complete, file_data, write_file, load_catalog):
    source = tmp_path / "source"
    action = complete(gloss="R\u00e9sum\u00e9 review", prompt_vars={"VALUE": "Cr\u00e8me br\u00fbl\u00e9e"}, prompt="Use %VALUE%.")
    write_file(source, file_data(actions={"test": {"agnostic": action}}))
    catalog = load_catalog(source)
    assert selectors(catalog, "test") == ["test[agnostic]"]
    assert catalog.inspect("test[agnostic]").action.fields["gloss"] == "R\u00e9sum\u00e9 review"


@pytest.mark.parametrize(
    ("field", "text", "expected_code"), [("prompt", "has\ud800surrogate", "invalid_prompt"), ("prompt", "has\x00nul", "invalid_prompt"), ("notes", "has\ud800surrogate", "invalid_notes")]
)
def test_action_text_rejects_unsupported_codepoints(tmp_path, complete, file_data, write_file, load_catalog, field, text, expected_code):
    source = tmp_path / "source"
    write_file(source, file_data(actions={"test": {"agnostic": complete(**{field: text})}}))
    catalog = load_catalog(source)
    assert selectors(catalog, "test") == []
    assert expected_code in diagnostic_codes(catalog)


@pytest.mark.parametrize(
    ("updates", "code"),
    [
        ({"goal_mode": True, "plan_mode": True, "no_edits": True, "interactive": "required"}, "conflicting_modes"),
        ({"plan_mode": True, "no_edits": True, "interactive": "allowed"}, "plan_requires_interactive"),
        ({"plan_mode": True, "no_edits": True, "interactive": "preferred"}, "plan_requires_interactive"),
        ({"plan_mode": True, "interactive": "required", "no_edits": False}, "plan_requires_no_edits"),
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
    write_file(source, file_data(actions={"test": {"agnostic": complete(reasoning_effort="medium", plan_mode=True, plan_reasoning_effort="high", no_edits=True, interactive="required")}}))
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
        "unused": {"agnostic": complete(prompt_vars={"X": "Value"})},
        "undeclared": {"agnostic": complete(prompt="Use %X%.")},
        "bad-key": {"agnostic": complete(prompt_vars={"%X%": "Value"}, prompt="Use %X%.")},
        "bad-description": {"agnostic": complete(prompt_vars={"X": "  "}, prompt="Use %X%.")},
    }
    write_file(source, file_data(actions=actions))
    catalog = load_catalog(source)
    assert selectors(catalog) == ["help[agnostic]"]
    assert set(diagnostic_codes(catalog)) >= {"unused_prompt_variable", "undeclared_prompt_variable", "invalid_variable_name", "invalid_variable_description"}


@pytest.mark.parametrize("name", ["", "1X", "X-Y", "X Y", "%X%", "caf\u00e9"])
def test_prompt_variable_names_use_strict_bare_ascii_grammar(tmp_path, complete, file_data, write_file, load_catalog, name):
    source = tmp_path / "source"
    write_file(source, file_data(actions={"bad": {"agnostic": complete(prompt_vars={name: "Value"}, prompt="Use %X%.")}, "good": {"agnostic": complete()}}))
    catalog = load_catalog(source)
    assert selectors(catalog) == ["good[agnostic]", "help[agnostic]"]
    assert "invalid_variable_name" in diagnostic_codes(catalog)


def test_prompt_variable_declarations_and_placeholders_are_case_sensitive(tmp_path, complete, file_data, write_file, load_catalog):
    source = tmp_path / "source"
    write_file(source, file_data(actions={"test": {"agnostic": complete(prompt_vars={"Area": "Area"}, prompt="Use %area%.")}}))
    catalog = load_catalog(source)
    assert selectors(catalog, "test") == []
    assert set(diagnostic_codes(catalog)) == {"unused_prompt_variable", "undeclared_prompt_variable"}


def test_exported_variable_name_and_placeholder_grammars_are_distinct():
    assert catalog_module.VARIABLE_NAME_REGEX == r"^[A-Za-z][A-Za-z0-9_]*$"
    assert catalog_module.VARIABLE_NAME_PATTERN.match("Area")
    assert catalog_module.VARIABLE_NAME_PATTERN.match("%Area%") is None
    assert catalog_module.PLACEHOLDER_REGEX == r"%[A-Za-z][A-Za-z0-9_]*%"


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
    assert json.loads(json.dumps(catalog.inspect("test[agnostic]").to_dict()))["prompt"] == prompt
