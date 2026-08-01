"""Failure-safe Markdown file operations."""

import os
import pathlib
import stat

from .. import _filesystem as filesystem
from . import formatter, models


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
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_NONBLOCK"):
        raise models.MarkdownTableError("Safe nonblocking no-follow file opening is unavailable", path=path)
    descriptor = None
    try:
        descriptor = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
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
