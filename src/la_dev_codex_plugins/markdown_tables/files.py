"""Git discovery and failure-safe file operations for Markdown tables."""

import os
import pathlib
import stat
import sys

from .. import _filesystem as filesystem
from .. import _process as process
from . import formatter, models

_GIT_TIMEOUT = 10
_GIT_OUTPUT_LIMIT = 32 * 1024 * 1024


def _coerce_path(path):
    try:
        value = filesystem.coerce_text_path(path)
    except filesystem.PathCoercionError as exc:
        raise models.MarkdownTableError("Invalid filesystem path") from exc
    return pathlib.Path(value)


def _lexical_absolute(path):
    return pathlib.Path(os.path.abspath(str(path)))  # noqa: PTH100 - lexical normalization must not resolve symlinks


def _symlink_after_open_failure(path):
    try:
        metadata = path.lstat()
    except OSError:
        return False
    return stat.S_ISLNK(metadata.st_mode)


def _read_text(path):
    if not hasattr(os, "O_NOFOLLOW"):
        raise models.MarkdownTableError("Safe no-follow file opening is unavailable", path=path)
    descriptor = None
    try:
        descriptor = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as exc:
        if _symlink_after_open_failure(path):
            raise models.MarkdownTableError("Refusing final-component symbolic link", path=path) from exc
        raise models.MarkdownTableError("Cannot inspect file safely: {}".format(exc), path=path) from exc
    try:
        try:
            metadata = os.fstat(descriptor)
        except OSError as exc:
            raise models.MarkdownTableError("Cannot inspect opened file: {}".format(exc), path=path) from exc
        if not stat.S_ISREG(metadata.st_mode):
            raise models.MarkdownTableError("Expected a regular file", path=path)
        try:
            with os.fdopen(descriptor, "rb") as handle:
                descriptor = None
                data = handle.read()
        except OSError as exc:
            raise models.MarkdownTableError("Cannot read file: {}".format(exc), path=path) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
    try:
        return data.decode("utf-8"), metadata
    except UnicodeDecodeError as exc:
        raise models.MarkdownTableError("File is not valid UTF-8: {}".format(exc), path=path) from exc


def _atomic_write(path, text, metadata):
    identity = (metadata.st_dev, metadata.st_ino)

    def verify_unchanged():
        try:
            current = path.lstat()
        except OSError as exc:
            raise OSError("Selected file changed after it was read: {}".format(exc)) from exc
        if not stat.S_ISREG(current.st_mode) or (current.st_dev, current.st_ino) != identity:
            raise OSError("Selected file changed after it was read")

    try:
        data = text.encode("utf-8")
        filesystem.atomic_write_bytes(path, data, ".la-dev-markdown-tables-", 0o600, final_mode=stat.S_IMODE(metadata.st_mode), before_replace=verify_unchanged)
    except UnicodeError as exc:
        raise models.MarkdownTableError("Cannot replace file atomically: {}".format(exc), path=path) from exc
    except filesystem.AtomicWriteError as exc:
        message = "Cannot replace file atomically: {}".format(exc.primary_error)
        if exc.cleanup_errors:
            message += "; temporary cleanup also failed: {}".format("; ".join(str(error) for error in exc.cleanup_errors))
        raise models.MarkdownTableError(message, path=path) from exc.primary_error


def _format_file(path):
    """Read and format one selected file without writing it."""
    selected = _lexical_absolute(_coerce_path(path))
    text, metadata = _read_text(selected)
    result = formatter.format_markdown_tables(text, path=str(selected))
    return selected, metadata, result


def format_markdown_tables_file(path, check=False):
    """Format every independently safe table in one regular UTF-8 file."""
    selected, metadata, result = _format_file(path)
    if result.changed and not check:
        _atomic_write(selected, result.text, metadata)
    return result


def normalize_markdown_tables_file(path, check=False):
    """Strictly normalize one file and return whether it changes."""
    selected, metadata, result = _format_file(path)
    if result.issues:
        first = result.issues[0]
        raise models.MarkdownTableError("Malformed Markdown table", path=selected, line_number=first.line_number, issues=result.issues, result=result)
    if result.changed and not check:
        _atomic_write(selected, result.text, metadata)
    return result.changed


def _decode_git_output(data):
    encoding = sys.getfilesystemencoding() or "utf-8"
    return data.decode(encoding, "surrogateescape")


def _run_git(command, cwd):
    result = process.run_bounded_process(command, str(cwd), os.environ, _GIT_TIMEOUT, _GIT_OUTPUT_LIMIT)
    if result.launch_error:
        raise models.MarkdownTableError("Git launch failed: {}".format(result.launch_error), path=cwd)
    if result.timed_out:
        raise models.MarkdownTableError("Git command timed out", path=cwd)
    if result.capture_incomplete or result.stdout_truncated or result.stderr_truncated:
        raise models.MarkdownTableError("Git command output exceeded the safe capture limit", path=cwd)
    if result.returncode != 0:
        message = _decode_git_output(result.stderr).strip() or "Git command failed with status {}".format(result.returncode)
        raise models.MarkdownTableError(message, path=cwd)
    return result.stdout


def _discover_git_root(start=None):
    selected = _lexical_absolute(pathlib.Path.cwd() if start is None else _coerce_path(start))
    output = _run_git(("git", "rev-parse", "--show-toplevel"), selected)
    root_text = _decode_git_output(output)
    if root_text.endswith("\n"):
        root_text = root_text[:-1]
    if not root_text:
        raise models.MarkdownTableError("Git returned an empty worktree root", path=selected)
    return _lexical_absolute(pathlib.Path(root_text))


def _tracked_markdown_paths(repository):
    output = _run_git(("git", "ls-files", "-z"), repository)
    paths = []
    for raw_path in output.split(b"\0"):
        if not raw_path:
            continue
        relative_text = _decode_git_output(raw_path)
        suffix = pathlib.PurePath(relative_text).suffix.lower()
        if suffix not in {".md", ".markdown"}:
            continue
        selected = _lexical_absolute(repository / relative_text)
        if not os.path.lexists(str(selected)):
            continue
        paths.append((relative_text, selected))
    paths.sort(key=lambda item: item[0])
    return tuple(item[1] for item in paths)


def tracked_markdown_paths(root=None):
    """Return present tracked Markdown paths sorted by repository-relative path."""
    return _tracked_markdown_paths(_discover_git_root(root))
