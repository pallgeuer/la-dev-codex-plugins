"""Stable action catalogue rendering and write-policy tests."""

import importlib
import os
import stat

import pytest

action_catalogue = importlib.import_module("toolkit_perform_runtime.action_catalogue")
catalog_module = importlib.import_module("toolkit_perform_runtime.catalog")
diagnostics_module = importlib.import_module("toolkit_perform_runtime.diagnostics")
discovery_module = importlib.import_module("toolkit_perform_runtime.discovery")
standalone_module = importlib.import_module("toolkit_perform_runtime.standalone")


def test_render_action_catalogue_is_grouped_escaped_and_stable():
    summaries = [
        catalog_module.ActionSummary("zeta", "python", "Python | <check>", {"Target": "Path `inside`"}),
        catalog_module.ActionSummary("alpha", "rust", "Shared", {}),
        catalog_module.ActionSummary("zeta", "agnostic", "General", {}),
        catalog_module.ActionSummary("alpha", "agnostic", "Shared", {}),
    ]
    rendered, action_count, variant_count = action_catalogue.render_action_catalogue(summaries)
    assert rendered == (
        "<!-- toolkit-perform-action-catalogue:v1 -->\n"
        "# Perform Action Catalogue\n"
        "\n"
        "This file lists the effective Perform actions available in the current Perform context.\n"
        "\n"
        "Regenerate it with `$toolkit:perform update-action-catalogue` or `codex-perform catalogue`. Use a bare action name when its language is clear, or an exact `ACTION[LANGUAGE]` selector. The `agnostic` language is language-independent.\n"
        "\n"
        "| Action  |      Languages       | Description                                                  | Required inputs                                               |\n"
        "|---------|:--------------------:|--------------------------------------------------------------|---------------------------------------------------------------|\n"
        "| `alpha` |  `agnostic`, `rust`  | Shared                                                       | None                                                          |\n"
        "| `zeta`  | `agnostic`, `python` | `agnostic`: General<br>`python`: Python &#124; &lt;check&gt; | `agnostic`: None<br>`python`: `Target`: Path &#96;inside&#96; |\n"
    )
    assert action_count == 2
    assert variant_count == 4


def test_render_action_catalogue_without_actions_uses_header_widths():
    rendered, action_count, variant_count = action_catalogue.render_action_catalogue([])
    table = rendered.splitlines()[-2:]
    assert table == [
        "| Action | Languages | Description | Required inputs |",
        "|--------|:---------:|-------------|-----------------|",
    ]
    assert action_count == 0
    assert variant_count == 0


def test_default_write_creates_parents_and_leaves_identical_file_untouched(tmp_path, complete, file_data, write_file, load_catalog):
    source = tmp_path / "source"
    write_file(source, file_data(actions={"test": {"agnostic": complete()}}))
    catalog = load_catalog(source)
    repository = tmp_path / "repository"
    repository.mkdir()
    catalog.discovery.repository_root = str(repository)

    first = action_catalogue.write_action_catalogue(catalog)
    path = repository / ".codex" / "toolkit_perform_actions" / "action_catalogue.md"
    first_stat = path.stat()
    second = action_catalogue.write_action_catalogue(catalog)
    second_stat = path.stat()

    assert first == {"path": str(path), "changed": True, "action_count": 2, "variant_count": 2}
    assert second == {"path": str(path), "changed": False, "action_count": 2, "variant_count": 2}
    assert second_stat.st_ino == first_stat.st_ino
    assert second_stat.st_mtime_ns == first_stat.st_mtime_ns
    assert path.read_text(encoding="utf-8").startswith(action_catalogue.CATALOGUE_MARKER + "\n")


def test_new_write_respects_umask_and_update_preserves_mode(tmp_path, load_catalog):
    source = tmp_path / "source"
    source.mkdir()
    catalog = load_catalog(source)
    output = tmp_path / "catalogue.md"
    previous_umask = os.umask(0o027)
    try:
        action_catalogue.write_action_catalogue(catalog, output=str(output))
    finally:
        os.umask(previous_umask)
    assert stat.S_IMODE(output.stat().st_mode) == 0o640

    output.chmod(0o604)
    output.write_text(action_catalogue.CATALOGUE_MARKER + "\nstale\n", encoding="ascii")
    action_catalogue.write_action_catalogue(catalog, output=str(output))
    assert stat.S_IMODE(output.stat().st_mode) == 0o604


def test_explicit_relative_and_absolute_paths_follow_repository_policy(tmp_path, load_catalog):
    source = tmp_path / "source"
    source.mkdir()
    catalog = load_catalog(source)
    repository = tmp_path / "repository"
    custom_parent = repository / "docs"
    custom_parent.mkdir(parents=True)
    catalog.discovery.repository_root = str(repository)

    relative = action_catalogue.write_action_catalogue(catalog, output="docs/actions.md")
    assert relative["path"] == str(custom_parent / "actions.md")
    outside = tmp_path / "outside"
    outside.mkdir()
    traversed = action_catalogue.write_action_catalogue(catalog, output="../outside/actions.md")
    assert traversed["path"] == str(outside / "actions.md")

    catalog.discovery.repository_root = None
    absolute_path = tmp_path / "absolute.md"
    absolute = action_catalogue.write_action_catalogue(catalog, output=str(absolute_path))
    assert absolute["path"] == str(absolute_path)
    with pytest.raises(diagnostics_module.PerformRequestError) as relative_error:
        action_catalogue.write_action_catalogue(catalog, output="relative.md")
    assert relative_error.value.status == "repository_not_found"


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symbolic links are unavailable")
def test_default_write_follows_parent_directory_symlinks(tmp_path, load_catalog):
    source = tmp_path / "source"
    source.mkdir()
    catalog = load_catalog(source)
    repository = tmp_path / "repository"
    repository.mkdir()
    external = tmp_path / "external"
    external.mkdir()
    (repository / ".codex").symlink_to(external, target_is_directory=True)
    catalog.discovery.repository_root = str(repository)

    result = action_catalogue.write_action_catalogue(catalog)

    assert result["path"] == str(repository / ".codex" / "toolkit_perform_actions" / "action_catalogue.md")
    assert (external / "toolkit_perform_actions" / "action_catalogue.md").is_file()


def test_custom_parent_must_exist(tmp_path, load_catalog):
    source = tmp_path / "source"
    source.mkdir()
    catalog = load_catalog(source)
    catalog.discovery.repository_root = str(tmp_path)
    with pytest.raises(diagnostics_module.PerformRequestError) as error:
        action_catalogue.write_action_catalogue(catalog, output="missing/actions.md")
    assert error.value.status == "output_parent_missing"


def test_writer_replaces_only_empty_or_marked_regular_files(tmp_path, load_catalog):
    source = tmp_path / "source"
    source.mkdir()
    catalog = load_catalog(source)
    output = tmp_path / "catalogue.md"
    output.write_text("manual\n", encoding="ascii")
    with pytest.raises(diagnostics_module.PerformRequestError) as manual_error:
        action_catalogue.write_action_catalogue(catalog, output=str(output))
    assert manual_error.value.status == "unsafe_output"
    assert output.read_text(encoding="ascii") == "manual\n"

    output.write_bytes(b"")
    assert action_catalogue.write_action_catalogue(catalog, output=str(output))["changed"] is True
    output.write_text(action_catalogue.CATALOGUE_MARKER + "\nstale\n", encoding="ascii")
    assert action_catalogue.write_action_catalogue(catalog, output=str(output))["changed"] is True
    assert "stale" not in output.read_text(encoding="utf-8")

    directory = tmp_path / "directory"
    directory.mkdir()
    with pytest.raises(diagnostics_module.PerformRequestError) as directory_error:
        action_catalogue.write_action_catalogue(catalog, output=str(directory))
    assert directory_error.value.status == "unsafe_output"


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symbolic links are unavailable")
def test_writer_refuses_symbolic_link_targets(tmp_path, load_catalog):
    source = tmp_path / "source"
    source.mkdir()
    catalog = load_catalog(source)
    real_file = tmp_path / "real.md"
    real_file.write_text(action_catalogue.CATALOGUE_MARKER + "\n", encoding="ascii")
    link = tmp_path / "link.md"
    link.symlink_to(real_file)
    with pytest.raises(diagnostics_module.PerformRequestError) as error:
        action_catalogue.write_action_catalogue(catalog, output=str(link))
    assert error.value.status == "unsafe_output"
    assert real_file.read_text(encoding="ascii") == action_catalogue.CATALOGUE_MARKER + "\n"


def test_incomplete_precedence_never_writes(tmp_path):
    discovery = discovery_module.explicit_discovery([])
    catalog = catalog_module.ActionCatalog({}, [], discovery, precedence_incomplete=True)
    output = tmp_path / "catalogue.md"
    with pytest.raises(diagnostics_module.PerformRequestError) as error:
        action_catalogue.write_action_catalogue(catalog, output=str(output))
    assert error.value.status == "fatal_catalog"
    assert not output.exists()


def test_facade_returns_nonfatal_diagnostics_without_putting_them_in_markdown(tmp_path, complete, file_data, write_file, load_catalog):
    invalid = complete()
    invalid["unknown"] = True
    source = tmp_path / "source"
    write_file(source, file_data(actions={"bad": {"agnostic": invalid}, "good": {"agnostic": complete()}}))
    launcher = standalone_module.StandaloneLauncher(load_catalog(source))
    output = tmp_path / "catalogue.md"
    payloads = [
        launcher.list_actions(),
        launcher.show_action("good"),
        launcher.write_action_catalogue(output=str(output)),
    ]
    assert all(payload["diagnostics"] for payload in payloads)
    assert all("Unknown version 1 action field" in payload["diagnostics"][0] for payload in payloads)
    assert "Unknown version 1 action field" not in output.read_text(encoding="utf-8")
