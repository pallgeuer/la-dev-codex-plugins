"""Tests for the repository Codex plugin manifest validator."""

import json
import pathlib
import subprocess
import sys

import pytest

REPOSITORY_ROOT = pathlib.Path(__file__).resolve().parents[2]
VALIDATOR = REPOSITORY_ROOT / "scripts" / "validate_plugin_manifests.py"
REPOSITORY_URL = "https://github.com/pallgeuer/la-dev-codex-plugins"
LATEST_DOCUMENTATION_URL_PREFIX = REPOSITORY_URL + "/blob/main/"
PRIVACY_POLICY_URL = REPOSITORY_URL + "/blob/main/PRIVACY.md"
TERMS_OF_SERVICE_URL = REPOSITORY_URL + "/blob/main/TERMS.md"
SUPPORT_URL = REPOSITORY_URL + "/issues"
SQUARE_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><path d="M0 0h64v64H0z"/></svg>\n'


def plugin_manifest(name="alpha", guide="docs/alpha.md"):
    homepage = LATEST_DOCUMENTATION_URL_PREFIX + guide
    return {
        "name": name,
        "version": "0.1.0",
        "description": "Reusable repository analysis for Codex.",
        "author": {"name": "Philipp Allgeuer", "url": "https://github.com/pallgeuer"},
        "homepage": homepage,
        "repository": REPOSITORY_URL,
        "license": "MIT",
        "keywords": ["codex analysis", "repository"],
        "skills": "./skills/",
        "interface": {
            "displayName": "Alpha Analysis",
            "shortDescription": "Analyze a repository.",
            "longDescription": "Runs reusable repository analysis workflows in Codex.",
            "developerName": "Philipp Allgeuer",
            "category": "Productivity",
            "capabilities": ["Read"],
            "websiteURL": homepage,
            "privacyPolicyURL": PRIVACY_POLICY_URL,
            "termsOfServiceURL": TERMS_OF_SERVICE_URL,
            "supportURL": SUPPORT_URL,
            "brandColor": "#005A80",
            "brandColorDark": "#60D0C0",
            "composerIcon": "./assets/composer-icon.svg",
            "logo": "./assets/logo.svg",
            "logoDark": "./assets/logo-dark.svg",
            "defaultPrompt": ["$alpha:analyze"],
        },
    }


def marketplace_entry(name="alpha"):
    return {
        "name": name,
        "source": {"source": "local", "path": "./plugins/{}".format(name)},
        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        "category": "Productivity",
    }


def write_fixture(repository):
    manifest_path = repository / "plugins" / "alpha" / ".codex-plugin" / "plugin.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps(plugin_manifest(), indent=2) + "\n", encoding="utf-8")
    skill_path = repository / "plugins" / "alpha" / "skills" / "analyze" / "SKILL.md"
    skill_path.parent.mkdir(parents=True)
    skill_path.write_text("---\nname: analyze\ndescription: Analyze a repository.\n---\n", encoding="utf-8")
    plugin_root = manifest_path.parents[1]
    for filename in ("README.md", "LICENSE", "SECURITY.md", ".codexignore"):
        (plugin_root / filename).write_text("fixture\n", encoding="utf-8")
    assets_path = plugin_root / "assets"
    assets_path.mkdir()
    for filename in ("composer-icon.svg", "logo.svg", "logo-dark.svg"):
        (assets_path / filename).write_text(SQUARE_SVG, encoding="utf-8")
    guide_path = repository / "docs" / "alpha.md"
    guide_path.parent.mkdir(parents=True)
    guide_path.write_text("# Alpha analysis\n", encoding="utf-8")
    marketplace_path = repository / ".agents" / "plugins" / "marketplace.json"
    marketplace_path.parent.mkdir(parents=True)
    marketplace = {"name": "la-dev-codex-plugins", "interface": {"displayName": "Plugin marketplace"}, "plugins": [marketplace_entry()]}
    marketplace_path.write_text(json.dumps(marketplace, indent=2) + "\n", encoding="utf-8")
    return manifest_path, marketplace_path


def run_validator(repository):
    return subprocess.run([sys.executable, str(VALIDATOR), "--repo-root", str(repository)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, check=False)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def set_nested(value, path, replacement):
    target = value
    for field in path[:-1]:
        target = target[field]
    target[path[-1]] = replacement


def test_current_repository_manifests_are_valid():
    completed = run_validator(REPOSITORY_ROOT)
    assert completed.returncode == 0, completed.stderr


def test_missing_default_prompt_uses_canonical_diagnostic(tmp_path):
    manifest_path, _ = write_fixture(tmp_path)
    manifest = read_json(manifest_path)
    del manifest["interface"]["defaultPrompt"]
    write_json(manifest_path, manifest)
    completed = run_validator(tmp_path)
    assert completed.returncode == 1
    assert "field 'defaultPrompt'" in completed.stderr
    assert "field 'default_prompt'" not in completed.stderr


def test_legacy_default_prompt_alias_remains_valid(tmp_path):
    manifest_path, _ = write_fixture(tmp_path)
    manifest = read_json(manifest_path)
    manifest["interface"]["default_prompt"] = manifest["interface"].pop("defaultPrompt")
    write_json(manifest_path, manifest)
    completed = run_validator(tmp_path)
    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize(
    ("path", "replacement", "diagnostic"),
    [
        (("version",), "0.1", "stable X.Y.Z"),
        (("author", "name"), "Unknown", "canonical publisher"),
        (("homepage",), "https://example.com/alpha", "canonical main branch"),
        (("keywords",), ["repository", "repository"], "must be unique"),
        (("skills",), "./../skills", "remain inside the plugin root"),
        (("skills",), "./missing/", "existing directory"),
        (("interface", "websiteURL"), "https://example.com/alpha", "must match the direct product homepage"),
        (("interface", "privacyPolicyURL"), "https://example.com/privacy", "canonical repository page"),
        (("interface", "displayName"), "x" * 31, "at most 30 characters"),
        (("interface", "shortDescription"), "first\nsecond", "fit on one line"),
        (("interface", "capabilities"), ["x" * 121], "must not exceed 120 characters"),
        (("interface", "brandColor"), "#FFFFFF", "at least 2:1 contrast"),
        (("interface", "brandColorDark"), "#212121", "at least 2:1 contrast"),
        (("interface", "defaultPrompt"), ["first\nsecond"], "must fit on one line"),
        (("interface", "defaultPrompt"), ["one", "two", "three", "four"], "at most 3"),
    ],
)
def test_manifest_contract_rejects_invalid_metadata(tmp_path, path, replacement, diagnostic):
    manifest_path, _ = write_fixture(tmp_path)
    manifest = read_json(manifest_path)
    set_nested(manifest, path, replacement)
    write_json(manifest_path, manifest)
    completed = run_validator(tmp_path)
    assert completed.returncode == 1
    assert diagnostic in completed.stderr


def test_manifest_contract_rejects_unsupported_fields(tmp_path):
    manifest_path, _ = write_fixture(tmp_path)
    manifest = read_json(manifest_path)
    manifest["dependencies"] = []
    write_json(manifest_path, manifest)
    completed = run_validator(tmp_path)
    assert completed.returncode == 1
    assert "unsupported field 'dependencies'" in completed.stderr


def test_manifest_contract_rejects_malformed_json(tmp_path):
    manifest_path, _ = write_fixture(tmp_path)
    manifest_path.write_text("{", encoding="utf-8")
    completed = run_validator(tmp_path)
    assert completed.returncode == 1
    assert "readable UTF-8 JSON" in completed.stderr


def test_manifest_contract_rejects_missing_documentation(tmp_path):
    write_fixture(tmp_path)
    (tmp_path / "docs" / "alpha.md").unlink()
    completed = run_validator(tmp_path)
    assert completed.returncode == 1
    assert "missing local documentation" in completed.stderr


def test_manifest_contract_rejects_missing_standalone_package_file(tmp_path):
    manifest_path, _ = write_fixture(tmp_path)
    (manifest_path.parents[1] / "SECURITY.md").unlink()
    completed = run_validator(tmp_path)
    assert completed.returncode == 1
    assert "standalone plugin package file must be a regular file" in completed.stderr


@pytest.mark.parametrize(
    ("contents", "diagnostic"),
    [
        ("not xml\n", "readable SVG XML"),
        ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"/>\n', "at least 48 by 48"),
        ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 32"/>\n', "positive square SVG viewBox"),
        ('<html xmlns="http://www.w3.org/1999/xhtml"/>\n', "SVG root element"),
    ],
)
def test_manifest_contract_rejects_invalid_svg_assets(tmp_path, contents, diagnostic):
    manifest_path, _ = write_fixture(tmp_path)
    asset_path = manifest_path.parents[1] / "assets" / "logo.svg"
    asset_path.write_text(contents, encoding="utf-8")
    completed = run_validator(tmp_path)
    assert completed.returncode == 1
    assert diagnostic in completed.stderr


def test_manifest_contract_rejects_component_symlink_outside_plugin(tmp_path):
    manifest_path, _ = write_fixture(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (manifest_path.parents[1] / "linked-skills").symlink_to(outside, target_is_directory=True)
    manifest = read_json(manifest_path)
    manifest["skills"] = "./linked-skills/"
    write_json(manifest_path, manifest)
    completed = run_validator(tmp_path)
    assert completed.returncode == 1
    assert "resolves outside the plugin root" in completed.stderr


@pytest.mark.parametrize(
    ("mutation", "diagnostic"),
    [
        ("missing", "has no marketplace registration"),
        ("duplicate", "registered more than once"),
        ("source", "must match the plugin identity"),
        ("policy", "unsupported policy"),
        ("category", "must match the plugin interface category"),
    ],
)
def test_marketplace_contract_rejects_registration_errors(tmp_path, mutation, diagnostic):
    _, marketplace_path = write_fixture(tmp_path)
    marketplace = read_json(marketplace_path)
    if mutation == "missing":
        marketplace["plugins"] = []
    elif mutation == "duplicate":
        marketplace["plugins"].append(marketplace_entry())
    elif mutation == "source":
        marketplace["plugins"][0]["source"]["path"] = "./plugins/other"
    elif mutation == "policy":
        marketplace["plugins"][0]["policy"]["installation"] = "UNKNOWN"
    elif mutation == "category":
        marketplace["plugins"][0]["category"] = "Other"
    write_json(marketplace_path, marketplace)
    completed = run_validator(tmp_path)
    assert completed.returncode == 1
    assert diagnostic in completed.stderr


def test_missing_skills_directory_does_not_report_missing_skill_manifest(tmp_path):
    manifest_path, _ = write_fixture(tmp_path)
    manifest = read_json(manifest_path)
    manifest["skills"] = "./missing/"
    write_json(manifest_path, manifest)
    completed = run_validator(tmp_path)
    assert completed.returncode == 1
    assert "existing directory" in completed.stderr
    assert "contain at least one" not in completed.stderr


def test_stray_plugin_directory_reports_missing_manifest(tmp_path):
    write_fixture(tmp_path)
    (tmp_path / "plugins" / "scratch").mkdir()
    completed = run_validator(tmp_path)
    assert completed.returncode == 1
    assert "plugins/scratch/.codex-plugin/plugin.json" in completed.stderr
    assert "plugin manifest is missing" in completed.stderr
    assert "Errno 2" not in completed.stderr


@pytest.mark.parametrize("url", ["https://[", "https://@", "https://example .com", "https://example.com:bad", "https:///missing-host"])
def test_manifest_contract_rejects_malformed_https_urls_without_tracebacks(tmp_path, url):
    manifest_path, _ = write_fixture(tmp_path)
    manifest = read_json(manifest_path)
    manifest["interface"]["privacyPolicyURL"] = url
    write_json(manifest_path, manifest)
    completed = run_validator(tmp_path)
    assert completed.returncode == 1
    assert "absolute HTTPS URL" in completed.stderr
    assert "Traceback" not in completed.stderr


def test_manifest_contract_parses_https_url_with_valid_port(tmp_path):
    manifest_path, _ = write_fixture(tmp_path)
    manifest = read_json(manifest_path)
    manifest["interface"]["privacyPolicyURL"] = "https://example.com:443/privacy"
    write_json(manifest_path, manifest)
    completed = run_validator(tmp_path)
    assert completed.returncode == 1
    assert "canonical repository page" in completed.stderr
    assert "absolute HTTPS URL" not in completed.stderr


@pytest.mark.parametrize(
    ("payload", "diagnostic"),
    [
        ([], "must contain a JSON object"),
        ({}, "field 'apps' must be an object"),
        ({"apps": []}, "field 'apps' must be an object"),
        ({"apps": {"docs": "broken"}}, "must be an object"),
        ({"apps": {"docs": {"id": "broken"}}}, "supported registered app identifier"),
        ({"apps": {"docs": {"id": "connector_docs", "optional": "yes"}}}, "field 'optional' must be a boolean"),
    ],
)
def test_manifest_contract_rejects_invalid_app_manifests(tmp_path, payload, diagnostic):
    manifest_path, _ = write_fixture(tmp_path)
    manifest = read_json(manifest_path)
    manifest["apps"] = "./.app.json"
    write_json(manifest_path, manifest)
    write_json(manifest_path.parents[1] / ".app.json", payload)
    completed = run_validator(tmp_path)
    assert completed.returncode == 1
    assert diagnostic in completed.stderr


def test_manifest_contract_rejects_malformed_app_json(tmp_path):
    manifest_path, _ = write_fixture(tmp_path)
    manifest = read_json(manifest_path)
    manifest["apps"] = "./.app.json"
    write_json(manifest_path, manifest)
    (manifest_path.parents[1] / ".app.json").write_text("{", encoding="utf-8")
    completed = run_validator(tmp_path)
    assert completed.returncode == 1
    assert "readable UTF-8 JSON" in completed.stderr


def test_manifest_contract_accepts_required_app_shape(tmp_path):
    manifest_path, _ = write_fixture(tmp_path)
    manifest = read_json(manifest_path)
    manifest["apps"] = "./.app.json"
    write_json(manifest_path, manifest)
    write_json(manifest_path.parents[1] / ".app.json", {"apps": {"docs": {"id": "connector_docs", "optional": False, "required": True}}})
    completed = run_validator(tmp_path)
    assert completed.returncode == 0, completed.stderr


def test_manifest_contract_rejects_inline_mcp_servers(tmp_path):
    manifest_path, _ = write_fixture(tmp_path)
    manifest = read_json(manifest_path)
    manifest["mcpServers"] = {"docs": {}}
    write_json(manifest_path, manifest)
    completed = run_validator(tmp_path)
    assert completed.returncode == 1
    assert "relative plugin path" in completed.stderr


@pytest.mark.parametrize(
    ("payload", "diagnostic"),
    [
        ([], "must contain a JSON object"),
        ({}, "field 'mcpServers' must be an object"),
        ({"mcpServers": []}, "field 'mcpServers' must be an object"),
        ({"mcpServers": {"": {}}}, "server names must be nonempty strings"),
        ({"mcpServers": {"docs": "broken"}}, "must be an object"),
    ],
)
def test_manifest_contract_rejects_invalid_mcp_manifests(tmp_path, payload, diagnostic):
    manifest_path, _ = write_fixture(tmp_path)
    manifest = read_json(manifest_path)
    manifest["mcpServers"] = "./.mcp.json"
    write_json(manifest_path, manifest)
    write_json(manifest_path.parents[1] / ".mcp.json", payload)
    completed = run_validator(tmp_path)
    assert completed.returncode == 1
    assert diagnostic in completed.stderr


def test_manifest_contract_accepts_required_mcp_shape(tmp_path):
    manifest_path, _ = write_fixture(tmp_path)
    manifest = read_json(manifest_path)
    manifest["mcpServers"] = "./.mcp.json"
    write_json(manifest_path, manifest)
    write_json(manifest_path.parents[1] / ".mcp.json", {"mcpServers": {"docs": {"command": "example"}}})
    completed = run_validator(tmp_path)
    assert completed.returncode == 0, completed.stderr


def test_manifest_contract_rejects_symlinked_plugin_root(tmp_path):
    write_fixture(tmp_path)
    plugin_root = tmp_path / "plugins" / "alpha"
    external_root = tmp_path / "external-alpha"
    plugin_root.rename(external_root)
    plugin_root.symlink_to(external_root, target_is_directory=True)
    completed = run_validator(tmp_path)
    assert completed.returncode == 1
    assert "plugin directories must not use symbolic links" in completed.stderr


def test_manifest_contract_rejects_symlinked_manifest_directory(tmp_path):
    manifest_path, _ = write_fixture(tmp_path)
    manifest_directory = manifest_path.parent
    real_manifest_directory = manifest_directory.with_name("real-manifest")
    manifest_directory.rename(real_manifest_directory)
    manifest_directory.symlink_to(real_manifest_directory, target_is_directory=True)
    completed = run_validator(tmp_path)
    assert completed.returncode == 1
    assert "manifest directory must not use symbolic links" in completed.stderr


def test_manifest_contract_rejects_symlinked_manifest(tmp_path):
    manifest_path, _ = write_fixture(tmp_path)
    real_manifest_path = manifest_path.with_name("real-plugin.json")
    manifest_path.rename(real_manifest_path)
    manifest_path.symlink_to(real_manifest_path)
    completed = run_validator(tmp_path)
    assert completed.returncode == 1
    assert "plugin manifest must not use symbolic links" in completed.stderr


def test_manifest_contract_rejects_symlinked_skill_directory(tmp_path):
    manifest_path, _ = write_fixture(tmp_path)
    skill_path = manifest_path.parents[1] / "skills" / "analyze"
    real_skill_path = skill_path.with_name("real-analyze")
    skill_path.rename(real_skill_path)
    skill_path.symlink_to(real_skill_path, target_is_directory=True)
    completed = run_validator(tmp_path)
    assert completed.returncode == 1
    assert "skill directories must not use symbolic links" in completed.stderr


def test_manifest_contract_rejects_symlinked_skill_manifest(tmp_path):
    manifest_path, _ = write_fixture(tmp_path)
    skill_manifest = manifest_path.parents[1] / "skills" / "analyze" / "SKILL.md"
    real_skill_manifest = skill_manifest.with_name("REAL_SKILL.md")
    skill_manifest.rename(real_skill_manifest)
    skill_manifest.symlink_to(real_skill_manifest)
    completed = run_validator(tmp_path)
    assert completed.returncode == 1
    assert "skill manifests must not use symbolic links" in completed.stderr


def test_manifest_contract_rejects_symlinked_documentation(tmp_path):
    write_fixture(tmp_path)
    guide_path = tmp_path / "docs" / "alpha.md"
    real_guide_path = tmp_path / "real-alpha.md"
    guide_path.rename(real_guide_path)
    guide_path.symlink_to(real_guide_path)
    completed = run_validator(tmp_path)
    assert completed.returncode == 1
    assert "documentation through symbolic links" in completed.stderr


def test_manifest_contract_rejects_symlinked_component_file(tmp_path):
    manifest_path, _ = write_fixture(tmp_path)
    manifest = read_json(manifest_path)
    manifest["apps"] = "./.app.json"
    write_json(manifest_path, manifest)
    real_app_path = manifest_path.parents[1] / "real-app.json"
    write_json(real_app_path, {"apps": {}})
    (manifest_path.parents[1] / ".app.json").symlink_to(real_app_path)
    completed = run_validator(tmp_path)
    assert completed.returncode == 1
    assert "must not use symbolic links" in completed.stderr


def test_manifest_contract_rejects_symlinked_asset(tmp_path):
    manifest_path, _ = write_fixture(tmp_path)
    asset_directory = manifest_path.parents[1] / "assets"
    asset_directory.mkdir(exist_ok=True)
    real_logo_path = asset_directory / "real-logo.png"
    real_logo_path.write_bytes(b"png")
    (asset_directory / "logo.png").symlink_to(real_logo_path)
    manifest = read_json(manifest_path)
    manifest["interface"]["logo"] = "./assets/logo.png"
    write_json(manifest_path, manifest)
    completed = run_validator(tmp_path)
    assert completed.returncode == 1
    assert "must not use symbolic links" in completed.stderr


@pytest.mark.parametrize("product", ["ATLAS", "CHATGPT", "CODEX"])
def test_marketplace_contract_accepts_supported_products(tmp_path, product):
    _, marketplace_path = write_fixture(tmp_path)
    marketplace = read_json(marketplace_path)
    marketplace["plugins"][0]["policy"]["products"] = [product]
    write_json(marketplace_path, marketplace)
    completed = run_validator(tmp_path)
    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize("products", [["UNKNOWN"], ["codex"], ["CODEX", "CODEX"]])
def test_marketplace_contract_rejects_invalid_products(tmp_path, products):
    _, marketplace_path = write_fixture(tmp_path)
    marketplace = read_json(marketplace_path)
    marketplace["plugins"][0]["policy"]["products"] = products
    write_json(marketplace_path, marketplace)
    completed = run_validator(tmp_path)
    assert completed.returncode == 1
