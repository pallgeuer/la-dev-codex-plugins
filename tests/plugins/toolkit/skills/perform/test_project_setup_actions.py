"""Bundled project-setup action and guidance mirror tests."""

import json
import os
import pathlib
import shutil
import subprocess
import sys

import pytest

REPOSITORY_ROOT = pathlib.Path(__file__).resolve().parents[5]
SKILL_ROOT = REPOSITORY_ROOT / "plugins" / "toolkit" / "skills" / "perform"
BUNDLED_ACTIONS = SKILL_ROOT / "assets" / "toolkit_perform_actions"
SETUP_REFERENCES = SKILL_ROOT / "references" / "repository_setup"
SETUP_DOCUMENTS = (
    "AGENTS_user.md",
    "docs/new_repo_recipe.md",
    "docs/installation.md",
    "docs/recommended_setup.md",
    "docs/project_setup_agnostic.md",
    "docs/project_setup_python.md",
    "docs/ai_supported_development.md",
    "docs/markdown_tables.md",
    "docs/pytest_isolation.md",
    "docs/release_checksums.md",
    "docs/templates/release_python_github.md",
)


@pytest.mark.parametrize("relative_path", SETUP_DOCUMENTS)
def test_project_setup_guidance_mirrors_are_current(relative_path):
    """Keep bundled setup and audit references byte-identical to their sources."""
    assert (SETUP_REFERENCES / relative_path).read_bytes() == (REPOSITORY_ROOT / relative_path).read_bytes()


def test_project_setup_payload_preserves_the_selected_source_tree():
    """Ship every selected document in its source-relative location."""
    assert {path.relative_to(SETUP_REFERENCES).as_posix() for path in SETUP_REFERENCES.rglob("*.md")} == set(SETUP_DOCUMENTS)


def test_new_repository_setup_is_interactive_and_plan_only(load_catalog):
    """Expose recipe-led setup intake without allowing edits during planning."""
    catalog = load_catalog(BUNDLED_ACTIONS)
    inspection = catalog.inspect("setup-new-repo[agnostic]")
    fields = inspection.action.fields

    assert catalog.diagnostics == []
    assert inspection.to_dict()["mode"] == "plan"
    assert fields["model"] == "default"
    assert fields["reasoning_effort"] == "high"
    assert fields["plan_reasoning_effort"] == "high"
    assert fields["plan_mode"] is True
    assert fields["goal_mode"] is False
    assert fields["no_edits"] is True
    assert fields["requires_interactive"] is True
    assert fields["prompt_vars"] == {}
    assert fields["custom_codex_args"] == []


def test_copied_plugin_supports_setup_intake_from_an_empty_directory(tmp_path):
    """Resolve the setup action and read its bundled guides without a checkout."""
    plugin = tmp_path / "installed toolkit"
    shutil.copytree(SKILL_ROOT.parents[1], plugin, ignore=shutil.ignore_patterns("__pycache__"))
    skill = plugin / "skills" / "perform"
    target = tmp_path / "new repository"
    target.mkdir()
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    environment = {key: value for key, value in os.environ.items() if key not in ("PYTHONPATH", "PYTHONHOME", "CODEX_HOME")}
    environment["CODEX_HOME"] = str(codex_home)

    for script, arguments in (
        ("list_perform_actions.py", ["--name=setup-new-repo"]),
        ("get_perform_action.py", ["--inspect=setup-new-repo[agnostic]"]),
    ):
        completed = subprocess.run(
            [sys.executable, str(skill / "scripts" / script), *arguments], cwd=str(target), env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, check=False
        )
        assert completed.returncode == 0, completed.stderr
        assert completed.stderr == ""
        response = json.loads(completed.stdout)
        assert not response.get("diagnostics")
        if script == "list_perform_actions.py":
            assert [variant["selector"] for variant in response["variants"]] == ["setup-new-repo[agnostic]"]
        else:
            assert response["mode"] == "plan"
            assert "prompt_vars" not in response

    for relative_path in SETUP_DOCUMENTS:
        assert (skill / "references" / "repository_setup" / relative_path).read_bytes() == (SETUP_REFERENCES / relative_path).read_bytes()
    assert list(target.iterdir()) == []


def test_python_setup_uses_case_insensitive_pydocformatter_hook_filters():
    """Keep built-in and custom pydocformatter extension filters case-insensitive."""
    guidance = (REPOSITORY_ROOT / "docs" / "project_setup_python.md").read_text(encoding="utf-8")

    assert guidance.count(r"files: (?i)\.(?:py|pyi|pyw|md)$") == 2
    assert r"files: (?i)\.(?:py|pyi|pyw|md|rpy|mdx)$" in guidance
    assert r"files: \.(?:py|pyi|pyw|md" not in guidance


def test_project_setup_audit_variants_are_bundled_and_nonmutating(load_catalog):
    """Expose both high-effort setup audits without edit permission."""
    catalog = load_catalog(BUNDLED_ACTIONS)

    assert catalog.diagnostics == []
    for selector in ("audit-project-setup[agnostic]", "audit-project-setup[python]"):
        fields = catalog.inspect(selector).action.fields
        assert fields["reasoning_effort"] == "high"
        assert fields["plan_reasoning_effort"] == "high"
        assert fields["no_edits"] is True
        assert fields["requires_interactive"] is False
        assert fields["prompt_vars"] == {}


def test_publish_release_remains_an_interactive_editing_action(load_catalog):
    """Keep release execution interactive and capable of following its runbook."""
    catalog = load_catalog(BUNDLED_ACTIONS)
    fields = catalog.inspect("publish-release[agnostic]").action.fields

    assert fields["reasoning_effort"] == "high"
    assert fields["no_edits"] is False
    assert fields["requires_interactive"] is True
