"""Shared text-path and atomic-file primitives."""

import os
import pathlib
import unicodedata
import uuid


class PathCoercionError(Exception):
    """A supplied path cannot be represented as text."""


class AtomicWriteError(Exception):
    """An expected atomic-write failure and any cleanup failures."""

    def __init__(self, primary_error, cleanup_errors=()):
        """Store the primary failure and later cleanup failures."""
        super().__init__(str(primary_error))
        self.primary_error = primary_error
        self.cleanup_errors = tuple(cleanup_errors)


_DISPLAY_ESCAPES = {"\a": "\\a", "\b": "\\b", "\t": "\\t", "\n": "\\n", "\v": "\\v", "\f": "\\f", "\r": "\\r"}


def escape_display_text(value):
    """Render text readably without terminal controls or physical line breaks."""
    escaped = []
    for character in str(value):
        if character == "\\":
            escaped.append("\\\\")
        elif character in _DISPLAY_ESCAPES:
            escaped.append(_DISPLAY_ESCAPES[character])
        elif unicodedata.category(character) in {"Cc", "Cf", "Cs", "Zl", "Zp"}:
            codepoint = ord(character)
            if codepoint <= 0xFF:
                escaped.append("\\x{:02x}".format(codepoint))
            elif codepoint <= 0xFFFF:
                escaped.append("\\u{:04x}".format(codepoint))
            else:
                escaped.append("\\U{:08x}".format(codepoint))
        else:
            escaped.append(character)
    return "".join(escaped)


def coerce_text_path(value):
    """Return one text filesystem path or raise a normalized error."""
    try:
        result = os.fspath(value)
    except (TypeError, ValueError, OSError) as exc:
        raise PathCoercionError("path must be a text string or text-returning path-like object") from exc
    if isinstance(result, bytes):
        raise PathCoercionError("path must not be bytes")
    if not isinstance(result, str):
        raise PathCoercionError("path-like object returned a non-text path")
    return result


def _exclusive_temporary(parent, prefix, mode, attempts):
    for _unused in range(attempts):
        path = pathlib.Path(parent) / "{}{}.tmp".format(prefix, uuid.uuid4().hex)
        try:
            descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
        except FileExistsError:
            continue
        return descriptor, path
    raise OSError("Could not allocate a unique temporary output")


def _cleanup_temporary(descriptor, temporary):
    errors = []
    if descriptor is not None:
        try:
            os.close(descriptor)
        except OSError as exc:
            errors.append(exc)
    if temporary is not None:
        try:
            pathlib.Path(temporary).unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            errors.append(exc)
    return tuple(errors)


def atomic_write_bytes(output, data, prefix, create_mode, final_mode=None, fsync=False, before_replace=None, attempts=100, expected_errors=(OSError, UnicodeError)):
    """Atomically replace a path after optional validation and clean temporary state on every failure."""
    descriptor = None
    temporary = None
    try:
        descriptor, temporary = _exclusive_temporary(pathlib.Path(output).parent, prefix, create_mode, attempts)
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = None
            handle.write(data)
            handle.flush()
            if fsync:
                os.fsync(handle.fileno())
            if final_mode is not None:
                os.fchmod(handle.fileno(), final_mode)
        if before_replace is not None:
            before_replace()
        os.replace(str(temporary), str(output))  # noqa: PTH105 - callers require atomic replacement
        temporary = None
    except BaseException as exc:
        cleanup_errors = _cleanup_temporary(descriptor, temporary)
        if isinstance(exc, expected_errors):
            raise AtomicWriteError(exc, cleanup_errors) from exc
        raise
