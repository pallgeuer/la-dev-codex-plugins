"""Tests for repository and plugin version declarations."""

import configparser
import json
import re
from pathlib import Path

import la_dev_codex_plugins

REPO_ROOT = Path(__file__).resolve().parents[1]
SEMVER_RE = re.compile(
    r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-(?:0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)(?:\.(?:0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*))*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)


def _assert_semver(label, version):
    assert isinstance(version, str), f"{label} version must be a string"
    assert SEMVER_RE.fullmatch(version), f"{label} version is not valid SemVer: {version!r}"


def _setup_version():
    config = configparser.ConfigParser()
    loaded = config.read(REPO_ROOT / "setup.cfg", encoding="utf-8")
    assert loaded
    return config["metadata"]["version"]


def test_repository_version_declarations_match_and_use_semver():
    setup_version = _setup_version()
    _assert_semver("repository", setup_version)
    assert la_dev_codex_plugins.__version__ == setup_version

    readme_lines = (REPO_ROOT / "README.md").read_text(encoding="utf-8").splitlines()
    assert readme_lines[2] == f"This repository is a Codex plugin marketplace, version {setup_version}."


def test_plugin_versions_use_semver():
    manifest_paths = sorted((REPO_ROOT / "plugins").glob("*/.codex-plugin/plugin.json"))
    assert manifest_paths

    for manifest_path in manifest_paths:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        _assert_semver(manifest_path.parent.parent.name, manifest.get("version"))
