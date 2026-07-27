"""Tests for the source-package Perform command-line interface."""

import importlib
import json
import os
import sys
import types
from pathlib import Path

import pytest

import la_dev_codex_plugins.cli.perform as perform
from la_dev_codex_plugins.cli import _perform_runtime as perform_runtime

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPOSITORY_ROOT / "plugins" / "toolkit"


class ExecCalled(BaseException):
    """Test-only signal carrying a requested process replacement."""

    def __init__(self, executable, argv, environment=None):
        super().__init__(executable)
        self.executable = executable
        self.argv = argv
        self.environment = environment


def local_arguments(*arguments):
    """Return launcher arguments that explicitly use the checkout plugin."""
    return ["--plugin-root", str(PLUGIN_ROOT), "--codex", sys.executable, *arguments]


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        ([], ["list"]),
        (["--json"], ["list", "--json"]),
        (["ensure-ascii-only"], ["run", "ensure-ascii-only"]),
        (["--cwd", "/tmp", "ensure-ascii-only"], ["--cwd", "/tmp", "run", "ensure-ascii-only"]),
        (["catalogue"], ["catalogue"]),
        (["--output", "/tmp/actions.md", "catalogue"], ["--output", "/tmp/actions.md", "catalogue"]),
        (["list", "ensure-ascii-only"], ["list", "ensure-ascii-only"]),
        (["help"], ["run", "help"]),
        (["help[agnostic]"], ["run", "help[agnostic]"]),
        (["--qualification", "Question?", "help"], ["--qualification", "Question?", "run", "help"]),
        (["--help"], ["--help"]),
    ],
)
def test_normalize_argv(arguments, expected):
    assert perform.normalize_argv(arguments) == expected


def test_normalize_argv_derives_value_options_from_parser():
    parser = perform.build_parser()
    assert not hasattr(perform, "OPTIONS_WITH_VALUES")
    for action in parser._actions:
        if action.nargs == 0:
            continue
        for option in action.option_strings:
            assert perform.normalize_argv([option, "value", "ensure-ascii-only"], parser=parser) == [option, "value", "run", "ensure-ascii-only"]


def test_explicit_help_option_remains_cli_help(capsys):
    with pytest.raises(SystemExit) as raised:
        perform.main(["--help"])
    assert raised.value.code == 0
    captured = capsys.readouterr()
    assert captured.out.startswith("usage: codex-perform ")
    assert captured.err == ""


def test_catalogue_command_writes_without_launching_codex(monkeypatch, tmp_path, capsys):
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / ".git").mkdir()
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    assert perform.main(local_arguments("--cwd", str(repository), "catalogue", "--json")) == 0
    payload = json.loads(capsys.readouterr().out)
    output = repository / ".codex" / "toolkit_perform_actions" / "action_catalogue.md"
    assert payload["path"] == str(output)
    assert payload["changed"] is True
    assert payload["action_count"] >= 2
    assert output.is_file()

    assert perform.main(local_arguments("--cwd", str(repository), "catalogue")) == 0
    captured = capsys.readouterr()
    assert captured.out.startswith("Unchanged action catalogue: ")
    assert str(output) in captured.out


def test_catalogue_command_supports_custom_output(monkeypatch, tmp_path, capsys):
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    repository = tmp_path / "repository"
    docs = repository / "docs"
    docs.mkdir(parents=True)
    (repository / ".git").mkdir()
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    assert perform.main(local_arguments("--cwd", str(repository), "catalogue", "--output", "docs/actions.md", "--json")) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["path"] == str(docs / "actions.md")
    assert payload["changed"] is True


@pytest.mark.parametrize(
    "arguments",
    [
        ("catalogue", "action-name"),
        ("catalogue", "--language", "python"),
        ("catalogue", "--var", "X=value"),
        ("list", "--output", "actions.md"),
        ("show", "find-todos", "--output", "actions.md"),
        ("run", "find-todos", "--output", "actions.md"),
    ],
)
def test_catalogue_options_are_command_specific(arguments, capsys):
    assert perform.main(local_arguments(*arguments, "--json")) == 2
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "invalid_arguments"


def test_catalogue_rejects_codex_remainder(capsys):
    assert perform.main(local_arguments("catalogue", "--json", "--", "--color=never")) == 2
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "invalid_arguments"


def test_run_output_error_does_not_reject_valid_codex_remainder(capsys):
    assert perform.main(local_arguments("run", "ensure-ascii-only", "--output", "actions.md", "--json", "--", "--color=never")) == 2
    error = json.loads(capsys.readouterr().out)["error"]
    assert error["code"] == "invalid_arguments"
    assert error["message"] == "run does not accept these options or arguments: output."


def test_empty_plugin_root_fails_closed(monkeypatch, capsys):
    def unexpected_discovery(*_args, **_kwargs):
        raise AssertionError("installed discovery must not run")

    monkeypatch.setattr(perform_runtime, "discover_plugin_root", unexpected_discovery)
    assert perform.main(["--plugin-root", "", "--json"]) == 2
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "invalid_directory"


def test_list_and_show_json_use_local_plugin(capsys):
    assert perform.main(local_arguments("--json")) == 0
    listed = json.loads(capsys.readouterr().out)
    ensure_ascii = next(variant for variant in listed["variants"] if variant["selector"] == "ensure-ascii-only[agnostic]")
    assert ensure_ascii == {
        "selector": "ensure-ascii-only[agnostic]",
        "name": "ensure-ascii-only",
        "language": "agnostic",
        "gloss": "Ensure ASCII-only source files wherever possible",
    }

    assert perform.main(local_arguments("show", "ensure-ascii-only", "--json")) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["selector"] == "ensure-ascii-only[agnostic]"
    assert set(shown["action"]) == {
        "gloss",
        "model",
        "reasoning_effort",
        "goal_mode",
        "plan_mode",
        "plan_reasoning_effort",
        "no_edits",
        "prompt_vars",
        "prompt",
        "requires_interactive",
        "custom_codex_args",
        "notes",
    }
    assert shown["action"]["requires_interactive"] is False

    assert perform.main(local_arguments("show", "help", "--json")) == 0
    help_payload = json.loads(capsys.readouterr().out)
    assert help_payload["selector"] == "help[agnostic]"
    assert help_payload["name"] == "help"
    assert help_payload["language"] == "agnostic"
    assert help_payload["action"] == {
        "gloss": "Explain Perform action files and launch methods",
        "model": "default",
        "reasoning_effort": "medium",
        "goal_mode": False,
        "plan_mode": False,
        "plan_reasoning_effort": "medium",
        "no_edits": True,
        "prompt_vars": {},
        "prompt": help_payload["action"]["prompt"],
        "requires_interactive": False,
        "custom_codex_args": [],
        "notes": "",
    }
    for filename in ("action_files.md", "codex_skill.md", "standalone_cli.md"):
        assert str(PLUGIN_ROOT / "skills" / "perform" / "references" / filename) in help_payload["action"]["prompt"]


def test_help_shorthand_explicit_run_and_question_are_launchable(capsys):
    assert perform.main(local_arguments("help", "--dry-run", "--json")) == 0
    shorthand = json.loads(capsys.readouterr().out)
    assert perform.main(local_arguments("run", "help", "--dry-run", "--json")) == 0
    explicit = json.loads(capsys.readouterr().out)
    assert shorthand == explicit
    assert shorthand["launch_spec"]["selector"] == "help[agnostic]"
    assert shorthand["launch_spec"]["qualification"] is None
    assert shorthand["submitted_prompt"].startswith("No edits. Read the following installed Perform guides")
    assert "If no user question is supplied" in shorthand["submitted_prompt"]

    question = "How do repository overrides work?"
    assert perform.main(local_arguments("help", "--qualification", question, "--dry-run", "--json")) == 0
    qualified = json.loads(capsys.readouterr().out)
    assert qualified["launch_spec"]["qualification"] == question
    assert qualified["submitted_prompt"].endswith("\n\nUser question: " + question)
    assert "BUT: " not in qualified["submitted_prompt"]


@pytest.mark.parametrize(
    "arguments",
    [
        ("list", "missing", "--json"),
        ("list", "missing[agnostic]", "--json"),
        ("list", "--language", "missing", "--json"),
    ],
)
def test_list_filters_with_no_matches_are_empty_successes(capsys, arguments):
    assert perform.main(local_arguments(*arguments)) == 0
    assert json.loads(capsys.readouterr().out) == {"variants": []}


def test_dry_run_json_reports_complete_noninteractive_invocation(capsys, tmp_path):
    assert perform.main(local_arguments("--cwd", str(tmp_path), "ensure-ascii-only", "--dry-run", "--json", "--model", "gpt-5")) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "default"
    assert payload["non_interactive"] is True
    assert payload["launch_spec"]["action"]["requires_interactive"] is False
    assert payload["effective_settings"]["non_interactive"] is True
    assert payload["effective_settings"]["model"] == "gpt-5"
    assert Path(payload["argv"][0]).is_absolute()
    assert "exec" in payload["argv"]
    assert payload["argv"][-2:] == ["--", payload["submitted_prompt"]]
    assert payload["effective_settings"]["cwd"] == str(tmp_path)
    assert payload["effective_settings"]["json_output"] is True
    assert payload["output_mode"] == "jsonl"
    assert "--json" in payload["argv"]


def test_real_noninteractive_json_is_forwarded_to_codex(monkeypatch, capsys):
    def fake_exec(argv, env=None):
        raise ExecCalled(argv[0], argv, env)

    monkeypatch.setattr(perform_runtime, "replace_process", fake_exec)

    with pytest.raises(ExecCalled) as raised:
        perform.main(local_arguments("ensure-ascii-only", "--json"))

    assert Path(raised.value.executable).is_absolute()
    assert raised.value.argv[0] == raised.value.executable
    assert "exec" in raised.value.argv
    assert "--json" in raised.value.argv
    assert raised.value.argv[-2] == "--"
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "PROMPT:" in captured.err


def test_default_run_is_interactive(monkeypatch, capsys):
    def fake_exec(argv, env=None):
        raise ExecCalled(argv[0], argv, env)

    monkeypatch.setattr(perform_runtime, "replace_process", fake_exec)
    with pytest.raises(ExecCalled) as raised:
        perform.main(local_arguments("ensure-ascii-only"))
    assert "exec" not in raised.value.argv
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "PERFORM: ensure-ascii-only[agnostic]" in captured.err
    assert "PROMPT:" not in captured.err
    assert captured.err.endswith("\n\n")


def test_noninteractive_alias_selects_final_only(capsys):
    assert perform.main(local_arguments("ensure-ascii-only", "--ni", "--dry-run")) == 0
    payload = json.loads(capsys.readouterr().out.split("bash command:\n", 1)[0])
    assert payload["non_interactive"] is True
    assert payload["effective_settings"]["non_interactive"] is True
    assert payload["output_mode"] == "final-only"


def test_final_only_success_shows_prelaunch_and_only_final_response(monkeypatch, capsys):
    observed = {}

    def run_supervised_process(argv, env, stderr):
        observed["argv"] = argv
        observed["env"] = env
        stderr.write(b"hidden progress\n")
        perform.output.write_text("final response\n")
        return 0

    monkeypatch.setattr(perform_runtime, "run_supervised_process", run_supervised_process)
    assert perform.main(local_arguments("ensure-ascii-only", "--non-interactive")) == 0
    captured = capsys.readouterr()
    assert captured.out == "final response\n"
    assert captured.err.startswith("PERFORM: ensure-ascii-only[agnostic]\n")
    assert "PROMPT:" in captured.err
    assert captured.err.endswith("\n\n")
    assert "hidden progress" not in captured.err
    assert "exec" in observed["argv"]
    assert observed["env"] is not None


def test_final_only_failure_replays_prelaunch_and_diagnostics(monkeypatch, capsys):
    def run_supervised_process(_argv, env, stderr):
        assert env is not None
        stderr.write(b"codex progress and failure\n")
        return 7

    monkeypatch.setattr(perform_runtime, "run_supervised_process", run_supervised_process)
    assert perform.main(local_arguments("ensure-ascii-only", "--non-interactive")) == 7
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("PERFORM: ensure-ascii-only[agnostic]\n")
    assert captured.err.count("PERFORM: ensure-ascii-only[agnostic]") == 1
    assert "PROMPT:" in captured.err
    assert "\n\ncodex progress and failure\n" in captured.err


def test_final_only_supervisor_failure_is_a_launch_error(monkeypatch, capsys):
    def fail_supervision(*_args, **_kwargs):
        raise OSError("missing codex")

    monkeypatch.setattr(perform_runtime, "run_supervised_process", fail_supervision)
    assert perform.main(local_arguments("ensure-ascii-only", "--non-interactive")) == 4
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "missing codex" in captured.err


def test_final_only_temporary_file_failure_is_a_launch_error(monkeypatch, capsys):
    def fail_temporary_file(**_kwargs):
        raise OSError("temporary storage unavailable")

    monkeypatch.setattr(perform, "tempfile", types.SimpleNamespace(TemporaryFile=fail_temporary_file))
    assert perform.main(local_arguments("ensure-ascii-only", "--non-interactive")) == 4
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "temporary storage unavailable" in captured.err


def test_verbose_noninteractive_uses_direct_progress_output(monkeypatch, capsys):
    def unexpected_supervision(*_args, **_kwargs):
        raise AssertionError("verbose launches must replace the process")

    def fake_exec(argv, env=None):
        raise ExecCalled(argv[0], argv, env)

    monkeypatch.setattr(perform_runtime, "run_supervised_process", unexpected_supervision)
    monkeypatch.setattr(perform_runtime, "replace_process", fake_exec)
    with pytest.raises(ExecCalled) as raised:
        perform.main(local_arguments("ensure-ascii-only", "--non-interactive", "--verbose"))
    assert "exec" in raised.value.argv
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "PERFORM: ensure-ascii-only[agnostic]" in captured.err
    assert "PROMPT:" in captured.err


@pytest.mark.parametrize(
    ("non_interactive", "json_output", "verbose", "expected_status", "expected_mode"),
    [
        (False, False, False, 0, "interactive"),
        (False, False, True, 2, None),
        (False, True, False, 0, "jsonl"),
        (False, True, True, 2, None),
        (True, False, False, 0, "final-only"),
        (True, False, True, 0, "verbose"),
        (True, True, False, 0, "jsonl"),
        (True, True, True, 2, None),
    ],
)
def test_run_output_flag_combinations(capsys, non_interactive, json_output, verbose, expected_status, expected_mode):
    arguments = ["ensure-ascii-only", "--dry-run"]
    if non_interactive:
        arguments.append("--non-interactive")
    if json_output:
        arguments.append("--json")
    if verbose:
        arguments.append("--verbose")
    assert perform.main(local_arguments(*arguments)) == expected_status
    captured = capsys.readouterr()
    if expected_status:
        if json_output:
            assert json.loads(captured.out)["error"]["code"] == "invalid_arguments"
        else:
            assert captured.out == ""
            assert captured.err.startswith("codex-perform: ")
    elif json_output:
        assert json.loads(captured.out)["output_mode"] == expected_mode
    else:
        payload = json.loads(captured.out.split("bash command:\n", 1)[0])
        assert payload["output_mode"] == expected_mode


def test_relative_codex_home_is_shared_by_catalog_and_launch(monkeypatch, tmp_path):
    codex_home = tmp_path / "relative-home"
    codex_home.mkdir()
    monkeypatch.setenv("CODEX_HOME", "relative-home")

    def fake_exec(argv, env=None):
        raise ExecCalled(argv[0], argv, env)

    monkeypatch.setattr(perform_runtime, "replace_process", fake_exec)
    with pytest.raises(ExecCalled) as raised:
        perform.main(local_arguments("--cwd", str(tmp_path), "ensure-ascii-only"))
    assert raised.value.environment is not None
    assert raised.value.environment["CODEX_HOME"] == str(codex_home)
    assert os.environ["CODEX_HOME"] == "relative-home"


def test_noninteractive_caller_ephemeral_is_placed_after_exec(capsys):
    assert perform.main(local_arguments("ensure-ascii-only", "--dry-run", "--json", "--", "--ephemeral")) == 0
    argv = json.loads(capsys.readouterr().out)["argv"]
    assert argv.index("exec") < argv.index("--ephemeral") < argv.index("--")


def test_json_implicitly_selects_noninteractive(capsys):
    assert perform.main(local_arguments("find-todos", "--dry-run", "--json")) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["launch_spec"]["action"]["requires_interactive"] is False
    assert payload["non_interactive"] is True
    assert payload["effective_settings"]["non_interactive"] is True
    assert payload["output_mode"] == "jsonl"
    assert "exec" in payload["argv"]
    assert "--json" in payload["argv"]


def test_removed_interactive_flag_is_rejected(capsys):
    assert perform.main(local_arguments("find-todos", "--interactive", "--dry-run", "--json")) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "invalid_arguments"


def test_invalid_language_and_run_only_list_option_are_usage_errors(capsys):
    assert perform.main(local_arguments("list", "--language", "bad language", "--json")) == 2
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "invalid_language"

    assert perform.main(local_arguments("list", "--non-interactive", "--json")) == 2
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "invalid_arguments"


@pytest.mark.parametrize(("command", "extra"), [("list", []), ("show", ["ensure-ascii-only"])])
@pytest.mark.parametrize(("option", "value"), [("--model", ""), ("--effort", ""), ("--plan-effort", ""), ("--qualification", "")])
def test_list_and_show_reject_explicit_empty_run_only_options(capsys, command, extra, option, value):
    assert perform.main(local_arguments(command, *extra, option, value, "--json")) == 2
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "invalid_arguments"


def test_long_option_abbreviations_are_rejected_consistently(capsys):
    assert perform.main(local_arguments("list", "--js")) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("codex-perform: ")


def test_missing_prompt_variable_preserves_catalog_status(capsys):
    assert perform.main(local_arguments("exec-md-goal", "--dry-run", "--json")) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "missing_variables"


def test_exec_md_goal_rejects_explicit_noninteractive_frontend(capsys):
    arguments = local_arguments("exec-md-goal", "--var", "MarkdownPlanFile=docs/plans/plan.md", "--non-interactive", "--dry-run", "--json")
    assert perform.main(arguments) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "interactive_required"
    assert "exec-md-goal[agnostic]" in payload["error"]["message"]


def test_exec_md_goal_rejects_implicit_json_noninteractive_frontend(capsys):
    arguments = local_arguments("exec-md-goal", "--var", "MarkdownPlanFile=docs/plans/plan.md", "--dry-run", "--json")
    assert perform.main(arguments) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "interactive_required"
    assert "exec-md-goal[agnostic]" in payload["error"]["message"]


def test_plan_action_reports_cli_activation_is_unavailable(monkeypatch, capsys, tmp_path):
    codex_home = tmp_path / "codex-home"
    actions = codex_home / "toolkit_perform_actions"
    actions.mkdir(parents=True)
    action = {
        "version": 1,
        "actions": {
            "plan-test": {
                "agnostic": {
                    "gloss": "Plan test",
                    "model": "default",
                    "reasoning_effort": "medium",
                    "goal_mode": False,
                    "plan_mode": True,
                    "plan_reasoning_effort": "high",
                    "no_edits": True,
                    "prompt_vars": {},
                    "prompt": "Plan this change.",
                    "requires_interactive": True,
                    "custom_codex_args": [],
                    "notes": "",
                }
            }
        },
    }
    (actions / "plan.json").write_text(json.dumps(action), encoding="ascii")
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    assert perform.main(local_arguments("--cwd", str(tmp_path), "plan-test", "--dry-run", "--json")) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "plan_mode_unavailable"
    assert "$toolkit:perform" in payload["error"]["message"]


def test_required_action_rejects_noninteractive_cli_override(monkeypatch, capsys, tmp_path):
    codex_home = tmp_path / "codex-home"
    actions = codex_home / "toolkit_perform_actions"
    actions.mkdir(parents=True)
    action = {
        "version": 1,
        "actions": {
            "interactive-test": {
                "agnostic": {
                    "gloss": "Interactive test",
                    "model": "default",
                    "reasoning_effort": "medium",
                    "goal_mode": False,
                    "plan_mode": False,
                    "plan_reasoning_effort": "medium",
                    "no_edits": False,
                    "prompt_vars": {},
                    "prompt": "Run interactively.",
                    "requires_interactive": True,
                    "custom_codex_args": [],
                    "notes": "",
                }
            }
        },
    }
    (actions / "interactive.json").write_text(json.dumps(action), encoding="ascii")
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    assert perform.main(local_arguments("--cwd", str(tmp_path), "interactive-test", "--non-interactive", "--dry-run", "--json")) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "interactive_required"
    assert "interactive-test[agnostic]" in payload["error"]["message"]

    def fake_exec(argv, env=None):
        raise ExecCalled(argv[0], argv, env)

    monkeypatch.setattr(perform_runtime, "replace_process", fake_exec)
    with pytest.raises(ExecCalled) as raised:
        perform.main(local_arguments("--cwd", str(tmp_path), "interactive-test"))
    assert "exec" not in raised.value.argv


def test_raw_codex_conflicts_are_rejected(capsys):
    assert perform.main(local_arguments("ensure-ascii-only", "--dry-run", "--json", "--", "--model", "other")) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "conflicting_extra_codex_args"

    assert perform.main(local_arguments("ensure-ascii-only", "--dry-run", "--json", "--", "--verbose")) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "conflicting_extra_codex_args"


@pytest.mark.parametrize("raw_argument", ["exec", "e", "review", "resume", "login", "mcp", "help"])
def test_raw_codex_subcommands_are_rejected(capsys, raw_argument):
    assert perform.main(local_arguments("ensure-ascii-only", "--dry-run", "--json", "--", raw_argument)) == 2
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "invalid_extra_codex_args"


def test_raw_codex_options_are_self_contained(capsys):
    assert perform.main(local_arguments("ensure-ascii-only", "--dry-run", "--json", "--", "--color", "never")) == 2
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "invalid_extra_codex_args"

    assert perform.main(local_arguments("ensure-ascii-only", "--dry-run", "--json", "--", "--color=never")) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "--color=never" in payload["argv"]


def test_incomplete_catalog_blocks_selector_resolution():
    scripts = PLUGIN_ROOT / "skills" / "perform" / "scripts"
    launcher_api = perform_runtime.import_runtime(str(scripts))
    catalog_module = importlib.import_module("toolkit_perform_runtime.catalog")
    discovery = types.SimpleNamespace(diagnostics=[], precedence_incomplete=False)
    catalog = catalog_module.ActionCatalog({}, [], discovery, precedence_incomplete=True)
    launcher = launcher_api.StandaloneLauncher(catalog)
    with pytest.raises(launcher_api.PerformRequestError) as raised:
        launcher.prepare_launch("missing")
    assert raised.value.status == "fatal_catalog"


def test_incomplete_catalog_keeps_missing_strict_list_filter_partial():
    scripts = PLUGIN_ROOT / "skills" / "perform" / "scripts"
    launcher_api = perform_runtime.import_runtime(str(scripts))
    catalog_module = importlib.import_module("toolkit_perform_runtime.catalog")
    discovery = types.SimpleNamespace(diagnostics=[], precedence_incomplete=True)
    catalog = catalog_module.ActionCatalog({}, [], discovery, precedence_incomplete=True)
    launcher = launcher_api.StandaloneLauncher(catalog)
    assert launcher.list_actions("missing[agnostic]") == {"variants": []}


def test_complete_catalog_keeps_missing_strict_list_filter_empty():
    scripts = PLUGIN_ROOT / "skills" / "perform" / "scripts"
    launcher_api = perform_runtime.import_runtime(str(scripts))
    catalog_module = importlib.import_module("toolkit_perform_runtime.catalog")
    discovery = types.SimpleNamespace(diagnostics=[], precedence_incomplete=False)
    catalog = catalog_module.ActionCatalog({}, [], discovery)
    launcher = launcher_api.StandaloneLauncher(catalog)
    assert launcher.list_actions("missing[agnostic]") == {"variants": []}


@pytest.mark.parametrize(
    "arguments",
    [
        ("list", "ensure-ascii-only[agnostic]", "--language", "agnostic", "--json"),
        ("show", "ensure-ascii-only[agnostic]", "--language", "agnostic", "--json"),
        ("run", "ensure-ascii-only[agnostic]", "--language", "agnostic", "--dry-run", "--json"),
        ("show", "help[agnostic]", "--language", "agnostic", "--json"),
    ],
)
def test_strict_selector_accepts_matching_language(capsys, arguments):
    assert perform.main(local_arguments(*arguments)) == 0
    assert json.loads(capsys.readouterr().out)


@pytest.mark.parametrize(
    "arguments",
    [
        ("list", "ensure-ascii-only[agnostic]", "--language", "python", "--json"),
        ("show", "ensure-ascii-only[agnostic]", "--language", "python", "--json"),
        ("run", "ensure-ascii-only[agnostic]", "--language", "python", "--dry-run", "--json"),
        ("show", "help[agnostic]", "--language", "python", "--json"),
    ],
)
def test_strict_selector_rejects_disagreeing_language(capsys, arguments):
    assert perform.main(local_arguments(*arguments)) == 2
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "conflicting_language"


def test_raw_codex_json_does_not_select_launcher_json_errors(capsys):
    assert perform.main(local_arguments("missing-action", "--", "--json")) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("codex-perform: ")
    assert "missing-action" in captured.err


def test_runtime_error_normalization_preserves_catalog_diagnostics():
    error = types.SimpleNamespace(status="fatal_catalog", message="Incomplete.", alternatives=[], diagnostics=["error: Broken source. (actions.json)"])
    normalized = perform._normalize_error(error)
    assert normalized.code == "fatal_catalog"
    assert normalized.exit_code == 3
    assert normalized.diagnostics == ["error: Broken source. (actions.json)"]


@pytest.mark.parametrize("action", ["ensure-ascii-only", "audit-agents-md-compliance"])
@pytest.mark.parametrize("raw_json", ["--json", "--json=true"])
def test_raw_codex_json_is_rejected_in_favor_of_structured_output(capsys, action, raw_json):
    assert perform.main(local_arguments(action, "--dry-run", "--", raw_json)) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "structured json_output field" in captured.err
