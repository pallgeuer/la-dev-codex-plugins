"""Shared fixtures for Perform runtime and bundled-script tests."""

import importlib
import json
import sys
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
SKILL_ROOT = REPOSITORY_ROOT / "plugins" / "toolkit" / "skills" / "perform"
SCRIPTS_ROOT = SKILL_ROOT / "scripts"
BUNDLED_ACTIONS = SKILL_ROOT / "assets" / "toolkit_perform_actions"

sys.path.insert(0, str(SCRIPTS_ROOT))

catalog_module = importlib.import_module("toolkit_perform_runtime.catalog")


def complete_action(**overrides):
    """Return one independently valid complete implementation."""
    action = {
        "gloss": "Test action",
        "model": "default",
        "reasoning_effort": "medium",
        "goal_mode": False,
        "plan_mode": False,
        "plan_reasoning_effort": "medium",
        "no_edits": False,
        "prompt_vars": {},
        "prompt": "Perform the test action.",
        "requires_interactive": False,
        "custom_codex_args": [],
        "notes": "",
    }
    action.update(overrides)
    return action


def action_file(actions=None, ignore_actions=None, **root_overrides):
    """Return one version 1 file object."""
    data = {"version": 1, "ignore_actions": list(ignore_actions or []), "actions": actions or {}}
    data.update(root_overrides)
    return data


def write_action_file(directory, data, filename="actions.json"):
    """Write one deterministic JSON action fixture."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def write_raw_action_file(directory, text, filename="actions.json"):
    """Write raw JSON fixture text, including intentionally malformed cases."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    path.write_text(text, encoding="utf-8")
    return path


def load_explicit(*directories):
    """Load an explicit ordered list of temporary catalog sources."""
    return catalog_module.load_action_catalog(action_directories=[str(directory) for directory in directories])


@pytest.fixture
def complete():
    """Expose the complete-action builder to tests."""
    return complete_action


@pytest.fixture
def file_data():
    """Expose the action-file builder to tests."""
    return action_file


@pytest.fixture
def write_file():
    """Expose the JSON fixture writer to tests."""
    return write_action_file


@pytest.fixture
def write_raw():
    """Expose the raw JSON fixture writer to tests."""
    return write_raw_action_file


@pytest.fixture
def load_catalog():
    """Expose the explicit pure catalog loader to tests."""
    return load_explicit
