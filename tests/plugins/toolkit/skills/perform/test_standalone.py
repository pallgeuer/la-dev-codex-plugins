"""High-level standalone launcher facade tests."""

import importlib
from pathlib import Path

import pytest

catalog_module = importlib.import_module("toolkit_perform_runtime.catalog")
diagnostics_module = importlib.import_module("toolkit_perform_runtime.diagnostics")
discovery_module = importlib.import_module("toolkit_perform_runtime.discovery")
standalone_module = importlib.import_module("toolkit_perform_runtime.standalone")
validation_module = importlib.import_module("toolkit_perform_runtime.validation")


def make_launcher(tmp_path, file_data, write_file, load_catalog, actions):
    """Create one facade backed by an explicit action source."""
    source = tmp_path / "source"
    write_file(source, file_data(actions=actions))
    return standalone_module.StandaloneLauncher(load_catalog(source))


def test_facade_lists_shows_and_prepares_actions(tmp_path, complete, file_data, write_file, load_catalog):
    launcher = make_launcher(
        tmp_path,
        file_data,
        write_file,
        load_catalog,
        {"test": {"agnostic": complete(prompt_vars={"Target": "Target"}, prompt="Inspect %Target%.", requires_interactive=False)}},
    )
    assert launcher.list_actions("test") == {
        "variants": [
            {
                "selector": "test[agnostic]",
                "name": "test",
                "language": "agnostic",
                "gloss": "Test action",
                "prompt_vars": {"Target": "Target"},
            }
        ]
    }
    shown = launcher.show_action("test")
    assert shown["selector"] == "test[agnostic]"
    assert shown["action"]["prompt"] == "Inspect %Target%."
    spec = launcher.prepare_launch("test", variable_bindings=["Target=src/"], qualification="Report findings.")
    assert spec.rendered_prompt == "Inspect src/. BUT: Report findings."
    assert spec.config.selector == "test[agnostic]"


def test_facade_returns_complete_builtin_help_payload(tmp_path, load_catalog):
    launcher = standalone_module.StandaloneLauncher(load_catalog(tmp_path))
    payload = launcher.show_action("help")
    assert payload["selector"] == "help[agnostic]"
    assert payload["help"] == "Read the installed Perform guides."
    assert [(guide["name"], guide["description"]) for guide in payload["guides"]] == [
        ("action_files", "Define, discover, layer, validate, and catalogue Perform actions."),
        ("codex_skill", "Select and run Perform actions inside an existing Codex chat."),
        ("standalone_cli", "Select and launch Perform actions with codex-perform or its Python API."),
    ]
    assert [Path(guide["path"]).name for guide in payload["guides"]] == ["action_files.md", "codex_skill.md", "standalone_cli.md"]
    assert all(Path(guide["path"]).is_absolute() and Path(guide["path"]).is_file() for guide in payload["guides"])


def test_facade_resolves_languages_and_reports_ambiguity(tmp_path, complete, file_data, write_file, load_catalog):
    launcher = make_launcher(
        tmp_path,
        file_data,
        write_file,
        load_catalog,
        {"test": {"python": complete(prompt="Python."), "rust": complete(prompt="Rust.")}},
    )
    assert launcher.prepare_launch("test", language="python").rendered_prompt == "Python."
    assert launcher.prepare_launch("test[rust]").rendered_prompt == "Rust."
    with pytest.raises(diagnostics_module.PerformRequestError) as error:
        launcher.prepare_launch("test")
    assert error.value.status == "ambiguous_language"
    assert error.value.alternatives == ["test[python]", "test[rust]"]


def test_facade_preserves_partial_listing_when_precedence_is_incomplete():
    discovery = discovery_module.explicit_discovery([])
    diagnostics = [diagnostics_module.Diagnostic("error", "broken_source", "The source is broken.", fatality="catalog_fatal")]
    catalog = catalog_module.ActionCatalog({}, diagnostics, discovery, precedence_incomplete=True)
    launcher = standalone_module.StandaloneLauncher(catalog)
    assert launcher.precedence_incomplete is True
    assert launcher.list_actions("missing[agnostic]") == {"variants": [], "diagnostics": ["error: The source is broken. (discovery)"]}
    with pytest.raises(diagnostics_module.PerformRequestError) as error:
        launcher.prepare_launch("missing")
    assert error.value.status == "fatal_catalog"
    assert error.value.diagnostics == ["error: The source is broken. (discovery)"]


@pytest.mark.parametrize(
    ("bindings", "status"),
    [
        ("not-a-list", "invalid_variable_argument"),
        (["missing-separator"], "invalid_variable_argument"),
        (["Target=one", "Target=two"], "duplicate_variable_argument"),
        (["%Target%=one"], "invalid_variable_argument"),
        (["=one"], "invalid_variable_argument"),
        (["1Target=one"], "invalid_variable_argument"),
        (["Target-Name=one"], "invalid_variable_argument"),
        (["caf\u00e9=one"], "invalid_variable_argument"),
    ],
)
def test_shared_variable_binding_parser_reports_stable_errors(bindings, status):
    with pytest.raises(diagnostics_module.PerformRequestError) as error:
        validation_module.parse_variable_bindings(bindings)
    assert error.value.status == status
