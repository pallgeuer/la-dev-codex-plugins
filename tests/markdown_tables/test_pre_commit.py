"""Published and local Markdown table pre-commit hook tests."""

import pathlib

import la_dev_codex_plugins.markdown_tables.cli as markdown_cli

REPOSITORY_ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_published_manifest_defines_distinct_python_fix_and_check_hooks():
    manifest = (REPOSITORY_ROOT / ".pre-commit-hooks.yaml").read_text(encoding="utf-8")
    assert manifest.count("- id: markdown-tables-fix\n") == 1
    assert manifest.count("- id: markdown-tables-check\n") == 1
    assert "entry: la-dev-markdown-tables\n" in manifest
    assert "entry: la-dev-markdown-tables --check\n" in manifest
    assert manifest.count("language: python\n") == 2
    assert manifest.count("types: [markdown]\n") == 2
    assert "pass_filenames: false" not in manifest
    assert "additional_dependencies" not in manifest


def test_local_hooks_run_fix_before_check_and_accept_filenames():
    configuration = (REPOSITORY_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    fix = configuration.index("- id: markdown-tables-fix")
    check = configuration.index("- id: markdown-tables-check")
    ruff = configuration.index("- id: ruff-check-fix")
    assert fix < check < ruff
    assert configuration[fix:ruff].count("language: system") == 2
    assert configuration[fix:ruff].count("PYTHONPATH=src python3 -m la_dev_codex_plugins.markdown_tables.cli") == 2
    assert "stages: [pre-commit]" in configuration[fix:check]
    assert "stages: [pre-push, manual]" in configuration[check:ruff]


def test_fix_and_check_hook_behavior_on_fixture(tmp_path):
    path = tmp_path / "fixture.md"
    source = "| A|B |\n|-|-|\n"
    path.write_text(source, encoding="utf-8")

    assert markdown_cli.main(["--check", str(path)]) == 1
    assert path.read_text(encoding="utf-8") == source
    assert markdown_cli.main([str(path)]) == 0
    fixed = path.read_text(encoding="utf-8")
    assert fixed == "| A | B |\n|---|---|\n"
    assert markdown_cli.main(["--check", str(path)]) == 0
