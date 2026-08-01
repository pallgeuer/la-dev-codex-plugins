"""Shared pytest configuration and repository fixtures."""

import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

pytest_plugins = ("la_dev_codex_plugins.pytest_isolation.plugin", "pytester")
