#!/usr/bin/env python3
"""Repository release-version validator."""

import argparse
import configparser
import json
import os
import pathlib
import re
import subprocess
import sys

STABLE_VERSION_RE = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
STABLE_TAG_RE = re.compile(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
MANIFEST_RE = re.compile(r"plugins/([^/]+)/\.codex-plugin/plugin\.json")
CHANGE_CLASSES = ("none", "fix", "enhancement", "feature", "breaking")
PLUGIN_CHANGE_CLASSES = ("fix", "enhancement", "feature", "breaking")
PATCH = 1
MINOR = 2
MAJOR = 3


class ReleaseValidationError(Exception):
    """Invalid release state."""


class Baseline:
    """Validated committed state relative to the previous release tag."""

    def __init__(self, repository_root, tag, repository_version, tag_plugins, head_plugins):
        self.repository_root = repository_root
        self.tag = tag
        self.repository_version = repository_version
        self.tag_plugins = tag_plugins
        self.head_plugins = head_plugins


def _run_git(repository_root, *args, check=True, binary=False):
    completed = subprocess.run(["git", *args], cwd=str(repository_root), stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=not binary, check=False)
    if check and completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown Git failure"
        if isinstance(detail, bytes):
            detail = detail.decode("utf-8", errors="backslashreplace")
        raise ReleaseValidationError("git {} failed: {}".format(" ".join(args), detail))
    return completed


def _parse_stable_version(text, label):
    if STABLE_VERSION_RE.fullmatch(text) is None:
        raise ReleaseValidationError("{} must be a stable X.Y.Z SemVer value, got {!r}".format(label, text))
    return tuple(int(part) for part in text.split("."))


def _format_version(version):
    return ".".join(str(part) for part in version)


def _parse_setup_version(text, label):
    parser = configparser.ConfigParser()
    try:
        parser.read_string(text)
        version = parser["metadata"]["version"]
    except (configparser.Error, KeyError) as error:
        raise ReleaseValidationError("{} does not contain metadata.version: {}".format(label, error)) from error
    _parse_stable_version(version, "{} repository version".format(label))
    return version


def _parse_init_version(text, label):
    match = re.search(r'^__version__ = "([^"]+)"$', text, flags=re.MULTILINE)
    if match is None:
        raise ReleaseValidationError("{} does not contain the expected __version__ declaration".format(label))
    version = match.group(1)
    _parse_stable_version(version, "{} repository version".format(label))
    return version


def _parse_readme_version(text, label):
    lines = text.splitlines()
    if len(lines) < 3:
        raise ReleaseValidationError("{} does not contain the expected opening sentence".format(label))
    match = re.fullmatch(r"This repository is a Codex plugin marketplace, version ([^.]+\.[^.]+\.[^.]+)\.", lines[2])
    if match is None:
        raise ReleaseValidationError("{} does not contain the expected opening version sentence".format(label))
    version = match.group(1)
    _parse_stable_version(version, "{} repository version".format(label))
    return version


def _git_file(repository_root, ref, path):
    return _run_git(repository_root, "show", "{}:{}".format(ref, path)).stdout


def _repository_versions_from_ref(repository_root, ref):
    return {
        "setup.cfg": _parse_setup_version(_git_file(repository_root, ref, "setup.cfg"), "{}:setup.cfg".format(ref)),
        "src/la_dev_codex_plugins/__init__.py": _parse_init_version(_git_file(repository_root, ref, "src/la_dev_codex_plugins/__init__.py"), "{}:src/la_dev_codex_plugins/__init__.py".format(ref)),
        "README.md": _parse_readme_version(_git_file(repository_root, ref, "README.md"), "{}:README.md".format(ref)),
    }


def _repository_versions_from_worktree(repository_root):
    return {
        "setup.cfg": _parse_setup_version((repository_root / "setup.cfg").read_text(encoding="utf-8"), "setup.cfg"),
        "src/la_dev_codex_plugins/__init__.py": _parse_init_version((repository_root / "src/la_dev_codex_plugins/__init__.py").read_text(encoding="utf-8"), "src/la_dev_codex_plugins/__init__.py"),
        "README.md": _parse_readme_version((repository_root / "README.md").read_text(encoding="utf-8"), "README.md"),
    }


def _require_versions(values, expected, context):
    mismatches = ["{}={!r}".format(path, version) for path, version in sorted(values.items()) if version != expected]
    if mismatches:
        raise ReleaseValidationError("{} must equal {}, but found {}".format(context, expected, ", ".join(mismatches)))


def _parse_manifest(text, label, expected_name):
    try:
        manifest = json.loads(text)
    except (TypeError, ValueError) as error:
        raise ReleaseValidationError("{} is not valid JSON: {}".format(label, error)) from error
    if not isinstance(manifest, dict):
        raise ReleaseValidationError("{} must contain a JSON object".format(label))
    if manifest.get("name") != expected_name:
        raise ReleaseValidationError("{} must declare name {!r}".format(label, expected_name))
    version = manifest.get("version")
    if not isinstance(version, str):
        raise ReleaseValidationError("{} must declare a string version".format(label))
    _parse_stable_version(version, "{} plugin version".format(label))
    return version


def _manifest_paths_from_ref(repository_root, ref):
    output = _run_git(repository_root, "ls-tree", "-r", "--name-only", ref, "--", "plugins").stdout
    paths = {}
    for path in output.splitlines():
        match = MANIFEST_RE.fullmatch(path)
        if match is not None:
            paths[match.group(1)] = path
    return paths


def _plugins_from_ref(repository_root, ref):
    plugins = {}
    for name, path in sorted(_manifest_paths_from_ref(repository_root, ref).items()):
        plugins[name] = _parse_manifest(_git_file(repository_root, ref, path), "{}:{}".format(ref, path), name)
    return plugins


def _plugins_from_worktree(repository_root):
    plugins = {}
    for path in sorted((repository_root / "plugins").glob("*/.codex-plugin/plugin.json")):
        name = path.parent.parent.name
        plugins[name] = _parse_manifest(path.read_text(encoding="utf-8"), str(path.relative_to(repository_root)), name)
    return plugins


def _stable_tags(repository_root):
    tags = []
    for tag in _run_git(repository_root, "tag", "--list").stdout.splitlines():
        match = STABLE_TAG_RE.fullmatch(tag)
        if match is not None:
            tags.append((tuple(int(part) for part in match.groups()), tag))
    return sorted(tags)


def _changed_plugin_names(repository_root, tag):
    output = _run_git(repository_root, "diff", "--name-only", "-z", "{}..HEAD".format(tag), "--", "plugins", binary=True).stdout
    names = set()
    for path in output.split(b"\0"):
        parts = path.split(b"/", 2)
        if len(parts) >= 2 and parts[0] == b"plugins" and parts[1]:
            names.add(os.fsdecode(parts[1]))
    return names


def validate_baseline(repository_root, tag):
    repository_root = pathlib.Path(repository_root).resolve()
    match = STABLE_TAG_RE.fullmatch(tag)
    if match is None:
        raise ReleaseValidationError("LAST_TAG must have stable form vX.Y.Z, got {!r}".format(tag))
    stable_tags = _stable_tags(repository_root)
    if not stable_tags:
        raise ReleaseValidationError("the repository has no stable vX.Y.Z tags")
    known_tags = {known_tag for _, known_tag in stable_tags}
    if tag not in known_tags:
        raise ReleaseValidationError("LAST_TAG {!r} does not exist locally".format(tag))
    highest_tag = stable_tags[-1][1]
    if tag != highest_tag:
        raise ReleaseValidationError("LAST_TAG must be the highest stable tag {}, not {}".format(highest_tag, tag))
    for _, known_tag in stable_tags:
        object_type = _run_git(repository_root, "cat-file", "-t", known_tag).stdout.strip()
        if object_type != "tag":
            raise ReleaseValidationError("stable tag {} must be annotated, found object type {}".format(known_tag, object_type))
        ancestry = _run_git(repository_root, "merge-base", "--is-ancestor", known_tag, "HEAD", check=False)
        if ancestry.returncode != 0:
            if ancestry.returncode == 1:
                raise ReleaseValidationError("stable tag {} is not reachable from HEAD".format(known_tag))
            detail = ancestry.stderr.strip() or "unknown Git failure"
            raise ReleaseValidationError("could not check ancestry of stable tag {}: {}".format(known_tag, detail))
    tag_version = ".".join(match.groups())
    tag_repository_versions = _repository_versions_from_ref(repository_root, tag)
    _require_versions(tag_repository_versions, tag_version, "{} repository declarations".format(tag))
    head_repository_versions = _repository_versions_from_ref(repository_root, "HEAD")
    _require_versions(head_repository_versions, tag_version, "committed HEAD repository declarations")
    tag_plugins = _plugins_from_ref(repository_root, tag)
    head_plugins = _plugins_from_ref(repository_root, "HEAD")
    for name in sorted(set(tag_plugins) & set(head_plugins)):
        if head_plugins[name] != tag_plugins[name]:
            raise ReleaseValidationError("committed HEAD pre-bumped existing plugin {} from {} to {}".format(name, tag_plugins[name], head_plugins[name]))
    for name in sorted(set(head_plugins) - set(tag_plugins)):
        if head_plugins[name] != "0.1.0":
            raise ReleaseValidationError("new plugin {} must start at 0.1.0, found {}".format(name, head_plugins[name]))
    return Baseline(repository_root, tag, _parse_stable_version(tag_version, "repository version"), tag_plugins, head_plugins)


def _bump_level(version, change_class):
    if change_class == "none":
        return 0
    if change_class in ("fix", "enhancement"):
        return PATCH
    if change_class == "feature":
        return MINOR
    if change_class == "breaking":
        return MINOR if version[0] == 0 else MAJOR
    raise ReleaseValidationError("unknown change classification {!r}".format(change_class))


def _bump_version(version, level):
    if level == PATCH:
        return version[0], version[1], version[2] + 1
    if level == MINOR:
        return version[0], version[1] + 1, 0
    if level == MAJOR:
        return version[0] + 1, 0, 0
    raise ReleaseValidationError("cannot calculate a version for bump level {}".format(level))


def validate_versions(repository_root, tag, repository_change, plugin_changes):
    baseline = validate_baseline(repository_root, tag)
    changed_names = _changed_plugin_names(baseline.repository_root, tag)
    tag_names = set(baseline.tag_plugins)
    head_names = set(baseline.head_plugins)
    existing_names = tag_names & head_names
    changed_existing = changed_names & existing_names
    new_names = head_names - tag_names
    removed_names = tag_names - head_names
    supplied_names = set(plugin_changes)
    missing = sorted(changed_existing - supplied_names)
    extra = sorted(supplied_names - changed_existing)
    if missing or extra:
        details = []
        if missing:
            details.append("missing classifications for {}".format(", ".join(missing)))
        if extra:
            details.append("unexpected classifications for {}".format(", ".join(extra)))
        raise ReleaseValidationError("; ".join(details))
    worktree_plugins = _plugins_from_worktree(baseline.repository_root)
    if set(worktree_plugins) != head_names:
        added = sorted(set(worktree_plugins) - head_names)
        missing_from_worktree = sorted(head_names - set(worktree_plugins))
        raise ReleaseValidationError("release version editing must not add or remove plugin manifests; added={}, missing={}".format(added, missing_from_worktree))
    expected_plugins = {}
    repository_levels = [_bump_level(baseline.repository_version, repository_change)]
    summary = []
    for name in sorted(existing_names):
        old_text = baseline.tag_plugins[name]
        old_version = _parse_stable_version(old_text, "{} base version".format(name))
        if name in changed_existing:
            change_class = plugin_changes[name]
            plugin_level = _bump_level(old_version, change_class)
            expected_text = _format_version(_bump_version(old_version, plugin_level))
            repository_levels.append(MINOR if plugin_level == MAJOR and baseline.repository_version[0] == 0 else plugin_level)
            summary.append("plugin {}: class={}, old={}, expected={}, actual={}".format(name, change_class, old_text, expected_text, worktree_plugins[name]))
        else:
            expected_text = old_text
            summary.append("plugin {}: class=unchanged, old={}, expected={}, actual={}".format(name, old_text, expected_text, worktree_plugins[name]))
        expected_plugins[name] = expected_text
    for name in sorted(new_names):
        expected_plugins[name] = "0.1.0"
        repository_levels.append(MINOR)
        summary.append("plugin {}: class=new, old=absent, expected=0.1.0, actual={}".format(name, worktree_plugins[name]))
    for name in sorted(removed_names):
        repository_levels.append(_bump_level(baseline.repository_version, "breaking"))
        summary.append("plugin {}: class=removed, old={}, expected=absent, actual=absent".format(name, baseline.tag_plugins[name]))
    repository_level = max(repository_levels)
    if repository_level == 0:
        raise ReleaseValidationError("the declared changes do not require a repository version bump")
    expected_repository = _format_version(_bump_version(baseline.repository_version, repository_level))
    actual_repository_versions = _repository_versions_from_worktree(baseline.repository_root)
    _require_versions(actual_repository_versions, expected_repository, "working-tree repository declarations")
    actual_repository = actual_repository_versions["setup.cfg"]
    mismatches = ["{}: expected {}, found {}".format(name, expected, worktree_plugins[name]) for name, expected in sorted(expected_plugins.items()) if worktree_plugins[name] != expected]
    if mismatches:
        raise ReleaseValidationError("working-tree plugin version mismatches: {}".format("; ".join(mismatches)))
    print("repository: class={}, old={}, expected={}, actual={}".format(repository_change, _format_version(baseline.repository_version), expected_repository, actual_repository))
    for line in summary:
        print(line)
    return expected_repository


def _plugin_change(value):
    name, separator, change_class = value.partition("=")
    if not separator or not name or change_class not in PLUGIN_CHANGE_CLASSES:
        raise argparse.ArgumentTypeError("plugin changes must have form NAME=fix|enhancement|feature|breaking")
    return name, change_class


def _argument_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(pathlib.Path(__file__).resolve().parents[1]), help=argparse.SUPPRESS)
    subparsers = parser.add_subparsers(dest="command")
    baseline_parser = subparsers.add_parser("baseline", help="Validate the committed development baseline")
    baseline_parser.add_argument("last_tag")
    versions_parser = subparsers.add_parser("versions", help="Validate edited release versions")
    versions_parser.add_argument("last_tag")
    versions_parser.add_argument("--repository-change", required=True, choices=CHANGE_CLASSES)
    versions_parser.add_argument("--plugin-change", action="append", default=[], type=_plugin_change, metavar="NAME=CLASS")
    return parser


def main(argv=None):
    parser = _argument_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.error("a subcommand is required")
    repository_root = pathlib.Path(args.repo_root)
    try:
        if args.command == "baseline":
            baseline = validate_baseline(repository_root, args.last_tag)
            print("release baseline {} is valid at repository version {}".format(args.last_tag, _format_version(baseline.repository_version)))
            return 0
        plugin_changes = {}
        for name, change_class in args.plugin_change:
            if name in plugin_changes:
                raise ReleaseValidationError("duplicate plugin classification for {}".format(name))
            plugin_changes[name] = change_class
        validate_versions(repository_root, args.last_tag, args.repository_change, plugin_changes)
    except (OSError, ReleaseValidationError) as error:
        print("error: {}".format(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
