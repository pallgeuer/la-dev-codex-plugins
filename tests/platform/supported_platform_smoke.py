#!/usr/bin/env python3
"""Dependency-free smoke checks for supported operating systems and Python 3.6+."""

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile

REPOSITORY_ROOT = pathlib.Path(__file__).resolve().parents[2]
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
        process_module = importlib.import_module("la_dev_codex_plugins._process")
    finally:
        sys.path.pop(0)
    result = process_module.run_bounded_process(
        [sys.executable, "-c", "import time; time.sleep(5)"],
        str(REPOSITORY_ROOT),
        environment,
        timeout=0.05,
        output_limit=4096,
    )
    assert result.timed_out is True
    assert result.capture_incomplete is False


def smoke_release_checksums(temporary_root):
    """Exercise pure UTF-8/LF checksum output and atomic final placement."""
    sys.path.insert(0, str(REPOSITORY_ROOT / "src"))
    try:
        release_checksums = importlib.import_module("la_dev_codex_plugins.release_checksums")
    finally:
        sys.path.pop(0)
    if "pytest" in sys.modules:
        raise AssertionError("Dependency-free checksum smoke unexpectedly imported pytest")
    unicode_basename = "r\u00e9lease.whl"
    try:
        os.fsencode(unicode_basename)
    except UnicodeEncodeError:
        artifact_basename = "release.whl"
        try:
            release_checksums.generate_sha256_manifest(temporary_root / unicode_basename)
        except release_checksums.ReleaseChecksumError as exc:
            if not isinstance(exc.__cause__, UnicodeEncodeError):
                raise AssertionError("Checksum smoke did not preserve the filesystem encoding failure") from exc
        else:
            raise AssertionError("Checksum smoke accepted a filename that the filesystem encoding cannot represent")
    else:
        artifact_basename = unicode_basename
    artifact = temporary_root / artifact_basename
    artifact_data = b"supported platform release artifact\n"
    artifact.write_bytes(artifact_data)
    output = temporary_root / "SHA256SUMS"
    output.write_bytes(b"stale manifest\n")
    manifest = release_checksums.write_sha256_manifest(artifact, output)
    expected = "{}  {}\n".format(hashlib.sha256(artifact_data).hexdigest(), artifact_basename)
    assert manifest == expected
    assert output.read_bytes() == expected.encode("utf-8")
    assert not list(temporary_root.glob(".la-dev-release-checksums-*.tmp"))

    symlink = temporary_root / "release-symlink.whl"
    hardlink = temporary_root / "release-hardlink.whl"
    symlink.symlink_to(artifact)
    os.link(str(artifact), str(hardlink))

    def assert_duplicate_rejected(duplicate):
        try:
            release_checksums.generate_sha256_manifest((artifact, duplicate))
        except release_checksums.ReleaseChecksumError:
            return
        raise AssertionError("Checksum smoke accepted duplicate artifact identity: {}".format(duplicate))

    for duplicate in (symlink, hardlink):
        assert_duplicate_rejected(duplicate)

    alias_output = temporary_root / "hardlinked-output"
    os.link(str(artifact), str(alias_output))
    try:
        release_checksums.write_sha256_manifest(artifact, alias_output)
    except release_checksums.ReleaseChecksumError:
        pass
    else:
        raise AssertionError("Checksum smoke accepted an output hard-linked to its artifact")
    assert artifact.read_bytes() == alias_output.read_bytes() == artifact_data


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
    assert payload["reviewers"][0]["session_id"] is None
    assert payload["reviewers"][0]["session_log_path"] is None


def main():
    """Run every dependency-free supported-platform smoke check."""
    if sys.version_info < (3, 6):
        raise AssertionError("Python 3.6+ is required")
    sys.dont_write_bytecode = True
    with tempfile.TemporaryDirectory(prefix="la-dev-codex-plugins-smoke-") as temporary_directory:
        temporary_root = pathlib.Path(temporary_directory)
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
        smoke_release_checksums(temporary_root)
        smoke_loupe_runner()
    print("Supported-platform smoke checks passed on {} with Python {}.{}.{}.".format(sys.platform, *sys.version_info[:3]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
