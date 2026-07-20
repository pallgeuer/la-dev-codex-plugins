"""Subprocess integration tests for the two bundled Perform entry scripts."""

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import SCRIPTS_ROOT

LIST_SCRIPT = SCRIPTS_ROOT / "list_perform_actions.py"
GET_SCRIPT = SCRIPTS_ROOT / "get_perform_action.py"


def clean_environment(tmp_path, codex_home=None):
    """Return an environment without repository-specific import configuration."""
    env = {key: value for key, value in os.environ.items() if key not in ("PYTHONPATH", "PYTHONHOME", "CODEX_HOME")}
    env["HOME"] = str(tmp_path / "home")
    home = Path(env["HOME"])
    home.mkdir(exist_ok=True)
    if codex_home is None:
        codex_home = tmp_path / "codex-home"
        codex_home.mkdir(exist_ok=True)
    env["CODEX_HOME"] = str(codex_home)
    return env


def run_script(script, arguments, cwd, env, input_bytes=None, executable_direct=False):
    """Run one bundled script from an arbitrary external working directory."""
    command = [str(script)] if executable_direct else [sys.executable, str(script)]
    command.extend(arguments)
    return subprocess.run(command, cwd=str(cwd), env=env, input=input_bytes, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def parse_stdout(completed):
    """Decode one JSON response from stdout."""
    return json.loads(completed.stdout.decode("utf-8"))


def user_catalog(codex_home, file_data, write_file, actions):
    """Write user-precedence actions for subprocess tests."""
    directory = codex_home / "toolkit_perform_actions"
    write_file(directory, file_data(actions=actions))
    return directory


def test_scripts_have_portable_shebang_and_executable_mode():
    for script in (LIST_SCRIPT, GET_SCRIPT):
        assert script.read_text(encoding="utf-8").startswith("#!/usr/bin/env python3\n")
        assert script.stat().st_mode & stat.S_IXUSR


def test_human_listing_from_outside_repository_uses_exact_action_lines(tmp_path):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    completed = run_script(LIST_SCRIPT, [], cwd, clean_environment(tmp_path), executable_direct=True)
    lines = completed.stdout.decode("utf-8").splitlines()
    assert completed.returncode == 0
    assert "find-todos[agnostic]: Enumerate all kinds of discernible TODOs in a repo" in lines
    assert "help[agnostic]: Explain Perform and its action-file format" in lines
    assert all(": " in line for line in lines)


def test_json_listing_envelope_and_name_filter_avoid_unrelated_actions(tmp_path):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    completed = run_script(LIST_SCRIPT, ["--name", "find-todos", "--json"], cwd, clean_environment(tmp_path))
    response = parse_stdout(completed)
    assert completed.returncode == 0
    assert response["schema_version"] == 1
    assert response["status"] == "ok"
    assert [variant["selector"] for variant in response["result"]["variants"]] == ["find-todos[agnostic]"]
    assert response["discovery"]["resolution_basis"] == "conventional_local"


def test_name_filter_miss_returns_soft_selection_fallback_signal(tmp_path):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    completed = run_script(LIST_SCRIPT, ["--name", "missing", "--json"], cwd, clean_environment(tmp_path))
    response = parse_stdout(completed)
    assert completed.returncode == 2
    assert response["status"] == "not_found"
    assert response["result"]["variants"] == []


def test_invalid_name_filter_is_request_error(tmp_path):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    completed = run_script(LIST_SCRIPT, ["--name", "Not Valid", "--json"], cwd, clean_environment(tmp_path))
    response = parse_stdout(completed)
    assert completed.returncode == 2
    assert response["status"] == "invalid_name"


def test_strict_selector_failure_reports_same_name_alternatives(tmp_path, complete, file_data, write_file):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    user_catalog(codex_home, file_data, write_file, {"language-action": {"python": complete(prompt="Python.")}})
    completed = run_script(GET_SCRIPT, ["--inspect", "language-action[rust]", "--json"], cwd, clean_environment(tmp_path, codex_home))
    response = parse_stdout(completed)
    assert completed.returncode == 2
    assert response["status"] == "not_found"
    assert response["result"]["available_variants"] == ["language-action[python]"]


@pytest.mark.parametrize("selector", ["find-todos", "find-todos[json,yaml]", "find-todos[agnostic]extra", "UPPER[python]"])
def test_get_accepts_only_canonical_strict_selectors(tmp_path, selector):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    completed = run_script(GET_SCRIPT, ["--inspect", selector, "--json"], cwd, clean_environment(tmp_path))
    response = parse_stdout(completed)
    assert completed.returncode == 2
    assert response["status"] == "invalid_selector"


def test_inspect_output_contains_exact_prompt_modes_notes_and_provenance(tmp_path):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    completed = run_script(GET_SCRIPT, ["--inspect", "md-goal[agnostic]", "--json"], cwd, clean_environment(tmp_path))
    response = parse_stdout(completed)
    result = response["result"]
    assert completed.returncode == 0
    assert response["status"] == "ok"
    assert result["selector"] == "md-goal[agnostic]"
    assert result["model"] == "default"
    assert result["reasoning_effort"] == "high"
    assert result["plan_reasoning_effort"] == "high"
    assert result["placeholders"] == ["%MarkdownPlanFile%"]
    assert result["goal_mode"] is True
    assert result["notes"]
    assert result["provenance"]["prompt"]["source_kind"] == "bundled"


def test_stdin_inspect_and_render_end_to_end(tmp_path, complete, file_data, write_file):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    user_catalog(
        codex_home,
        file_data,
        write_file,
        {"shell-data": {"agnostic": complete(prompt_vars={"%Value%": "Literal value"}, prompt="Handle %Value%.", notes="Visible note.")}},
    )
    env = clean_environment(tmp_path, codex_home)
    inspect_request = {"schema_version": 1, "operation": "inspect", "selector": "shell-data[agnostic]"}
    inspected = run_script(GET_SCRIPT, ["--request-json", "-", "--json"], cwd, env, json.dumps(inspect_request).encode("utf-8"))
    inspection = parse_stdout(inspected)["result"]
    assert inspection["base_prompt"] == "Handle %Value%."
    render_request = {
        "schema_version": 1,
        "operation": "render",
        "selector": "shell-data[agnostic]",
        "variables": {"%Value%": "quotes '` $() ; \\ \u03bb\nnext"},
        "qualification": "Restrict %Value% literally.",
    }
    rendered = run_script(GET_SCRIPT, ["--request-json", "-", "--json"], cwd, env, json.dumps(render_request).encode("utf-8"))
    response = parse_stdout(rendered)
    assert rendered.returncode == 0
    assert response["result"]["prompt"] == "Handle quotes '` $() ; \\ \u03bb\nnext.\n\nBUT: Restrict %Value% literally."
    assert response["result"]["notes"] == "Visible note."


def test_shell_like_stdin_values_never_execute_and_never_appear_in_command_line(tmp_path, complete, file_data, write_file):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    user_catalog(codex_home, file_data, write_file, {"shell-data": {"agnostic": complete(prompt_vars={"%Value%": "Value"}, prompt="Use %Value%.")}})
    env = clean_environment(tmp_path, codex_home)
    inspect_request = json.dumps({"schema_version": 1, "operation": "inspect", "selector": "shell-data[agnostic]"}).encode("utf-8")
    inspected = run_script(GET_SCRIPT, ["--request-json", "-", "--json"], cwd, env, inspect_request)
    assert inspected.returncode == 0
    marker = cwd / "must-not-exist"
    malicious = "$(touch {}) `touch {}` ; $HOME".format(marker, marker)
    request = {
        "schema_version": 1,
        "operation": "render",
        "selector": "shell-data[agnostic]",
        "variables": {"%Value%": malicious},
        "qualification": "Keep $(touch {}) literal.".format(marker),
    }
    command = [sys.executable, str(GET_SCRIPT), "--request-json", "-", "--json"]
    assert malicious not in command
    completed = subprocess.run(command, cwd=str(cwd), env=env, input=json.dumps(request).encode("utf-8"), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    assert completed.returncode == 0
    assert marker.exists() is False
    assert malicious in parse_stdout(completed)["result"]["prompt"]


@pytest.mark.parametrize(
    ("raw", "status"),
    [
        (b'{"schema_version":1,"schema_version":1,"operation":"inspect","selector":"find-todos[agnostic]"}', "duplicate_request_key"),
        (b'{"schema_version":1,"operation":"inspect","selector":"find-todos[agnostic]","extra":true}', "unknown_request_fields"),
        (b'{"schema_version":1,"operation":"inspect"}', "missing_request_fields"),
        (b'{"schema_version":true,"operation":"inspect","selector":"find-todos[agnostic]"}', "invalid_schema_version"),
        (b'{"schema_version":1,"operation":"unknown","selector":"find-todos[agnostic]"}', "invalid_operation"),
        (b"{", "invalid_request_json"),
        (b"{} trailing", "invalid_request_json"),
        (b"\xff", "invalid_request_utf8"),
    ],
)
def test_stdin_request_validation(tmp_path, raw, status):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    completed = run_script(GET_SCRIPT, ["--request-json", "-", "--json"], cwd, clean_environment(tmp_path), raw)
    response = parse_stdout(completed)
    assert completed.returncode == 2
    assert response["status"] == status


def test_oversized_stdin_request_is_rejected(tmp_path):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    raw = b" " * (1_048_576 + 1)
    completed = run_script(GET_SCRIPT, ["--request-json", "-", "--json"], cwd, clean_environment(tmp_path), raw)
    response = parse_stdout(completed)
    assert completed.returncode == 2
    assert response["status"] == "request_too_large"


@pytest.mark.parametrize(
    ("request_data", "status"),
    [
        ({"schema_version": 1, "operation": "render", "selector": "find-todos[agnostic]", "variables": {}}, "missing_request_fields"),
        ({"schema_version": 1, "operation": "render", "selector": "find-todos[agnostic]", "variables": {}, "qualification": None, "extra": 1}, "unknown_request_fields"),
        ({"schema_version": 1, "operation": "render", "selector": "find-todos[agnostic]", "variables": [], "qualification": None}, "invalid_variables"),
    ],
)
def test_render_operation_exact_fields(tmp_path, request_data, status):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    completed = run_script(GET_SCRIPT, ["--request-json", "-", "--json"], cwd, clean_environment(tmp_path), json.dumps(request_data).encode("utf-8"))
    assert completed.returncode == 2
    assert parse_stdout(completed)["status"] == status


def test_fatal_explicit_codex_home_allows_partial_listing_but_blocks_inspection(tmp_path):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    missing_home = tmp_path / "missing-codex-home"
    env = clean_environment(tmp_path)
    env["CODEX_HOME"] = str(missing_home)
    listing = run_script(LIST_SCRIPT, ["--json"], cwd, env)
    inspection = run_script(GET_SCRIPT, ["--inspect", "find-todos[agnostic]", "--json"], cwd, env)
    listing_response = parse_stdout(listing)
    inspection_response = parse_stdout(inspection)
    assert listing.returncode == 3
    assert listing_response["status"] == "fatal_catalog"
    assert listing_response["result"]["variants"]
    assert inspection.returncode == 3
    assert inspection_response["status"] == "fatal_catalog"


def test_absolute_scripts_resolve_adjacent_runtime_and_assets_without_install_or_pythonpath(tmp_path):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    env = clean_environment(tmp_path)
    assert "PYTHONPATH" not in env
    before = set(cwd.iterdir())
    for script, arguments in ((LIST_SCRIPT, ["--json"]), (GET_SCRIPT, ["--inspect", "find-todos[agnostic]", "--json"])):
        completed = run_script(script.resolve(), arguments, cwd, env)
        assert completed.returncode == 0
        assert parse_stdout(completed)["status"] == "ok"
    assert set(cwd.iterdir()) == before
    assert not (cwd / ".venv").exists()


def test_builtin_help_is_listed_and_get_reports_documentation_path(tmp_path):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    env = clean_environment(tmp_path)
    listing = parse_stdout(run_script(LIST_SCRIPT, ["--name", "help", "--json"], cwd, env))
    get_help = run_script(GET_SCRIPT, ["--inspect", "help[agnostic]", "--json"], cwd, env)
    response = parse_stdout(get_help)
    assert listing["result"]["variants"][0]["built_in"] is True
    assert get_help.returncode == 0
    assert response["status"] == "built_in_help"
    assert "references/action-files.md" in response["result"]["message"]


def test_builtin_help_remains_available_when_catalog_precedence_is_fatal(tmp_path):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    env = clean_environment(tmp_path)
    env["CODEX_HOME"] = str(tmp_path / "missing-codex-home")
    completed = run_script(GET_SCRIPT, ["--inspect", "help[agnostic]", "--json"], cwd, env)
    response = parse_stdout(completed)
    assert completed.returncode == 0
    assert response["status"] == "built_in_help"
    assert any(diagnostic["code"] == "invalid_codex_home" for diagnostic in response["diagnostics"])
