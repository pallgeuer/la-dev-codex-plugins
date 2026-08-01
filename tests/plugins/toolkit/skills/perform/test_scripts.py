"""Subprocess integration tests for the bundled Perform entry scripts."""

import json
import os
import pathlib
import stat
import subprocess
import sys

import pytest

REPOSITORY_ROOT = pathlib.Path(__file__).resolve().parents[5]
SKILL_ROOT = REPOSITORY_ROOT / "plugins" / "toolkit" / "skills" / "perform"
SCRIPTS_ROOT = SKILL_ROOT / "scripts"
LIST_SCRIPT = SCRIPTS_ROOT / "list_perform_actions.py"
GET_SCRIPT = SCRIPTS_ROOT / "get_perform_action.py"
CATALOGUE_SCRIPT = SCRIPTS_ROOT / "write_perform_action_catalogue.py"
REMOVED_OUTPUT_KEYS = {
    "schema_version",
    "status",
    "discovery",
    "result",
    "source",
    "provenance",
    "name",
    "language",
    "model",
    "reasoning_effort",
    "plan_reasoning_effort",
    "requires_interactive",
    "custom_codex_args",
    "goal_mode",
    "plan_mode",
    "notes_present",
    "qualification",
    "placeholders",
}


def clean_environment(tmp_path, codex_home=None):
    """Return an environment without repository-specific import configuration."""
    env = {key: value for key, value in os.environ.items() if key not in ("PYTHONPATH", "PYTHONHOME", "CODEX_HOME")}
    env["HOME"] = str(tmp_path / "home")
    pathlib.Path(env["HOME"]).mkdir(exist_ok=True)
    if codex_home is None:
        codex_home = tmp_path / "codex-home"
        codex_home.mkdir(exist_ok=True)
    env["CODEX_HOME"] = str(codex_home)
    return env


def run_script(script, arguments, cwd, env, executable_direct=False):
    """Run one bundled script from an arbitrary external working directory."""
    command = [str(script)] if executable_direct else [sys.executable, str(script)]
    command.extend(arguments)
    return subprocess.run(command, cwd=str(cwd), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def parse_stdout(completed):
    """Decode one JSON response from stdout."""
    assert completed.stdout.endswith(b"\n")
    assert completed.stdout.count(b"\n") == 1
    return json.loads(completed.stdout.decode("utf-8"))


def posix_single_quote(value):
    """Quote one value with the POSIX recipe documented by the skill."""
    return "'" + value.replace("'", "'\"'\"'") + "'"


def user_catalog(codex_home, file_data, write_file, actions):
    """Write user-precedence actions for subprocess tests."""
    directory = codex_home / "toolkit_perform_actions"
    write_file(directory, file_data(actions=actions))
    return directory


def assert_removed_keys_absent(value, allowed_keys=frozenset()):
    """Assert that compact output recursively omits every retired field."""
    if isinstance(value, dict):
        assert not (set(value) & (REMOVED_OUTPUT_KEYS - set(allowed_keys)))
        for child in value.values():
            assert_removed_keys_absent(child, allowed_keys=allowed_keys)
    elif isinstance(value, list):
        for child in value:
            assert_removed_keys_absent(child, allowed_keys=allowed_keys)


def test_scripts_have_portable_shebang_and_executable_mode():
    for script in (LIST_SCRIPT, GET_SCRIPT, CATALOGUE_SCRIPT):
        assert script.read_text(encoding="utf-8").startswith("#!/usr/bin/env python3\n")
        assert script.stat().st_mode & stat.S_IXUSR


@pytest.mark.parametrize(
    ("script", "mixed_arguments", "documented_option"),
    [
        (LIST_SCRIPT, ["--name=first", "--name=second", "--invalid", "--help", "-h"], "--fallback"),
        (GET_SCRIPT, ["--inspect=first[agnostic]", "--inspect=second[agnostic]", "--invalid", "-h", "--help"], "--question"),
        (CATALOGUE_SCRIPT, ["--output=first", "--output=second", "--invalid", "-h", "--help"], "--output"),
    ],
)
def test_help_is_compact_json_and_always_short_circuits(tmp_path, script, mixed_arguments, documented_option):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    env = clean_environment(tmp_path)
    for arguments in (["-h"], ["--help"], mixed_arguments):
        completed = run_script(script, arguments, cwd, env)
        response = parse_stdout(completed)
        assert completed.returncode == 0
        assert completed.stderr == b""
        assert set(response) == {"help"}
        assert script.name in response["help"]
        assert documented_option in response["help"]


def test_listing_is_one_compact_json_line(tmp_path):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    completed = run_script(LIST_SCRIPT, [], cwd, clean_environment(tmp_path), executable_direct=True)
    response = parse_stdout(completed)
    assert completed.returncode == 0
    assert completed.stderr == b""
    assert b'"variants":[' in completed.stdout
    assert {variant["selector"] for variant in response["variants"]} >= {"exec-md-goal[agnostic]", "find-todos[agnostic]", "help[agnostic]"}
    find_todos = next(variant for variant in response["variants"] if variant["selector"] == "find-todos[agnostic]")
    assert set(find_todos) == {"selector", "name", "language", "gloss"}
    assert find_todos["name"] == "find-todos"
    assert find_todos["language"] == "agnostic"
    assert isinstance(find_todos["gloss"], str)
    assert find_todos["gloss"]
    exec_md_goal = next(variant for variant in response["variants"] if variant["selector"] == "exec-md-goal[agnostic]")
    assert set(exec_md_goal["prompt_vars"]) == {"MarkdownPlanFile"}
    assert_removed_keys_absent(response, allowed_keys={"name", "language"})


def test_name_filter_and_one_call_fallback(tmp_path):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    env = clean_environment(tmp_path)
    matched = parse_stdout(run_script(LIST_SCRIPT, ["--name=find-todos", "--fallback"], cwd, env))
    fallback = parse_stdout(run_script(LIST_SCRIPT, ["--name=find", "--fallback"], cwd, env))
    assert [variant["selector"] for variant in matched["variants"]] == ["find-todos[agnostic]"]
    assert len(fallback["variants"]) > 1
    assert "find-todos[agnostic]" in [variant["selector"] for variant in fallback["variants"]]


def test_name_filter_miss_without_fallback_is_empty_success(tmp_path):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    completed = run_script(LIST_SCRIPT, ["--name=missing"], cwd, clean_environment(tmp_path))
    response = parse_stdout(completed)
    assert completed.returncode == 0
    assert response == {"variants": []}


@pytest.mark.parametrize(
    ("script", "arguments", "code"),
    [
        (LIST_SCRIPT, ["--name=Not Valid"], "invalid_name"),
        (LIST_SCRIPT, ["--fallback"], "invalid_arguments"),
        (GET_SCRIPT, [], "invalid_arguments"),
        (GET_SCRIPT, ["--inspect=find-todos[agnostic]", "--var=X=x"], "invalid_arguments"),
        (GET_SCRIPT, ["--render=find-todos[agnostic]", "--var=malformed"], "invalid_variable_argument"),
        (GET_SCRIPT, ["--render=find-todos[agnostic]", "--var=X=one", "--var=X=two"], "duplicate_variable_argument"),
        (GET_SCRIPT, ["--render=find-todos[agnostic]", "--var=%X%=one"], "invalid_variable_argument"),
        (GET_SCRIPT, ["--inspect=find-todos[agnostic]", "--json"], "invalid_arguments"),
        (GET_SCRIPT, ["--request-json=-"], "invalid_arguments"),
        (LIST_SCRIPT, ["--nam=find-todos"], "invalid_arguments"),
        (LIST_SCRIPT, ["--fall"], "invalid_arguments"),
        (GET_SCRIPT, ["--ins=find-todos[agnostic]"], "invalid_arguments"),
        (GET_SCRIPT, ["--render=find-todos[agnostic]", "--qual=tools"], "invalid_arguments"),
        (CATALOGUE_SCRIPT, ["--out=actions.md"], "invalid_arguments"),
    ],
)
def test_invalid_direct_arguments_are_json_errors(tmp_path, script, arguments, code):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    completed = run_script(script, arguments, cwd, clean_environment(tmp_path))
    assert completed.returncode == 2
    assert completed.stderr == b""
    assert parse_stdout(completed)["error"]["code"] == code


@pytest.mark.parametrize(
    ("script", "arguments"),
    [
        (LIST_SCRIPT, ["--name=first", "--name=second"]),
        (LIST_SCRIPT, ["--name=first", "--fallback", "--fallback"]),
        (LIST_SCRIPT, ["--cwd=/first", "--cwd=/second"]),
        (GET_SCRIPT, ["--inspect=find-todos[agnostic]", "--inspect=exec-md-goal[agnostic]"]),
        (GET_SCRIPT, ["--render=find-todos[agnostic]", "--render=exec-md-goal[agnostic]"]),
        (GET_SCRIPT, ["--render=find-todos[agnostic]", "--qualification=first", "--qualification=second"]),
        (GET_SCRIPT, ["--render=find-todos[agnostic]", "--qualification=first", "--question=second"]),
        (GET_SCRIPT, ["--inspect=find-todos[agnostic]", "--cwd=/first", "--cwd=/second"]),
        (CATALOGUE_SCRIPT, ["--output=/first", "--output=/second"]),
        (CATALOGUE_SCRIPT, ["--cwd=/first", "--cwd=/second"]),
    ],
)
def test_singleton_arguments_cannot_repeat(tmp_path, script, arguments):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    completed = run_script(script, arguments, cwd, clean_environment(tmp_path))
    assert completed.returncode == 2
    assert completed.stderr == b""
    assert parse_stdout(completed)["error"]["code"] == "invalid_arguments"


def test_strict_selector_failure_reports_same_name_alternatives(tmp_path, complete, file_data, write_file):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    user_catalog(codex_home, file_data, write_file, {"language-action": {"python": complete(prompt="Python.")}})
    completed = run_script(GET_SCRIPT, ["--inspect=language-action[rust]"], cwd, clean_environment(tmp_path, codex_home))
    response = parse_stdout(completed)
    assert completed.returncode == 2
    assert response["error"]["code"] == "not_found"
    assert response["available_variants"] == ["language-action[python]"]


@pytest.mark.parametrize("selector", ["find-todos", "find-todos[json,yaml]", "find-todos[agnostic]extra", "UPPER[python]"])
def test_get_accepts_only_canonical_strict_selectors(tmp_path, selector):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    completed = run_script(GET_SCRIPT, ["--inspect={}".format(selector)], cwd, clean_environment(tmp_path))
    assert completed.returncode == 2
    assert parse_stdout(completed)["error"]["code"] == "invalid_selector"


def test_inspect_output_contains_only_prompt_mode_variables_and_nonempty_notes(tmp_path):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    completed = run_script(GET_SCRIPT, ["--inspect=exec-md-goal[agnostic]"], cwd, clean_environment(tmp_path))
    response = parse_stdout(completed)
    assert completed.returncode == 0
    assert set(response) == {"prompt", "mode", "prompt_vars", "notes"}
    assert response["mode"] == "goal"
    assert set(response["prompt_vars"]) == {"MarkdownPlanFile"}
    assert response["notes"]
    assert_removed_keys_absent(response)


def test_inspect_omits_empty_optional_fields(tmp_path):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    response = parse_stdout(run_script(GET_SCRIPT, ["--inspect=find-todos[agnostic]"], cwd, clean_environment(tmp_path)))
    assert set(response) == {"prompt", "mode"}
    assert response["mode"] == "default"


def test_bundled_cross_platform_action_inspects_and_renders_os_list(tmp_path):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    env = clean_environment(tmp_path)
    inspection = parse_stdout(run_script(GET_SCRIPT, ["--inspect=check-cross-platform[agnostic]"], cwd, env))
    assert set(inspection) == {"prompt", "mode", "prompt_vars"}
    assert inspection["mode"] == "default"
    assert inspection["prompt"].startswith("No edits. ")
    assert set(inspection["prompt_vars"]) == {"OSList"}
    os_list = "Linux, macOS, Windows 11 (x86_64)"
    rendered = parse_stdout(run_script(GET_SCRIPT, ["--render=check-cross-platform[agnostic]", "--var=OSList={}".format(os_list)], cwd, env))
    assert set(rendered) == {"prompt"}
    assert rendered["prompt"].startswith("No edits. ")
    assert os_list in rendered["prompt"]
    assert "%OSList%" not in rendered["prompt"]


def test_direct_render_end_to_end_with_literal_complex_data(tmp_path, complete, file_data, write_file):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    user_catalog(codex_home, file_data, write_file, {"shell-data": {"agnostic": complete(prompt_vars={"Value": "Literal value"}, prompt="Handle %Value%.", notes="Visible note.")}})
    value = "quotes '` $() ; \\ \u03bb=equals\n--next"
    arguments = ["--render=shell-data[agnostic]", "--var=Value={}".format(value), "--qualification=Restrict %Value% literally."]
    completed = run_script(GET_SCRIPT, arguments, cwd, clean_environment(tmp_path, codex_home))
    response = parse_stdout(completed)
    assert completed.returncode == 0
    assert set(response) == {"prompt"}
    assert response["prompt"] == "Handle {}.\nBUT: Restrict %Value% literally.".format(value)


@pytest.mark.parametrize(
    "value",
    [
        "spaces and = equals",
        "quotes ' \" and percent %",
        "`backticks` $(touch /tmp/never) ; $HOME",
        "backslash \\\\ path",
        "Unicode \u03bb",
        "embedded\nnewline",
        "--leading-option-like-value",
    ],
)
def test_direct_variable_values_remain_literal(tmp_path, complete, file_data, write_file, value):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    user_catalog(codex_home, file_data, write_file, {"data": {"agnostic": complete(prompt_vars={"Value": "Value"}, prompt="Value=%Value%")}})
    completed = run_script(GET_SCRIPT, ["--render=data[agnostic]", "--var=Value={}".format(value)], cwd, clean_environment(tmp_path, codex_home))
    assert completed.returncode == 0
    assert parse_stdout(completed) == {"prompt": "Value=" + value}


def test_distinct_repeated_variable_arguments_remain_supported(tmp_path, complete, file_data, write_file):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    user_catalog(codex_home, file_data, write_file, {"data": {"agnostic": complete(prompt_vars={"A": "First", "B": "Second"}, prompt="%A% then %B%")}})
    completed = run_script(GET_SCRIPT, ["--render=data[agnostic]", "--var=A=one", "--var=B=two"], cwd, clean_environment(tmp_path, codex_home))
    assert completed.returncode == 0
    assert parse_stdout(completed) == {"prompt": "one then two"}


def test_shell_like_direct_values_never_execute(tmp_path, complete, file_data, write_file):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    user_catalog(codex_home, file_data, write_file, {"shell-data": {"agnostic": complete(prompt_vars={"Value": "Value"}, prompt="Use %Value%.")}})
    marker = cwd / "must-not-exist"
    malicious = "$(touch {}) `touch {}` ; $HOME".format(marker, marker)
    completed = run_script(GET_SCRIPT, ["--render=shell-data[agnostic]", "--var=Value={}".format(malicious)], cwd, clean_environment(tmp_path, codex_home))
    assert completed.returncode == 0
    assert marker.exists() is False
    assert malicious in parse_stdout(completed)["prompt"]


def test_documented_posix_quoting_keeps_shell_like_values_literal(tmp_path, complete, file_data, write_file):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    user_catalog(codex_home, file_data, write_file, {"shell-data": {"agnostic": complete(prompt_vars={"Value": "Value"}, prompt="Use %Value%.")}})
    marker = cwd / "must-not-exist"
    value = "quotes ' $(touch {}) `touch {}` ; $HOME\n--leading-option".format(marker, marker)
    qualification = "Keep ' $(touch {}) `touch {}` ; literal.".format(marker, marker)
    arguments = [str(GET_SCRIPT.resolve()), "--render=shell-data[agnostic]", "--var=Value={}".format(value), "--qualification={}".format(qualification)]
    command = " ".join(posix_single_quote(argument) for argument in arguments)
    completed = subprocess.run(["sh", "-c", command], cwd=str(cwd), env=clean_environment(tmp_path, codex_home), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    assert completed.returncode == 0
    assert completed.stderr == b""
    assert marker.exists() is False
    assert parse_stdout(completed) == {"prompt": "Use {}.\nBUT: {}".format(value, qualification)}


def test_option_like_qualification_is_data(tmp_path):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    completed = run_script(GET_SCRIPT, ["--render=find-todos[agnostic]", "--qualification=--only-tools"], cwd, clean_environment(tmp_path))
    assert completed.returncode == 0
    assert parse_stdout(completed)["prompt"].endswith("\nBUT: --only-tools")


def test_render_requires_every_declared_direct_variable(tmp_path):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    completed = run_script(GET_SCRIPT, ["--render=exec-md-goal[agnostic]"], cwd, clean_environment(tmp_path))
    assert completed.returncode == 2
    assert parse_stdout(completed)["error"]["code"] == "missing_variables"


def test_render_rejects_an_empty_substituted_main_prompt(tmp_path, complete, file_data, write_file):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    user_catalog(codex_home, file_data, write_file, {"blank": {"agnostic": complete(prompt_vars={"Value": "Value"}, prompt="%Value%")}})
    completed = run_script(GET_SCRIPT, ["--render=blank[agnostic]", "--var=Value= \t"], cwd, clean_environment(tmp_path, codex_home))
    assert completed.returncode == 2
    assert parse_stdout(completed)["error"]["code"] == "empty_rendered_prompt"


def test_scripts_emit_literal_utf8_under_ascii_stdout(tmp_path, complete, file_data, write_file):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    user_catalog(
        codex_home,
        file_data,
        write_file,
        {
            "unicode": {
                "agnostic": complete(
                    gloss="Unicode \u03bb action",
                    prompt_vars={"Value": "Unicode \u03bb value"},
                    prompt="Handle %Value% and \u03bb.",
                    notes="Unicode \u03bb note.",
                )
            }
        },
    )
    env = clean_environment(tmp_path, codex_home)
    env["PYTHONIOENCODING"] = "ascii"
    listing = run_script(LIST_SCRIPT, ["--name=unicode"], cwd, env)
    inspection = run_script(GET_SCRIPT, ["--inspect=unicode[agnostic]"], cwd, env)
    rendered = run_script(GET_SCRIPT, ["--render=unicode[agnostic]", "--var=Value=\u03bb", "--qualification=Keep \u03bb literal."], cwd, env)
    for completed in (listing, inspection, rendered):
        assert completed.returncode == 0
        assert "\u03bb".encode("utf-8") in completed.stdout
        assert completed.stderr == b""
        parse_stdout(completed)
    assert parse_stdout(rendered)["prompt"] == "Handle \u03bb and \u03bb. BUT: Keep \u03bb literal."


def test_scripts_reject_lone_surrogates_as_invalid_action_text(tmp_path, complete, file_data, write_file):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    surrogate = chr(0xD800)
    user_catalog(codex_home, file_data, write_file, {"surrogate": {"agnostic": complete(gloss="Gloss " + surrogate, prompt="Prompt " + surrogate)}})
    env = clean_environment(tmp_path, codex_home)
    listing = run_script(LIST_SCRIPT, ["--name=surrogate"], cwd, env)
    inspection = run_script(GET_SCRIPT, ["--inspect=surrogate[agnostic]"], cwd, env)
    assert listing.returncode == 0
    listing_payload = parse_stdout(listing)
    assert listing_payload["variants"] == []
    assert "Unicode surrogate" in " ".join(listing_payload["diagnostics"])
    assert inspection.returncode == 2
    assert inspection.stderr == b""
    inspection_payload = parse_stdout(inspection)
    assert inspection_payload["error"]["code"] == "not_found"
    assert "Unicode surrogate" in " ".join(inspection_payload["diagnostics"])


def test_scripts_isolate_lone_surrogates_in_invalid_json_keys(tmp_path, complete, file_data, write_file):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    codex_home = tmp_path / "codex-home"
    action_directory = codex_home / "toolkit_perform_actions"
    surrogate = chr(0xD800)
    invalid_root = file_data()
    invalid_root[surrogate] = True
    write_file(action_directory, invalid_root, "10-invalid.json")
    write_file(action_directory, file_data(actions={"good": {"agnostic": complete(prompt="Good.")}}), "20-good.json")
    completed = run_script(LIST_SCRIPT, ["--name=good"], cwd, clean_environment(tmp_path, codex_home))
    response = parse_stdout(completed)
    assert completed.returncode == 0
    assert completed.stderr == b""
    assert response["variants"] == [{"selector": "good[agnostic]", "name": "good", "language": "agnostic", "gloss": "Test action"}]
    assert len(response["diagnostics"]) == 1
    assert "\\ud800" in response["diagnostics"][0]


def test_compact_diagnostic_strings_include_file_and_json_location(tmp_path, complete, file_data, write_file):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    invalid = complete()
    invalid["unknown"] = True
    user_catalog(codex_home, file_data, write_file, {"bad": {"agnostic": invalid}, "good": {"agnostic": complete(prompt="Good.")}})
    completed = run_script(GET_SCRIPT, ["--inspect=good[agnostic]"], cwd, clean_environment(tmp_path, codex_home))
    response = parse_stdout(completed)
    assert completed.returncode == 0
    assert set(response) == {"prompt", "mode", "diagnostics"}
    assert len(response["diagnostics"]) == 1
    assert response["diagnostics"][0].startswith("error: ")
    assert "actions.json/actions/bad/agnostic" in response["diagnostics"][0]


def test_fatal_explicit_codex_home_allows_partial_listing_but_blocks_inspection(tmp_path):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    env = clean_environment(tmp_path)
    env["CODEX_HOME"] = str(tmp_path / "missing-codex-home")
    listing = run_script(LIST_SCRIPT, [], cwd, env)
    inspection = run_script(GET_SCRIPT, ["--inspect=find-todos[agnostic]"], cwd, env)
    listing_response = parse_stdout(listing)
    inspection_response = parse_stdout(inspection)
    assert listing.returncode == 3
    assert listing_response["variants"]
    assert listing_response["error"]["code"] == "fatal_catalog"
    assert listing_response["diagnostics"]
    assert inspection.returncode == 3
    assert inspection_response["error"]["code"] == "fatal_catalog"
    assert "prompt" not in inspection_response


def test_catalogue_script_writes_absolute_output_and_preserves_identical_file(tmp_path):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    output = tmp_path / "action_catalogue.md"
    env = clean_environment(tmp_path)
    first = run_script(CATALOGUE_SCRIPT, ["--output={}".format(output)], cwd, env, executable_direct=True)
    first_response = parse_stdout(first)
    first_stat = output.stat()
    second = run_script(CATALOGUE_SCRIPT, ["--output={}".format(output)], cwd, env)
    second_response = parse_stdout(second)
    second_stat = output.stat()

    assert first.returncode == 0
    assert first.stderr == b""
    assert first_response["path"] == str(output)
    assert first_response["changed"] is True
    assert first_response["action_count"] >= 2
    assert first_response["variant_count"] >= first_response["action_count"]
    assert second.returncode == 0
    assert second_response == {**first_response, "changed": False}
    assert second_stat.st_ino == first_stat.st_ino
    assert second_stat.st_mtime_ns == first_stat.st_mtime_ns
    content = output.read_text(encoding="utf-8")
    assert content.startswith("<!-- toolkit-perform-action-catalogue:v1 -->\n")
    update_row = next(line for line in content.splitlines() if line.startswith("| `update-action-catalogue` "))
    assert [cell.strip() for cell in update_row.strip("|").split("|")][:2] == ["`update-action-catalogue`", "`agnostic`"]
    assert "Diagnostic:" not in content


def test_catalogue_script_default_and_relative_paths_use_repository_root(tmp_path):
    repository = tmp_path / "repository"
    nested = repository / "nested"
    nested.mkdir(parents=True)
    (repository / ".git").mkdir()
    env = clean_environment(tmp_path)

    default = run_script(CATALOGUE_SCRIPT, [], nested, env)
    default_response = parse_stdout(default)
    default_path = repository / ".codex" / "toolkit_perform_actions" / "action_catalogue.md"
    assert default.returncode == 0
    assert default_response["path"] == str(default_path)
    assert default_path.is_file()

    docs = repository / "docs"
    docs.mkdir()
    relative = run_script(CATALOGUE_SCRIPT, ["--output=docs/actions.md"], nested, env)
    relative_response = parse_stdout(relative)
    assert relative.returncode == 0
    assert relative_response["path"] == str(docs / "actions.md")


def test_catalogue_script_refuses_unmarked_output(tmp_path):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    output = tmp_path / "manual.md"
    output.write_text("manual\n", encoding="ascii")
    completed = run_script(CATALOGUE_SCRIPT, ["--output={}".format(output)], cwd, clean_environment(tmp_path))
    response = parse_stdout(completed)
    assert completed.returncode == 2
    assert response["error"]["code"] == "unsafe_output"
    assert output.read_text(encoding="ascii") == "manual\n"


def test_absolute_scripts_resolve_adjacent_runtime_and_assets_without_install_or_pythonpath(tmp_path):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    env = clean_environment(tmp_path)
    assert "PYTHONPATH" not in env
    before = set(cwd.iterdir())
    catalogue = tmp_path / "catalogue.md"
    for script, arguments in ((LIST_SCRIPT, []), (GET_SCRIPT, ["--inspect=find-todos[agnostic]"]), (CATALOGUE_SCRIPT, ["--output={}".format(catalogue)])):
        completed = run_script(script.resolve(), arguments, cwd, env, executable_direct=True)
        assert completed.returncode == 0
        assert parse_stdout(completed)
    assert set(cwd.iterdir()) == before
    assert not (cwd / ".venv").exists()


def test_builtin_help_is_listed_and_inspected_as_a_normal_result(tmp_path):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    env = clean_environment(tmp_path)
    listing = parse_stdout(run_script(LIST_SCRIPT, ["--name=help"], cwd, env))
    get_help = run_script(GET_SCRIPT, ["--inspect=help[agnostic]"], cwd, env)
    response = parse_stdout(get_help)
    assert len(listing["variants"]) == 1
    help_variant = listing["variants"][0]
    assert set(help_variant) == {"selector", "name", "language", "gloss"}
    assert help_variant["selector"] == "help[agnostic]"
    assert help_variant["name"] == "help"
    assert help_variant["language"] == "agnostic"
    assert isinstance(help_variant["gloss"], str)
    assert help_variant["gloss"]
    assert get_help.returncode == 0
    assert response["mode"] == "default"
    for filename in ("action_files.md", "codex_skill.md", "standalone_cli.md"):
        assert str(SKILL_ROOT / "references" / filename) in response["prompt"]


def test_builtin_help_renders_an_optional_question(tmp_path):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    question = "How do repository overrides work?"
    completed = run_script(GET_SCRIPT, ["--render=help[agnostic]", "--question=  BUT: {}  ".format(question)], cwd, clean_environment(tmp_path))
    response = parse_stdout(completed)
    assert completed.returncode == 0
    assert response["prompt"].endswith("\n\nUser question: " + question)
    assert "BUT: " not in response["prompt"]


def test_builtin_help_remains_available_when_catalog_precedence_is_fatal(tmp_path):
    cwd = tmp_path / "outside"
    cwd.mkdir()
    env = clean_environment(tmp_path)
    env["CODEX_HOME"] = str(tmp_path / "missing-codex-home")
    completed = run_script(GET_SCRIPT, ["--inspect=help[agnostic]"], cwd, env)
    response = parse_stdout(completed)
    assert completed.returncode == 0
    assert response["prompt"]
    assert response["diagnostics"]

    rendered = run_script(GET_SCRIPT, ["--render=help[agnostic]", "--question=What failed?"], cwd, env)
    rendered_response = parse_stdout(rendered)
    assert rendered.returncode == 0
    assert rendered_response["prompt"].endswith("\n\nUser question: What failed?")
    assert rendered_response["diagnostics"]
