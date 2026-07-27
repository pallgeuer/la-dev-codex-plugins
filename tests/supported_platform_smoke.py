#!/usr/bin/env python3
"""Dependency-free smoke checks for supported operating systems and Python 3.6+."""

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PERFORM_SCRIPTS = REPOSITORY_ROOT / "plugins" / "toolkit" / "skills" / "perform" / "scripts"
TOOLKIT_ROOT = REPOSITORY_ROOT / "plugins" / "toolkit"
ACTIVATE = REPOSITORY_ROOT / "activate.sh"
LOUPE_RUNNER = REPOSITORY_ROOT / "plugins" / "la-review" / "skills" / "loupe" / "scripts" / "run_reviewers.py"


def run(command, environment, timeout=20):
    """Run one smoke command and require successful UTF-8 output."""
    completed = subprocess.run(
        command,
        cwd=str(REPOSITORY_ROOT),
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    stdout = completed.stdout.decode("utf-8", errors="replace")
    stderr = completed.stderr.decode("utf-8", errors="replace")
    if completed.returncode != 0:
        raise AssertionError("Command failed with exit code {}: {!r}\nstdout:\n{}\nstderr:\n{}".format(completed.returncode, command, stdout, stderr))
    return stdout


def load_module(name, path):
    """Load one shipped script as an importable module."""
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise AssertionError("Could not load {}".format(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def smoke_perform_scripts(environment, temporary_root):
    """Exercise action discovery, inspection, and atomic catalogue output."""
    listing = json.loads(run([sys.executable, str(PERFORM_SCRIPTS / "list_perform_actions.py"), "--cwd={}".format(REPOSITORY_ROOT)], environment))
    selectors = {variant["selector"] for variant in listing["variants"]}
    assert "check-cross-platform[agnostic]" in selectors

    inspection = json.loads(
        run(
            [
                sys.executable,
                str(PERFORM_SCRIPTS / "get_perform_action.py"),
                "--inspect=check-cross-platform[agnostic]",
                "--cwd={}".format(REPOSITORY_ROOT),
            ],
            environment,
        )
    )
    assert inspection["mode"] == "default"
    assert inspection["prompt_vars"]["OSList"]

    catalogue_path = temporary_root / "action_catalogue.md"
    command = [
        sys.executable,
        str(PERFORM_SCRIPTS / "write_perform_action_catalogue.py"),
        "--output={}".format(catalogue_path),
        "--cwd={}".format(REPOSITORY_ROOT),
    ]
    first = json.loads(run(command, environment))
    second = json.loads(run(command, environment))
    assert first["changed"] is True
    assert second["changed"] is False
    assert catalogue_path.read_bytes().startswith(b"<!-- toolkit-perform-action-catalogue:v1 -->\n")


def smoke_activated_launcher(environment):
    """Exercise the source activation script and isolated launcher bootstrap."""
    command = [
        "bash",
        "-c",
        'source "$1" && CODEX_PERFORM_PYTHON="$2" codex-perform list --plugin-root "$3" --codex "$2" --json',
        "supported-platform-smoke",
        str(ACTIVATE),
        sys.executable,
        str(TOOLKIT_ROOT),
    ]
    payload = json.loads(run(command, environment))
    assert any(variant["name"] == "check-cross-platform" for variant in payload["variants"])


def smoke_bounded_process(environment):
    """Exercise POSIX process-group timeout and pipe cleanup behavior."""
    sys.path.insert(0, str(REPOSITORY_ROOT / "src"))
    try:
        perform_runtime = importlib.import_module("la_dev_codex_plugins.cli._perform_runtime")
    finally:
        sys.path.pop(0)
    result = perform_runtime._run_bounded_command(
        [sys.executable, "-c", "import time; time.sleep(5)"],
        str(REPOSITORY_ROOT),
        environment,
        timeout=0.05,
    )
    assert result.timed_out is True
    assert result.capture_incomplete is False


def smoke_loupe_runner():
    """Exercise Loupe's Bash launch and UTF-8 JSON capture path."""
    runner = load_module("supported_platform_loupe_runner", LOUPE_RUNNER)
    reviewers = (runner.Reviewer("smoke", "printf smoke", "{review_scope}"),)
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        exit_code = runner.main(["supported-platform smoke"], reviewers=reviewers, environment={})
    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["reviewers"][0]["stdout"] == "smoke"


def main():
    """Run every dependency-free supported-platform smoke check."""
    if sys.version_info < (3, 6):
        raise AssertionError("Python 3.6+ is required")
    sys.dont_write_bytecode = True
    with tempfile.TemporaryDirectory(prefix="la-dev-codex-plugins-smoke-") as temporary_directory:
        temporary_root = Path(temporary_directory)
        codex_home = temporary_root / "codex-home"
        home = temporary_root / "home"
        codex_home.mkdir()
        home.mkdir()
        environment = dict(os.environ)
        environment.update(
            {
                "CODEX_HOME": str(codex_home),
                "HOME": str(home),
                "PYTHONDONTWRITEBYTECODE": "1",
            }
        )
        smoke_perform_scripts(environment, temporary_root)
        smoke_activated_launcher(environment)
        smoke_bounded_process(environment)
        smoke_loupe_runner()
    print("Supported-platform smoke checks passed on {} with Python {}.{}.{}.".format(sys.platform, *sys.version_info[:3]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
