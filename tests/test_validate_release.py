"""Tests for the repository release validator."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = REPOSITORY_ROOT / "scripts" / "validate_release.py"
GIT_LOCAL_ENVIRONMENT_VARIABLES = (
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_CONFIG",
    "GIT_CONFIG_COUNT",
    "GIT_CONFIG_PARAMETERS",
    "GIT_DIR",
    "GIT_GRAFT_FILE",
    "GIT_IMPLICIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_NO_REPLACE_OBJECTS",
    "GIT_OBJECT_DIRECTORY",
    "GIT_PREFIX",
    "GIT_REPLACE_REF_BASE",
    "GIT_SHALLOW_FILE",
    "GIT_WORK_TREE",
)


def isolated_git_environment():
    """Remove caller repository state from nested Git fixture commands."""
    environment = dict(os.environ)
    for variable in GIT_LOCAL_ENVIRONMENT_VARIABLES:
        environment.pop(variable, None)
    return environment


def git(repository, *args):
    return subprocess.run(["git", *args], cwd=str(repository), env=isolated_git_environment(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, check=True).stdout.strip()


def write_repository_versions(repository, version):
    (repository / "src" / "la_dev_codex_plugins").mkdir(parents=True, exist_ok=True)
    (repository / "setup.cfg").write_text("[metadata]\nname = fixture\nversion = {}\n".format(version), encoding="utf-8")
    (repository / "src" / "la_dev_codex_plugins" / "__init__.py").write_text('"""Fixture package."""\n\n__version__ = "{}"\n'.format(version), encoding="utf-8")
    (repository / "README.md").write_text("# Fixture\n\nThis repository is a Codex plugin marketplace, version {}.\n".format(version), encoding="utf-8")


def write_plugin(repository, name, version):
    manifest = repository / "plugins" / name / ".codex-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps({"name": name, "version": version}, indent=2) + "\n", encoding="utf-8")


def set_plugin_version(repository, name, version):
    manifest = repository / "plugins" / name / ".codex-plugin" / "plugin.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["version"] = version
    manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def change_plugin(repository, name, text="changed\n"):
    payload = repository / "plugins" / name / "payload.txt"
    payload.parent.mkdir(parents=True, exist_ok=True)
    payload.write_text(text, encoding="utf-8")


def commit_all(repository, message):
    git(repository, "add", "--all")
    git(repository, "commit", "-m", message)


def create_repository(tmp_path, repository_version="0.1.0", plugins=None):
    repository = tmp_path / "repository"
    repository.mkdir()
    git(repository, "init", "-b", "main")
    git(repository, "config", "user.name", "Release Test")
    git(repository, "config", "user.email", "release-test@example.com")
    write_repository_versions(repository, repository_version)
    for name, version in sorted((plugins or {"demo": "0.1.0"}).items()):
        write_plugin(repository, name, version)
    commit_all(repository, "Base release")
    tag = "v{}".format(repository_version)
    git(repository, "tag", "--no-sign", "-a", tag, "-m", "Release {}".format(tag))
    return repository, tag


def run_validator(repository, *args):
    return subprocess.run(
        [sys.executable, str(VALIDATOR), "--repo-root", str(repository), *args],
        cwd=str(repository),
        env=isolated_git_environment(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        check=False,
    )


def test_baseline_accepts_unchanged_versions(tmp_path):
    repository, tag = create_repository(tmp_path)
    (repository / "repository.txt").write_text("development\n", encoding="utf-8")
    commit_all(repository, "Repository maintenance")

    completed = run_validator(repository, "baseline", tag)

    assert completed.returncode == 0
    assert "release baseline v0.1.0 is valid" in completed.stdout


def test_versions_combine_repository_feature_plugin_fix_and_stable_plugin_breaking_below_one(tmp_path):
    repository, tag = create_repository(tmp_path, plugins={"alpha": "0.2.3", "stable": "1.4.2"})
    change_plugin(repository, "alpha")
    change_plugin(repository, "stable")
    (repository / "repository.txt").write_text("feature\n", encoding="utf-8")
    commit_all(repository, "Mixed development")
    write_repository_versions(repository, "0.2.0")
    set_plugin_version(repository, "alpha", "0.2.4")
    set_plugin_version(repository, "stable", "2.0.0")

    completed = run_validator(repository, "versions", tag, "--repository-change", "feature", "--plugin-change", "alpha=fix", "--plugin-change", "stable=breaking")

    assert completed.returncode == 0
    assert "repository: class=feature, old=0.1.0, expected=0.2.0" in completed.stdout
    assert "plugin stable: class=breaking, old=1.4.2, expected=2.0.0" in completed.stdout


def test_stable_repository_receives_major_bump_from_stable_plugin_breaking_change(tmp_path):
    repository, tag = create_repository(tmp_path, repository_version="1.3.0", plugins={"stable": "1.4.2"})
    change_plugin(repository, "stable")
    commit_all(repository, "Breaking plugin change")
    write_repository_versions(repository, "2.0.0")
    set_plugin_version(repository, "stable", "2.0.0")

    completed = run_validator(repository, "versions", tag, "--repository-change", "none", "--plugin-change", "stable=breaking")

    assert completed.returncode == 0
    assert "repository: class=none, old=1.3.0, expected=2.0.0" in completed.stdout


def test_breaking_initial_development_plugin_and_repository_receive_minor_bumps(tmp_path):
    repository, tag = create_repository(tmp_path, repository_version="0.4.2", plugins={"demo": "0.2.5"})
    change_plugin(repository, "demo")
    (repository / "repository.txt").write_text("breaking\n", encoding="utf-8")
    commit_all(repository, "Breaking initial development changes")
    write_repository_versions(repository, "0.5.0")
    set_plugin_version(repository, "demo", "0.3.0")

    completed = run_validator(repository, "versions", tag, "--repository-change", "breaking", "--plugin-change", "demo=breaking")

    assert completed.returncode == 0


def test_rename_is_removed_plugin_plus_new_identity_at_0_1_0(tmp_path):
    repository, tag = create_repository(tmp_path, repository_version="0.3.0", plugins={"old-name": "0.4.1"})
    shutil.rmtree(repository / "plugins" / "old-name")
    write_plugin(repository, "new-name", "0.1.0")
    commit_all(repository, "Rename plugin")
    write_repository_versions(repository, "0.4.0")

    completed = run_validator(repository, "versions", tag, "--repository-change", "none")

    assert completed.returncode == 0
    assert "plugin new-name: class=new" in completed.stdout
    assert "plugin old-name: class=removed" in completed.stdout


def test_new_plugin_must_start_at_0_1_0(tmp_path):
    repository, tag = create_repository(tmp_path)
    write_plugin(repository, "new-plugin", "0.2.0")
    commit_all(repository, "Add plugin with invalid initial version")

    completed = run_validator(repository, "baseline", tag)

    assert completed.returncode == 1
    assert "new plugin new-plugin must start at 0.1.0" in completed.stderr


def test_baseline_rejects_pre_bumped_existing_plugin(tmp_path):
    repository, tag = create_repository(tmp_path)
    change_plugin(repository, "demo")
    set_plugin_version(repository, "demo", "0.1.1")
    commit_all(repository, "Pre-bump plugin")

    completed = run_validator(repository, "baseline", tag)

    assert completed.returncode == 1
    assert "pre-bumped existing plugin demo" in completed.stderr


def test_baseline_rejects_pre_bumped_repository_declaration(tmp_path):
    repository, tag = create_repository(tmp_path)
    write_repository_versions(repository, "0.1.1")
    commit_all(repository, "Pre-bump repository")

    completed = run_validator(repository, "baseline", tag)

    assert completed.returncode == 1
    assert "committed HEAD repository declarations must equal 0.1.0" in completed.stderr


def test_versions_reject_bump_of_unchanged_plugin(tmp_path):
    repository, tag = create_repository(tmp_path, plugins={"changed": "0.1.0", "unchanged": "0.5.0"})
    change_plugin(repository, "changed")
    commit_all(repository, "Change one plugin")
    write_repository_versions(repository, "0.1.1")
    set_plugin_version(repository, "changed", "0.1.1")
    set_plugin_version(repository, "unchanged", "0.5.1")

    completed = run_validator(repository, "versions", tag, "--repository-change", "none", "--plugin-change", "changed=fix")

    assert completed.returncode == 1
    assert "unchanged: expected 0.5.0, found 0.5.1" in completed.stderr


def test_versions_reject_inexact_changed_plugin_bump(tmp_path):
    repository, tag = create_repository(tmp_path)
    change_plugin(repository, "demo")
    commit_all(repository, "Change plugin")
    write_repository_versions(repository, "0.1.1")
    set_plugin_version(repository, "demo", "0.1.2")

    completed = run_validator(repository, "versions", tag, "--repository-change", "none", "--plugin-change", "demo=fix")

    assert completed.returncode == 1
    assert "demo: expected 0.1.1, found 0.1.2" in completed.stderr


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (("--repository-change", "none"), "missing classifications for demo"),
        (("--repository-change", "none", "--plugin-change", "demo=fix", "--plugin-change", "extra=fix"), "unexpected classifications for extra"),
        (("--repository-change", "none", "--plugin-change", "demo=fix", "--plugin-change", "demo=feature"), "duplicate plugin classification for demo"),
    ],
)
def test_versions_reject_missing_extra_and_duplicate_plugin_classifications(tmp_path, arguments, message):
    repository, tag = create_repository(tmp_path)
    change_plugin(repository, "demo")
    commit_all(repository, "Change plugin")
    write_repository_versions(repository, "0.1.1")
    set_plugin_version(repository, "demo", "0.1.1")

    completed = run_validator(repository, "versions", tag, *arguments)

    assert completed.returncode == 1
    assert message in completed.stderr


@pytest.mark.parametrize("filename", ["payload\nname.txt", "payload\tname.txt"])
def test_versions_detect_plugin_changes_with_control_characters_in_filename(tmp_path, filename):
    repository, tag = create_repository(tmp_path)
    (repository / "plugins" / "demo" / filename).write_text("changed\n", encoding="utf-8")
    commit_all(repository, "Change unusually named plugin file")
    write_repository_versions(repository, "0.1.1")
    completed = run_validator(repository, "versions", tag, "--repository-change", "none")
    assert completed.returncode == 1
    assert "missing classifications for demo" in completed.stderr


@pytest.mark.skipif(os.name != "posix", reason="POSIX undecodable filename regression")
def test_versions_detect_plugin_changes_with_non_utf8_filename(tmp_path):
    repository, tag = create_repository(tmp_path)
    filename = os.fsdecode(b"payload-\xff.txt")
    (repository / "plugins" / "demo" / filename).write_text("changed\n", encoding="utf-8")
    commit_all(repository, "Change non-UTF-8 plugin file")
    write_repository_versions(repository, "0.1.1")
    completed = run_validator(repository, "versions", tag, "--repository-change", "none")
    assert completed.returncode == 1
    assert "missing classifications for demo" in completed.stderr


def test_versions_reject_inexact_repository_bump(tmp_path):
    repository, tag = create_repository(tmp_path)
    (repository / "repository.txt").write_text("feature\n", encoding="utf-8")
    commit_all(repository, "Repository feature")
    write_repository_versions(repository, "0.1.1")

    completed = run_validator(repository, "versions", tag, "--repository-change", "feature")

    assert completed.returncode == 1
    assert "working-tree repository declarations must equal 0.2.0" in completed.stderr


def test_versions_reject_mismatched_worktree_repository_declarations(tmp_path):
    repository, tag = create_repository(tmp_path)
    (repository / "repository.txt").write_text("fix\n", encoding="utf-8")
    commit_all(repository, "Repository fix")
    (repository / "setup.cfg").write_text("[metadata]\nname = fixture\nversion = 0.1.1\n", encoding="utf-8")

    completed = run_validator(repository, "versions", tag, "--repository-change", "fix")

    assert completed.returncode == 1
    assert "README.md='0.1.0'" in completed.stderr
    assert "src/la_dev_codex_plugins/__init__.py='0.1.0'" in completed.stderr


def test_versions_reject_release_without_effective_change(tmp_path):
    repository, tag = create_repository(tmp_path)
    (repository / "repository.txt").write_text("unclassified\n", encoding="utf-8")
    commit_all(repository, "Unclassified repository change")

    completed = run_validator(repository, "versions", tag, "--repository-change", "none")

    assert completed.returncode == 1
    assert "do not require a repository version bump" in completed.stderr


def test_baseline_rejects_lightweight_stable_tag(tmp_path):
    repository, tag = create_repository(tmp_path)
    git(repository, "tag", "-d", tag)
    git(repository, "tag", tag)

    completed = run_validator(repository, "baseline", tag)

    assert completed.returncode == 1
    assert "must be annotated" in completed.stderr


def test_baseline_rejects_non_highest_stable_tag(tmp_path):
    repository, tag = create_repository(tmp_path)
    git(repository, "tag", "--no-sign", "-a", "v0.2.0", "-m", "Unexpected higher tag")

    completed = run_validator(repository, "baseline", tag)

    assert completed.returncode == 1
    assert "must be the highest stable tag v0.2.0" in completed.stderr


def test_baseline_rejects_missing_stable_tag(tmp_path):
    repository, _ = create_repository(tmp_path)

    completed = run_validator(repository, "baseline", "v0.2.0")

    assert completed.returncode == 1
    assert "LAST_TAG 'v0.2.0' does not exist locally" in completed.stderr


def test_baseline_rejects_divergent_stable_tag(tmp_path):
    repository, _ = create_repository(tmp_path)
    tree = git(repository, "rev-parse", "HEAD^{tree}")
    side_commit = git(repository, "commit-tree", tree, "-m", "Divergent release")
    git(repository, "tag", "--no-sign", "-a", "v0.2.0", side_commit, "-m", "Divergent release")

    completed = run_validator(repository, "baseline", "v0.2.0")

    assert completed.returncode == 1
    assert "stable tag v0.2.0 is not reachable from HEAD" in completed.stderr


@pytest.mark.parametrize("tag", ["0.1.0", "v1.0", "latest"])
def test_baseline_rejects_malformed_last_tag(tmp_path, tag):
    repository, _ = create_repository(tmp_path)

    completed = run_validator(repository, "baseline", tag)

    assert completed.returncode == 1
    assert "LAST_TAG must have stable form vX.Y.Z" in completed.stderr


def test_versions_reject_invalid_plugin_classification(tmp_path):
    repository, tag = create_repository(tmp_path)

    completed = run_validator(repository, "versions", tag, "--repository-change", "none", "--plugin-change", "demo=maintenance")

    assert completed.returncode == 2
    assert "plugin changes must have form NAME=fix|feature|breaking" in completed.stderr
