#!/usr/bin/env python3
"""Dependency-free smoke checks for an installed Python distribution."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import la_dev_codex_plugins


def run(command, environment=None, cwd=None):
    """Run one command and require successful UTF-8 output."""
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=20,
        check=False,
    )
    stdout = completed.stdout.decode("utf-8", errors="replace")
    stderr = completed.stderr.decode("utf-8", errors="replace")
    if completed.returncode != 0:
        raise AssertionError("Command failed with exit code {}: {!r}\nstdout:\n{}\nstderr:\n{}".format(completed.returncode, command, stdout, stderr))
    return stdout, stderr


def smoke_isolated_command(executable, expected_version):
    """Prove that the installed command ignores hostile import roots."""
    with tempfile.TemporaryDirectory(prefix="la-dev-codex-plugins-package-smoke-") as temporary_directory:
        temporary_root = Path(temporary_directory)
        hostile_package = temporary_root / "la_dev_codex_plugins"
        hostile_package.mkdir()
        (hostile_package / "__init__.py").write_text('raise RuntimeError("hostile package loaded")\n', encoding="ascii")
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(temporary_root)
        environment["CODEX_PERFORM_PYTHON"] = str(temporary_root / "hostile-python")

        stdout, stderr = run([executable, "--version"], environment=environment, cwd=str(temporary_root))
        if stdout.strip() != "codex-perform {}".format(expected_version) or stderr:
            raise AssertionError("Unexpected version output: stdout={!r}, stderr={!r}".format(stdout, stderr))

        stdout, stderr = run([executable, "--help"], environment=environment, cwd=str(temporary_root))
        if not stdout.startswith("usage: codex-perform ") or stderr:
            raise AssertionError("Unexpected help output: stdout={!r}, stderr={!r}".format(stdout, stderr))


def smoke_plugin_root(executable, plugin_root):
    """Exercise the installed command against one external Toolkit plugin."""
    stdout, stderr = run([executable, "--plugin-root", plugin_root, "show", "ensure-ascii-only", "--json"])
    payload = json.loads(stdout)
    if payload.get("selector") != "ensure-ascii-only[agnostic]" or stderr:
        raise AssertionError("Unexpected Toolkit result: payload={!r}, stderr={!r}".format(payload, stderr))


def main(argv=None):
    """Run every installed-distribution smoke check."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--plugin-root")
    args = parser.parse_args(argv)

    if sys.version_info < (3, 6):
        raise AssertionError("Python 3.6+ is required")
    if la_dev_codex_plugins.__version__ != args.expected_version:
        raise AssertionError("Imported version {!r} does not match {!r}".format(la_dev_codex_plugins.__version__, args.expected_version))
    executable = shutil.which("codex-perform")
    if executable is None:
        raise AssertionError("codex-perform is not available on PATH")

    smoke_isolated_command(executable, args.expected_version)
    if args.plugin_root is not None:
        smoke_plugin_root(executable, str(Path(args.plugin_root).resolve()))
    print("Installed package smoke checks passed on Python {}.{}.{}.".format(*sys.version_info[:3]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
