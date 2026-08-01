"""Tests for the Loupe reviewer runner."""

import importlib.util
import json
import pathlib
from types import ModuleType
from typing import Any, Callable, List, Sequence

import pytest

RUNNER_PATH = pathlib.Path(__file__).resolve().parents[5] / "plugins" / "la-review" / "skills" / "loupe" / "scripts" / "run_reviewers.py"


def load_loupe_runner() -> ModuleType:
    """Load the Loupe runner script as an importable module."""
    spec = importlib.util.spec_from_file_location("loupe_run_reviewers", RUNNER_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def executable_availability(*available_executables: str) -> Callable[[str], bool]:
    """Return an availability probe for selected executable names."""
    return lambda executable: executable in available_executables


def unexpected_executable_probe(_executable: str) -> bool:
    """Fail if invalid configuration reaches executable launch planning."""
    raise AssertionError("reviewer launch planning should not run")


def test_parse_args_requires_review_scope() -> None:
    """Require callers to pass explicit review scope text."""
    runner = load_loupe_runner()

    with pytest.raises(SystemExit) as exc_info:
        runner.parse_args([])

    assert exc_info.value.code == 2


def test_parse_args_rejects_blank_review_scope() -> None:
    """Reject blank scope values instead of substituting a default."""
    runner = load_loupe_runner()

    for scope in ("", "   "):
        with pytest.raises(SystemExit) as exc_info:
            runner.parse_args([scope])

        assert exc_info.value.code == 2


def test_parse_args_rejects_multiple_review_scope_arguments() -> None:
    """Require the review scope to be passed as one shell-quoted argument."""
    runner = load_loupe_runner()

    with pytest.raises(SystemExit) as exc_info:
        runner.parse_args(["uncommitted", "changes"])

    assert exc_info.value.code == 2


@pytest.mark.parametrize("timeout", ["-1", "nan", "NaN", "inf", "-inf", "Infinity"])
def test_parse_args_rejects_negative_and_nonfinite_timeouts(timeout: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Reject timeout values that cannot produce a finite deadline or strict JSON."""
    runner = load_loupe_runner()
    monkeypatch.setattr(runner, "executable_is_available", unexpected_executable_probe)

    with pytest.raises(SystemExit) as exc_info:
        runner.main(["--dry-run", "--timeout-seconds", timeout, "configured scope"], environment={})

    assert exc_info.value.code == 2


def test_parse_args_accepts_zero_timeout() -> None:
    """Preserve zero as an immediate reviewer timeout."""
    runner = load_loupe_runner()

    args = runner.parse_args(["--timeout-seconds", "0", "configured scope"], environment={})

    assert args.timeout_seconds == 0


def test_dry_run_uses_expected_json_shape_and_reviewer_commands(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    """Emit dry-run reviewer names and commands using the public JSON keys."""
    runner = load_loupe_runner()
    session_id = "11111111-2222-4333-8444-555555555555"
    monkeypatch.setattr(runner, "executable_is_available", executable_availability("claude", "codex", "jq"))
    monkeypatch.setattr(runner.uuid, "uuid4", lambda: session_id)

    exit_code = runner.main(["--dry-run", "uncommitted changes"], environment={})

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert list(payload) == ["review_scope", "git_root", "timeout_seconds", "reviewers"]
    assert payload["review_scope"] == "uncommitted changes"
    assert payload["timeout_seconds"] == 1800
    assert [list(reviewer) for reviewer in payload["reviewers"]] == [
        ["reviewer_name", "launched_command", "session_id", "session_log_path"],
        ["reviewer_name", "launched_command", "session_id", "session_log_path"],
        ["reviewer_name", "launched_command", "session_id", "session_log_path"],
        ["reviewer_name", "launched_command", "session_id", "session_log_path"],
    ]
    assert payload["reviewers"] == [
        {
            "reviewer_name": "Claude Code Review",
            "launched_command": runner.CLAUDE_COMMAND_TEMPLATE.format(
                prompt=runner.shlex.quote(
                    runner.CODE_REVIEW_COMMAND_PROMPT_TEMPLATE.format(
                        review_scope="uncommitted changes", review_policy=runner.REVIEW_POLICY, review_skill_prohibition=runner.REVIEW_SKILL_PROHIBITION, review_note=runner.REVIEW_NOTE
                    )
                ),
                reasoning_effort="medium",
                session_id=runner.shlex.quote(session_id),
            ),
            "session_id": session_id,
            "session_log_path": runner.claude_session_log_path({}, payload["git_root"], session_id),
        },
        {
            "reviewer_name": "Codex Review",
            "launched_command": runner.CODEX_COMMAND_TEMPLATE.format(
                prompt=runner.shlex.quote(
                    runner.REVIEW_COMMAND_PROMPT_TEMPLATE.format(
                        review_scope="uncommitted changes", review_policy=runner.REVIEW_POLICY, review_skill_prohibition=runner.REVIEW_SKILL_PROHIBITION, review_note=runner.REVIEW_NOTE
                    )
                ),
                reasoning_effort="high",
            ),
            "session_id": None,
            "session_log_path": None,
        },
        {
            "reviewer_name": "Codex Correctness",
            "launched_command": runner.CODEX_COMMAND_TEMPLATE.format(
                prompt=runner.shlex.quote(
                    runner.CORRECTNESS_REVIEW_PROMPT_TEMPLATE.format(
                        review_scope="uncommitted changes", review_policy=runner.REVIEW_POLICY, review_skill_prohibition=runner.REVIEW_SKILL_PROHIBITION, review_note=runner.REVIEW_NOTE
                    )
                ),
                reasoning_effort="high",
            ),
            "session_id": None,
            "session_log_path": None,
        },
        {
            "reviewer_name": "Codex Design",
            "launched_command": runner.CODEX_COMMAND_TEMPLATE.format(
                prompt=runner.shlex.quote(
                    runner.DESIGN_REVIEW_PROMPT_TEMPLATE.format(
                        review_scope="uncommitted changes", review_policy=runner.REVIEW_POLICY, review_skill_prohibition=runner.REVIEW_SKILL_PROHIBITION, review_note=runner.REVIEW_NOTE
                    )
                ),
                reasoning_effort="high",
            ),
            "session_id": None,
            "session_log_path": None,
        },
    ]
    assert runner.REVIEW_SKILL_PROHIBITION in payload["reviewers"][2]["launched_command"]
    assert runner.REVIEW_SKILL_PROHIBITION in payload["reviewers"][3]["launched_command"]


def test_environment_effort_overrides_apply_by_provider_and_reviewer(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    """Apply reviewer environment values over provider values and provider values over built-in defaults."""
    runner = load_loupe_runner()
    monkeypatch.setattr(runner, "executable_is_available", executable_availability("claude", "codex", "jq"))
    environment = {
        "LOUPE_EFFORT_CLAUDE": "low",
        "LOUPE_EFFORT_CLAUDE_CODE_REVIEW": "high",
        "LOUPE_EFFORT_CODEX": "medium",
        "LOUPE_EFFORT_CODEX_DESIGN": "ultra",
    }

    exit_code = runner.main(["--dry-run", "configured scope"], environment=environment)

    assert exit_code == 0
    commands = [reviewer["launched_command"] for reviewer in json.loads(capsys.readouterr().out)["reviewers"]]
    assert "--effort high" in commands[0]
    assert "model_reasoning_effort='\"medium\"'" in commands[1]
    assert "model_reasoning_effort='\"medium\"'" in commands[2]
    assert "model_reasoning_effort='\"ultra\"'" in commands[3]


def test_cli_effort_overrides_win_by_layer_and_later_values(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    """Prefer CLI reviewer and provider values over environment values, with the final duplicate winning."""
    runner = load_loupe_runner()
    monkeypatch.setattr(runner, "executable_is_available", executable_availability("claude", "codex", "jq"))
    environment = {
        "LOUPE_EFFORT_CODEX_CORRECTNESS": "ultra",
        "LOUPE_EFFORT_CODEX_DESIGN": "max",
    }

    exit_code = runner.main(
        [
            "--dry-run",
            "--effort",
            "codex=low",
            "--effort",
            "codex-correctness=xhigh",
            "--effort",
            "codex-correctness=high",
            "configured scope",
        ],
        environment=environment,
    )

    assert exit_code == 0
    commands = [reviewer["launched_command"] for reviewer in json.loads(capsys.readouterr().out)["reviewers"]]
    assert "--effort medium" in commands[0]
    assert "model_reasoning_effort='\"low\"'" in commands[1]
    assert "model_reasoning_effort='\"high\"'" in commands[2]
    assert "model_reasoning_effort='\"low\"'" in commands[3]


def test_every_builtin_reviewer_has_stable_effort_configuration_keys() -> None:
    """Expose provider-wide and reviewer-specific keys and environment variables for every built-in reviewer."""
    runner = load_loupe_runner()

    key_providers = runner.effort_key_providers(runner.REVIEWERS)

    assert {key: provider.provider_key for key, provider in key_providers.items()} == {
        "claude": "claude",
        "codex": "codex",
        "claude-code-review": "claude",
        "codex-review": "codex",
        "codex-correctness": "codex",
        "codex-design": "codex",
    }
    assert {key: runner.effort_environment_variable(key) for key in key_providers} == {
        "claude": "LOUPE_EFFORT_CLAUDE",
        "codex": "LOUPE_EFFORT_CODEX",
        "claude-code-review": "LOUPE_EFFORT_CLAUDE_CODE_REVIEW",
        "codex-review": "LOUPE_EFFORT_CODEX_REVIEW",
        "codex-correctness": "LOUPE_EFFORT_CODEX_CORRECTNESS",
        "codex-design": "LOUPE_EFFORT_CODEX_DESIGN",
    }
    assert "--effort medium" in runner.REVIEWERS[0].build_command("configured scope", session_id="11111111-2222-4333-8444-555555555555")
    assert all("model_reasoning_effort='\"high\"'" in reviewer.build_command("configured scope") for reviewer in runner.REVIEWERS[1:])


def test_persistent_reviewer_requires_assigned_session_id() -> None:
    """Reject commands that would launch a persistent reviewer without its assigned identity."""
    runner = load_loupe_runner()

    with pytest.raises(ValueError, match="requires a session ID"):
        runner.REVIEWERS[0].build_command("configured scope")


def test_claude_session_log_path_uses_config_root_and_ascii_project_encoding(tmp_path: pathlib.Path) -> None:
    """Build Claude's documented transcript path from its config root, Git root, and session ID."""
    runner = load_loupe_runner()
    config_root = tmp_path / "claude state"
    git_root = "/work/Review repo.v1/\N{SNOWMAN}"

    path = runner.claude_session_log_path({"CLAUDE_CONFIG_DIR": str(config_root)}, git_root, "session-id")

    assert path == str(config_root / "projects" / "-work-Review-repo-v1--" / "session-id.jsonl")


def test_relative_claude_config_root_resolves_from_git_root() -> None:
    """Resolve a relative Claude config override from the reviewer's launch directory."""
    runner = load_loupe_runner()

    assert runner.claude_config_root({"CLAUDE_CONFIG_DIR": "state/claude"}, "/repo/root") == "/repo/root/state/claude"


def test_persistent_reviewer_launch_plan_assigns_session_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """Assign one UUID consistently to a persistent reviewer's command and transcript path."""
    runner = load_loupe_runner()
    session_id = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    reviewer = runner.Reviewer("Persistent", "review --session {session_id} {prompt}", "{review_scope}", persistent_session=True)
    monkeypatch.setattr(runner.uuid, "uuid4", lambda: session_id)

    runs = runner.reviewer_launch_plan((reviewer,), "metadata scope", git_root="/repo/root", environment={"CLAUDE_CONFIG_DIR": "/config"})

    assert len(runs) == 1
    assert runs[0].session_id == session_id
    assert runs[0].session_log_path == "/config/projects/-repo-root/{}.jsonl".format(session_id)
    assert "--session {}".format(session_id) in runs[0].launched_command


def test_persistent_reviewer_keeps_session_metadata_on_launch_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Retain assigned transcript metadata when a helper prevents reviewer launch."""
    runner = load_loupe_runner()
    session_id = "aaaaaaaa-bbbb-4ccc-8ddd-ffffffffffff"
    reviewer = runner.Reviewer(
        "Persistent",
        "review --session {session_id} {prompt}",
        "{review_scope}",
        required_executable="claude",
        additional_required_executables=("jq",),
        persistent_session=True,
    )
    monkeypatch.setattr(runner, "executable_is_available", executable_availability("claude"))
    monkeypatch.setattr(runner.uuid, "uuid4", lambda: session_id)

    run = runner.reviewer_launch_plan((reviewer,), "metadata scope", git_root="/repo/root", environment={"CLAUDE_CONFIG_DIR": "/config"})[0]
    result = run.result()

    assert result["status"] == "launch_failed"
    assert result["session_id"] == session_id
    assert result["session_log_path"] == "/config/projects/-repo-root/{}.jsonl".format(session_id)


def test_reviewer_configuration_rejects_duplicate_and_colliding_keys() -> None:
    """Reject reviewer keys that would overwrite provider or reviewer configuration."""
    runner = load_loupe_runner()
    duplicate = (
        runner.Reviewer("First", "printf first", "{review_scope}", reviewer_key="same", provider=runner.CODEX_PROVIDER),
        runner.Reviewer("Second", "printf second", "{review_scope}", reviewer_key="same", provider=runner.CODEX_PROVIDER),
    )
    collision = (runner.Reviewer("Collision", "printf collision", "{review_scope}", reviewer_key="codex", provider=runner.CODEX_PROVIDER),)

    with pytest.raises(ValueError, match="duplicate or colliding"):
        runner.effort_key_providers(duplicate)
    with pytest.raises(ValueError, match="duplicate or colliding"):
        runner.effort_key_providers(collision)


def test_reviewer_configuration_rejects_invalid_provider_records() -> None:
    """Validate provider defaults, registration, and complete reviewer metadata."""
    runner = load_loupe_runner()
    invalid_default = runner.ReasoningEffortProvider("invalid", "max", ("low", "high"))
    unregistered = runner.ReasoningEffortProvider("custom", "low", ("low",))

    with pytest.raises(ValueError, match="default"):
        runner.effort_key_providers((), providers=(invalid_default,))
    with pytest.raises(ValueError, match="both reviewer_key and provider"):
        runner.effort_key_providers((runner.Reviewer("Incomplete", "printf incomplete", "{review_scope}", reviewer_key="incomplete"),))
    with pytest.raises(ValueError, match="unregistered"):
        runner.effort_key_providers((runner.Reviewer("Unknown", "printf unknown", "{review_scope}", reviewer_key="unknown", provider=unregistered),))


def test_unconfigured_custom_reviewer_remains_valid() -> None:
    """Allow custom reviewers that do not participate in effort configuration."""
    runner = load_loupe_runner()
    reviewer = runner.Reviewer("Custom", "printf custom", "{review_scope}")

    assert runner.resolve_reasoning_efforts((reviewer,), {}, {}) == {}
    assert runner.effort_key_providers((reviewer,))


@pytest.mark.parametrize(
    "assignment",
    [
        "broken",
        "=high",
        "codex=",
        "unknown=high",
        "claude=minimal",
        "codex=maximum",
    ],
)
def test_invalid_cli_effort_overrides_fail_before_launch(assignment: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Reject malformed, unknown, and provider-incompatible CLI effort overrides before probing executables."""
    runner = load_loupe_runner()
    monkeypatch.setattr(runner, "executable_is_available", unexpected_executable_probe)

    with pytest.raises(SystemExit) as exc_info:
        runner.main(["--dry-run", "--effort", assignment, "configured scope"], environment={})

    assert exc_info.value.code == 2


@pytest.mark.parametrize(
    ("variable", "reasoning_effort"),
    [
        ("LOUPE_EFFORT_CODEX", ""),
        ("LOUPE_EFFORT_CODEX_DESIGN", "maximum"),
        ("LOUPE_EFFORT_CLAUDE_CODE_REVIEW", "minimal"),
    ],
)
def test_invalid_environment_effort_overrides_fail_before_launch(variable: str, reasoning_effort: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Reject blank and provider-incompatible environment defaults before probing executables."""
    runner = load_loupe_runner()
    monkeypatch.setattr(runner, "executable_is_available", unexpected_executable_probe)

    with pytest.raises(SystemExit) as exc_info:
        runner.main(["--dry-run", "configured scope"], environment={variable: reasoning_effort})

    assert exc_info.value.code == 2


def test_dry_run_skips_claude_reviewers_when_claude_is_missing(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    """Omit Claude reviewers from dry-run output when the Claude CLI is unavailable."""
    runner = load_loupe_runner()
    monkeypatch.setattr(runner, "executable_is_available", executable_availability("codex", "jq"))

    exit_code = runner.main(["--dry-run", "uncommitted changes"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert list(payload) == ["review_scope", "git_root", "timeout_seconds", "reviewers"]
    reviewer_names = [reviewer["reviewer_name"] for reviewer in payload["reviewers"]]
    assert reviewer_names == ["Codex Review", "Codex Correctness", "Codex Design"]
    assert all(not reviewer_name.startswith("Claude ") for reviewer_name in reviewer_names)


def test_dry_run_skips_codex_reviewers_when_codex_is_missing(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    """Omit Codex reviewers from dry-run output when the Codex CLI is unavailable."""
    runner = load_loupe_runner()
    monkeypatch.setattr(runner, "executable_is_available", executable_availability("claude", "jq"))

    exit_code = runner.main(["--dry-run", "uncommitted changes"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert list(payload) == ["review_scope", "git_root", "timeout_seconds", "reviewers"]
    reviewer_names = [reviewer["reviewer_name"] for reviewer in payload["reviewers"]]
    assert reviewer_names == ["Claude Code Review"]


def test_dry_run_output_file_matches_stdout(capsys: pytest.CaptureFixture[str], tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Write the exact emitted dry-run JSON to the requested output file."""
    runner = load_loupe_runner()
    monkeypatch.setattr(runner, "executable_is_available", executable_availability("claude", "codex", "jq"))
    output_path = tmp_path / "reviewers.json"

    exit_code = runner.main(["--dry-run", "--output", str(output_path), "uncommitted changes"])

    stdout = capsys.readouterr().out
    assert exit_code == 0
    assert output_path.read_text(encoding="utf-8") == stdout
    assert json.loads(stdout)["review_scope"] == "uncommitted changes"


def test_reviewer_launch_plan_uses_required_executable_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """Filter reviewer runs by executable metadata instead of display name."""
    runner = load_loupe_runner()
    monkeypatch.setattr(runner, "executable_is_available", lambda _executable: False)
    reviewers = (
        runner.Reviewer("Claude Local", "printf keep", "{review_scope}"),
        runner.Reviewer("Anthropic Review", "printf skip", "{review_scope}", required_executable="claude"),
    )

    runs = runner.reviewer_launch_plan(reviewers, "metadata scope")

    assert [run.reviewer.reviewer_name for run in runs] == ["Claude Local"]
    assert [run.launch_error for run in runs] == [None]


def test_reviewer_launch_plan_shares_executable_availability_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Probe each executable only once across primary and helper dependencies."""
    runner = load_loupe_runner()
    checked_executables: List[str] = []

    def executable_is_available(executable: str) -> bool:
        checked_executables.append(executable)
        return True

    monkeypatch.setattr(runner, "executable_is_available", executable_is_available)
    reviewers = (
        runner.Reviewer("Primary Shared", "printf primary", "{review_scope}", required_executable="shared-tool"),
        runner.Reviewer("Helper Shared", "printf helper", "{review_scope}", additional_required_executables=("shared-tool",)),
    )

    runs = runner.reviewer_launch_plan(reviewers, "shared cache scope")

    assert [run.reviewer.reviewer_name for run in runs] == ["Primary Shared", "Helper Shared"]
    assert [run.launch_error for run in runs] == [None, None]
    assert checked_executables == ["shared-tool"]


def test_reviewer_launch_plan_attaches_missing_helper_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Store helper dependency failures on the planned reviewer run."""
    runner = load_loupe_runner()
    monkeypatch.setattr(runner, "executable_is_available", executable_availability("codex"))
    reviewers = (runner.Reviewer("Codex Local", "printf should-not-run", "{review_scope}", required_executable="codex", additional_required_executables=("jq",)),)

    runs = runner.reviewer_launch_plan(reviewers, "helper-missing scope")

    assert len(runs) == 1
    assert runs[0].launch_error is not None
    assert "jq" in runs[0].launch_error
    assert "Codex Local" in runs[0].launch_error


def test_executable_availability_uses_reviewer_launch_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    """Probe executable availability through bash login-shell command resolution."""
    runner = load_loupe_runner()
    launched_commands: List[Sequence[str]] = []

    class CompletedProcess:
        returncode = 0

    def run(command: Sequence[str], **_kwargs: Any) -> CompletedProcess:
        launched_commands.append(command)
        return CompletedProcess()

    monkeypatch.setattr(runner.subprocess, "run", run)

    assert runner.executable_is_available("claude") is True
    assert launched_commands == [["bash", "-lc", "command -v claude"]]


def test_missing_claude_skips_claude_reviewers_before_launch(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    """Do not launch Claude reviewers when the Claude CLI is unavailable."""
    runner = load_loupe_runner()
    monkeypatch.setattr(runner, "executable_is_available", executable_availability("codex", "jq"))
    reviewers = (
        runner.Reviewer("Claude Missing", "printf should-not-run; exit 9", "{review_scope}", required_executable="claude"),
        runner.Reviewer("Codex Local", "printf ok", "{review_scope}", required_executable="codex", additional_required_executables=("jq",)),
    )

    exit_code = runner.main(["filtered scope"], reviewers=reviewers)

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert [reviewer["reviewer_name"] for reviewer in payload["reviewers"]] == ["Codex Local"]
    assert payload["reviewers"][0]["stdout"] == "ok"


def test_all_filtered_reviewers_return_nonzero_and_empty_payload(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail clearly when no configured reviewer can be launched."""
    runner = load_loupe_runner()
    monkeypatch.setattr(runner, "executable_is_available", lambda _executable: False)
    reviewers = (runner.Reviewer("Anthropic Review", "printf should-not-run", "{review_scope}", required_executable="claude"),)

    exit_code = runner.main(["filtered scope"], reviewers=reviewers)

    captured = capsys.readouterr()
    assert exit_code == 1
    assert runner.NO_LAUNCHABLE_REVIEWERS_MESSAGE in captured.err
    payload = json.loads(captured.out)
    assert list(payload) == ["review_scope", "git_root", "timeout_seconds", "elapsed_seconds", "reviewers"]
    assert payload["reviewers"] == []


def test_dry_run_all_filtered_reviewers_return_nonzero_and_empty_payload(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail dry runs clearly when no configured reviewer can be launched."""
    runner = load_loupe_runner()
    monkeypatch.setattr(runner, "executable_is_available", lambda _executable: False)
    reviewers = (runner.Reviewer("Anthropic Review", "printf should-not-run", "{review_scope}", required_executable="claude"),)

    exit_code = runner.main(["--dry-run", "filtered scope"], reviewers=reviewers)

    captured = capsys.readouterr()
    assert exit_code == 1
    assert runner.NO_LAUNCHABLE_REVIEWERS_MESSAGE in captured.err
    payload = json.loads(captured.out)
    assert list(payload) == ["review_scope", "git_root", "timeout_seconds", "reviewers"]
    assert payload["reviewers"] == []


def test_missing_additional_executable_produces_launch_failed_without_launch(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail a launchable reviewer clearly when a helper executable is unavailable."""
    runner = load_loupe_runner()
    monkeypatch.setattr(runner, "executable_is_available", executable_availability("codex"))
    reviewers = (runner.Reviewer("Codex Local", "printf should-not-run", "{review_scope}", required_executable="codex", additional_required_executables=("jq",)),)

    exit_code = runner.main(["helper-missing scope"], reviewers=reviewers)

    captured = capsys.readouterr()
    assert exit_code == 1
    payload = json.loads(captured.out)
    result = payload["reviewers"][0]
    assert result["reviewer_name"] == "Codex Local"
    assert result["status"] == "launch_failed"
    assert result["return_code"] is None
    assert result["stdout"] == ""
    assert "jq" in result["stderr"]
    assert "Codex Local" in result["stderr"]


def test_dry_run_reports_missing_additional_executable(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    """Return dry-run commands while warning about missing helper executables."""
    runner = load_loupe_runner()
    monkeypatch.setattr(runner, "executable_is_available", executable_availability("codex"))
    reviewers = (runner.Reviewer("Codex Local", "printf would-run", "{review_scope}", required_executable="codex", additional_required_executables=("jq",)),)

    exit_code = runner.main(["--dry-run", "helper-missing scope"], reviewers=reviewers)

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "jq" in captured.err
    assert "Codex Local" in captured.err
    payload = json.loads(captured.out)
    assert [reviewer["reviewer_name"] for reviewer in payload["reviewers"]] == ["Codex Local"]
    assert payload["reviewers"][0]["launched_command"] == "printf would-run"


def test_failed_reviewer_produces_failed_status_and_nonzero_exit(capsys: pytest.CaptureFixture[str]) -> None:
    """Return nonzero when any reviewer command fails."""
    runner = load_loupe_runner()
    reviewers = (
        runner.Reviewer("success", "printf ok", "{review_scope}"),
        runner.Reviewer("failure", "printf problem >&2; exit 4", "{review_scope}"),
    )

    exit_code = runner.main(["failing scope"], reviewers=reviewers)

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    success, failure = payload["reviewers"]
    assert success["status"] == "succeeded"
    assert success["return_code"] == 0
    assert failure["status"] == "failed"
    assert failure["return_code"] == 4
    assert failure["stderr"] == "problem"


@pytest.mark.parametrize(
    ("command", "arguments", "expected_status"),
    [
        ("printf ok # {session_id}", ["persistent success"], "succeeded"),
        ("exit 4 # {session_id}", ["persistent failure"], "failed"),
        ("sleep 10 # {session_id}", ["--timeout-seconds", "0", "persistent timeout"], "timed_out"),
    ],
)
def test_persistent_session_metadata_survives_reviewer_outcomes(
    command: str,
    arguments: List[str],
    expected_status: str,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retain assigned session metadata across successful, failed, and timed-out runs."""
    runner = load_loupe_runner()
    session_id = "aaaaaaaa-bbbb-4ccc-8ddd-111111111111"
    reviewer = runner.Reviewer("Persistent", command, "{review_scope}", persistent_session=True)
    monkeypatch.setattr(runner.uuid, "uuid4", lambda: session_id)

    runner.main(arguments, reviewers=(reviewer,), environment={"CLAUDE_CONFIG_DIR": "/config"})

    payload = json.loads(capsys.readouterr().out)
    result = payload["reviewers"][0]
    assert result["status"] == expected_status
    assert result["session_id"] == session_id
    assert result["session_log_path"] == "/config/projects/{}/{}.jsonl".format(runner.re.sub(r"[^A-Za-z0-9]", "-", payload["git_root"]), session_id)


def test_zero_timeout_immediately_stops_active_reviewer(capsys: pytest.CaptureFixture[str]) -> None:
    """Treat a zero timeout as an immediate global reviewer timeout."""
    runner = load_loupe_runner()
    reviewers = (runner.Reviewer("slow", "sleep 10", "{review_scope}"),)

    exit_code = runner.main(["--timeout-seconds", "0", "immediate timeout"], reviewers=reviewers)

    assert exit_code == 1
    result = json.loads(capsys.readouterr().out)["reviewers"][0]
    assert result["status"] == "timed_out"
    assert result["timed_out"] is True


def test_json_output_rejects_nonfinite_numbers(capsys: pytest.CaptureFixture[str]) -> None:
    """Keep emitted reviewer artifacts valid for strict JSON parsers."""
    runner = load_loupe_runner()

    with pytest.raises(ValueError, match="Out of range"):
        runner.emit_json_output({"invalid": float("nan")}, None)

    assert capsys.readouterr().out == ""


def test_review_output_file_matches_stdout(capsys: pytest.CaptureFixture[str], tmp_path: pathlib.Path) -> None:
    """Write the exact emitted reviewer JSON to the requested output file."""
    runner = load_loupe_runner()
    output_path = tmp_path / "reviewers.json"
    reviewers = (runner.Reviewer("only", "printf result", "{review_scope}"),)

    exit_code = runner.main(["--output", str(output_path), "artifact scope"], reviewers=reviewers)

    stdout = capsys.readouterr().out
    assert exit_code == 0
    assert output_path.read_text(encoding="utf-8") == stdout
    payload = json.loads(stdout)
    assert payload["review_scope"] == "artifact scope"
    assert payload["reviewers"][0]["stdout"] == "result"


def test_reviewer_elapsed_timer_starts_at_launch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start reviewer elapsed timing at process launch instead of run construction."""
    runner = load_loupe_runner()
    run = runner.ReviewerRun(runner.Reviewer("timed", "printf ok", "{review_scope}"), "printf ok")
    times = iter((100.0, 100.25))

    class FakePopen:
        returncode = 0

        def wait(self) -> int:
            return 0

    monkeypatch.setattr(runner.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *_args, **_kwargs: FakePopen())

    assert run.started_at is None
    assert run.elapsed_seconds() == 0.0

    run.launch()
    assert run.thread is not None
    run.thread.join()
    run.close()

    assert run.started_at == 100.0
    assert run.elapsed_seconds() == 0.25
