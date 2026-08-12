"""Bundled project-setup action and guidance mirror tests."""

import pathlib

REPOSITORY_ROOT = pathlib.Path(__file__).resolve().parents[5]
SKILL_ROOT = REPOSITORY_ROOT / "plugins" / "toolkit" / "skills" / "perform"
BUNDLED_ACTIONS = SKILL_ROOT / "assets" / "toolkit_perform_actions"


def test_project_setup_guidance_mirrors_are_current():
    """Keep offline audit references byte-identical to the public guides."""
    for filename in ("project_setup_agnostic.md", "project_setup_python.md"):
        assert (SKILL_ROOT / "references" / filename).read_bytes() == (REPOSITORY_ROOT / "docs" / filename).read_bytes()


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
