"""Conventional local action-source discovery for Perform."""

import os
import subprocess
import threading
from pathlib import Path

from .diagnostics import Diagnostic, sorted_unique_diagnostics

GIT_TIMEOUT_SECONDS = 5
GIT_OUTPUT_LIMIT = 64 * 1024
VCS_MARKERS = (".git", ".hg", ".sl")


class FilesystemView:
    """Injectable read-only filesystem operations used during discovery."""

    def expanduser(self, path):
        """Expand a leading user-home component."""
        return str(Path(path).expanduser())

    def abspath(self, path):
        """Return an absolute normalized path without requiring existence."""
        return os.path.abspath(path)  # noqa: PTH100 - Preserve symlinks while normalizing dot components.

    def realpath(self, path):
        """Return a symlink-resolved normalized path."""
        return os.path.realpath(path)

    def exists(self, path):
        """Return whether a path exists."""
        return Path(path).exists()

    def is_file(self, path):
        """Return whether a path is a regular file."""
        return Path(path).is_file()

    def is_dir(self, path):
        """Return whether a path is a directory."""
        return Path(path).is_dir()

    def accessible_directory(self, path):
        """Return whether a directory can be traversed and read."""
        return os.access(path, os.R_OK | os.X_OK)

    def join(self, *parts):
        """Join path components."""
        return str(Path(parts[0]).joinpath(*parts[1:]))

    def dirname(self, path):
        """Return a path's parent directory."""
        return str(Path(path).parent)

    def commonpath(self, paths):
        """Return the common normalized path."""
        return os.path.commonpath(paths)


class SourceDirectory:
    """One ordered action directory participating in catalog loading."""

    __slots__ = ("display_path", "kind", "normalized_path", "source_order")

    def __init__(self, kind, normalized_path, display_path=None, source_order=0):
        """Store source kind, normalized identity, display path, and precedence index."""
        self.kind = kind
        self.normalized_path = normalized_path
        self.display_path = display_path if display_path is not None else normalized_path
        self.source_order = source_order


class DiscoveryResult:
    """Ordered sources and metadata from conventional local discovery."""

    __slots__ = (
        "diagnostics",
        "precedence_incomplete",
        "repository_resolution",
        "repository_root",
        "sources",
    )

    def __init__(
        self,
        sources,
        repository_resolution="none",
        repository_root=None,
        diagnostics=None,
        precedence_incomplete=False,
    ):
        """Store discovery outcome and whether safe execution is possible."""
        self.sources = list(sources)
        self.repository_resolution = repository_resolution
        self.repository_root = repository_root
        self.diagnostics = sorted_unique_diagnostics(diagnostics or [])
        self.precedence_incomplete = precedence_incomplete


class GitCommandResult:
    """Bounded result from the optional read-only Git subprocess."""

    __slots__ = ("launch_error", "returncode", "stderr", "stderr_truncated", "stdout", "stdout_truncated", "timed_out")

    def __init__(
        self,
        returncode=None,
        stdout=b"",
        stderr=b"",
        timed_out=False,
        stdout_truncated=False,
        stderr_truncated=False,
        launch_error=None,
    ):
        """Store process completion, capped output, and failure state."""
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.timed_out = timed_out
        self.stdout_truncated = stdout_truncated
        self.stderr_truncated = stderr_truncated
        self.launch_error = launch_error


def _capture_pipe(pipe, limit, result):
    """Drain one process pipe while retaining no more than the configured limit."""
    retained = bytearray()
    truncated = False
    try:
        while True:
            chunk = pipe.read(8192)
            if not chunk:
                break
            remaining = limit - len(retained)
            if remaining > 0:
                retained.extend(chunk[:remaining])
            if len(chunk) > remaining:
                truncated = True
    finally:
        pipe.close()
    result.append((bytes(retained), truncated))


def run_bounded_git_root(cwd, popen_factory=None, timeout=GIT_TIMEOUT_SECONDS):
    """Run the one allowed read-only Git command with capped output and timeout."""
    if popen_factory is None:
        popen_factory = subprocess.Popen
    try:
        process = popen_factory(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
        )
    except OSError as exc:
        return GitCommandResult(launch_error=str(exc))

    stdout_result = []
    stderr_result = []
    stdout_thread = threading.Thread(target=_capture_pipe, args=(process.stdout, GIT_OUTPUT_LIMIT, stdout_result))
    stderr_thread = threading.Thread(target=_capture_pipe, args=(process.stderr, GIT_OUTPUT_LIMIT, stderr_result))
    stdout_thread.daemon = True
    stderr_thread.daemon = True
    stdout_thread.start()
    stderr_thread.start()

    timed_out = False
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.terminate()
        try:
            process.wait(timeout=0.25)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    stdout_thread.join(timeout=1)
    stderr_thread.join(timeout=1)
    stdout = stdout_result[0] if stdout_result else (b"", True)
    stderr = stderr_result[0] if stderr_result else (b"", True)
    return GitCommandResult(
        returncode=process.returncode,
        stdout=stdout[0],
        stderr=stderr[0],
        timed_out=timed_out,
        stdout_truncated=stdout[1],
        stderr_truncated=stderr[1],
    )


def _diagnostic(code, message, severity="warning", fatality="nonfatal"):
    """Construct a discovery diagnostic."""
    return Diagnostic(severity=severity, code=code, message=message, fatality=fatality, source_order=-1)


def _contains(filesystem, root, child):
    """Return whether resolved root contains resolved child."""
    try:
        return filesystem.commonpath([root, child]) == root
    except ValueError:
        return False


def _walk_for_repository(filesystem, cwd):
    """Find the closest ancestor carrying a supported VCS marker."""
    current = cwd
    while True:
        for marker in VCS_MARKERS:
            if filesystem.exists(filesystem.join(current, marker)):
                return current
        parent = filesystem.dirname(current)
        if parent == current:
            return None
        current = parent


def _resolve_repository(filesystem, cwd, git_runner):
    """Resolve one containing VCS root using Git then the marker walk."""
    diagnostics = []
    git_result = git_runner(cwd)
    if git_result.launch_error is not None:
        diagnostics.append(_diagnostic("git_unavailable", "Git repository discovery was unavailable: {}. Falling back to a marker walk.".format(git_result.launch_error), severity="info"))
    elif git_result.timed_out:
        diagnostics.append(_diagnostic("git_timeout", "Git repository discovery exceeded five seconds. Falling back to a marker walk."))
    elif git_result.stdout_truncated or git_result.stderr_truncated:
        diagnostics.append(_diagnostic("git_output_too_large", "Git repository discovery produced more than 64 KiB of output. Falling back to a marker walk."))
    elif git_result.returncode == 0:
        try:
            decoded = git_result.stdout.decode("utf-8")
        except UnicodeDecodeError:
            diagnostics.append(_diagnostic("git_invalid_utf8", "Git repository discovery returned non-UTF-8 output. Falling back to a marker walk."))
        else:
            lines = decoded.splitlines()
            if len(lines) == 1 and lines[0].strip() == lines[0] and lines[0] and Path(lines[0]).is_absolute():
                candidate = filesystem.realpath(filesystem.abspath(lines[0]))
                if filesystem.is_dir(candidate) and _contains(filesystem, candidate, cwd):
                    return candidate, "git", diagnostics
                diagnostics.append(
                    _diagnostic("git_invalid_root", "Git repository discovery returned a root that is missing or does not contain the working directory. Falling back to a marker walk.")
                )
            else:
                diagnostics.append(_diagnostic("git_malformed_output", "Git repository discovery did not return exactly one nonempty absolute root line. Falling back to a marker walk."))

    marker_root = _walk_for_repository(filesystem, cwd)
    if marker_root is not None:
        return filesystem.realpath(marker_root), "marker_walk", diagnostics
    return None, "none", diagnostics


def _normalize_source(filesystem, kind, path):
    """Create one source using resolved identity and the conventional display path."""
    return SourceDirectory(kind=kind, normalized_path=filesystem.realpath(path), display_path=filesystem.abspath(path))


def discover_action_directories(
    bundled_dir,
    cwd=None,
    env=None,
    filesystem=None,
    git_runner=None,
    system_config_path="/etc/codex/config.toml",
):
    """Discover ordered bundled, system, user, and one-root repository sources."""
    filesystem = filesystem or FilesystemView()
    env = dict(os.environ if env is None else env)
    cwd_input = str(Path.cwd()) if cwd is None else cwd
    cwd_absolute = filesystem.abspath(cwd_input)
    diagnostics = []
    sources = []
    precedence_incomplete = False

    if filesystem.is_dir(cwd_absolute):
        cwd_normalized = filesystem.realpath(cwd_absolute)
    else:
        cwd_normalized = cwd_absolute
        diagnostics.append(_diagnostic("invalid_cwd", "The requested working directory does not exist or is not a directory: {}".format(cwd_absolute), severity="error", fatality="catalog_fatal"))
        precedence_incomplete = True

    def add_optional_source(kind, action_dir):
        nonlocal precedence_incomplete
        if not filesystem.exists(action_dir):
            return
        if not filesystem.is_dir(action_dir):
            diagnostics.append(
                _diagnostic("action_source_not_directory", "The applicable {} action source is not a directory: {}".format(kind, action_dir), severity="error", fatality="catalog_fatal")
            )
            precedence_incomplete = True
            return
        if not filesystem.accessible_directory(action_dir):
            diagnostics.append(
                _diagnostic("action_source_inaccessible", "The applicable {} action source cannot be safely read: {}".format(kind, action_dir), severity="error", fatality="catalog_fatal")
            )
            precedence_incomplete = True
            return
        source = _normalize_source(filesystem, kind, action_dir)
        duplicate_index = None
        for index, existing in enumerate(sources):
            if existing.normalized_path == source.normalized_path:
                duplicate_index = index
                break
        if duplicate_index is not None:
            previous = sources.pop(duplicate_index)
            diagnostics.append(
                _diagnostic("source_deduplicated", "The {} and {} source paths resolve to the same directory; applying it once at {} precedence.".format(previous.kind, kind, kind), severity="info")
            )
        sources.append(source)

    bundled_absolute = filesystem.abspath(bundled_dir)
    if not filesystem.is_dir(bundled_absolute) or not filesystem.accessible_directory(bundled_absolute):
        diagnostics.append(
            _diagnostic("bundled_source_unavailable", "The bundled Perform action directory is missing or inaccessible: {}".format(bundled_absolute), severity="error", fatality="catalog_fatal")
        )
        precedence_incomplete = True
    else:
        add_optional_source("bundled", bundled_absolute)

    if filesystem.is_file(system_config_path):
        add_optional_source("system", filesystem.join(filesystem.dirname(system_config_path), "toolkit_perform_actions"))

    explicit_codex_home = env.get("CODEX_HOME")
    if explicit_codex_home:
        expanded_home = filesystem.expanduser(explicit_codex_home)
        if not Path(expanded_home).is_absolute():
            expanded_home = filesystem.join(cwd_absolute, expanded_home)
        user_root = filesystem.abspath(expanded_home)
        if not filesystem.is_dir(user_root) or not filesystem.accessible_directory(user_root):
            diagnostics.append(_diagnostic("invalid_codex_home", "Explicit CODEX_HOME must name an existing accessible directory: {}".format(user_root), severity="error", fatality="catalog_fatal"))
            precedence_incomplete = True
            user_root = None
    else:
        user_root = filesystem.abspath(filesystem.expanduser("~/.codex"))
        if filesystem.exists(user_root) and (not filesystem.is_dir(user_root) or not filesystem.accessible_directory(user_root)):
            diagnostics.append(_diagnostic("invalid_default_codex_home", "The default Codex home is not an accessible directory: {}".format(user_root), severity="error", fatality="catalog_fatal"))
            precedence_incomplete = True
            user_root = None
    if user_root is not None:
        add_optional_source("user", filesystem.join(user_root, "toolkit_perform_actions"))

    repository_root = None
    repository_resolution = "none"
    if filesystem.is_dir(cwd_normalized):
        if git_runner is None:
            git_runner = run_bounded_git_root
        repository_root, repository_resolution, repository_diagnostics = _resolve_repository(filesystem, cwd_normalized, git_runner)
        diagnostics.extend(repository_diagnostics)
        if repository_root is not None:
            repository_config = filesystem.join(repository_root, ".codex", "config.toml")
            if filesystem.is_file(repository_config):
                add_optional_source("repository", filesystem.join(repository_root, ".codex", "toolkit_perform_actions"))

    for source_order, source in enumerate(sources):
        source.source_order = source_order
    return DiscoveryResult(
        sources=sources,
        repository_resolution=repository_resolution,
        repository_root=repository_root,
        diagnostics=diagnostics,
        precedence_incomplete=precedence_incomplete,
    )


def explicit_discovery(action_directories):
    """Build discovery metadata for an explicit ordered source list."""
    sources = []
    filesystem = FilesystemView()
    for index, item in enumerate(action_directories):
        if isinstance(item, SourceDirectory):
            item.source_order = index
            sources.append(item)
        elif isinstance(item, (tuple, list)) and len(item) == 2:
            sources.append(SourceDirectory(item[0], filesystem.realpath(item[1]), filesystem.abspath(item[1]), index))
        else:
            sources.append(SourceDirectory("explicit", filesystem.realpath(item), filesystem.abspath(item), index))
    return DiscoveryResult(sources=sources)
