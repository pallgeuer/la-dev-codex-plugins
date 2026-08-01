"""Deterministic SHA-256 release manifests with failure-safe output replacement."""

import collections
import hashlib
import os
import pathlib
import stat

from .. import _filesystem as filesystem

_CHUNK_SIZE = 1024 * 1024
_Artifact = collections.namedtuple("_Artifact", "path basename")


class ReleaseChecksumError(Exception):
    """Expected checksum validation, hashing, or output failure."""

    def __init__(self, message, path=None):
        """Store a concise normalized message and optional supplied path."""
        super().__init__(message)
        self.message = message
        self.path = None if path is None else str(path)

    def __str__(self):
        return "{}: {}".format(self.path, self.message) if self.path is not None else self.message


def _coerce_path(value, role):
    try:
        return filesystem.coerce_text_path(value)
    except filesystem.PathCoercionError as exc:
        raise ReleaseChecksumError("{} {}".format(role, exc)) from exc


def _materialize_artifacts(artifacts):
    if isinstance(artifacts, (str, bytes, os.PathLike)):
        supplied = (artifacts,)
    else:
        try:
            supplied = tuple(artifacts)
        except (TypeError, ValueError, OSError) as exc:
            raise ReleaseChecksumError("artifacts must be one path or a finite iterable of paths") from exc
    return tuple(_coerce_path(value, "Artifact") for value in supplied)


def _validate_basename(path):
    normalized = os.path.normpath(path)
    basename = pathlib.PurePath(normalized).name
    if not basename:
        raise ReleaseChecksumError("Artifact basename is empty", path=path)
    if basename == "-":
        raise ReleaseChecksumError("Artifact basename '-' is reserved by checksum verification tools", path=path)
    if any(character in basename for character in ("\r", "\n", "\\", "\x00")):
        raise ReleaseChecksumError("Artifact basename contains a character unsafe for the manifest format", path=path)
    try:
        encoded = basename.encode("utf-8", "strict")
    except UnicodeEncodeError as exc:
        raise ReleaseChecksumError("Artifact basename is not strictly UTF-8 encodable", path=path) from exc
    return basename, encoded


def _normalized_absolute(path):
    return os.path.normcase(os.path.abspath(path))  # noqa: PTH100 - artifact identity requires lexical absolute normalization


def _resolved_path(path):
    return os.path.normcase(os.path.realpath(path))


def _validate_artifacts(coerced):
    if not coerced:
        raise ReleaseChecksumError("At least one artifact is required")
    validated = []
    lexical_identities = set()
    resolved_identities = set()
    file_identities = set()
    basenames = set()
    for path in coerced:
        basename, basename_bytes = _validate_basename(path)
        if basename_bytes in basenames:
            raise ReleaseChecksumError("Duplicate artifact basename {!r}".format(basename), path=path)
        try:
            lexical = _normalized_absolute(path)
            resolved = _resolved_path(path)
        except (OSError, ValueError, UnicodeError) as exc:
            raise ReleaseChecksumError("Artifact path is invalid: {}".format(exc), path=path) from exc
        if lexical in lexical_identities or resolved in resolved_identities:
            raise ReleaseChecksumError("Duplicate artifact path or symlink target", path=path)
        try:
            metadata = pathlib.Path(path).stat()
        except (OSError, ValueError, UnicodeError) as exc:
            raise ReleaseChecksumError("Artifact is unavailable: {}".format(exc), path=path) from exc
        if not stat.S_ISREG(metadata.st_mode):
            raise ReleaseChecksumError("Artifact does not resolve to a regular file", path=path)
        identity = (metadata.st_dev, metadata.st_ino)
        if identity in file_identities:
            raise ReleaseChecksumError("Duplicate artifact file identity", path=path)
        lexical_identities.add(lexical)
        resolved_identities.add(resolved)
        file_identities.add(identity)
        basenames.add(basename_bytes)
        validated.append(_Artifact(path, basename))
    return tuple(validated)


def _hash_artifact(artifact):
    digest = hashlib.sha256()
    try:
        with pathlib.Path(artifact.path).open("rb") as handle:
            while True:
                chunk = handle.read(_CHUNK_SIZE)
                if not chunk:
                    break
                digest.update(chunk)
    except (OSError, ValueError, UnicodeError) as exc:
        raise ReleaseChecksumError("Could not hash artifact: {}".format(exc), path=artifact.path) from exc
    return digest.hexdigest()


def _render_manifest(validated):
    return "".join("{}  {}\n".format(_hash_artifact(artifact), artifact.basename) for artifact in validated)


def generate_sha256_manifest(artifacts):
    """Validate and hash one or more artifacts without writing output."""
    coerced = _materialize_artifacts(artifacts)
    validated = _validate_artifacts(coerced)
    return _render_manifest(validated)


def _inspect_output(output):
    try:
        absolute = os.path.abspath(output)  # noqa: PTH100 - output safety is checked on the lexical final component
        absolute_path = pathlib.Path(absolute)
        parent = absolute_path.parent
        parent_metadata = parent.stat()
    except (OSError, ValueError, UnicodeError) as exc:
        raise ReleaseChecksumError("Output parent is unavailable: {}".format(exc), path=output) from exc
    if not stat.S_ISDIR(parent_metadata.st_mode):
        raise ReleaseChecksumError("Output parent is not a directory", path=output)
    try:
        metadata = absolute_path.lstat()
    except FileNotFoundError:
        return absolute, None
    except (OSError, ValueError, UnicodeError) as exc:
        raise ReleaseChecksumError("Could not inspect output: {}".format(exc), path=output) from exc
    if stat.S_ISLNK(metadata.st_mode):
        raise ReleaseChecksumError("Refusing final-component output symbolic link", path=output)
    if not stat.S_ISREG(metadata.st_mode):
        raise ReleaseChecksumError("Output must be absent or a regular file", path=output)
    return absolute, metadata


def _output_aliases_artifact(output, output_metadata, coerced):
    try:
        output_lexical = _normalized_absolute(output)
        output_resolved = _resolved_path(output)
    except (OSError, ValueError, UnicodeError) as exc:
        raise ReleaseChecksumError("Could not normalize output identity: {}".format(exc), path=output) from exc
    output_identity = None if output_metadata is None else (output_metadata.st_dev, output_metadata.st_ino)
    for artifact in coerced:
        try:
            artifact_lexical = _normalized_absolute(artifact)
            artifact_resolved = _resolved_path(artifact)
        except (OSError, ValueError, UnicodeError) as exc:
            raise ReleaseChecksumError("Could not verify artifact/output identity: {}".format(exc), path=artifact) from exc
        if output_lexical == artifact_lexical or output_resolved == artifact_resolved:
            return artifact
        if output_identity is not None:
            try:
                artifact_metadata = pathlib.Path(artifact).stat()
            except (FileNotFoundError, NotADirectoryError):
                continue
            except (OSError, ValueError, UnicodeError) as exc:
                raise ReleaseChecksumError("Could not verify artifact/output identity: {}".format(exc), path=artifact) from exc
            if output_identity == (artifact_metadata.st_dev, artifact_metadata.st_ino):
                return artifact
    return None


def _write_atomic(output, manifest):
    try:
        data = manifest.encode("utf-8", "strict")
        filesystem.atomic_write_bytes(output, data, ".la-dev-release-checksums-", 0o666, fsync=True)
    except UnicodeError as exc:
        raise ReleaseChecksumError("Could not write checksum output: {}".format(exc), path=output) from exc
    except filesystem.AtomicWriteError as exc:
        if exc.cleanup_errors:
            message = "Output generation failed ({}); temporary cleanup also failed ({})".format(exc.primary_error, "; ".join(str(error) for error in exc.cleanup_errors))
        else:
            message = "Could not write checksum output: {}".format(exc.primary_error)
        raise ReleaseChecksumError(message, path=output) from exc.primary_error


def write_sha256_manifest(artifacts, output):
    """Invalidate a safe stale output and atomically write a new manifest."""
    coerced = _materialize_artifacts(artifacts)
    output_path = _coerce_path(output, "Output")
    absolute_output, output_metadata = _inspect_output(output_path)
    alias = _output_aliases_artifact(absolute_output, output_metadata, coerced)
    if alias is not None:
        raise ReleaseChecksumError("Output aliases artifact {!r}".format(alias), path=output_path)
    if output_metadata is not None:
        try:
            pathlib.Path(absolute_output).unlink()
        except OSError as exc:
            raise ReleaseChecksumError("Could not invalidate stale output: {}".format(exc), path=output_path) from exc

    validated = _validate_artifacts(coerced)
    manifest = _render_manifest(validated)
    _write_atomic(absolute_output, manifest)
    return manifest
