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


def render_catalog(catalog):
    """Render one catalog through its guarded immutable projection."""
    return action_catalogue.render_action_catalogue(catalog.catalogue_entries(), repository_root=catalog.discovery.repository_root)


def test_render_action_catalogue_is_grouped_escaped_and_stable(tmp_path, complete, file_data, write_file, load_catalog):
    source = tmp_path / "source"
    write_file(
        source,
        file_data(
            actions={
                "alpha": {"agnostic": complete(gloss="Shared"), "rust": {"gloss": "Shared"}},
                "zeta": {
                    "agnostic": complete(gloss="General"),
                    "python": {"gloss": "Python | <check>", "prompt_vars": {"Target": "Path `inside`"}, "prompt": "Check %Target%."},
                },
            }
        ),
    )
    catalog = load_catalog(source)
    rendered, action_count, variant_count = render_catalog(catalog)
    lines = rendered.splitlines()
    assert lines[:2] == [action_catalogue.CATALOGUE_MARKER, "# Perform Action Catalogue"]
    assert "## Built-in" in lines
    assert "**JSON source:** `<source-1>/actions.json`" in rendered
    assert lines[-4:] == [
        "| Action  |      Languages       | Description                                                  | Required inputs                                               |",
        "|---------|:--------------------:|--------------------------------------------------------------|---------------------------------------------------------------|",
        "| `alpha` |  `agnostic`, `rust`  | Shared                                                       | None                                                          |",
        "| `zeta`  | `agnostic`, `python` | `agnostic`: General<br>`python`: Python &#124; &lt;check&gt; | `agnostic`: None<br>`python`: `Target`: Path &#96;inside&#96; |",
    ]
    assert action_count == 3
    assert variant_count == 5


def test_render_action_catalogue_accepts_only_entries_and_explicit_repository_context():
    entry = catalog_module.ActionCatalogueEntry("test", "agnostic", "Test action", {})
    rendered, action_count, variant_count = action_catalogue.render_action_catalogue([entry])
    assert "## Built-in" in rendered
    assert action_count == 1
    assert variant_count == 1
    with pytest.raises(TypeError, match="entries must contain only ActionCatalogueEntry values"):
        action_catalogue.render_action_catalogue([catalog_module.ActionSummary("test", "agnostic", "Test action", {})])
    with pytest.raises(TypeError, match="repository_root must be a string or None"):
        action_catalogue.render_action_catalogue([entry], repository_root=object())


def test_shortest_unique_path_suffixes_and_inline_code_are_markdown_safe():
    paths = ["/one/shared/actions.json", "/two/shared/actions.json", "/three/unique.json", "actions.json", "/four/actions.json"]
    assert action_catalogue._shortest_unique_suffixes(paths) == {
        "/one/shared/actions.json": "one/shared/actions.json",
        "/two/shared/actions.json": "two/shared/actions.json",
        "/three/unique.json": "unique.json",
        "actions.json": "actions.json",
        "/four/actions.json": "four/actions.json",
    }
    assert action_catalogue._format_inline_code("/tmp/name`part.json") == "``/tmp/name`part.json``"
    assert action_catalogue._format_inline_code("/tmp/line\nbreak.json") == "`/tmp/line\\nbreak.json`"
    assert action_catalogue._format_inline_code("/tmp/line\\nbreak.json") == "`/tmp/line\\\\nbreak.json`"
    assert action_catalogue._format_inline_code("/tmp/left\u200emark\u2028next\udcff{}end.json".format(chr(0xE0001))) == "`/tmp/left\\u200emark\\u2028next\\udcff\\U000e0001end.json`"
    assert action_catalogue._format_inline_code("/tmp/plain space.json") == "`/tmp/plain space.json`"
    assert action_catalogue._format_inline_code("/tmp/no\u00a0break\u2007figure\u202fnarrow.json") == "`/tmp/no\\u00a0break\\u2007figure\\u202fnarrow.json`"


def test_catalogue_sections_follow_definition_precedence_and_split_language_variants(tmp_path, complete, file_data, write_file, load_catalog):
    low = tmp_path / "z-low" / "shared"
    middle = tmp_path / "middle"
    high = tmp_path / "a-high" / "shared"
    obsolete_path = write_file(low, file_data(actions={"reintroduced": {"agnostic": complete()}, "shadowed": {"agnostic": complete()}}), "00-obsolete.json")
    write_file(
        low,
        file_data(actions={"split": {"agnostic": complete(), "python": {"gloss": "Python-specific"}}}),
    )
    ignored_path = write_file(middle, file_data(ignore_actions=["reintroduced"]), "50-ignore.json")
    empty_path = write_file(middle, file_data(), "80-empty.json")
    write_file(middle, file_data(actions={"middle": {"agnostic": complete()}}), "90-middle.json")
    write_file(
        high,
        file_data(actions={"reintroduced": {"agnostic": complete()}, "shadowed": {"agnostic": complete()}, "split": {"agnostic": complete()}}),
    )
    catalog = load_catalog(low, middle, high)

    rendered, action_count, variant_count = render_catalog(catalog)
    low_heading = "## `<source-1>/actions.json`"
    middle_heading = "## `90-middle.json`"
    high_heading = "## `<source-3>/actions.json`"
    assert rendered.index("## Built-in") < rendered.index(low_heading) < rendered.index(middle_heading) < rendered.index(high_heading)
    assert "**JSON source:** `<source-1>/actions.json`" in rendered
    assert "**JSON source:** `<source-2>/90-middle.json`" in rendered
    assert "**JSON source:** `<source-3>/actions.json`" in rendered
    assert obsolete_path.name not in rendered
    assert ignored_path.name not in rendered
    assert empty_path.name not in rendered

    low_section = rendered[rendered.index(low_heading) : rendered.index(middle_heading)]
    high_section = rendered[rendered.index(high_heading) :]
    low_split_row = next(line for line in low_section.splitlines() if line.startswith("| `split` "))
    high_split_row = next(line for line in high_section.splitlines() if line.startswith("| `split` "))
    assert [cell.strip() for cell in low_split_row.strip("|").split("|")][:2] == ["`split`", "`python`"]
    assert [cell.strip() for cell in high_split_row.strip("|").split("|")][:2] == ["`split`", "`agnostic`"]
    assert action_count == 5
    assert variant_count == 6
    assert all(not ({"definition_origin", "definition_path"} & set(summary.to_dict())) for summary in catalog.list_actions())


def test_catalogue_entries_are_read_only_and_keep_provenance_out_of_selection_objects(tmp_path, complete, file_data, write_file, load_catalog):
    source = tmp_path / "source"
    write_file(source, file_data(actions={"test": {"agnostic": complete(prompt_vars={"Target": "Path"}, prompt="Check %Target%.")}}))
    catalog = load_catalog(source)

    summary = next(summary for summary in catalog.list_actions() if summary.name == "test")
    action = catalog.inspect("test[agnostic]").action
    entry = next(entry for entry in catalog.catalogue_entries() if entry.name == "test")
    assert not hasattr(summary, "_definition_origin")
    assert not hasattr(action, "_definition_origin")
    assert entry.definition_source.kind == "explicit"
    assert entry.definition_source.directory == str(source)
    assert entry.definition_source.filename == "actions.json"
    assert entry.definition_source.source_order == 0
    assert isinstance(entry, catalog_module.ActionSummary)
    assert entry.to_dict() == summary.to_dict()
    with pytest.raises(AttributeError, match="ActionCatalogueEntry is immutable"):
        entry.name = "changed"
    with pytest.raises(AttributeError, match="ActionDefinitionSource is immutable"):
        entry.definition_source.filename = "changed.json"
    with pytest.raises(TypeError):
        entry.prompt_vars["Later"] = "value"


def test_catalogue_entries_snapshot_source_provenance_during_materialization(tmp_path, complete, file_data, write_file):
    first_directory = tmp_path / "first"
    earlier_directory = tmp_path / "earlier"
    write_file(first_directory, file_data(actions={"test": {"agnostic": complete()}}))
    earlier_directory.mkdir()
    source = discovery_module.SourceDirectory("explicit", str(first_directory))
    first_catalog = catalog_module.load_action_catalog(action_directories=[source])
    before_entries = first_catalog.catalogue_entries()
    before_rendered = action_catalogue.render_action_catalogue(before_entries)[0]

    catalog_module.load_action_catalog(action_directories=[str(earlier_directory), source])

    after_entries = first_catalog.catalogue_entries()
    test_entry = next(entry for entry in after_entries if entry.name == "test")
    assert test_entry.definition_source.source_order == 0
    assert test_entry.definition_source.directory == str(first_directory)
    assert action_catalogue.render_action_catalogue(after_entries)[0] == before_rendered


def test_portable_json_sources_prefer_repository_paths_then_semantic_roots(tmp_path, complete, file_data, write_file):
    repository = tmp_path / "repository"
    sources = [
        ("explicit", repository / ".codex" / "toolkit_perform_actions", "inside"),
        ("bundled", tmp_path / "bundled", "bundled"),
        ("system", tmp_path / "system", "system"),
        ("user", tmp_path / "user", "user"),
        ("repository", tmp_path / "external-repository", "repository"),
        ("explicit", tmp_path / "arbitrary", "explicit"),
    ]
    for _kind, directory, action in sources:
        write_file(directory, file_data(actions={action: {"agnostic": complete(gloss=action)}}))
    catalog = catalog_module.load_action_catalog(action_directories=[(kind, str(directory)) for kind, directory, _action in sources])
    catalog.discovery.repository_root = str(repository)

    rendered = render_catalog(catalog)[0]
    assert "**JSON source:** `./.codex/toolkit_perform_actions/actions.json`" in rendered
    assert "**JSON source:** `<bundled-actions>/actions.json`" in rendered
    assert "**JSON source:** `<system-actions>/actions.json`" in rendered
    assert "**JSON source:** `$CODEX_HOME/toolkit_perform_actions/actions.json`" in rendered
    assert "**JSON source:** `<repository-actions>/actions.json`" in rendered
    assert "**JSON source:** `<source-6>/actions.json`" in rendered
    assert str(tmp_path) not in rendered


@pytest.mark.parametrize("filenames", [("actions.json", "actions.json"), ("first.json", "second.json")])
def test_colliding_semantic_sources_fall_back_to_unique_source_ordinals(tmp_path, complete, file_data, write_file, filenames):
    first = tmp_path / "first"
    second = tmp_path / "second"
    write_file(first, file_data(actions={"first": {"agnostic": complete()}}), filenames[0])
    write_file(second, file_data(actions={"second": {"agnostic": complete()}}), filenames[1])
    catalog = catalog_module.load_action_catalog(action_directories=[("user", str(first)), ("user", str(second))])

    rendered = render_catalog(catalog)[0]
    assert "**JSON source:** `<source-1>/{}`".format(filenames[0]) in rendered
    assert "**JSON source:** `<source-2>/{}`".format(filenames[1]) in rendered
    assert "$CODEX_HOME" not in rendered


def test_multiple_files_in_one_semantic_source_keep_the_semantic_root(tmp_path, complete, file_data, write_file):
    source = tmp_path / "user"
    write_file(source, file_data(actions={"first": {"agnostic": complete()}}), "first.json")
    write_file(source, file_data(actions={"second": {"agnostic": complete()}}), "second.json")
    catalog = catalog_module.load_action_catalog(action_directories=[("user", str(source))])

    rendered = render_catalog(catalog)[0]
    assert "**JSON source:** `$CODEX_HOME/toolkit_perform_actions/first.json`" in rendered
    assert "**JSON source:** `$CODEX_HOME/toolkit_perform_actions/second.json`" in rendered
    assert "<source-1>" not in rendered


def test_control_escapes_and_literal_backslashes_keep_distinct_source_labels(tmp_path, complete, file_data, write_file, load_catalog):
    source = tmp_path / "source"
    write_file(source, file_data(actions={"control": {"agnostic": complete()}}), "line\nbreak.json")
    write_file(source, file_data(actions={"literal": {"agnostic": complete()}}), "line\\nbreak.json")
    catalog = load_catalog(source)

    rendered = render_catalog(catalog)[0]
    assert "## `line\\nbreak.json`" in rendered
    assert "## `line\\\\nbreak.json`" in rendered
    assert rendered.count("## `line") == 2


def test_repository_relative_surrogate_path_writes_valid_utf8(tmp_path, complete, file_data, write_file, load_catalog):
    repository = tmp_path / "repository"
    source = repository / "source-{}".format(os.fsdecode(b"\xff"))
    write_file(source, file_data(actions={"test": {"agnostic": complete()}}))
    catalog = load_catalog(source)
    catalog.discovery.repository_root = str(repository)
    output = tmp_path / "catalogue.md"

    action_catalogue.write_action_catalogue(catalog, output=str(output))

    content = output.read_bytes()
    assert b"**JSON source:** `./source-\\udcff/actions.json`" in content
    content.decode("utf-8")


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
    with pytest.raises(diagnostics_module.PerformRequestError) as projection_error:
        catalog.catalogue_entries()
    assert projection_error.value.status == "fatal_catalog"
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
    markdown = output.read_text(encoding="utf-8")
    assert all(diagnostic not in markdown for payload in payloads for diagnostic in payload["diagnostics"])
