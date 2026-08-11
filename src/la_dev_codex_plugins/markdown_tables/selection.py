"""Git-aware Markdown path selection and configuration."""

import collections
import json
import os
import pathlib
import re
import stat
import sys

from .. import _filesystem as filesystem
from .. import _process as process
from . import files, models

_GIT_TIMEOUT = 10
_GIT_OUTPUT_LIMIT = 32 * 1024 * 1024
_CONFIG_NAME = ".la-dev-markdown-tables.json"
_CONFIG_FIELDS = frozenset(("version", "exclude"))
_MARKDOWN_SUFFIXES = frozenset((".md", ".markdown"))
_NOT_WORKTREE_PREFIX = b"fatal: not a git repository (or any "


class _GitNotWorktreeError(models.MarkdownTableError):
    """Git confirmed that discovery started outside every worktree."""


class _ExplicitPath(collections.namedtuple("_ExplicitPathBase", "path is_directory error")):
    """One normalized input with its directory classification or inspection error."""

    __slots__ = ()


class _SelectionResult(collections.namedtuple("_SelectionResultBase", "paths repository input_errors")):
    """Selected paths, active repository, and recoverable input errors."""

    __slots__ = ()

    def __new__(cls, paths, repository, input_errors=()):
        return super(_SelectionResult, cls).__new__(cls, tuple(paths), repository, tuple(input_errors))


def _coerce_path(path):
    try:
        value = filesystem.coerce_text_path(path)
    except filesystem.PathCoercionError as exc:
        raise models.MarkdownTableError("Invalid filesystem path") from exc
    return pathlib.Path(value)


def _lexical_absolute(path):
    return pathlib.Path(os.path.abspath(str(path)))  # noqa: PTH100 - lexical normalization must not resolve symlinks


def _decode_git_output(data):
    encoding = sys.getfilesystemencoding() or "utf-8"
    return data.decode(encoding, "surrogateescape")


def _git_environment():
    environment = dict(os.environ)
    environment["LC_ALL"] = "C"
    return environment


def _run_git(command, cwd, detect_not_worktree=False):
    result = process.run_bounded_process(command, str(cwd), _git_environment(), _GIT_TIMEOUT, _GIT_OUTPUT_LIMIT)
    if result.launch_error:
        raise models.MarkdownTableError("Git launch failed: {}".format(result.launch_error), path=cwd)
    if result.timed_out:
        raise models.MarkdownTableError("Git command timed out", path=cwd)
    if result.capture_incomplete or result.stdout_truncated or result.stderr_truncated:
        raise models.MarkdownTableError("Git command output exceeded the safe capture limit", path=cwd)
    if result.returncode != 0:
        message = _decode_git_output(result.stderr).strip() or "Git command failed with status {}".format(result.returncode)
        if detect_not_worktree and result.returncode == 128 and result.stderr.startswith(_NOT_WORKTREE_PREFIX):
            raise _GitNotWorktreeError(message, path=cwd)
        raise models.MarkdownTableError(message, path=cwd)
    return result.stdout


def _discover_git_root(start=None):
    selected = _lexical_absolute(pathlib.Path.cwd() if start is None else _coerce_path(start))
    output = _run_git(("git", "rev-parse", "--show-toplevel"), selected, detect_not_worktree=True)
    root_text = _decode_git_output(output)
    if root_text.endswith("\n"):
        root_text = root_text[:-1]
    if not root_text:
        raise models.MarkdownTableError("Git returned an empty worktree root", path=selected)
    return _lexical_absolute(pathlib.Path(root_text))


def _git_markdown_entries(repository, include_untracked=False):
    command = ("git", "ls-files", "-z")
    if include_untracked:
        command = ("git", "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    output = _run_git(command, repository)
    entries = []
    for raw_path in output.split(b"\0"):
        if not raw_path:
            continue
        relative_text = _decode_git_output(raw_path)
        suffix = pathlib.PurePosixPath(relative_text).suffix.lower()
        if suffix not in _MARKDOWN_SUFFIXES:
            continue
        selected = _lexical_absolute(repository / relative_text)
        if not os.path.lexists(str(selected)):
            continue
        entries.append((relative_text, selected))
    entries.sort(key=lambda item: item[0])
    return tuple(entries)


def _coerce_path_inputs(paths):
    if isinstance(paths, (str, bytes, pathlib.PurePath)) or hasattr(paths, "__fspath__"):
        raw_paths = (paths,)
    else:
        try:
            raw_paths = tuple(paths)
        except TypeError as exc:
            raise models.MarkdownTableError("paths must be one path or an iterable of paths") from exc
    selected = []
    seen = set()
    for raw_path in raw_paths:
        path = _lexical_absolute(_coerce_path(raw_path))
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        selected.append(path)
    return tuple(selected)


def _coerce_exclude_patterns(exclude):
    if isinstance(exclude, str):
        patterns = (exclude,)
    else:
        try:
            patterns = tuple(exclude)
        except TypeError as exc:
            raise models.MarkdownTableError("exclude must be one string or an iterable of strings") from exc
    if any(not isinstance(pattern, str) for pattern in patterns):
        raise models.MarkdownTableError("exclude patterns must be strings")
    return patterns


def _compile_exclusion(pattern, source):
    try:
        return re.compile(pattern)
    except re.error as exc:
        raise models.MarkdownTableError("Invalid exclusion regular expression {!r}: {}".format(pattern, exc), path=source) from exc


def _compile_exclusions(patterns, source=None):
    return tuple(_compile_exclusion(pattern, source) for pattern in patterns)


def _inspect_explicit_path(path):
    try:
        metadata = path.lstat()
    except (FileNotFoundError, NotADirectoryError):
        return _ExplicitPath(path, False, None)
    except OSError as exc:
        error = models.MarkdownTableError("Cannot inspect input path: {}".format(exc), path=path)
        return _ExplicitPath(path, False, error)
    return _ExplicitPath(path, stat.S_ISDIR(metadata.st_mode), None)


def _selection_root(root, explicit_paths, repository_required):
    if root is not None:
        return _discover_git_root(root)
    try:
        return _discover_git_root()
    except _GitNotWorktreeError:
        if repository_required or not explicit_paths:
            raise
        return None


def _path_text(path, repository):
    if repository is not None:
        try:
            return path.relative_to(repository).as_posix()
        except ValueError:
            pass
    return path.as_posix()


def _is_excluded(path, repository, exclusions):
    match_text = _path_text(path, repository)
    return any(pattern.search(match_text) is not None for pattern in exclusions)


def _directory_relative_key(path, repository):
    try:
        return path.relative_to(repository).as_posix()
    except ValueError as exc:
        raise models.MarkdownTableError("Directory must be inside the active Git worktree", path=path) from exc


def _index_entries_by_directory(entries):
    indexed = {}
    for relative_text, candidate in entries:
        parent = pathlib.PurePosixPath(relative_text).parent
        while True:
            key = parent.as_posix()
            indexed.setdefault(key, []).append(candidate)
            if key == ".":
                break
            parent = parent.parent
    return {key: tuple(paths) for key, paths in indexed.items()}


def _read_config(path):
    try:
        text, _metadata = files._read_text(path)
    except models.MarkdownTableError as exc:
        raise models.MarkdownTableError("Cannot read configuration: {}".format(exc.message), path=path) from exc
    try:
        data = json.loads(text)
    except (TypeError, ValueError) as exc:
        raise models.MarkdownTableError("Invalid JSON configuration: {}".format(exc), path=path) from exc
    if not isinstance(data, dict):
        raise models.MarkdownTableError("Configuration root must be an object", path=path)
    fields = frozenset(data)
    missing = _CONFIG_FIELDS - fields
    unknown = fields - _CONFIG_FIELDS
    if missing:
        raise models.MarkdownTableError("Configuration is missing required field(s): {}".format(", ".join(sorted(missing))), path=path)
    if unknown:
        raise models.MarkdownTableError("Configuration has unknown field(s): {}".format(", ".join(sorted(unknown))), path=path)
    if type(data["version"]) is not int or data["version"] != 1:
        raise models.MarkdownTableError("Configuration version must be 1", path=path)
    if not isinstance(data["exclude"], list) or any(not isinstance(pattern, str) for pattern in data["exclude"]):
        raise models.MarkdownTableError("Configuration exclude must be an array of strings", path=path)
    return tuple(data["exclude"])


def _config_patterns(repository, config_path, use_config):
    if not use_config:
        return (), None
    selected = None
    if config_path is not None:
        selected = _lexical_absolute(_coerce_path(config_path))
        if not os.path.lexists(str(selected)):
            raise models.MarkdownTableError("Explicit configuration does not exist", path=selected)
    elif repository is not None:
        candidate = repository / _CONFIG_NAME
        if os.path.lexists(str(candidate)):
            selected = candidate
    return (() if selected is None else _read_config(selected)), selected


def _select_markdown_paths(paths=(), root=None, include_untracked=False, exclude=(), config_path=None, use_config=True, apply_excludes=True, collect_input_errors=False):
    if type(include_untracked) is not bool:
        raise models.MarkdownTableError("include_untracked must be a Boolean")
    if type(use_config) is not bool:
        raise models.MarkdownTableError("use_config must be a Boolean")
    if type(apply_excludes) is not bool:
        raise models.MarkdownTableError("apply_excludes must be a Boolean")
    explicit_paths = _coerce_path_inputs(paths)
    patterns = _coerce_exclude_patterns(exclude)
    if config_path is not None and not use_config:
        raise models.MarkdownTableError("config_path cannot be used when use_config is false")
    if not apply_excludes and (patterns or config_path is not None):
        raise models.MarkdownTableError("Exclusion patterns and config_path cannot be used when apply_excludes is false")

    inspected = tuple(_inspect_explicit_path(path) for path in explicit_paths)
    if not collect_input_errors:
        for item in inspected:
            if item.error is not None:
                raise item.error
    repository_required = not explicit_paths or any(item.is_directory for item in inspected if item.error is None)
    repository = _selection_root(root, explicit_paths, repository_required)
    configured, selected_config = _config_patterns(repository, config_path, use_config) if apply_excludes else ((), None)
    exclusions = _compile_exclusions(configured, selected_config) + _compile_exclusions(patterns) if apply_excludes else ()
    entries = _git_markdown_entries(repository, include_untracked=include_untracked) if repository_required else ()
    entries_by_directory = _index_entries_by_directory(entries)

    selected = []
    seen = set()
    input_errors = []

    def append(candidate):
        key = str(candidate)
        if key in seen or _is_excluded(candidate, repository, exclusions):
            return
        seen.add(key)
        selected.append(candidate)

    if not explicit_paths:
        for _relative_text, candidate in entries:
            append(candidate)
    else:
        for item in inspected:
            if item.error is not None:
                input_errors.append(item.error)
                continue
            if not item.is_directory:
                append(item.path)
                continue
            try:
                relative_directory = _directory_relative_key(item.path, repository)
            except models.MarkdownTableError as exc:
                if not collect_input_errors:
                    raise
                input_errors.append(exc)
                continue
            for candidate in entries_by_directory.get(relative_directory, ()):
                append(candidate)
    return _SelectionResult(selected, repository, input_errors)


def select_markdown_paths(paths=(), root=None, include_untracked=False, exclude=(), config_path=None, use_config=True, apply_excludes=True):
    """Select absolute Markdown paths using CLI-equivalent Git and exclusion rules."""
    result = _select_markdown_paths(
        paths=paths,
        root=root,
        include_untracked=include_untracked,
        exclude=exclude,
        config_path=config_path,
        use_config=use_config,
        apply_excludes=apply_excludes,
    )
    return result.paths
