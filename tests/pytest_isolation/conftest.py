"""Fixtures for nested pytest-isolation plugin behavior tests."""

import os
import pathlib

import pytest

REPOSITORY_ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC_ROOT = REPOSITORY_ROOT / "src"
PLUGIN = "la_dev_codex_plugins.pytest_isolation.plugin"


@pytest.fixture
def run_isolation(pytester, monkeypatch):
    """Return a subprocess pytest runner with the source package importable."""
    existing = os.environ.get("PYTHONPATH")
    pythonpath = str(SRC_ROOT) if not existing else str(SRC_ROOT) + os.pathsep + existing
    monkeypatch.setenv("PYTHONPATH", pythonpath)
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")

    def run(source, *arguments, load_plugin=True, conftest=None):
        pytester.makepyfile(test_isolation=source)
        if conftest is not None:
            pytester.makeconftest(conftest)
        options = ["-q"]
        if load_plugin:
            options.extend(("-p", PLUGIN))
        options.extend(arguments)
        return pytester.runpytest_subprocess(*options)

    return run
