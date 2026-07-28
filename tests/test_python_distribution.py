"""Tests for the minimal installable Python distribution contract."""

import configparser
import importlib.util
import os
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SETUP_CONFIG = REPOSITORY_ROOT / "setup.cfg"
INSTALLED_BOOTSTRAP = REPOSITORY_ROOT / "package_scripts" / "codex-perform"
SOURCE_BOOTSTRAP = REPOSITORY_ROOT / "source_launcher" / "codex_perform.py"
VALIDATOR = REPOSITORY_ROOT / "scripts" / "validate_python_distribution.py"


def load_validator():
    """Load the distribution validator as an importable module."""
    spec = importlib.util.spec_from_file_location("validate_python_distribution", VALIDATOR)
    if spec is None or spec.loader is None:
        raise AssertionError("Could not load {}".format(VALIDATOR))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_setup_declares_dependency_free_python36_package_and_script():
    parser = configparser.ConfigParser()
    assert parser.read(SETUP_CONFIG, encoding="utf-8")
    assert parser["metadata"]["name"] == "la-dev-codex-plugins"
    assert parser["metadata"]["long_description"] == "file: PYPI.md"
    assert parser["options"]["python_requires"] == ">=3.6"
    assert not parser["options"]["install_requires"].strip()
    assert parser["options"]["scripts"].split() == ["package_scripts/codex-perform"]


def test_installed_bootstrap_is_executable_and_reexecutes_isolated_module():
    contents = INSTALLED_BOOTSTRAP.read_text(encoding="ascii")
    assert contents.startswith("#!python\n")
    assert '"-I", "-m", "la_dev_codex_plugins.cli.perform"' in contents
    assert os.access(str(INSTALLED_BOOTSTRAP), os.X_OK)


def test_source_bootstrap_is_excluded_from_installable_package():
    assert SOURCE_BOOTSTRAP.is_file()
    assert not (REPOSITORY_ROOT / "src" / "la_dev_codex_plugins" / "cli" / "_perform_bootstrap.py").exists()
    validator = load_validator()
    assert "la_dev_codex_plugins/cli/_perform_bootstrap.py" not in validator.PACKAGE_FILES
    assert "source_launcher/codex_perform.py" not in validator.SDIST_FILES


def test_sdist_manifest_includes_only_dedicated_distribution_tests():
    manifest = (REPOSITORY_ROOT / "MANIFEST.in").read_text(encoding="ascii")
    assert "prune tests\n" in manifest
    assert "recursive-include tests/python_package_distribution *.py\n" in manifest
    assert not any(line.startswith(("include plugins", "recursive-include plugins", "graft plugins")) for line in manifest.splitlines())
    assert not any(line.startswith(("include source_launcher", "recursive-include source_launcher", "graft source_launcher")) for line in manifest.splitlines())
