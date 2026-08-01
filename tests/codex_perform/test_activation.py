"""Tests for source-only Perform activation."""

import json
import pathlib
import subprocess

import pytest

REPOSITORY_ROOT = pathlib.Path(__file__).resolve().parents[2]
PLUGIN_ROOT = REPOSITORY_ROOT / "plugins" / "toolkit"


def test_activation_script_defines_source_only_command():
    command = [
        "bash",
        "--noprofile",
        "--norc",
        "-c",
        'source "$1"; type -t codex-perform; codex-perform --plugin-root "$2" show ensure-ascii-only --json',
        "bash",
        str(REPOSITORY_ROOT / "activate.sh"),
        str(PLUGIN_ROOT),
    ]
    completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, check=False)
    lines = completed.stdout.splitlines()
    assert completed.returncode == 0, completed.stderr
    assert lines[0] == "function"
    assert json.loads(lines[1])["selector"] == "ensure-ascii-only[agnostic]"


def test_activation_script_isolates_launcher_from_hostile_import_roots(tmp_path):
    hostile_package = tmp_path / "la_dev_codex_plugins"
    hostile_cli = hostile_package / "cli"
    hostile_cli.mkdir(parents=True)
    (hostile_package / "__init__.py").write_text('raise RuntimeError("hostile package loaded")\n', encoding="ascii")
    (hostile_cli / "__init__.py").write_text("", encoding="ascii")
    (hostile_cli / "perform.py").write_text('raise RuntimeError("hostile launcher loaded")\n', encoding="ascii")
    command = [
        "bash",
        "--noprofile",
        "--norc",
        "-c",
        'cd "$3"; export PYTHONPATH="$3"; source "$1"; codex-perform --plugin-root "$2" show ensure-ascii-only --json',
        "bash",
        str(REPOSITORY_ROOT / "activate.sh"),
        str(PLUGIN_ROOT),
        str(tmp_path),
    ]
    completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, check=False)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["selector"] == "ensure-ascii-only[agnostic]"


@pytest.mark.parametrize("chain", [False, True])
def test_activation_script_resolves_absolute_relative_and_chained_symlinks(tmp_path, chain):
    links = tmp_path / "links with spaces"
    links.mkdir()
    target = links / "target.sh"
    target.symlink_to(REPOSITORY_ROOT / "activate.sh")
    source = target
    if chain:
        source = tmp_path / "activate-link.sh"
        source.symlink_to(pathlib.Path("links with spaces") / "target.sh")
    command = [
        "bash",
        "--noprofile",
        "--norc",
        "-c",
        'source "$1"; printf "%s\\n" "${_LA_DEV_CODEX_PLUGINS_ROOT}"',
        "bash",
        str(source),
    ]
    completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, check=False)
    assert completed.returncode == 0, completed.stderr
    assert pathlib.Path(completed.stdout.strip()) == REPOSITORY_ROOT


def test_activation_script_rejects_direct_execution():
    completed = subprocess.run([str(REPOSITORY_ROOT / "activate.sh")], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, check=False)
    assert completed.returncode == 2
    assert "must be sourced" in completed.stderr


def test_activation_script_honors_python_override(tmp_path):
    marker = tmp_path / "python-marker"
    marker.write_text("#!/usr/bin/env bash\nprintf '%s\\n' \"$*\"\n", encoding="ascii")
    marker.chmod(0o755)
    command = [
        "bash",
        "--noprofile",
        "--norc",
        "-c",
        'source "$1"; CODEX_PERFORM_PYTHON="$2" codex-perform list',
        "bash",
        str(REPOSITORY_ROOT / "activate.sh"),
        str(marker),
    ]
    completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, check=False)
    assert completed.returncode == 0
    assert completed.stdout.strip() == "-I {} list".format(REPOSITORY_ROOT / "source_launcher" / "codex_perform.py")


def test_documented_codex_home_fallback_uses_home_directory():
    documentation = (PLUGIN_ROOT / "skills" / "perform" / "references" / "standalone_cli.md").read_text(encoding="utf-8")
    assert 'find "${CODEX_HOME:-$HOME/.codex}"' in documentation


def test_installed_perform_guides_cross_link_inside_plugin_payload():
    references = PLUGIN_ROOT / "skills" / "perform" / "references"
    filenames = ("action_files.md", "codex_skill.md", "standalone_cli.md")
    assert {path.name for path in references.glob("*.md")} == set(filenames)
    for filename in filenames:
        guide = references / filename
        documentation = guide.read_text(encoding="utf-8")
        for other_filename in filenames:
            if other_filename != filename:
                assert "({})".format(other_filename) in documentation
