"""Release checksum validation, hashing, and output safety tests."""

import hashlib
import os
import pathlib
import socket
import stat

import pytest

import la_dev_codex_plugins._filesystem as filesystem
import la_dev_codex_plugins.release_checksums as release_checksums
import la_dev_codex_plugins.release_checksums.core as checksum_core


class TextPath:
    """Counted text-returning path-like test object."""

    def __init__(self, value):
        self.value = value
        self.calls = 0

    def __fspath__(self):
        self.calls += 1
        return self.value


class BytesPath:
    """Bytes-returning path-like test object."""

    def __fspath__(self):
        return b"artifact"


def _expected(path, content):
    return "{}  {}\n".format(hashlib.sha256(content).hexdigest(), path.name)


def test_scalar_string_pathlike_sequence_and_one_shot_generator_preserve_order(tmp_path):
    first = tmp_path / "first.bin"
    second = tmp_path / "second file.bin"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    counted = TextPath(str(first))

    assert release_checksums.generate_sha256_manifest(counted) == _expected(first, b"first")
    assert counted.calls == 1

    iterations = []

    def artifacts():
        iterations.append(True)
        yield first
        yield second

    manifest = release_checksums.generate_sha256_manifest(artifacts())
    assert manifest == _expected(first, b"first") + _expected(second, b"second")
    assert iterations == [True]


@pytest.mark.parametrize("artifacts", [b"artifact", [b"artifact"], BytesPath(), [BytesPath()]])
def test_bytes_paths_are_rejected(artifacts):
    with pytest.raises(release_checksums.ReleaseChecksumError, match="must not be bytes"):
        release_checksums.generate_sha256_manifest(artifacts)


def test_empty_input_and_non_iterable_are_rejected():
    with pytest.raises(release_checksums.ReleaseChecksumError, match="At least one"):
        release_checksums.generate_sha256_manifest([])
    with pytest.raises(release_checksums.ReleaseChecksumError, match="finite iterable"):
        release_checksums.generate_sha256_manifest(42)


def test_binary_and_multi_chunk_hashing_use_known_digest(tmp_path):
    artifact = tmp_path / "large.bin"
    content = bytes(range(256)) * 9000
    artifact.write_bytes(content)
    assert len(content) > checksum_core._CHUNK_SIZE
    assert release_checksums.generate_sha256_manifest(artifact) == _expected(artifact, content)


def test_artifact_symlink_uses_supplied_basename_and_regular_target(tmp_path):
    target = tmp_path / "target.bin"
    target.write_bytes(b"target")
    link = tmp_path / "release-link.bin"
    link.symlink_to(target)
    assert release_checksums.generate_sha256_manifest(link) == _expected(link, b"target")


def test_missing_directory_fifo_broken_and_cyclic_symlink_artifacts_are_rejected(tmp_path):
    fifo = tmp_path / "fifo.bin"
    os.mkfifo(str(fifo))
    broken = tmp_path / "broken.bin"
    broken.symlink_to(tmp_path / "missing-target")
    cycle_a = tmp_path / "a.bin"
    cycle_b = tmp_path / "b.bin"
    cycle_a.symlink_to(cycle_b)
    cycle_b.symlink_to(cycle_a)
    for artifact in (tmp_path / "missing.bin", tmp_path, fifo, broken, cycle_a):
        with pytest.raises(release_checksums.ReleaseChecksumError):
            release_checksums.generate_sha256_manifest(artifact)


def test_duplicate_lexical_relative_symlink_and_hardlink_identities_are_rejected(tmp_path, monkeypatch):
    artifact = tmp_path / "artifact.bin"
    artifact.write_bytes(b"data")
    symlink = tmp_path / "symlink.bin"
    hardlink = tmp_path / "hardlink.bin"
    symlink.symlink_to(artifact)
    os.link(str(artifact), str(hardlink))
    monkeypatch.chdir(tmp_path)
    duplicates = [
        [artifact, artifact],
        [artifact, "artifact.bin"],
        [artifact, symlink],
        [artifact, hardlink],
    ]
    for paths in duplicates:
        with pytest.raises(release_checksums.ReleaseChecksumError, match="Duplicate artifact"):
            release_checksums.generate_sha256_manifest(paths)


def test_duplicate_basenames_are_exact_utf8_without_case_folding(tmp_path):
    first_dir = tmp_path / "one"
    second_dir = tmp_path / "two"
    first_dir.mkdir()
    second_dir.mkdir()
    first = first_dir / "artifact.bin"
    duplicate = second_dir / "artifact.bin"
    case_distinct = second_dir / "ARTIFACT.bin"
    for path in (first, duplicate, case_distinct):
        path.write_bytes(path.name.encode("ascii"))
    with pytest.raises(release_checksums.ReleaseChecksumError, match="Duplicate artifact basename"):
        release_checksums.generate_sha256_manifest((first, duplicate))
    assert release_checksums.generate_sha256_manifest((first, case_distinct)).count("\n") == 2


@pytest.mark.parametrize("basename", ["carriage\rreturn", "line\nfeed", "back\\slash", "nul\x00name", "surrogate\ud800"])
def test_unsafe_or_non_utf8_basenames_are_rejected_before_file_access(tmp_path, basename):
    with pytest.raises(release_checksums.ReleaseChecksumError, match="basename"):
        release_checksums.generate_sha256_manifest(str(tmp_path / basename))


def test_dash_basename_is_rejected_as_reserved_before_file_access(tmp_path):
    with pytest.raises(release_checksums.ReleaseChecksumError, match="reserved"):
        release_checksums.generate_sha256_manifest(tmp_path / "-")


def test_utf8_and_space_basenames_produce_strict_lf_manifest(tmp_path):
    artifact = tmp_path / "caf\u00e9 release.bin"
    artifact.write_bytes(b"data")
    manifest = release_checksums.generate_sha256_manifest(artifact)
    assert manifest.encode("utf-8") == _expected(artifact, b"data").encode("utf-8")
    assert manifest.endswith("\n")
    assert "\r" not in manifest


def test_safe_stale_output_is_invalidated_before_empty_missing_duplicate_and_hash_failures(tmp_path, monkeypatch):
    output = tmp_path / "SHA256SUMS"
    artifact = tmp_path / "artifact.bin"
    artifact.write_bytes(b"data")

    cases = [[], [tmp_path / "missing.bin"], [artifact, artifact]]
    for artifacts in cases:
        output.write_text("stale\n", encoding="ascii")
        with pytest.raises(release_checksums.ReleaseChecksumError):
            release_checksums.write_sha256_manifest(artifacts, output)
        assert not output.exists()

    output.write_text("stale\n", encoding="ascii")

    def fail_hash(_artifact):
        raise release_checksums.ReleaseChecksumError("hash failed")

    monkeypatch.setattr(checksum_core, "_hash_artifact", fail_hash)
    with pytest.raises(release_checksums.ReleaseChecksumError, match="hash failed"):
        release_checksums.write_sha256_manifest(artifact, output)
    assert not output.exists()


def test_safe_stale_output_is_invalidated_before_basename_validation(tmp_path):
    output = tmp_path / "SHA256SUMS"
    output.write_text("stale\n", encoding="ascii")

    with pytest.raises(release_checksums.ReleaseChecksumError, match="basename"):
        release_checksums.write_sha256_manifest(str(tmp_path / "unsafe\nname"), output)

    assert not output.exists()


def test_safe_stale_output_is_invalidated_before_reserved_basename_validation(tmp_path):
    output = tmp_path / "SHA256SUMS"
    output.write_text("stale\n", encoding="ascii")

    with pytest.raises(release_checksums.ReleaseChecksumError, match="reserved"):
        release_checksums.write_sha256_manifest(tmp_path / "-", output)

    assert not output.exists()


def test_path_coercion_and_unsafe_output_failures_preserve_existing_targets(tmp_path):
    output = tmp_path / "SHA256SUMS"
    output.write_text("stale\n", encoding="ascii")
    with pytest.raises(release_checksums.ReleaseChecksumError):
        release_checksums.write_sha256_manifest([BytesPath()], output)
    assert output.read_text(encoding="ascii") == "stale\n"

    with pytest.raises(release_checksums.ReleaseChecksumError):
        release_checksums.write_sha256_manifest([], BytesPath())
    assert output.read_text(encoding="ascii") == "stale\n"

    target = tmp_path / "target"
    target.write_text("target\n", encoding="ascii")
    link = tmp_path / "link"
    link.symlink_to(target)
    with pytest.raises(release_checksums.ReleaseChecksumError, match="symbolic link"):
        release_checksums.write_sha256_manifest([], link)
    assert target.read_text(encoding="ascii") == "target\n"

    directory = tmp_path / "directory"
    directory.mkdir()
    with pytest.raises(release_checksums.ReleaseChecksumError, match="absent or a regular file"):
        release_checksums.write_sha256_manifest([], directory)


@pytest.mark.parametrize("invalid", ["nul\x00path", "unencodable\ud800"])
def test_invalid_filesystem_paths_use_release_checksum_errors(tmp_path, invalid):
    artifact = tmp_path / "artifact.bin"
    artifact.write_bytes(b"data")
    output = tmp_path / "SHA256SUMS"
    output.write_text("stale\n", encoding="ascii")

    with pytest.raises(release_checksums.ReleaseChecksumError):
        release_checksums.write_sha256_manifest(artifact, str(tmp_path / invalid))
    with pytest.raises(release_checksums.ReleaseChecksumError):
        release_checksums.write_sha256_manifest(str(tmp_path / invalid), output)

    assert output.read_text(encoding="ascii") == "stale\n"


def test_broken_symlink_fifo_socket_and_device_outputs_are_refused_and_preserved(tmp_path):
    artifact = tmp_path / "artifact.bin"
    artifact.write_bytes(b"data")
    broken = tmp_path / "broken-output"
    broken.symlink_to(tmp_path / "missing-target")
    fifo = tmp_path / "fifo-output"
    os.mkfifo(str(fifo))
    socket_path = tmp_path / "socket-output"
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(socket_path))
    try:
        for output in (broken, fifo, socket_path):
            with pytest.raises(release_checksums.ReleaseChecksumError):
                release_checksums.write_sha256_manifest(artifact, output)
            assert os.path.lexists(str(output))
    finally:
        listener.close()

    device = pathlib.Path("/dev/null")
    if device.exists() and stat.S_ISCHR(device.stat().st_mode):
        with pytest.raises(release_checksums.ReleaseChecksumError):
            release_checksums.write_sha256_manifest(artifact, device)


def test_output_aliases_artifact_lexically_by_symlink_or_hardlink_without_mutation(tmp_path):
    artifact = tmp_path / "artifact.bin"
    artifact.write_bytes(b"data")
    with pytest.raises(release_checksums.ReleaseChecksumError, match="aliases artifact"):
        release_checksums.write_sha256_manifest(artifact, artifact)
    assert artifact.read_bytes() == b"data"

    symlink_parent = tmp_path / "symlink-parent"
    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    symlink_parent.symlink_to(real_parent, target_is_directory=True)
    nested_artifact = real_parent / "nested.bin"
    nested_artifact.write_bytes(b"nested")
    with pytest.raises(release_checksums.ReleaseChecksumError, match="aliases artifact"):
        release_checksums.write_sha256_manifest(nested_artifact, symlink_parent / "nested.bin")
    assert nested_artifact.read_bytes() == b"nested"

    hardlink = tmp_path / "hardlink"
    os.link(str(artifact), str(hardlink))
    with pytest.raises(release_checksums.ReleaseChecksumError, match="aliases artifact"):
        release_checksums.write_sha256_manifest(artifact, hardlink)
    assert artifact.read_bytes() == b"data"


def test_uncertain_hardlink_identity_preserves_output_before_validation(tmp_path, monkeypatch):
    artifact = tmp_path / "artifact.bin"
    output = tmp_path / "SHA256SUMS"
    artifact.write_bytes(b"data")
    os.link(str(artifact), str(output))
    original_stat = checksum_core.pathlib.Path.stat

    def fail_artifact_stat(path, *args, **kwargs):
        if path == artifact:
            raise PermissionError("identity unavailable")
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(checksum_core.pathlib.Path, "stat", fail_artifact_stat)
    with pytest.raises(release_checksums.ReleaseChecksumError, match="verify artifact/output identity") as caught:
        release_checksums.write_sha256_manifest(artifact, output)

    assert isinstance(caught.value.__cause__, PermissionError)
    assert output.read_bytes() == artifact.read_bytes() == b"data"


def test_symlinked_output_parent_is_accepted(tmp_path):
    artifact = tmp_path / "artifact.bin"
    artifact.write_bytes(b"data")
    real_parent = tmp_path / "real"
    real_parent.mkdir()
    link_parent = tmp_path / "linked"
    link_parent.symlink_to(real_parent, target_is_directory=True)
    output = link_parent / "SHA256SUMS"
    manifest = release_checksums.write_sha256_manifest(artifact, output)
    assert output.read_bytes() == manifest.encode("utf-8")


def test_missing_or_nondirectory_output_parent_fails_before_mutation(tmp_path):
    artifact = tmp_path / "artifact.bin"
    artifact.write_bytes(b"data")
    with pytest.raises(release_checksums.ReleaseChecksumError, match="parent"):
        release_checksums.write_sha256_manifest(artifact, tmp_path / "missing" / "SHA256SUMS")
    parent_file = tmp_path / "parent-file"
    parent_file.write_text("file", encoding="ascii")
    with pytest.raises(release_checksums.ReleaseChecksumError, match="parent"):
        release_checksums.write_sha256_manifest(artifact, parent_file / "SHA256SUMS")


def test_atomic_output_has_umask_permissions_and_fsync_before_replace(tmp_path, monkeypatch):
    artifact = tmp_path / "artifact.bin"
    output = tmp_path / "SHA256SUMS"
    artifact.write_bytes(b"data")
    calls = []
    original_fsync = filesystem.os.fsync
    original_open = filesystem.os.open
    original_replace = filesystem.os.replace

    def record_fsync(descriptor):
        calls.append("fsync")
        return original_fsync(descriptor)

    def record_replace(source, target):
        calls.append("replace")
        return original_replace(source, target)

    def record_open(path, flags, mode):
        assert flags & os.O_EXCL
        assert flags & os.O_CREAT
        assert mode == 0o666
        return original_open(path, flags, mode)

    monkeypatch.setattr(filesystem.os, "fsync", record_fsync)
    monkeypatch.setattr(filesystem.os, "open", record_open)
    monkeypatch.setattr(filesystem.os, "replace", record_replace)
    previous_umask = os.umask(0o027)
    try:
        manifest = release_checksums.write_sha256_manifest(artifact, output)
    finally:
        os.umask(previous_umask)
    assert output.read_bytes() == manifest.encode("utf-8")
    assert stat.S_IMODE(output.stat().st_mode) == 0o640
    assert calls == ["fsync", "replace"]


def test_temporary_creation_failure_and_collision_exhaustion_leave_final_absent(tmp_path, monkeypatch):
    artifact = tmp_path / "artifact.bin"
    output = tmp_path / "SHA256SUMS"
    artifact.write_bytes(b"data")
    output.write_text("stale\n", encoding="ascii")
    original_open = filesystem.os.open

    def fail_open(_path, _flags, _mode):
        raise OSError("creation failed")

    monkeypatch.setattr(filesystem.os, "open", fail_open)
    with pytest.raises(release_checksums.ReleaseChecksumError, match="creation failed"):
        release_checksums.write_sha256_manifest(artifact, output)
    assert not output.exists()
    assert list(tmp_path.glob(".la-dev-release-checksums-*.tmp")) == []

    class FixedUuid:
        hex = "collision"

    collision = tmp_path / ".la-dev-release-checksums-collision.tmp"
    collision.write_bytes(b"preexisting")
    monkeypatch.setattr(filesystem.os, "open", original_open)
    monkeypatch.setattr(filesystem.uuid, "uuid4", FixedUuid)
    with pytest.raises(release_checksums.ReleaseChecksumError, match="unique temporary"):
        release_checksums.write_sha256_manifest(artifact, output)
    assert not output.exists()
    assert collision.read_bytes() == b"preexisting"


@pytest.mark.parametrize("failure_stage", ["write", "flush", "fsync", "close"])
def test_write_flush_fsync_and_close_failures_clean_temporary_and_final(tmp_path, monkeypatch, failure_stage):
    artifact = tmp_path / "artifact.bin"
    output = tmp_path / "SHA256SUMS"
    artifact.write_bytes(b"data")
    output.write_text("stale\n", encoding="ascii")
    original_fdopen = filesystem.os.fdopen

    class FailingHandle:
        def __init__(self, handle):
            self.handle = handle

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            self.handle.close()
            if failure_stage == "close" and exc_type is None:
                raise OSError("close failed")

        def write(self, data):
            if failure_stage == "write":
                raise OSError("write failed")
            return self.handle.write(data)

        def flush(self):
            if failure_stage == "flush":
                raise OSError("flush failed")
            return self.handle.flush()

        def fileno(self):
            return self.handle.fileno()

    def wrapped_fdopen(descriptor, mode):
        return FailingHandle(original_fdopen(descriptor, mode))

    monkeypatch.setattr(filesystem.os, "fdopen", wrapped_fdopen)
    if failure_stage == "fsync":

        def fail_fsync(_descriptor):
            raise OSError("fsync failed")

        monkeypatch.setattr(filesystem.os, "fsync", fail_fsync)

    with pytest.raises(release_checksums.ReleaseChecksumError, match="{} failed".format(failure_stage)) as caught:
        release_checksums.write_sha256_manifest(artifact, output)

    assert isinstance(caught.value.__cause__, OSError)
    assert not output.exists()
    assert list(tmp_path.glob(".la-dev-release-checksums-*.tmp")) == []


def test_utf8_encoding_failure_cleans_temporary_and_final(tmp_path, monkeypatch):
    artifact = tmp_path / "artifact.bin"
    output = tmp_path / "SHA256SUMS"
    artifact.write_bytes(b"data")
    output.write_text("stale\n", encoding="ascii")
    monkeypatch.setattr(checksum_core, "_render_manifest", lambda _validated: "invalid\ud800")

    with pytest.raises(release_checksums.ReleaseChecksumError, match="write checksum output") as caught:
        release_checksums.write_sha256_manifest(artifact, output)

    assert isinstance(caught.value.__cause__, UnicodeEncodeError)
    assert not output.exists()
    assert list(tmp_path.glob(".la-dev-release-checksums-*.tmp")) == []


def test_replacement_failure_removes_temporary_and_leaves_final_absent(tmp_path, monkeypatch):
    artifact = tmp_path / "artifact.bin"
    output = tmp_path / "SHA256SUMS"
    artifact.write_bytes(b"data")
    output.write_text("stale\n", encoding="ascii")

    def fail_replace(_source, _target):
        raise OSError("replace failed")

    monkeypatch.setattr(filesystem.os, "replace", fail_replace)
    with pytest.raises(release_checksums.ReleaseChecksumError, match="replace failed"):
        release_checksums.write_sha256_manifest(artifact, output)
    assert not output.exists()
    assert list(tmp_path.glob(".la-dev-release-checksums-*.tmp")) == []


def test_cleanup_failure_is_reported_without_hiding_primary_failure(tmp_path, monkeypatch):
    artifact = tmp_path / "artifact.bin"
    output = tmp_path / "SHA256SUMS"
    artifact.write_bytes(b"data")

    def fail_replace(_source, _target):
        raise OSError("replace failed")

    monkeypatch.setattr(filesystem.os, "replace", fail_replace)
    original_cleanup = filesystem._cleanup_temporary

    def fail_cleanup(descriptor, temporary):
        return (*original_cleanup(descriptor, temporary), OSError("cleanup failed"))

    monkeypatch.setattr(filesystem, "_cleanup_temporary", fail_cleanup)
    with pytest.raises(release_checksums.ReleaseChecksumError, match=r"replace failed.*cleanup failed"):
        release_checksums.write_sha256_manifest(artifact, output)


@pytest.mark.parametrize("failure", [RuntimeError("unexpected"), KeyboardInterrupt(), SystemExit(7)])
def test_unexpected_atomic_failures_cleanup_and_propagate_unchanged(tmp_path, monkeypatch, failure):
    artifact = tmp_path / "artifact.bin"
    output = tmp_path / "SHA256SUMS"
    artifact.write_bytes(b"data")
    output.write_text("stale\n", encoding="ascii")

    def fail_fsync(_descriptor):
        raise failure

    monkeypatch.setattr(filesystem.os, "fsync", fail_fsync)
    with pytest.raises(type(failure)) as caught:
        release_checksums.write_sha256_manifest(artifact, output)

    assert caught.value is failure
    assert not output.exists()
    assert list(tmp_path.glob(".la-dev-release-checksums-*.tmp")) == []
