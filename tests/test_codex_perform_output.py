"""Tests for Perform command-line output handling."""

import io
import json
import os
import subprocess
import sys
import types
from pathlib import Path

from la_dev_codex_plugins.cli import _perform_output as perform_output
from la_dev_codex_plugins.cli import _perform_runtime as perform_runtime

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPOSITORY_ROOT / "plugins" / "toolkit"


class BufferlessAsciiStream:
    """Text stream test double that accepts only ASCII."""

    encoding = "ascii"

    def __init__(self):
        """Collect written ASCII text."""
        self.value = ""

    def write(self, value):
        """Reject non-ASCII text like a narrow encoded stream."""
        value.encode(self.encoding)
        self.value += value


def test_prelaunch_display_escapes_untrusted_terminal_controls(capsys):
    config = types.SimpleNamespace(
        notes="note\\path\x1b]52;c;payload\x07\r\t\u202e\nnext",
        selector="test[agnostic]",
        custom_codex_args=("--future-option=value\x1b",),
    )
    spec = types.SimpleNamespace(config=config, rendered_prompt="prompt\\text\x1b[2J\u2028line")
    perform_output.display_prelaunch(spec)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "\x1b" not in captured.err
    assert "\x07" not in captured.err
    assert "\r" not in captured.err
    assert "\t" not in captured.err
    assert "\u202e" not in captured.err
    assert "\u2028" not in captured.err
    assert "note\\\\path\\x1b]52;c;payload\\x07\\x0d\\x09\\u202e\nnext" in captured.err
    assert "CODEX ACTION ARGS:" in captured.err
    assert "prompt\\\\text\\x1b[2J\\u2028line" in captured.err
    assert captured.err.startswith("NOTES TO USER:\n")
    assert "\n\nPERFORM: test[agnostic]\nCODEX ACTION ARGS:" in captured.err
    assert "\n\nPROMPT:\nprompt\\\\text" in captured.err


def test_human_dry_run_and_json_escape_terminal_controls(capsys):
    invocation = types.SimpleNamespace(
        argv=("codex", "--", "prompt\x1b\u202e"),
        to_dict=lambda: {"argv": ["codex", "--", "prompt\x1b\u202e"]},
    )
    perform_output.print_dry_run(invocation, "final-only")
    captured = capsys.readouterr()
    assert "\x1b" not in captured.out
    assert "\u202e" not in captured.out
    assert json.loads(captured.out.split("bash command:\n", 1)[0]) == {"argv": ["codex", "--", "prompt\x1b\u202e"], "output_mode": "final-only"}
    assert "$'prompt\\033\\342\\200\\256'" in captured.out


def test_bash_command_round_trips_exact_arguments():
    arguments = ["plain", "with space", "prompt\\path", "line\nnext", "\u03bb", "quote'"]
    command = "printf '%s\\0' " + perform_output.bash_command(arguments)
    completed = subprocess.run(["bash", "-c", command], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.split(b"\0")[:-1] == [argument.encode("utf-8") for argument in arguments]


def test_utf8_output_bypasses_ascii_text_encoding():
    binary = io.BytesIO()
    stream = io.TextIOWrapper(binary, encoding="ascii")
    perform_output.write_text("\u03bb", stream=stream)
    stream.flush()
    assert binary.getvalue() == "\u03bb".encode("utf-8")


def test_binary_output_bypasses_text_encoding():
    binary = io.BytesIO()
    stream = io.TextIOWrapper(binary, encoding="ascii")
    perform_output.write_bytes(b"\xff\x00", stream=stream)
    stream.flush()
    assert binary.getvalue() == b"\xff\x00"


def test_bufferless_ascii_output_uses_deterministic_escapes():
    text_stream = BufferlessAsciiStream()
    byte_stream = BufferlessAsciiStream()
    invalid_stream = BufferlessAsciiStream()
    perform_output.write_text("\u03bb", stream=text_stream)
    perform_output.write_bytes("\u03bb".encode("utf-8"), stream=byte_stream)
    perform_output.write_bytes(b"\xff", stream=invalid_stream)
    assert text_stream.value == "\\u03bb"
    assert byte_stream.value == "\\u03bb"
    assert invalid_stream.value == "\\xff"


def test_list_uses_separate_name_and_language_columns_and_wraps_gloss(monkeypatch, capsys):
    monkeypatch.setattr(perform_output, "_terminal_width", lambda: 80)
    payload = {
        "variants": [
            {
                "selector": "audit-test-organization[agnostic]",
                "gloss": "Audit test suite organization and quality",
                "prompt_vars": {},
            },
            {
                "selector": "check-cross-platform[agnostic]",
                "gloss": "Check repository support for specified operating systems",
                "prompt_vars": {"OSList": "Free-form list of operating systems to assess, including any requested versions or architectures."},
            },
        ]
    }
    perform_output.print_list(payload)
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out == (
        "NAME                     LANGUAGE  GLOSS\n"
        "audit-test-organization  agnostic  Audit test suite organization and quality\n"
        "check-cross-platform     agnostic  Check repository support for specified\n"
        "                                   operating systems\n"
        "                                   OSList: Free-form list of operating systems\n"
        "                                           to assess, including any requested\n"
        "                                           versions or architectures.\n"
    )


def test_list_preserves_minimum_gloss_width_for_narrow_terminal(monkeypatch, capsys):
    monkeypatch.setattr(perform_output, "_terminal_width", lambda: 20)
    perform_output.print_list(
        {
            "variants": [
                {
                    "selector": "exceptionally-long-action-name[exceptionally-long-language]",
                    "gloss": "One two three four five six seven eight nine ten eleven",
                }
            ]
        }
    )
    lines = capsys.readouterr().out.splitlines()
    gloss_column = lines[0].index("GLOSS")
    assert lines == [
        "NAME                            LANGUAGE                     GLOSS",
        "exceptionally-long-action-name  exceptionally-long-language  One two three four five six seven eight",
        "{}nine ten eleven".format(" " * gloss_column),
    ]


def test_error_output_preserves_diagnostics_for_json_and_human_modes(capsys):
    error = perform_runtime.CliError("Broken catalog.", exit_code=3, code="fatal_catalog", diagnostics=["error: Bad action.\x1b (actions.json)"])
    assert perform_output.emit_error(error, json_requested=True) == 3
    assert json.loads(capsys.readouterr().out) == {
        "error": {"code": "fatal_catalog", "message": "Broken catalog."},
        "diagnostics": ["error: Bad action.\x1b (actions.json)"],
    }

    assert perform_output.emit_error(error, json_requested=False) == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "codex-perform: Broken catalog.\nDiagnostic: error: Bad action.\\x1b (actions.json)\n"


def test_standalone_cli_preserves_unicode_under_ascii_locale(tmp_path):
    codex_home = tmp_path / "codex-home"
    actions = codex_home / "toolkit_perform_actions"
    actions.mkdir(parents=True)
    action = {
        "version": 1,
        "actions": {
            "unicode": {
                "agnostic": {
                    "gloss": "Handle \u03bb",
                    "model": "default",
                    "reasoning_effort": "medium",
                    "goal_mode": False,
                    "plan_mode": False,
                    "plan_reasoning_effort": "medium",
                    "no_edits": False,
                    "prompt_vars": {},
                    "prompt": "Handle \u03bb.",
                    "requires_interactive": False,
                    "custom_codex_args": [],
                    "notes": "",
                }
            }
        },
    }
    (actions / "unicode.json").write_text(json.dumps(action), encoding="ascii")
    fake_codex = tmp_path / "fake-codex"
    fake_codex.write_text("#!/bin/sh\nprintf 'final response\\n'\nprintf 'hidden progress\\n' >&2\n", encoding="ascii")
    fake_codex.chmod(0o755)
    env = os.environ.copy()
    env.update({"CODEX_HOME": str(codex_home), "LC_ALL": "C", "PYTHONCOERCECLOCALE": "0", "PYTHONIOENCODING": "ascii", "PYTHONPATH": str(REPOSITORY_ROOT / "src"), "PYTHONUTF8": "0"})
    base_command = [
        sys.executable,
        "-m",
        "la_dev_codex_plugins.cli.perform",
        "--plugin-root",
        str(PLUGIN_ROOT),
        "--cwd",
        str(tmp_path),
    ]
    listing = subprocess.run([*base_command, "list", "unicode"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    dry_run = subprocess.run([*base_command, "--codex", "/bin/true", "unicode", "--dry-run", "--json"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    final_only = subprocess.run([*base_command, "--codex", str(fake_codex), "unicode", "--non-interactive"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    assert listing.returncode == 0, listing.stderr
    assert dry_run.returncode == 0, dry_run.stderr
    assert final_only.returncode == 0, final_only.stderr
    assert "\u03bb".encode("utf-8") in listing.stdout
    assert json.loads(dry_run.stdout.decode("utf-8"))["submitted_prompt"] == "Handle \u03bb."
    assert final_only.stdout == b"final response\n"
    assert final_only.stderr == b""
