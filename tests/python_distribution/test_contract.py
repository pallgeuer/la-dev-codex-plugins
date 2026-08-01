"""Tests for the minimal installable Python distribution contract."""

import configparser
import importlib.util
import os
import pathlib

REPOSITORY_ROOT = pathlib.Path(__file__).resolve().parents[2]
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
    assert dict(parser.items("options.entry_points")) == {
        "console_scripts": "\nla-dev-markdown-tables = la_dev_codex_plugins.markdown_tables.cli:main\nla-dev-release-checksums = la_dev_codex_plugins.release_checksums.cli:main",
    }
    assert dict(parser.items("options.extras_require")) == {
        "dev": "\npytest>=7.0.1",
        "pytest": "\npytest>=7.0.1",
    }
    assert "pytest11" not in SETUP_CONFIG.read_text(encoding="ascii")


def test_installed_bootstrap_is_executable_and_reexecutes_isolated_module():
    contents = INSTALLED_BOOTSTRAP.read_text(encoding="ascii")
    assert contents.startswith("#!python\n")
    assert '"-I", "-m", "la_dev_codex_plugins.codex_perform.cli"' in contents
    assert os.access(str(INSTALLED_BOOTSTRAP), os.X_OK)


def test_source_bootstrap_is_excluded_from_installable_package():
    assert SOURCE_BOOTSTRAP.is_file()
    validator = load_validator()
    assert not any(pathlib.PurePosixPath(path).parts[:2] == ("la_dev_codex_plugins", "cli") for path in validator.PACKAGE_FILES)
    assert "la_dev_codex_plugins/_filesystem.py" in validator.PACKAGE_FILES
    assert "la_dev_codex_plugins/_process.py" in validator.PACKAGE_FILES
    assert "la_dev_codex_plugins/codex_perform/cli.py" in validator.PACKAGE_FILES
    assert "la_dev_codex_plugins/pytest_isolation/plugin.py" in validator.PACKAGE_FILES
    assert "source_launcher/codex_perform.py" not in validator.SDIST_FILES


def test_sdist_manifest_includes_only_dedicated_distribution_tests():
    manifest = (REPOSITORY_ROOT / "MANIFEST.in").read_text(encoding="ascii")
    assert "prune tests\n" in manifest
    assert "include tests/python_distribution/smoke_*.py\n" in manifest
    assert "recursive-include tests/python_distribution *.py\n" not in manifest
    assert "tests/python_distribution/test_contract.py" not in load_validator().SDIST_FILES
    assert {path for path in load_validator().SDIST_FILES if path.startswith("tests/python_distribution/")} == {
        "tests/python_distribution/smoke_installed_package.py",
        "tests/python_distribution/smoke_pytest_isolation.py",
    }
    assert not any(line.startswith(("include plugins", "recursive-include plugins", "graft plugins")) for line in manifest.splitlines())
    assert not any(line.startswith(("include source_launcher", "recursive-include source_launcher", "graft source_launcher")) for line in manifest.splitlines())


def test_sdist_package_inventory_is_derived_from_wheel_package_files():
    validator = load_validator()
    package_entries = {path for path in validator.SDIST_FILES if path.startswith("src/la_dev_codex_plugins/")}

    assert package_entries == {"src/{}".format(path) for path in validator.PACKAGE_FILES}
    assert validator.SDIST_NON_PACKAGE_FILES | package_entries == validator.SDIST_FILES
