"""Language inheritance, overrides, ignores, provenance, and precedence tests."""

from conftest import runtime


def listed(catalog, name):
    """Return selectors for one action name."""
    return [summary.selector for summary in catalog.list_actions(name=name)]


def test_partial_json_and_yaml_variants_inherit_agnostic(tmp_path, complete, file_data, write_file, load_catalog):
    source = tmp_path / "source"
    actions = {
        "check": {
            "agnostic": complete(gloss="Check config", prompt="Check configuration."),
            "json": {"prompt": "Check JSON."},
            "yaml": {"prompt": "Check YAML."},
        }
    }
    write_file(source, file_data(actions=actions))
    catalog = load_catalog(source)
    assert listed(catalog, "check") == ["check[agnostic]", "check[json]", "check[yaml]"]
    assert catalog.inspect("check[json]").action.fields["gloss"] == "Check config"
    assert catalog.inspect("check[yaml]").base_prompt == "Check YAML."


def test_prompt_vars_and_custom_arguments_replace_whole_inherited_fields(tmp_path, complete, file_data, write_file, load_catalog):
    source = tmp_path / "source"
    base = complete(prompt_vars={"%A%": "A"}, prompt="Use %A%.", custom_codex_args=["--base"])
    language = {"prompt_vars": {"%B%": "B"}, "prompt": "Use %B%.", "custom_codex_args": ["--language"]}
    write_file(source, file_data(actions={"test": {"agnostic": base, "python": language}}))
    action = load_catalog(source).inspect("test[python]").action
    assert action.fields["prompt_vars"] == {"%B%": "B"}
    assert action.fields["custom_codex_args"] == ["--language"]


def test_complete_specific_implementation_survives_invalid_agnostic(tmp_path, complete, file_data, write_file, load_catalog):
    source = tmp_path / "source"
    invalid_base = complete(goal_mode=True, plan_mode=True)
    write_file(source, file_data(actions={"test": {"agnostic": invalid_base, "python": complete(prompt="Python.")}}))
    catalog = load_catalog(source)
    assert listed(catalog, "test") == ["test[python]"]
    assert catalog.inspect("test[python]").base_prompt == "Python."
    assert any(diagnostic.code == "conflicting_modes" and diagnostic.selector == "test[agnostic]" for diagnostic in catalog.diagnostics)


def test_partial_specific_implementation_fails_without_usable_base(tmp_path, file_data, write_file, load_catalog):
    source = tmp_path / "source"
    write_file(source, file_data(actions={"test": {"python": {"prompt": "Python."}}}))
    catalog = load_catalog(source)
    assert listed(catalog, "test") == []
    assert any(diagnostic.code == "incomplete_action" and diagnostic.selector == "test[python]" for diagnostic in catalog.diagnostics)


def test_specific_prompt_must_replace_inherited_prompt_vars_when_needed(tmp_path, complete, file_data, write_file, load_catalog):
    source = tmp_path / "source"
    base = complete(prompt_vars={"%A%": "A"}, prompt="Use %A%.")
    write_file(source, file_data(actions={"test": {"agnostic": base, "python": {"prompt": "No variables."}}}))
    catalog = load_catalog(source)
    assert listed(catalog, "test") == ["test[agnostic]"]
    assert any(diagnostic.code == "unused_prompt_variable" and diagnostic.selector == "test[python]" for diagnostic in catalog.diagnostics)


def test_cross_field_invariants_are_rechecked_after_inheritance(tmp_path, complete, file_data, write_file, load_catalog):
    source = tmp_path / "source"
    actions = {
        "conflicting-modes": {"agnostic": complete(goal_mode=True), "python": {"plan_mode": True}},
        "unequal-efforts": {"agnostic": complete(), "python": {"plan_reasoning_effort": "high"}},
    }
    write_file(source, file_data(actions=actions))
    catalog = load_catalog(source)
    assert listed(catalog, "conflicting-modes") == ["conflicting-modes[agnostic]"]
    assert listed(catalog, "unequal-efforts") == ["unequal-efforts[agnostic]"]
    assert any(diagnostic.code == "conflicting_modes" and diagnostic.selector == "conflicting-modes[python]" for diagnostic in catalog.diagnostics)
    assert any(diagnostic.code == "unequal_efforts_without_plan" and diagnostic.selector == "unequal-efforts[python]" for diagnostic in catalog.diagnostics)


def test_no_edits_prefix_is_rechecked_after_inheritance(tmp_path, complete, file_data, write_file, load_catalog):
    source = tmp_path / "source"
    base = complete(no_edits=False, prompt="No edits. Check Python.")
    write_file(source, file_data(actions={"test": {"agnostic": base, "python": {"no_edits": True}}}))
    catalog = load_catalog(source)
    assert listed(catalog, "test") == ["test[agnostic]"]
    assert any(diagnostic.code == "manual_no_edits_prefix" and diagnostic.selector == "test[python]" for diagnostic in catalog.diagnostics)


def test_higher_language_override_preserves_sibling_and_lower_same_language_fields(tmp_path, complete, file_data, write_file, load_catalog):
    low = tmp_path / "low"
    high = tmp_path / "high"
    write_file(
        low,
        file_data(
            actions={
                "check": {
                    "agnostic": complete(gloss="Base", prompt="Base."),
                    "python": {"gloss": "Python", "prompt": "Old Python."},
                    "rust": {"prompt": "Rust."},
                }
            }
        ),
    )
    write_file(high, file_data(actions={"check": {"python": {"prompt": "New Python."}}}))
    catalog = load_catalog(low, high)
    assert listed(catalog, "check") == ["check[agnostic]", "check[python]", "check[rust]"]
    assert catalog.inspect("check[python]").action.fields["gloss"] == "Python"
    assert catalog.inspect("check[python]").base_prompt == "New Python."
    assert catalog.inspect("check[rust]").base_prompt == "Rust."


def test_higher_agnostic_replacement_rematerializes_inherited_language_patches(tmp_path, complete, file_data, write_file, load_catalog):
    low = tmp_path / "low"
    high = tmp_path / "high"
    write_file(low, file_data(actions={"check": {"agnostic": complete(gloss="Old", notes="old"), "python": {"prompt": "Python."}}}))
    write_file(high, file_data(actions={"check": {"agnostic": complete(gloss="New", notes="new")}}))
    catalog = load_catalog(low, high)
    python = catalog.inspect("check[python]").action
    assert python.fields["gloss"] == "New"
    assert python.fields["notes"] == "new"
    assert python.fields["prompt"] == "Python."


def test_action_wide_ignore_then_same_file_clean_redefinition(tmp_path, complete, file_data, write_file, load_catalog):
    low = tmp_path / "low"
    high = tmp_path / "high"
    write_file(low, file_data(actions={"check": {"agnostic": complete(gloss="Old"), "python": {"prompt": "Old Python."}}}))
    write_file(high, file_data(actions={"check": {"agnostic": complete(gloss="Clean")}}, ignore_actions=["check"]))
    catalog = load_catalog(low, high)
    assert listed(catalog, "check") == ["check[agnostic]"]
    assert catalog.inspect("check[agnostic]").action.fields["gloss"] == "Clean"


def test_language_ignore_and_higher_reintroduction(tmp_path, complete, file_data, write_file, load_catalog):
    low = tmp_path / "low"
    middle = tmp_path / "middle"
    high = tmp_path / "high"
    write_file(low, file_data(actions={"check": {"agnostic": complete(), "python": {"prompt": "Low Python."}, "rust": {"prompt": "Rust."}}}))
    write_file(middle, file_data(ignore_actions=["check[python]"]))
    write_file(high, file_data(actions={"check": {"python": {"prompt": "High Python."}}}))
    catalog = load_catalog(low, middle, high)
    assert listed(catalog, "check") == ["check[agnostic]", "check[python]", "check[rust]"]
    assert catalog.inspect("check[python]").base_prompt == "High Python."


def test_no_op_ignore_is_valid_and_silent(tmp_path, file_data, write_file, load_catalog):
    source = tmp_path / "source"
    write_file(source, file_data(ignore_actions=["future-action", "other[python]"]))
    catalog = load_catalog(source)
    assert catalog.diagnostics == []


def test_filenames_sort_by_exact_utf8_bytes_and_later_file_wins(tmp_path, complete, file_data, write_file, load_catalog):
    source = tmp_path / "source"
    write_file(source, file_data(actions={"test": {"agnostic": complete(gloss="Upper")}}), "A.json")
    write_file(source, file_data(actions={"test": {"agnostic": complete(gloss="Lowercase")}}), "a.json")
    catalog = load_catalog(source)
    assert catalog.inspect("test[agnostic]").action.fields["gloss"] == "Lowercase"


def test_bundled_system_user_repository_precedence_and_provenance(tmp_path, complete, file_data, write_file):
    sources = []
    for kind in ("bundled", "system", "user", "repository"):
        directory = tmp_path / kind
        write_file(directory, file_data(actions={"test": {"agnostic": complete(gloss=kind)}}))
        sources.append((kind, str(directory)))
    catalog = runtime.load_action_catalog(action_directories=sources)
    action = catalog.inspect("test[agnostic]").action
    assert action.fields["gloss"] == "repository"
    assert action.provenance["gloss"].source_kind == "repository"
    assert action.primary_source()["source_kind"] == "repository"


def test_effective_variant_has_per_field_provenance_from_base_and_overlay(tmp_path, complete, file_data, write_file):
    bundled = tmp_path / "bundled"
    user = tmp_path / "user"
    write_file(bundled, file_data(actions={"test": {"agnostic": complete(gloss="Base"), "python": {"gloss": "Python"}}}))
    write_file(user, file_data(actions={"test": {"python": {"prompt": "User Python."}}}))
    catalog = runtime.load_action_catalog(action_directories=[("bundled", str(bundled)), ("user", str(user))])
    action = catalog.inspect("test[python]").action
    assert action.provenance["model"].source_kind == "bundled"
    assert action.provenance["gloss"].source_kind == "bundled"
    assert action.provenance["prompt"].source_kind == "user"


def test_ignore_agnostic_leaves_only_independently_complete_specific_variant(tmp_path, complete, file_data, write_file, load_catalog):
    low = tmp_path / "low"
    high = tmp_path / "high"
    write_file(low, file_data(actions={"test": {"agnostic": complete(), "python": complete(prompt="Complete Python."), "rust": {"prompt": "Partial Rust."}}}))
    write_file(high, file_data(ignore_actions=["test[agnostic]"]))
    catalog = load_catalog(low, high)
    assert listed(catalog, "test") == ["test[python]"]
    assert any(diagnostic.code == "incomplete_action" and diagnostic.selector == "test[rust]" for diagnostic in catalog.diagnostics)
