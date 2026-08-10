"""Explicit and configured pytest working-directory isolation."""

import collections.abc
import contextlib
import hashlib
import os
import pathlib
import stat
import sys
import tempfile
import warnings

import pytest

_ENVIRONMENT_NAMES = ("TMPDIR", "TEMP", "TMP")
_MISSING = object()
_UNMARKED_OPTION = "la_dev_cwd_isolation_unmarked"
_UNMARKED_MODES = ("none", "shared_guarded")
_CLEANUP_OPTION = "la_dev_cwd_isolation_cleanup"
_CLEANUP_MODES = ("eager", "pytest_retained")
_DISPOSITION_PENDING = "pending"
_DISPOSITION_REMOVED = "eagerly_removed"
_DISPOSITION_RETAINED = "safely_retained"
_DISPOSITION_FAILED = "failed_preserved"
_DEFAULT_POISON_FILES = {"pyproject.toml": "[tool.la_dev_cwd_guard\n"}
_SHARED_POLICY_KEYS = {"boundary_files", "poison_files"}
_BOUNDARY_RESERVED_NAMES = {"cwd", "tmp"}
_SESSION_ATTRIBUTE = "_la_dev_cwd_isolation_session"
_PRIVATE_ITEM_ATTRIBUTE = "_la_dev_cwd_isolation_private_item"
_SHARED_ITEM_ATTRIBUTE = "_la_dev_cwd_isolation_shared_item"


class _HookSpecifications:
    """Project hooks for configured working-directory isolation."""

    @pytest.hookspec
    def pytest_la_dev_cwd_isolation_shared_policy(self, config):
        """Return one process-global shared boundary and poison-file policy."""


class _PolicyError(ValueError):
    """Invalid private or shared file policy."""


class _IsolationState:
    """Lifecycle state for one private or session-shared boundary.

    The original process fields preserve the exact CWD, temporary-environment
    values, and ``tempfile.tempdir`` cache restored when the boundary ends.
    The boundary fields identify the disposable root and its parent, guarded
    or writable CWD, sibling temporary directory, and recorded identities used
    for fail-closed cleanup and shared-state activation. The cleanup mode and
    disposition distinguish pending, removed, safely retained, and failed
    lifecycles, while preserved nested paths prevent an outer shared cleanup
    from traversing uncertain private data.
    """

    __slots__ = (
        "boundary",
        "boundary_identity",
        "boundary_parent_identity",
        "cleanup_mode",
        "cwd",
        "cwd_identity",
        "disposition",
        "environment",
        "guarded",
        "integrity_manifest",
        "original_cwd",
        "preserved_nested_boundaries",
        "tempdir",
        "tmp",
        "tmp_identity",
    )

    def __init__(self, original_cwd, environment, tempdir, guarded, cleanup_mode):
        self.original_cwd = original_cwd
        self.environment = environment
        self.tempdir = tempdir
        self.guarded = guarded
        self.cleanup_mode = cleanup_mode
        self.integrity_manifest = None
        self.disposition = _DISPOSITION_PENDING
        self.preserved_nested_boundaries = set()
        self.boundary = None
        self.boundary_identity = None
        self.boundary_parent_identity = None
        self.cwd = None
        self.cwd_identity = None
        self.tmp = None
        self.tmp_identity = None


class _SessionIsolation:
    """Configured shared-isolation state owned by one pytest configuration."""

    __slots__ = ("allocation_parent", "boundary_files", "cleanup_attempted", "cleanup_mode", "enabled", "poison_files", "policy_hookimpls", "shared_state")

    def __init__(self, enabled, cleanup_mode):
        self.enabled = enabled
        self.cleanup_mode = cleanup_mode
        self.allocation_parent = None
        self.boundary_files = None
        self.poison_files = None
        self.policy_hookimpls = frozenset()
        self.shared_state = None
        self.cleanup_attempted = False


class _SharedItemIsolation:
    """Active outer shared isolation for one pytest item."""

    __slots__ = ("original_cwd", "state")

    def __init__(self, state, original_cwd):
        self.state = state
        self.original_cwd = original_cwd


class _BoundaryRootDescriptors:
    """Verified parent and boundary descriptors for one isolation root."""

    __slots__ = ("boundary", "parent")

    def __init__(self, parent, boundary):
        self.parent = parent
        self.boundary = boundary


class _BoundaryDescriptors(_BoundaryRootDescriptors):
    """Verified descriptors for one complete isolation boundary."""

    __slots__ = ("cwd", "tmp")

    def __init__(self, parent, boundary, cwd, tmp):
        super().__init__(parent, boundary)
        self.cwd = cwd
        self.tmp = tmp


class _PolicyVerificationFrame:
    """One open directory in an iterative policy-tree verification."""

    __slots__ = ("descriptor", "index", "names", "owned", "prefix")

    def __init__(self, descriptor, prefix, names, owned):
        self.descriptor = descriptor
        self.prefix = prefix
        self.names = names
        self.index = 0
        self.owned = owned


class _CleanupFrame:
    """One open directory in an iterative cleanup traversal."""

    __slots__ = ("complete", "descriptor", "display_path", "identity", "index", "name", "names", "owned")

    def __init__(self, descriptor, display_path, names, owned, name=None, identity=None, complete=True):
        self.descriptor = descriptor
        self.display_path = display_path
        self.names = names
        self.index = 0
        self.owned = owned
        self.name = name
        self.identity = identity
        self.complete = complete


def pytest_addhooks(pluginmanager):
    """Register the process-global shared-isolation policy hook."""
    pluginmanager.add_hookspecs(_HookSpecifications)


def pytest_addoption(parser):
    """Register the string-valued isolation settings."""
    parser.addini(_UNMARKED_OPTION, "Isolation mode for tests without an explicit isolation marker or fixture", default="none")
    parser.addini(_CLEANUP_OPTION, "Cleanup lifecycle for working-directory isolation boundaries", default="eager")


def _get_optional_ini(config, name):
    """Return one public pytest ini setting or the missing sentinel."""
    try:
        return config.getini(name)
    except ValueError:
        return _MISSING


def _validate_retained_compatibility(config):
    """Require pytest to keep the current base temp through process exit."""
    if config.getoption("basetemp") is not None:
        return
    policy = _get_optional_ini(config, "tmp_path_retention_policy")
    count = _get_optional_ini(config, "tmp_path_retention_count")
    if policy is _MISSING and count is _MISSING:
        return
    if policy != "all":
        raise pytest.UsageError("{}=pytest_retained requires tmp_path_retention_policy=all so the current base temp outlives the session; supplied value: {!r}".format(_CLEANUP_OPTION, policy))
    try:
        positive_count = int(count) >= 1
    except (TypeError, ValueError):
        positive_count = False
    if not positive_count:
        raise pytest.UsageError("{}=pytest_retained requires tmp_path_retention_count of at least 1 so the current base temp outlives the session; supplied value: {!r}".format(_CLEANUP_OPTION, count))


def pytest_configure(config):
    """Register markers and validate process-wide isolation configuration."""
    config.addinivalue_line("markers", "guarded_cwd(poison_files=None, include_default_poison=True): Run in a read-only poisoned working directory")
    config.addinivalue_line("markers", "isolated_cwd: Run in a fresh writable working directory")
    configured = config.getini(_UNMARKED_OPTION)
    if configured not in _UNMARKED_MODES:
        raise pytest.UsageError("{}={!r} is invalid; allowed values are: {}".format(_UNMARKED_OPTION, configured, ", ".join(_UNMARKED_MODES)))
    cleanup_mode = config.getini(_CLEANUP_OPTION)
    if cleanup_mode not in _CLEANUP_MODES:
        raise pytest.UsageError("{}={!r} is invalid; allowed values are: {}".format(_CLEANUP_OPTION, cleanup_mode, ", ".join(_CLEANUP_MODES)))
    if cleanup_mode == "pytest_retained":
        _validate_retained_compatibility(config)
    setattr(config, _SESSION_ATTRIBUTE, _SessionIsolation(enabled=configured == "shared_guarded", cleanup_mode=cleanup_mode))


def _fail(message):
    raise pytest.fail.Exception(message, pytrace=False)


def _warn(message):
    warning = pytest.PytestWarning(message)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("always", pytest.PytestWarning)
            warnings.warn(warning, stacklevel=2)
    except Exception:
        with contextlib.suppress(Exception):
            sys.stderr.write("PytestWarning: {}\n".format(message))


def _nearest_marker(node, name):
    return next(node.iter_markers(name=name), None)


def _normalized_file_mapping(supplied, label, initial=None):
    """Copy and validate one complete or overlay file mapping."""
    if not isinstance(supplied, collections.abc.Mapping):
        raise _PolicyError("{} must be a mapping of string paths to string contents".format(label))

    entries = {} if initial is None else dict(initial)
    normalized_sources = {}
    for raw_path, contents in supplied.items():
        if not isinstance(raw_path, str) or not isinstance(contents, str):
            raise _PolicyError("{} paths and contents must be strings".format(label))
        if not raw_path or "\x00" in raw_path or pathlib.Path(raw_path).is_absolute():
            raise _PolicyError("{} paths must be nonempty relative paths".format(label))
        raw_parts = raw_path.split("/")
        if ".." in raw_parts:
            raise _PolicyError("{} paths must not contain '..' components".format(label))
        normalized = os.path.normpath(raw_path)
        if normalized in {"", "."} or normalized == ".." or normalized.startswith(".." + os.sep):
            raise _PolicyError("{} paths must identify a file below the policy root".format(label))
        try:
            os.fsencode(normalized)
        except UnicodeEncodeError:
            raise _PolicyError("{} paths must be encodable by the filesystem".format(label)) from None
        try:
            contents.encode("utf-8")
        except UnicodeEncodeError:
            raise _PolicyError("{} contents must be encodable as UTF-8".format(label)) from None
        if normalized in normalized_sources and normalized_sources[normalized] != raw_path:
            raise _PolicyError("{} paths normalize to the same path: {!r} and {!r}".format(label, normalized_sources[normalized], raw_path))
        normalized_sources[normalized] = raw_path
        entries[normalized] = contents

    normalized_paths = set(entries)
    for path in sorted(normalized_paths):
        for parent_path in pathlib.PurePath(path).parents:
            parent = str(parent_path)
            if parent == os.curdir:
                continue
            if parent in normalized_paths:
                raise _PolicyError("{} paths collide as a file and directory: {!r} and {!r}".format(label, parent, path))
    return entries


def _normalized_poison_files(marker):
    """Resolve the nearest private guarded marker's merge policy."""
    try:
        if marker is None:
            return dict(_DEFAULT_POISON_FILES)
        if marker.args:
            raise _PolicyError("guarded_cwd accepts keyword arguments only")
        unknown = sorted(set(marker.kwargs) - {"poison_files", "include_default_poison"})
        if unknown:
            raise _PolicyError("guarded_cwd received unknown keyword argument(s): {}".format(", ".join(unknown)))
        include_default = marker.kwargs.get("include_default_poison", True)
        if not isinstance(include_default, bool):
            raise _PolicyError("guarded_cwd include_default_poison must be a boolean")
        supplied = marker.kwargs.get("poison_files")
        if supplied is None:
            supplied = {}
        initial = _DEFAULT_POISON_FILES if include_default else None
        return _normalized_file_mapping(supplied, "guarded_cwd poison_files", initial=initial)
    except _PolicyError as exc:
        _fail(str(exc))


def _shared_policy(config):
    """Resolve one early process-global shared-boundary policy."""
    policies = config.hook.pytest_la_dev_cwd_isolation_shared_policy(config=config)
    if len(policies) > 1:
        raise pytest.UsageError("pytest_la_dev_cwd_isolation_shared_policy must have at most one non-None provider per pytest process")
    supplied = {} if not policies else policies[0]
    try:
        if not isinstance(supplied, collections.abc.Mapping):
            raise _PolicyError("pytest_la_dev_cwd_isolation_shared_policy must return a mapping or None")
        supplied_keys = list(supplied)
        if any(not isinstance(key, str) for key in supplied_keys):
            raise _PolicyError("pytest_la_dev_cwd_isolation_shared_policy keys must be strings")
        unknown = sorted(set(supplied_keys) - _SHARED_POLICY_KEYS)
        if unknown:
            raise _PolicyError("pytest_la_dev_cwd_isolation_shared_policy returned unknown key(s): {}".format(", ".join(unknown)))

        boundary_files = _normalized_file_mapping(supplied.get("boundary_files", {}), "shared policy boundary_files")
        poison_files = _normalized_file_mapping(supplied.get("poison_files", _DEFAULT_POISON_FILES), "shared policy poison_files")
        for relative in boundary_files:
            first = pathlib.PurePath(relative).parts[0]
            if first in _BOUNDARY_RESERVED_NAMES:
                raise _PolicyError("shared policy boundary_files must not use reserved boundary path {!r}".format(first))
    except _PolicyError as exc:
        raise pytest.UsageError(str(exc)) from None
    return boundary_files, poison_files


def _policy_hookimpl_ids(config):
    """Return identities for policy implementations currently registered."""
    return frozenset(id(implementation) for implementation in config.hook.pytest_la_dev_cwd_isolation_shared_policy.get_hookimpls())


def _late_policy_hookimpls(config, original):
    """Return policy implementations registered after session start."""
    return [implementation for implementation in config.hook.pytest_la_dev_cwd_isolation_shared_policy.get_hookimpls() if id(implementation) not in original]


def _non_root_conftest_policy_hookimpls(config, implementations):
    """Return policy providers implemented by nested conftest modules."""
    root = pathlib.Path(str(config.rootpath)).resolve()
    conftest_plugins = getattr(config.pluginmanager, "_conftest_plugins", frozenset())
    invalid = []
    for implementation in implementations:
        conftest_modules = []
        if implementation.plugin in conftest_plugins:
            conftest_modules.append(implementation.plugin)
        function_module_name = getattr(implementation.function, "__module__", None)
        function_module = sys.modules.get(function_module_name) if function_module_name is not None else None
        if function_module in conftest_plugins and function_module not in conftest_modules:
            conftest_modules.append(function_module)
        conftest_paths = [getattr(module, "__file__", None) for module in conftest_modules]
        if any(path is not None and pathlib.Path(path).resolve().parent != root for path in conftest_paths):
            invalid.append(implementation)
    return invalid


def _policy_provider_names(implementations):
    """Return stable display names for policy hook implementations."""
    return sorted({str(getattr(implementation, "plugin_name", "unknown")) for implementation in implementations})


def _select_mode(item):
    """Resolve and validate an explicit private isolation request."""
    guarded_marker = _nearest_marker(item, "guarded_cwd")
    isolated_marker = _nearest_marker(item, "isolated_cwd")
    fixture_names = set(getattr(item, "fixturenames", ()))
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


def _save_process_state(guarded, cleanup_mode):
    """Capture exact process state before creating an isolation boundary."""
    try:
        original_cwd = os.getcwd()  # noqa: PTH109 - the contract requires saving the exact os.getcwd value
    except OSError as exc:
        _fail("could not save the original working directory: {}".format(exc))
    environment = {name: os.environ.get(name, _MISSING) for name in _ENVIRONMENT_NAMES}
    return _IsolationState(original_cwd, environment, tempfile.tempdir, guarded=guarded, cleanup_mode=cleanup_mode)


def _write_read_only_files(root, files):
    """Create an exact mapping below one root and return its compact manifest."""
    created_directories = set()
    manifest = {}
    for relative, contents in files.items():
        path = root / relative
        parent = root
        for component in pathlib.PurePath(relative).parts[:-1]:
            parent = parent / component
            if not parent.exists():
                parent.mkdir()
                parent.chmod(0o700)
                created_directories.add(parent)
            manifest[str(parent.relative_to(root))] = ("directory", 0o500, None)
        with path.open("w", encoding="utf-8", newline="") as handle:
            handle.write(contents)
        path.chmod(0o400)
        manifest[relative] = ("file", 0o400, hashlib.sha256(contents.encode("utf-8")).hexdigest())
    for directory in sorted(created_directories, key=lambda path: len(path.parts), reverse=True):
        directory.chmod(0o500)
    return manifest


def _create_boundary(state, poison_files, boundary_files=None, record_integrity=False, allocation_parent=None):
    """Create one boundary below an optional explicit allocation parent."""
    saved_tempdir = tempfile.tempdir
    tempfile.tempdir = None
    try:
        boundary_value = tempfile.mkdtemp(prefix="la-dev-pytest-isolation-", dir=None if allocation_parent is None else str(allocation_parent))
    finally:
        tempfile.tempdir = saved_tempdir
    state.boundary = pathlib.Path(os.path.realpath(os.fsdecode(boundary_value)))
    boundary_metadata = state.boundary.stat()
    boundary_parent_metadata = state.boundary.parent.stat()
    state.boundary_identity = (boundary_metadata.st_dev, boundary_metadata.st_ino)
    state.boundary_parent_identity = (boundary_parent_metadata.st_dev, boundary_parent_metadata.st_ino)
    state.boundary.chmod(0o700)
    state.cwd = state.boundary / "cwd"
    state.tmp = state.boundary / "tmp"
    state.cwd.mkdir()
    cwd_metadata = state.cwd.stat()
    state.cwd_identity = (cwd_metadata.st_dev, cwd_metadata.st_ino)
    state.cwd.chmod(0o700)
    state.tmp.mkdir()
    tmp_metadata = state.tmp.stat()
    state.tmp_identity = (tmp_metadata.st_dev, tmp_metadata.st_ino)
    state.tmp.chmod(0o700)
    boundary_manifest = _write_read_only_files(state.boundary, boundary_files or {})
    cwd_manifest = None
    if poison_files is not None:
        cwd_manifest = _write_read_only_files(state.cwd, poison_files)
        state.cwd.chmod(0o500)
    if record_integrity:
        state.integrity_manifest = {"boundary": boundary_manifest, "cwd": cwd_manifest or {}}


def _redirect_temporary_state(state):
    """Redirect standard temporary state to a previously verified sibling."""
    assert state.tmp is not None
    temporary_path = str(state.tmp.absolute())
    for name in _ENVIRONMENT_NAMES:
        os.environ[name] = temporary_path
    tempfile.tempdir = None


def _directory_open_flags():
    if not hasattr(os, "O_DIRECTORY") or not hasattr(os, "O_NOFOLLOW"):
        raise OSError("safe no-follow directory traversal is unavailable")
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def _metadata_identity(metadata):
    return metadata.st_dev, metadata.st_ino


def _close_descriptor(descriptor):
    if descriptor is not None:
        os.close(descriptor)


@contextlib.contextmanager
def _open_recorded_boundary_root(state, failures, shared=False):
    """Open one recorded boundary parent and root by verified identity."""
    if state.boundary is None or state.boundary_identity is None or state.boundary_parent_identity is None:
        failures.append("{} isolation boundary state is incomplete".format("shared" if shared else "recorded"))
        yield None
        return

    parent = state.boundary.parent
    parent_descriptor = None
    boundary_descriptor = None
    try:
        try:
            parent_descriptor = os.open(str(parent), _directory_open_flags())
        except OSError as exc:
            failures.append("could not safely open {} isolation boundary parent {}: {}".format("shared" if shared else "recorded", parent, exc))
            yield None
            return
        if _metadata_identity(os.fstat(parent_descriptor)) != state.boundary_parent_identity:
            failures.append("{} isolation boundary parent changed identity: {}".format("shared" if shared else "recorded", parent))
            yield None
            return
        try:
            boundary_descriptor = os.open(state.boundary.name, _directory_open_flags(), dir_fd=parent_descriptor)
        except OSError as exc:
            failures.append("could not safely open {} isolation boundary {}: {}".format("shared" if shared else "recorded", state.boundary, exc))
            yield None
            return
        if _metadata_identity(os.fstat(boundary_descriptor)) != state.boundary_identity:
            failures.append("{} isolation boundary changed identity: {}".format("shared" if shared else "recorded", state.boundary))
            yield None
            return
        yield _BoundaryRootDescriptors(parent_descriptor, boundary_descriptor)
    finally:
        _close_descriptor(boundary_descriptor)
        _close_descriptor(parent_descriptor)


def _open_recorded_child(boundary_descriptor, path, identity, description, failures):
    """Open one complete recorded boundary child by verified identity."""
    try:
        descriptor = os.open(path.name, _directory_open_flags(), dir_fd=boundary_descriptor)
    except OSError as exc:
        failures.append("could not safely open {} {}: {}".format(description, path, exc))
        return None
    if _metadata_identity(os.fstat(descriptor)) != identity:
        failures.append("{} changed identity: {}".format(description, path))
        os.close(descriptor)
        return None
    return descriptor


@contextlib.contextmanager
def _open_recorded_boundary(state, failures, shared=False):
    """Open one complete boundary and both identity-verified children."""
    if state.cwd is None or state.cwd_identity is None or state.tmp is None or state.tmp_identity is None:
        failures.append("{} isolation boundary state is incomplete".format("shared" if shared else "recorded"))
        yield None
        return

    cwd_descriptor = None
    tmp_descriptor = None
    with _open_recorded_boundary_root(state, failures, shared=shared) as root_descriptors:
        if root_descriptors is None:
            yield None
            return
        try:
            cwd_descriptor = _open_recorded_child(
                root_descriptors.boundary,
                state.cwd,
                state.cwd_identity,
                "{} working directory".format("shared guarded" if shared else "recorded"),
                failures,
            )
            if cwd_descriptor is None:
                yield None
                return
            tmp_descriptor = _open_recorded_child(
                root_descriptors.boundary,
                state.tmp,
                state.tmp_identity,
                "{} temporary directory".format("shared" if shared else "recorded"),
                failures,
            )
            if tmp_descriptor is None:
                yield None
                return
            yield _BoundaryDescriptors(root_descriptors.parent, root_descriptors.boundary, cwd_descriptor, tmp_descriptor)
        finally:
            _close_descriptor(tmp_descriptor)
            _close_descriptor(cwd_descriptor)


def _entry_mode(metadata):
    return stat.S_IMODE(metadata.st_mode)


def _verify_descriptor_mode(descriptor, expected, display_path, failures):
    actual = _entry_mode(os.fstat(descriptor))
    if actual != expected:
        failures.append("recorded isolation entry has mode {:04o} instead of {:04o}: {}".format(actual, expected, display_path))


def _hash_descriptor(descriptor):
    digest = hashlib.sha256()
    while True:
        chunk = os.read(descriptor, 65536)
        if not chunk:
            return digest.hexdigest()
        digest.update(chunk)


def _policy_child_index(manifest):
    """Index manifest paths by parent and immediate child name."""
    children = {}
    for relative in manifest:
        parent, name = os.path.split(relative)
        children.setdefault(parent, set()).add(name)
    return children


def _policy_verification_frame(descriptor, display_path, prefix, children, failures, excluded_names, owned):
    """Inspect one policy directory and return its iterative frame."""
    try:
        names = set(os.listdir(descriptor))  # noqa: PTH208 - verification is anchored to a recorded descriptor
    except OSError as exc:
        failures.append("could not inspect shared policy directory {}: {}".format(display_path / prefix, exc))
        if owned:
            os.close(descriptor)
        return None
    if not prefix:
        names -= set(excluded_names)
    expected_names = children.get(prefix, set())
    for missing in sorted(expected_names - names):
        relative = prefix + os.sep + missing if prefix else missing
        failures.append("shared policy entry is missing: {}".format(display_path / relative))
    for unexpected in sorted(names - expected_names):
        relative = prefix + os.sep + unexpected if prefix else unexpected
        failures.append("shared policy contains unexpected entry: {}".format(display_path / relative))
    return _PolicyVerificationFrame(descriptor, prefix, sorted(names & expected_names), owned)


def _verify_policy_tree(descriptor, display_path, manifest, failures, excluded_names=frozenset(), prefix=""):
    """Verify one exact no-follow policy tree with iterative descriptor traversal."""
    children = _policy_child_index(manifest)
    first = _policy_verification_frame(descriptor, display_path, prefix, children, failures, excluded_names, owned=False)
    if first is None:
        return
    frames = [first]
    try:
        while frames:
            frame = frames[-1]
            if frame.index >= len(frame.names):
                frames.pop()
                if frame.owned:
                    os.close(frame.descriptor)
                continue
            name = frame.names[frame.index]
            frame.index += 1
            relative = frame.prefix + os.sep + name if frame.prefix else name
            expected_kind, expected_mode, expected_digest = manifest[relative]
            entry_display = display_path / relative
            try:
                metadata = os.stat(name, dir_fd=frame.descriptor, follow_symlinks=False)
            except OSError as exc:
                failures.append("could not inspect shared policy entry {}: {}".format(entry_display, exc))
                continue
            actual_kind = "directory" if stat.S_ISDIR(metadata.st_mode) else "file" if stat.S_ISREG(metadata.st_mode) else "other"
            if actual_kind != expected_kind:
                failures.append("shared policy entry has type {} instead of {}: {}".format(actual_kind, expected_kind, entry_display))
                continue
            actual_mode = _entry_mode(metadata)
            if actual_mode != expected_mode:
                failures.append("shared policy entry has mode {:04o} instead of {:04o}: {}".format(actual_mode, expected_mode, entry_display))
            flags = _directory_open_flags() if expected_kind == "directory" else os.O_RDONLY | os.O_NOFOLLOW
            try:
                child_descriptor = os.open(name, flags, dir_fd=frame.descriptor)
            except OSError as exc:
                failures.append("could not safely open shared policy entry {}: {}".format(entry_display, exc))
                continue
            try:
                opened = os.fstat(child_descriptor)
                if _metadata_identity(opened) != _metadata_identity(metadata):
                    failures.append("shared policy entry changed identity during verification: {}".format(entry_display))
                    continue
                if expected_kind == "directory":
                    child_frame = _policy_verification_frame(child_descriptor, display_path, relative, children, failures, frozenset(), owned=True)
                    child_descriptor = None
                    if child_frame is not None:
                        frames.append(child_frame)
                elif _hash_descriptor(child_descriptor) != expected_digest:
                    failures.append("shared policy file contents changed: {}".format(entry_display))
            finally:
                _close_descriptor(child_descriptor)
    finally:
        for frame in frames:
            if frame.owned:
                os.close(frame.descriptor)


def _verify_layout_modes(state, descriptors, cwd_mode, failures):
    """Verify constant-size boundary modes after identities are known."""
    original_failure_count = len(failures)
    _verify_descriptor_mode(descriptors.boundary, 0o700, state.boundary, failures)
    _verify_descriptor_mode(descriptors.cwd, cwd_mode, state.cwd, failures)
    _verify_descriptor_mode(descriptors.tmp, 0o700, state.tmp, failures)
    return len(failures) == original_failure_count


def _verify_shared_integrity(state, descriptors, failures):
    """Verify exact shared modes and policy trees before session cleanup."""
    if state.integrity_manifest is None:
        failures.append("shared isolation integrity manifest is missing")
        return False
    original_failure_count = len(failures)
    _verify_layout_modes(state, descriptors, 0o500, failures)
    _verify_policy_tree(descriptors.boundary, state.boundary, state.integrity_manifest["boundary"], failures, excluded_names=_BOUNDARY_RESERVED_NAMES)
    _verify_policy_tree(descriptors.cwd, state.cwd, state.integrity_manifest["cwd"], failures)
    return len(failures) == original_failure_count


def _activate_shared_state(state, enter_cwd, failures):
    """Verify and activate one unchanged shared layout in constant time."""
    with _open_recorded_boundary(state, failures, shared=True) as descriptors:
        if descriptors is None or not _verify_layout_modes(state, descriptors, 0o500, failures):
            return False
        if enter_cwd:
            try:
                os.fchdir(descriptors.cwd)
            except OSError as exc:
                failures.append("could not enter shared guarded working directory {}: {}".format(state.cwd, exc))
                return False

    _redirect_temporary_state(state)
    return True


def _remove_directory_contents(descriptor, display_path, failures):
    """Restore and remove verified contents with iterative descriptor traversal."""
    try:
        os.fchmod(descriptor, 0o700)
        names = sorted(os.listdir(descriptor))  # noqa: PTH208 - traversal is anchored to a verified descriptor
    except OSError as exc:
        failures.append("could not inspect isolation directory {} during cleanup: {}".format(display_path, exc))
        return False

    frames = [_CleanupFrame(descriptor, display_path, names, owned=False)]
    try:
        while frames:
            frame = frames[-1]
            if frame.index < len(frame.names):
                name = frame.names[frame.index]
                frame.index += 1
                child_display = frame.display_path / name
                try:
                    metadata = os.stat(name, dir_fd=frame.descriptor, follow_symlinks=False)
                except OSError as exc:
                    failures.append("could not inspect isolation entry {} during cleanup: {}".format(child_display, exc))
                    frame.complete = False
                    continue
                if not stat.S_ISDIR(metadata.st_mode):
                    try:
                        os.unlink(name, dir_fd=frame.descriptor)
                    except OSError as exc:
                        failures.append("could not remove isolation entry {}: {}".format(child_display, exc))
                        frame.complete = False
                    continue

                expected_identity = _metadata_identity(metadata)
                try:
                    os.chmod(name, 0o700, dir_fd=frame.descriptor)
                    current = os.stat(name, dir_fd=frame.descriptor, follow_symlinks=False)
                except OSError as exc:
                    failures.append("could not restore isolation directory permissions {} during cleanup: {}".format(child_display, exc))
                    frame.complete = False
                    continue
                if not stat.S_ISDIR(current.st_mode) or _metadata_identity(current) != expected_identity:
                    failures.append("isolation directory changed identity during cleanup: {}".format(child_display))
                    frame.complete = False
                    continue
                try:
                    child_descriptor = os.open(name, _directory_open_flags(), dir_fd=frame.descriptor)
                except OSError as exc:
                    failures.append("could not safely open isolation directory {} during cleanup: {}".format(child_display, exc))
                    frame.complete = False
                    continue
                opened_identity = _metadata_identity(os.fstat(child_descriptor))
                if opened_identity != expected_identity:
                    failures.append("isolation directory changed identity during cleanup: {}".format(child_display))
                    frame.complete = False
                    os.close(child_descriptor)
                    continue
                try:
                    os.fchmod(child_descriptor, 0o700)
                    child_names = sorted(os.listdir(child_descriptor))  # noqa: PTH208 - traversal is anchored to a verified descriptor
                except OSError as exc:
                    failures.append("could not inspect isolation directory {} during cleanup: {}".format(child_display, exc))
                    frames.append(_CleanupFrame(child_descriptor, child_display, (), owned=True, name=name, identity=opened_identity, complete=False))
                    continue
                frames.append(_CleanupFrame(child_descriptor, child_display, child_names, owned=True, name=name, identity=opened_identity))
                continue

            frames.pop()
            if not frame.owned:
                return frame.complete
            parent = frames[-1]
            assert frame.name is not None
            try:
                current = os.stat(frame.name, dir_fd=parent.descriptor, follow_symlinks=False)
            except OSError as exc:
                failures.append("could not recheck isolation directory {} during cleanup: {}".format(frame.display_path, exc))
                parent.complete = False
                os.close(frame.descriptor)
                continue
            if _metadata_identity(current) != frame.identity:
                failures.append("isolation directory changed identity during cleanup: {}".format(frame.display_path))
                parent.complete = False
                os.close(frame.descriptor)
                continue
            if not frame.complete:
                parent.complete = False
                os.close(frame.descriptor)
                continue
            try:
                os.rmdir(frame.name, dir_fd=parent.descriptor)
            except OSError as exc:
                failures.append("could not remove isolation directory {}: {}".format(frame.display_path, exc))
                parent.complete = False
            os.close(frame.descriptor)
    finally:
        for frame in frames:
            if frame.owned:
                os.close(frame.descriptor)
    return False


def _remove_verified_child(parent_descriptor, child_descriptor, name, identity, display_path, failures):
    """Remove one already opened child without accepting a path replacement."""
    complete = _remove_directory_contents(child_descriptor, display_path, failures)
    try:
        current = os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
    except OSError as exc:
        failures.append("could not recheck isolation directory {} during cleanup: {}".format(display_path, exc))
        return False
    if _metadata_identity(current) != identity:
        failures.append("isolation directory changed identity during cleanup: {}".format(display_path))
        return False
    if not complete:
        return False
    try:
        os.rmdir(name, dir_fd=parent_descriptor)
    except OSError as exc:
        failures.append("could not remove isolation directory {}: {}".format(display_path, exc))
        return False
    return True


def _cleanup_boundary(state, failures):
    """Verify one recorded boundary and delete or retain it as configured."""
    if state.boundary is None:
        state.disposition = _DISPOSITION_REMOVED
        return
    state.disposition = _DISPOSITION_FAILED
    with _open_recorded_boundary_root(state, failures) as descriptors:
        if descriptors is None:
            return
        partial = state.cwd is None or state.cwd_identity is None or state.tmp is None or state.tmp_identity is None
        child_descriptors = []
        unresolved = False
        try:
            for name, path, identity, description in (
                ("cwd", state.cwd, state.cwd_identity, "recorded working directory"),
                ("tmp", state.tmp, state.tmp_identity, "recorded temporary directory"),
            ):
                display_path = state.boundary / name if path is None else path
                if path is None or identity is None:
                    try:
                        os.stat(name, dir_fd=descriptors.boundary, follow_symlinks=False)
                    except FileNotFoundError:
                        continue
                    except OSError as exc:
                        failures.append("could not inspect incomplete isolation entry {} during cleanup: {}".format(display_path, exc))
                    else:
                        failures.append("isolation entry exists without a recorded identity and was preserved: {}".format(display_path))
                    unresolved = True
                    continue
                child_descriptor = _open_recorded_child(descriptors.boundary, path, identity, description, failures)
                if child_descriptor is None:
                    if not partial:
                        return
                    unresolved = True
                    continue
                child_descriptors.append((child_descriptor, path, identity))

            if not partial and len(child_descriptors) != 2:
                return
            if state.integrity_manifest is not None:
                complete_descriptors = _BoundaryDescriptors(descriptors.parent, descriptors.boundary, child_descriptors[0][0], child_descriptors[1][0])
                integrity_verified = _verify_shared_integrity(state, complete_descriptors, failures)
            elif state.cleanup_mode == "pytest_retained" and not partial and len(child_descriptors) == 2:
                complete_descriptors = _BoundaryDescriptors(descriptors.parent, descriptors.boundary, child_descriptors[0][0], child_descriptors[1][0])
                integrity_verified = _verify_layout_modes(state, complete_descriptors, 0o500 if state.guarded else 0o700, failures)
            else:
                integrity_verified = True
            if state.preserved_nested_boundaries:
                failures.append("shared isolation boundary was preserved because nested private cleanup was incomplete: {}".format(", ".join(sorted(state.preserved_nested_boundaries))))
                return
            if state.cleanup_mode == "pytest_retained":
                if not partial and not unresolved and len(child_descriptors) == 2 and integrity_verified:
                    state.disposition = _DISPOSITION_RETAINED
                elif partial or unresolved or len(child_descriptors) != 2:
                    failures.append("recorded isolation boundary state was incomplete and was retained: {}".format(state.boundary))
                return

            children_complete = True
            for child_descriptor, path, identity in child_descriptors:
                if not _remove_verified_child(descriptors.boundary, child_descriptor, path.name, identity, path, failures):
                    children_complete = False
            if unresolved or not children_complete:
                return
        finally:
            for child_descriptor, _path, _identity in child_descriptors:
                os.close(child_descriptor)

        if not _remove_directory_contents(descriptors.boundary, state.boundary, failures):
            return
        try:
            current = os.stat(state.boundary.name, dir_fd=descriptors.parent, follow_symlinks=False)
        except OSError as exc:
            failures.append("could not recheck isolation boundary {} before removal: {}".format(state.boundary, exc))
            return
        if _metadata_identity(current) != state.boundary_identity:
            failures.append("isolation boundary changed identity during cleanup: {}".format(state.boundary))
            return
        try:
            os.rmdir(state.boundary.name, dir_fd=descriptors.parent)
        except OSError as exc:
            failures.append("could not remove isolation boundary {}: {}".format(state.boundary, exc))
            return
        state.disposition = _DISPOSITION_REMOVED


def _inspect_final_cwd(state, escaped_label, failures):
    """Inspect final CWD accessibility and enforce guarded identity."""
    try:
        final_cwd = os.getcwd()  # noqa: PTH109 - deleted working directories must be detected through os.getcwd
    except OSError as exc:
        failures.append("could not inspect the test's final working directory: {}".format(exc))
        return
    if not state.guarded:
        return
    try:
        remains_guarded = pathlib.Path(final_cwd).samefile(state.cwd)
    except OSError as exc:
        failures.append("could not verify the test's final guarded working directory: {}".format(exc))
    else:
        if not remains_guarded:
            failures.append("{} escaped its guarded working directory: {}".format(escaped_label, final_cwd))


def _restore_cwd(original_cwd, failures):
    """Attempt to return to an exact previously saved working directory."""
    try:
        os.chdir(original_cwd)
    except OSError as exc:
        failures.append("could not restore the original working directory {}: {}".format(original_cwd, exc))


def _restore_state(state, inspect_final=True):
    """Restore process state and finalize one private or shared boundary."""
    failures = []
    if inspect_final:
        _inspect_final_cwd(state, "guarded_cwd test", failures)
    _restore_cwd(state.original_cwd, failures)

    for name, previous in state.environment.items():
        if previous is _MISSING:
            os.environ.pop(name, None)
        else:
            os.environ[name] = previous
    tempfile.tempdir = state.tempdir

    _cleanup_boundary(state, failures)
    return failures


def _session_isolation(config):
    return getattr(config, _SESSION_ATTRIBUTE)


def pytest_sessionstart(session):
    """Resolve policy and initialize any required pytest base temp early."""
    isolation = _session_isolation(session.config)
    if isolation.enabled:
        implementations = session.config.hook.pytest_la_dev_cwd_isolation_shared_policy.get_hookimpls()
        invalid = _non_root_conftest_policy_hookimpls(session.config, implementations)
        if invalid:
            raise pytest.UsageError(
                "pytest_la_dev_cwd_isolation_shared_policy must be implemented by the root conftest or an early-loaded plugin; nested conftest provider(s): {}".format(
                    ", ".join(_policy_provider_names(invalid))
                )
            )
        isolation.policy_hookimpls = _policy_hookimpl_ids(session.config)
        isolation.boundary_files, isolation.poison_files = _shared_policy(session.config)
    if not isolation.enabled and isolation.cleanup_mode != "pytest_retained":
        return
    temporary_factory = getattr(session.config, "_tmp_path_factory", None)
    if temporary_factory is None:
        raise pytest.UsageError("working-directory isolation requires pytest's built-in temporary-path plugin")
    saved_tempdir = tempfile.tempdir
    try:
        isolation.allocation_parent = pathlib.Path(os.path.realpath(os.fsdecode(temporary_factory.getbasetemp())))
    finally:
        tempfile.tempdir = saved_tempdir


@pytest.hookimpl(trylast=True)
def pytest_collection_finish(session):
    """Reject late policy providers and allocate the shared boundary."""
    isolation = _session_isolation(session.config)
    if not isolation.enabled:
        return
    late_implementations = _late_policy_hookimpls(session.config, isolation.policy_hookimpls)
    if late_implementations:
        raise pytest.UsageError(
            "pytest_la_dev_cwd_isolation_shared_policy must be implemented by the root conftest or a plugin loaded before pytest_sessionstart; late provider(s): {}".format(
                ", ".join(_policy_provider_names(late_implementations))
            )
        )

    state = _save_process_state(guarded=True, cleanup_mode=isolation.cleanup_mode)
    try:
        _create_boundary(
            state,
            isolation.poison_files,
            boundary_files=isolation.boundary_files,
            record_integrity=True,
            allocation_parent=isolation.allocation_parent if isolation.cleanup_mode == "pytest_retained" else None,
        )
        _redirect_temporary_state(state)
    except BaseException as exc:
        failures = _restore_state(state, inspect_final=False)
        message = "Shared guarded session setup failed: {}".format(exc)
        if failures:
            message += "; restoration also failed: {}".format("; ".join(failures))
        raise pytest.UsageError(message) from exc
    isolation.shared_state = state
    isolation.boundary_files = None
    isolation.poison_files = None
    isolation.policy_hookimpls = frozenset()


def _cleanup_shared_session(config):
    """Restore a configured shared session exactly once."""
    isolation = _session_isolation(config)
    if isolation.cleanup_attempted or isolation.shared_state is None:
        return []
    isolation.cleanup_attempted = True
    state = isolation.shared_state
    isolation.shared_state = None
    return _restore_state(state, inspect_final=False)


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_sessionfinish(session, exitstatus):
    """Keep shared state active through other session-finalization hooks."""
    del exitstatus
    outcome = yield
    failures = _cleanup_shared_session(session.config)
    if failures:
        message = "Shared guarded session teardown failed: {}".format("; ".join(failures))
        if outcome.excinfo is None and session.exitstatus == pytest.ExitCode.OK:
            session.exitstatus = pytest.ExitCode.TESTS_FAILED
        _warn(message)


@pytest.hookimpl(trylast=True)
def pytest_unconfigure(config):
    """Restore shared state when session start did not complete."""
    if not hasattr(config, _SESSION_ATTRIBUTE):
        return
    failures = _cleanup_shared_session(config)
    if failures:
        _warn("Shared guarded session fallback teardown failed: {}".format("; ".join(failures)))
    delattr(config, _SESSION_ATTRIBUTE)


def _setup_shared_item_isolation(item):
    """Activate the outer shared layer before fixtures of every scope."""
    if hasattr(item, _SHARED_ITEM_ATTRIBUTE):
        _fail("shared working-directory isolation is already active for this test")
    shared_state = _session_isolation(item.config).shared_state
    if shared_state is None:
        return
    try:
        original_cwd = os.getcwd()  # noqa: PTH109 - the contract requires saving the exact os.getcwd value
    except OSError as exc:
        _fail("could not save the original working directory before shared guarding: {}".format(exc))
    failures = []
    if not _activate_shared_state(shared_state, enter_cwd=True, failures=failures):
        _restore_cwd(original_cwd, failures)
        _fail("Shared guarded test setup failed: {}".format("; ".join(failures)))
    setattr(item, _SHARED_ITEM_ATTRIBUTE, _SharedItemIsolation(shared_state, original_cwd))


def _teardown_shared_item_isolation(item, inspect_final):
    """Restore one active outer shared item layer."""
    active = getattr(item, _SHARED_ITEM_ATTRIBUTE, None)
    if active is None:
        return []
    delattr(item, _SHARED_ITEM_ATTRIBUTE)
    shared_state = _session_isolation(item.config).shared_state
    failures = []
    if inspect_final:
        _inspect_final_cwd(active.state, "shared guarded test", failures)
    _restore_cwd(active.original_cwd, failures)
    if shared_state is not None:
        _activate_shared_state(shared_state, enter_cwd=False, failures=failures)
    return failures


def _preserve_shared_after_private_cleanup(private_state, shared_state):
    """Block outer cleanup after an incomplete nested private cleanup."""
    if shared_state is not None and private_state.disposition == _DISPOSITION_FAILED and private_state.boundary is not None and private_state.boundary_parent_identity == shared_state.tmp_identity:
        shared_state.preserved_nested_boundaries.add(str(private_state.boundary))


def _setup_private_item_isolation(item, mode, poison_files):
    """Create the private function-scoped layer for one explicit test."""
    if hasattr(item, _PRIVATE_ITEM_ATTRIBUTE):
        _fail("private working-directory isolation is already active for this test")
    shared_state = _session_isolation(item.config).shared_state
    if shared_state is not None:
        failures = []
        if not _activate_shared_state(shared_state, enter_cwd=False, failures=failures):
            _fail("Shared guarded state verification failed before private test setup: {}".format("; ".join(failures)))
    isolation = _session_isolation(item.config)
    state = _save_process_state(guarded=mode == "guarded", cleanup_mode=isolation.cleanup_mode)
    try:
        if isolation.cleanup_mode == "pytest_retained":
            allocation_parent = shared_state.tmp if shared_state is not None else isolation.allocation_parent
            _create_boundary(state, poison_files, allocation_parent=allocation_parent)
        else:
            _create_boundary(state, poison_files)
        _redirect_temporary_state(state)
        os.chdir(str(state.cwd))
    except BaseException:
        failures = _restore_state(state, inspect_final=False)
        _preserve_shared_after_private_cleanup(state, shared_state)
        if failures:
            _warn("Isolation setup restoration failed: {}".format("; ".join(failures)))
        raise
    setattr(item, _PRIVATE_ITEM_ATTRIBUTE, state)


def _teardown_private_item_isolation(item, inspect_final):
    """Restore one active private function-scoped layer."""
    state = getattr(item, _PRIVATE_ITEM_ATTRIBUTE, None)
    if state is None:
        return []
    delattr(item, _PRIVATE_ITEM_ATTRIBUTE)
    failures = _restore_state(state, inspect_final=inspect_final)
    shared_state = _session_isolation(item.config).shared_state
    if shared_state is not None:
        _preserve_shared_after_private_cleanup(state, shared_state)
        _activate_shared_state(shared_state, enter_cwd=False, failures=failures)
    return failures


def _force_outcome_exception(outcome, exception):
    """Force a hookwrapper exception with a Pluggy 1.0 compatibility path."""
    force_exception = getattr(outcome, "force_exception", None)
    if force_exception is not None:
        force_exception(exception)
        return
    outcome._excinfo = (type(exception), exception, exception.__traceback__)


def _report_item_failures(outcome, label, failures):
    if not failures:
        return
    message = "{}: {}".format(label, "; ".join(failures))
    if outcome.excinfo is None:
        _force_outcome_exception(outcome, pytest.fail.Exception(message, pytrace=False))
        return
    _warn(message)


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_protocol(item, nextitem):
    """Restore isolation before pytest resets CWD during interrupt unwind."""
    del nextitem
    outcome = yield
    if not hasattr(item, _PRIVATE_ITEM_ATTRIBUTE) and not hasattr(item, _SHARED_ITEM_ATTRIBUTE):
        return
    failures = _teardown_private_item_isolation(item, inspect_final=outcome.excinfo is None)
    failures.extend(_teardown_shared_item_isolation(item, inspect_final=outcome.excinfo is None))
    _report_item_failures(outcome, "Working-directory isolation emergency teardown failed", failures)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    """Enter the shared outer layer before pytest creates fixtures."""
    _setup_shared_item_isolation(item)


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_teardown(item, nextitem):
    """Leave the shared outer layer after pytest finalizes broad fixtures."""
    del nextitem
    outcome = yield
    failures = _teardown_shared_item_isolation(item, inspect_final=True)
    _report_item_failures(outcome, "Working-directory isolation teardown failed", failures)


@pytest.fixture(autouse=True)
def _private_isolation_dispatcher(request):
    """Nest explicit private isolation around downstream function fixtures."""
    mode, poison_files = _select_mode(request.node)
    if mode is None:
        yield
        return
    _setup_private_item_isolation(request.node, mode, poison_files)
    yield
    failures = _teardown_private_item_isolation(request.node, inspect_final=True)
    if failures:
        _fail("Working-directory isolation teardown failed: {}".format("; ".join(failures)))


def _fixture_path(request, expected_mode):
    """Return only an explicitly requested private fixture boundary."""
    state = getattr(request.node, _PRIVATE_ITEM_ATTRIBUTE, None)
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
    """Return the private read-only poisoned CWD for an explicitly guarded test."""
    return _fixture_path(request, "guarded_cwd")
