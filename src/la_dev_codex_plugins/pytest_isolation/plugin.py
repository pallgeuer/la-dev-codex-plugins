"""Explicit pytest fixtures and markers for per-test working-directory isolation."""

import collections.abc
import os
import pathlib
import shutil
import stat
import tempfile

import pytest

_ENVIRONMENT_NAMES = ("TMPDIR", "TEMP", "TMP")
_MISSING = object()
_STATE_ATTRIBUTE = "_la_dev_pytest_isolation_state"
_DEFAULT_POISON_FILES = {"pyproject.toml": "[tool.la_dev_cwd_guard\n"}


class _IsolationState:
    """Mutable lifecycle state for one opted-in test."""

    __slots__ = ("boundary", "cwd", "cwd_identity", "environment", "guarded", "original_cwd", "tempdir", "tmp")

    def __init__(self, original_cwd, environment, tempdir, guarded):
        self.original_cwd = original_cwd
        self.environment = environment
        self.tempdir = tempdir
        self.guarded = guarded
        self.boundary = None
        self.cwd = None
        self.cwd_identity = None
        self.tmp = None


def pytest_configure(config):
    """Register the two explicit isolation markers."""
    config.addinivalue_line("markers", "guarded_cwd(poison_files=None, include_default_poison=True): Run in a read-only poisoned working directory")
    config.addinivalue_line("markers", "isolated_cwd: Run in a fresh writable working directory")


def _fail(message):
    raise pytest.fail.Exception(message, pytrace=False)


def _nearest_marker(node, name):
    return next(node.iter_markers(name=name), None)


def _normalized_poison_files(marker):
    if marker is None:
        return dict(_DEFAULT_POISON_FILES)
    if marker.args:
        _fail("guarded_cwd accepts keyword arguments only")
    unknown = sorted(set(marker.kwargs) - {"poison_files", "include_default_poison"})
    if unknown:
        _fail("guarded_cwd received unknown keyword argument(s): {}".format(", ".join(unknown)))
    include_default = marker.kwargs.get("include_default_poison", True)
    if not isinstance(include_default, bool):
        _fail("guarded_cwd include_default_poison must be a boolean")
    supplied = marker.kwargs.get("poison_files")
    if supplied is None:
        supplied = {}
    if not isinstance(supplied, collections.abc.Mapping):
        _fail("guarded_cwd poison_files must be a mapping of string paths to string contents")

    entries = dict(_DEFAULT_POISON_FILES) if include_default else {}
    normalized_sources = {}
    for raw_path, contents in supplied.items():
        if not isinstance(raw_path, str) or not isinstance(contents, str):
            _fail("guarded_cwd poison_files paths and contents must be strings")
        if not raw_path or "\x00" in raw_path or pathlib.Path(raw_path).is_absolute():
            _fail("guarded_cwd poison file paths must be nonempty relative paths")
        raw_parts = raw_path.split("/")
        if ".." in raw_parts:
            _fail("guarded_cwd poison file paths must not contain '..' components")
        normalized = os.path.normpath(raw_path)
        if normalized in {"", "."} or normalized == ".." or normalized.startswith(".." + os.sep):
            _fail("guarded_cwd poison file paths must identify a file below the guarded directory")
        if normalized in normalized_sources and normalized_sources[normalized] != raw_path:
            _fail("guarded_cwd poison file paths normalize to the same path: {!r} and {!r}".format(normalized_sources[normalized], raw_path))
        normalized_sources[normalized] = raw_path
        entries[normalized] = contents

    normalized_paths = sorted(entries)
    for index, path in enumerate(normalized_paths):
        parts = pathlib.PurePath(path).parts
        for other in normalized_paths[index + 1 :]:
            other_parts = pathlib.PurePath(other).parts
            if len(parts) < len(other_parts) and other_parts[: len(parts)] == parts:
                _fail("guarded_cwd poison file paths collide as a file and directory: {!r} and {!r}".format(path, other))
    return entries


def _select_mode(request):
    guarded_marker = _nearest_marker(request.node, "guarded_cwd")
    isolated_marker = _nearest_marker(request.node, "isolated_cwd")
    fixture_names = set(request.fixturenames)
    guarded = guarded_marker is not None or "guarded_cwd" in fixture_names
    isolated = isolated_marker is not None or "isolated_cwd" in fixture_names
    if guarded and isolated:
        _fail("guarded_cwd and isolated_cwd cannot be applied to the same test")
    if not guarded and not isolated:
        return None, None
    if isolated_marker is not None and (isolated_marker.args or isolated_marker.kwargs):
        _fail("isolated_cwd accepts no positional or keyword arguments")
    poison_files = _normalized_poison_files(guarded_marker) if guarded else None
    return "guarded" if guarded else "isolated", poison_files


def _create_boundary(state, poison_files):
    saved_tempdir = tempfile.tempdir
    tempfile.tempdir = None
    try:
        boundary_value = tempfile.mkdtemp(prefix="la-dev-pytest-isolation-")
    finally:
        tempfile.tempdir = saved_tempdir
    state.boundary = pathlib.Path(os.fsdecode(boundary_value))
    state.boundary.chmod(0o700)
    state.cwd = state.boundary / "cwd"
    state.tmp = state.boundary / "tmp"
    state.cwd.mkdir()
    state.cwd.chmod(0o700)
    state.tmp.mkdir()
    state.tmp.chmod(0o700)
    cwd_metadata = state.cwd.stat()
    state.cwd_identity = (cwd_metadata.st_dev, cwd_metadata.st_ino)
    if poison_files is not None:
        for relative, contents in poison_files.items():
            path = state.cwd / relative
            parent = state.cwd
            for component in pathlib.PurePath(relative).parts[:-1]:
                parent = parent / component
                if not parent.exists():
                    parent.mkdir()
                    parent.chmod(0o700)
            with path.open("w", encoding="utf-8", newline="") as handle:
                handle.write(contents)
        for root, directories, filenames in os.walk(str(state.cwd), topdown=False):
            root_path = pathlib.Path(root)
            for filename in filenames:
                (root_path / filename).chmod(0o400)
            for directory in directories:
                (root_path / directory).chmod(0o500)
        state.cwd.chmod(0o500)


def _directory_open_flags():
    if not hasattr(os, "O_DIRECTORY") or not hasattr(os, "O_NOFOLLOW"):
        raise OSError("safe no-follow directory traversal is unavailable")
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def _restore_directory_permissions(descriptor, display_path, failures):
    try:
        os.fchmod(descriptor, 0o700)
        names = os.listdir(descriptor)  # noqa: PTH208 - pathlib cannot enumerate an already verified directory descriptor
    except OSError as exc:
        failures.append("could not restore guarded directory {}: {}".format(display_path, exc))
        return
    for name in names:
        child_display = display_path / name
        try:
            metadata = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
        except OSError as exc:
            failures.append("could not inspect guarded entry {}: {}".format(child_display, exc))
            continue
        if not stat.S_ISDIR(metadata.st_mode):
            continue
        try:
            child_descriptor = os.open(name, _directory_open_flags(), dir_fd=descriptor)
        except OSError as exc:
            failures.append("could not safely open guarded directory {}: {}".format(child_display, exc))
            continue
        try:
            opened = os.fstat(child_descriptor)
            if (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino):
                failures.append("guarded directory changed identity during restoration: {}".format(child_display))
                continue
            _restore_directory_permissions(child_descriptor, child_display, failures)
        finally:
            os.close(child_descriptor)


def _restore_permissions(state, failures):
    if not state.guarded or state.cwd is None or state.cwd_identity is None:
        return
    try:
        descriptor = os.open(str(state.cwd), _directory_open_flags())
    except OSError as exc:
        failures.append("could not safely open guarded working directory {}: {}".format(state.cwd, exc))
        return
    try:
        metadata = os.fstat(descriptor)
        if (metadata.st_dev, metadata.st_ino) != state.cwd_identity:
            failures.append("guarded working directory changed identity before restoration: {}".format(state.cwd))
            return
        _restore_directory_permissions(descriptor, state.cwd, failures)
    finally:
        os.close(descriptor)


def _restore_state(state, inspect_final=True):
    failures = []
    final_cwd = None
    if inspect_final:
        try:
            final_cwd = os.getcwd()  # noqa: PTH109 - deleted working directories must be detected through os.getcwd
        except OSError as exc:
            failures.append("could not inspect the test's final working directory: {}".format(exc))
        if state.guarded and final_cwd is not None:
            try:
                remains_guarded = pathlib.Path(final_cwd).samefile(state.cwd)
            except OSError as exc:
                failures.append("could not verify the test's final guarded working directory: {}".format(exc))
            else:
                if not remains_guarded:
                    failures.append("guarded_cwd test escaped its guarded working directory: {}".format(final_cwd))

    try:
        os.chdir(state.original_cwd)
    except OSError as exc:
        failures.append("could not restore the original working directory {}: {}".format(state.original_cwd, exc))

    for name, previous in state.environment.items():
        if previous is _MISSING:
            os.environ.pop(name, None)
        else:
            os.environ[name] = previous
    tempfile.tempdir = state.tempdir

    _restore_permissions(state, failures)
    if state.boundary is not None:
        try:
            shutil.rmtree(str(state.boundary))
        except OSError as exc:
            failures.append("could not clean the isolation boundary {}: {}".format(state.boundary, exc))
    return failures


@pytest.fixture(autouse=True)
def _cwd_isolation_dispatcher(request):
    """Activate exactly one requested isolation mode before ordinary fixtures."""
    mode, poison_files = _select_mode(request)
    if mode is None:
        yield
        return

    try:
        original_cwd = os.getcwd()  # noqa: PTH109 - the contract requires saving the exact os.getcwd value
    except OSError as exc:
        _fail("could not save the original working directory: {}".format(exc))
    environment = {name: os.environ.get(name, _MISSING) for name in _ENVIRONMENT_NAMES}
    state = _IsolationState(original_cwd, environment, tempfile.tempdir, guarded=mode == "guarded")
    setattr(request.node, _STATE_ATTRIBUTE, state)
    try:
        _create_boundary(state, poison_files)
        assert state.tmp is not None
        temporary_path = str(state.tmp.absolute())
        for name in _ENVIRONMENT_NAMES:
            os.environ[name] = temporary_path
        tempfile.tempdir = None
        os.chdir(str(state.cwd))
    except BaseException:
        failures = _restore_state(state, inspect_final=False)
        if failures:
            _fail("Isolation setup failed; restoration also failed: {}".format("; ".join(failures)))
        raise

    yield

    failures = _restore_state(state)
    if failures:
        _fail("Working-directory isolation teardown failed: {}".format("; ".join(failures)))


def _fixture_path(request, expected_mode):
    state = getattr(request.node, _STATE_ATTRIBUTE, None)
    if state is None:
        _fail("{} fixture was requested without active isolation".format(expected_mode))
    assert state is not None
    if state.guarded != (expected_mode == "guarded_cwd"):
        _fail("{} fixture conflicts with the active isolation mode".format(expected_mode))
    return state.cwd


@pytest.fixture
def isolated_cwd(request):
    """Return the fresh writable working directory for an isolated test."""
    return _fixture_path(request, "isolated_cwd")


@pytest.fixture
def guarded_cwd(request):
    """Return the read-only poisoned working directory for a guarded test."""
    return _fixture_path(request, "guarded_cwd")
