"""Fixtures for nested pytest-isolation plugin behavior tests."""

import os
import pathlib
import shutil

import pytest

REPOSITORY_ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC_ROOT = REPOSITORY_ROOT / "src"
PLUGIN = "la_dev_codex_plugins.pytest_isolation.plugin"


@pytest.fixture
def remove_preserved_boundary():
    """Return a cleanup helper for intentionally preserved guarded trees."""

    def restore_permissions(path):
        if path.is_symlink():
            return
        if path.is_dir():
            path.chmod(0o700)
            for child in path.iterdir():
                restore_permissions(child)
            return
        path.chmod(0o600)

    def remove(path):
        restore_permissions(path)
        shutil.rmtree(str(path))

    return remove


@pytest.fixture
def run_isolation(pytester, monkeypatch):
    """Return a subprocess pytest runner with the source package importable."""
    existing = os.environ.get("PYTHONPATH")
    pythonpath = str(SRC_ROOT) if not existing else str(SRC_ROOT) + os.pathsep + existing
    monkeypatch.setenv("PYTHONPATH", pythonpath)
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")

    def run(source=None, *arguments, load_plugin=True, conftest=None, config=None, files=None):
        if source is not None:
            pytester.makepyfile(test_isolation=source)
        if conftest is not None:
            pytester.makeconftest(conftest)
        if config is not None:
            pytester.makeini(config)
        if files is not None:
            for relative, contents in files.items():
                path = pytester.path / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(contents, encoding="utf-8")
        options = ["-q"]
        if load_plugin:
            options.extend(("-p", PLUGIN))
        options.extend(arguments)
        return pytester.runpytest_subprocess(*options)

    return run
