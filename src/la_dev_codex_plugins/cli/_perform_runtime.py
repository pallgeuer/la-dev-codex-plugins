"""Runtime discovery and process execution for the Perform launcher."""

import contextlib
import importlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
from pathlib import Path

MARKETPLACE_NAME = "la-dev-codex-plugins"
PLUGIN_NAME = "toolkit"
PLUGIN_ID = "{}@{}".format(PLUGIN_NAME, MARKETPLACE_NAME)
LAUNCHER_API_VERSION = 1
PLUGIN_DISCOVERY_TIMEOUT_SECONDS = 10
PLUGIN_DISCOVERY_OUTPUT_LIMIT = 1024 * 1024
PLUGIN_VERSION_RE = re.compile(
    r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-(?:0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)(?:\.(?:0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*))*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)


class CliError(Exception):
    """User-facing launcher failure with a stable exit class."""

    def __init__(self, message, exit_code=2, code="invalid_request", alternatives=None, diagnostics=None):
        """Store one concise error with optional alternatives and diagnostics."""
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code
        self.code = code
        self.alternatives = list(alternatives or [])
        self.diagnostics = list(diagnostics or [])

    def to_dict(self):
        """Return a compact structured launcher error."""
        payload = {"error": {"code": self.code, "message": self.message}}
        if self.alternatives:
            payload["available_variants"] = list(self.alternatives)
        if self.diagnostics:
            payload["diagnostics"] = list(self.diagnostics)
        return payload


class _BoundedProcessResult:
    """Captured bounded subprocess state."""

    __slots__ = ("capture_incomplete", "launch_error", "returncode", "stderr", "stderr_truncated", "stdout", "stdout_truncated", "timed_out")

    def __init__(self, returncode=None, stdout=b"", stderr=b"", timed_out=False, stdout_truncated=False, stderr_truncated=False, capture_incomplete=False, launch_error=None):
        """Store completion, capped streams, timeout state, and launch failure."""
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.timed_out = timed_out
        self.stdout_truncated = stdout_truncated
        self.stderr_truncated = stderr_truncated
        self.capture_incomplete = capture_incomplete
        self.launch_error = launch_error


def _capture_pipe(pipe, limit, result):
    """Drain one pipe while retaining no more than the requested byte limit."""
    retained = bytearray()
    truncated = False
    complete = True
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
    except (OSError, ValueError):
        complete = False
    finally:
        try:
            pipe.close()
        except (OSError, ValueError):
            complete = False
        result.append((bytes(retained), truncated, complete))


def _signal_process_tree(process, force):
    """Signal an isolated process tree, falling back to its direct child."""
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL if force else signal.SIGTERM)
            return True
        except (AttributeError, OSError):
            pass
    elif os.name == "nt":
        try:
            command = ["taskkill", "/PID", str(process.pid), "/T"]
            if force:
                command.append("/F")
            completed = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False, timeout=1)
            if completed.returncode == 0:
                return True
        except (AttributeError, OSError, subprocess.TimeoutExpired):
            pass
        if not force:
            try:
                process.send_signal(subprocess.CTRL_BREAK_EVENT)
                return True
            except (AttributeError, OSError, ValueError):
                pass
    try:
        if force:
            process.kill()
        else:
            process.terminate()
    except OSError:
        pass
    return False


def _stop_process_tree(process):
    """Stop one isolated process tree with a short graceful interval."""
    tree_signaled = _signal_process_tree(process, force=False)
    still_running = False
    try:
        process.wait(timeout=0.25)
    except subprocess.TimeoutExpired:
        still_running = True
    if tree_signaled or still_running:
        _signal_process_tree(process, force=True)
    if still_running:
        process.wait()


def _finish_pipe_capture(process, threads, pipes, results):
    """Finish pipe readers after cleaning descendants that retained handles."""
    for thread in threads:
        thread.join(timeout=0.1)
    if any(thread.is_alive() for thread in threads):
        _stop_process_tree(process)
        for thread in threads:
            thread.join(timeout=1)
    if any(thread.is_alive() for thread in threads):
        for pipe in pipes:
            with contextlib.suppress(OSError, ValueError):
                pipe.close()
        for thread in threads:
            thread.join(timeout=0.1)
    captures = [result[0] if result else (b"", False, False) for result in results]
    incomplete = any(thread.is_alive() for thread in threads) or any(not capture[2] for capture in captures)
    return captures, incomplete


def _run_bounded_command(command, cwd, env, popen_factory=None, timeout=PLUGIN_DISCOVERY_TIMEOUT_SECONDS, output_limit=PLUGIN_DISCOVERY_OUTPUT_LIMIT):
    """Run one command with exact environment, capped streams, and timeout."""
    if popen_factory is None:
        popen_factory = subprocess.Popen
    try:
        process = popen_factory(
            command,
            cwd=cwd,
            env=dict(env),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            start_new_session=os.name == "posix",
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0,
        )
    except OSError as exc:
        return _BoundedProcessResult(launch_error=str(exc))

    stdout_result = []
    stderr_result = []
    stdout_thread = threading.Thread(target=_capture_pipe, args=(process.stdout, output_limit, stdout_result))
    stderr_thread = threading.Thread(target=_capture_pipe, args=(process.stderr, output_limit, stderr_result))
    stdout_thread.daemon = True
    stderr_thread.daemon = True
    stdout_thread.start()
    stderr_thread.start()

    timed_out = False
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        _stop_process_tree(process)
    captures, capture_incomplete = _finish_pipe_capture(process, (stdout_thread, stderr_thread), (process.stdout, process.stderr), (stdout_result, stderr_result))
    stdout, stderr = captures
    return _BoundedProcessResult(
        returncode=process.returncode,
        stdout=stdout[0],
        stderr=stderr[0],
        timed_out=timed_out,
        stdout_truncated=stdout[1],
        stderr_truncated=stderr[1],
        capture_incomplete=capture_incomplete,
    )


def _expand_environment_path(path, environment, description):
    """Expand a current-user tilde from one explicit environment."""
    if path == "~" or path.startswith("~/"):
        home = environment.get("HOME")
        if not home:
            raise CliError("Could not resolve {} {!r} because HOME is unset or empty.".format(description, path), exit_code=4, code="directory_unavailable")
        return Path(home) if path == "~" else Path(home) / path[2:]
    if path.startswith("~"):
        raise CliError("Could not resolve {} {!r}; named-user tilde expansion is unsupported.".format(description, path), exit_code=4, code="directory_unavailable")
    return Path(path)


def resolve_directory(path):
    """Resolve and validate one existing directory from the process directory."""
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    try:
        resolved = candidate.resolve()
    except (OSError, RuntimeError) as exc:
        raise CliError("Could not resolve directory {}: {}".format(candidate, exc), exit_code=4, code="directory_unavailable") from exc
    if not resolved.is_dir():
        raise CliError("Directory does not exist or is not a directory: {}".format(resolved), code="invalid_directory")
    if not os.access(str(resolved), os.R_OK | os.X_OK):
        raise CliError("Directory is not readable and traversable: {}".format(resolved), exit_code=4, code="directory_unavailable")
    return str(resolved)


def normalize_codex_environment(cwd, env=None):
    """Copy an environment and normalize CODEX_HOME against one working root."""
    environment = dict(os.environ if env is None else env)
    configured_home = environment.get("CODEX_HOME")
    if not configured_home:
        environment.pop("CODEX_HOME", None)
        return environment
    codex_home = _expand_environment_path(configured_home, environment, "CODEX_HOME")
    if not codex_home.is_absolute():
        codex_home = Path(cwd) / codex_home
    try:
        codex_home = codex_home.resolve()
    except (OSError, RuntimeError) as exc:
        raise CliError("Could not resolve CODEX_HOME {}: {}".format(codex_home, exc), exit_code=4, code="directory_unavailable") from exc
    environment["CODEX_HOME"] = str(codex_home)
    return environment


def resolve_codex_executable(codex_executable, original_cwd, env=None):
    """Resolve one Codex executable to the absolute program used throughout."""
    if not isinstance(codex_executable, str) or not codex_executable or "\x00" in codex_executable:
        raise CliError("The Codex executable must be a nonempty string without NUL characters.", code="invalid_codex_executable")
    environment = dict(os.environ if env is None else env)
    expanded = _expand_environment_path(codex_executable, environment, "Codex executable")
    has_directory = any(separator is not None and separator in codex_executable for separator in (os.sep, os.altsep))
    if has_directory or expanded.is_absolute():
        candidate = expanded if expanded.is_absolute() else Path(original_cwd) / expanded
        discovered = shutil.which(str(candidate))
    else:
        discovered = shutil.which(str(expanded), path=os.pathsep.join(os.get_exec_path(environment)))
    if discovered is None:
        raise CliError("Could not find an executable Codex program for {!r}.".format(codex_executable), exit_code=4, code="codex_executable_unavailable")
    absolute = Path(discovered)
    if not absolute.is_absolute():
        absolute = Path(original_cwd) / absolute
    return os.path.abspath(str(absolute))  # noqa: PTH100 - Preserve the final executable symlink.


def _decode_utf8(value, description):
    """Decode required UTF-8 subprocess output independently of the locale."""
    if isinstance(value, str):
        return value
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CliError("{} is not valid UTF-8: {}".format(description, exc), exit_code=4, code="plugin_discovery_failed") from exc


def decode_codex_json(stdout):
    """Decode exact Codex JSON output without accepting stream contamination."""
    text = _decode_utf8(stdout, "Codex plugin discovery output")
    try:
        return json.loads(text)
    except ValueError as exc:
        raise CliError("Codex plugin discovery returned invalid JSON: {}".format(exc), exit_code=4, code="plugin_discovery_failed") from exc


def validate_plugin_root(plugin_root, expected_version=None):
    """Validate one toolkit plugin root and return its Perform scripts path."""
    root = Path(plugin_root)
    manifest_path = root / ".codex-plugin" / "plugin.json"
    try:
        with manifest_path.open("r", encoding="utf-8") as stream:
            manifest = json.load(stream)
    except (OSError, ValueError) as exc:
        raise CliError("Could not read toolkit plugin manifest {}: {}".format(manifest_path, exc), exit_code=4, code="plugin_layout_invalid") from exc
    if not isinstance(manifest, dict):
        raise CliError("Toolkit plugin manifest {} must contain a JSON object.".format(manifest_path), exit_code=4, code="plugin_layout_invalid")
    if manifest.get("name") != PLUGIN_NAME:
        raise CliError("Plugin root {} contains {!r}, not the required toolkit plugin.".format(root, manifest.get("name")), exit_code=4, code="plugin_layout_invalid")
    if expected_version is not None and manifest.get("version") != expected_version:
        raise CliError(
            "Installed toolkit manifest version {!r} does not match the Codex-installed version {!r}.".format(manifest.get("version"), expected_version),
            exit_code=4,
            code="plugin_version_mismatch",
        )
    scripts = root / "skills" / "perform" / "scripts"
    runtime_init = scripts / "toolkit_perform_runtime" / "__init__.py"
    assets = root / "skills" / "perform" / "assets" / "toolkit_perform_actions"
    if not runtime_init.is_file() or not assets.is_dir():
        raise CliError("Toolkit plugin root {} does not contain the required Perform runtime and assets.".format(root), exit_code=4, code="plugin_layout_invalid")
    return str(root.resolve()), str(scripts.resolve())


def discover_plugin_root(codex_executable, cwd, env=None, popen_factory=None, timeout=PLUGIN_DISCOVERY_TIMEOUT_SECONDS, output_limit=PLUGIN_DISCOVERY_OUTPUT_LIMIT):
    """Resolve the enabled installed toolkit plugin from Codex JSON state."""
    environment = normalize_codex_environment(cwd, env=env)
    command = [codex_executable, "plugin", "list", "--marketplace", MARKETPLACE_NAME, "--json"]
    completed = _run_bounded_command(command, cwd, environment, popen_factory=popen_factory, timeout=timeout, output_limit=output_limit)
    if completed.launch_error is not None:
        raise CliError("Could not run Codex plugin discovery: {}.".format(completed.launch_error), exit_code=4, code="plugin_discovery_failed")
    if completed.timed_out:
        raise CliError("Codex plugin discovery exceeded {} seconds.".format(timeout), exit_code=4, code="plugin_discovery_failed")
    if completed.capture_incomplete:
        raise CliError("Codex plugin discovery output could not be captured completely.", exit_code=4, code="plugin_discovery_failed")
    if completed.stdout_truncated or completed.stderr_truncated:
        raise CliError("Codex plugin discovery output exceeded {} bytes per stream.".format(output_limit), exit_code=4, code="plugin_discovery_failed")
    if completed.returncode != 0:
        detail_bytes = completed.stderr.strip() or completed.stdout.strip()
        detail = detail_bytes.decode("utf-8", errors="backslashreplace") if isinstance(detail_bytes, bytes) else detail_bytes
        raise CliError("Codex plugin discovery failed: {}".format(detail or "exit code {}".format(completed.returncode)), exit_code=4, code="plugin_discovery_failed")
    data = decode_codex_json(completed.stdout)
    installed = data.get("installed") if isinstance(data, dict) else None
    if not isinstance(installed, list):
        raise CliError("Codex plugin discovery JSON has no installed plugin list.", exit_code=4, code="plugin_discovery_failed")
    matches = [entry for entry in installed if isinstance(entry, dict) and entry.get("name") == PLUGIN_NAME and entry.get("marketplaceName") == MARKETPLACE_NAME]
    if len(matches) != 1:
        raise CliError("Expected exactly one installed {} entry, found {}.".format(PLUGIN_ID, len(matches)), exit_code=4, code="plugin_not_installed")
    entry = matches[0]
    if entry.get("installed") is not True:
        raise CliError("{} is not installed.".format(PLUGIN_ID), exit_code=4, code="plugin_not_installed")
    if entry.get("enabled") is not True:
        raise CliError("{} is installed but disabled.".format(PLUGIN_ID), exit_code=4, code="plugin_disabled")
    version = entry.get("version")
    if not isinstance(version, str) or PLUGIN_VERSION_RE.fullmatch(version) is None:
        raise CliError("{} has invalid installed version {!r}; expected a SemVer value.".format(PLUGIN_ID, version), exit_code=4, code="plugin_discovery_failed")
    configured_home = environment.get("CODEX_HOME")
    if configured_home:
        codex_home = Path(configured_home)
    else:
        home = environment.get("HOME")
        if not home:
            raise CliError("Could not resolve the default Codex home because HOME is unset or empty.", exit_code=4, code="plugin_discovery_failed")
        codex_home = Path(home)
        if not codex_home.is_absolute():
            codex_home = Path(cwd) / codex_home
        codex_home /= ".codex"
    cache_root = codex_home / "plugins" / "cache" / MARKETPLACE_NAME / PLUGIN_NAME
    try:
        resolved_cache_root = cache_root.resolve()
        plugin_root = (cache_root / version).resolve()
        contained = os.path.commonpath((str(resolved_cache_root), str(plugin_root))) == str(resolved_cache_root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise CliError("Could not safely resolve the installed toolkit cache path: {}.".format(exc), exit_code=4, code="plugin_discovery_failed") from exc
    if not contained:
        raise CliError("Installed toolkit version {!r} resolves outside the expected cache directory {}.".format(version, resolved_cache_root), exit_code=4, code="plugin_discovery_failed")
    return validate_plugin_root(plugin_root, expected_version=version)


def _validate_runtime_api(runtime):
    """Return one runtime after checking its standalone launcher API version."""
    version = getattr(runtime, "LAUNCHER_API_VERSION", None)
    if version != LAUNCHER_API_VERSION:
        raise CliError(
            "Installed toolkit launcher API version {!r} is incompatible with required version {}. Upgrade the toolkit plugin or use --plugin-root explicitly.".format(version, LAUNCHER_API_VERSION),
            exit_code=4,
            code="runtime_api_incompatible",
        )
    return runtime


def import_runtime(scripts_path):
    """Import the exact versioned launcher API rooted at one scripts directory."""
    expected_init = (Path(scripts_path) / "toolkit_perform_runtime" / "__init__.py").resolve()
    existing = sys.modules.get("toolkit_perform_runtime")
    if existing is not None:
        existing_file = getattr(existing, "__file__", None)
        if existing_file is None:
            raise CliError("A toolkit_perform_runtime without a filesystem location is already loaded.", exit_code=4, code="runtime_conflict")
        existing_path = Path(existing_file).resolve()
        if existing_path != expected_init:
            raise CliError("A different toolkit_perform_runtime is already loaded from {}.".format(existing_path), exit_code=4, code="runtime_conflict")
        _validate_runtime_api(existing)
        original_modules = set(sys.modules)
        try:
            return importlib.import_module("toolkit_perform_runtime.launcher_api")
        except Exception as exc:
            for module_name in list(sys.modules):
                if module_name not in original_modules and module_name.startswith("toolkit_perform_runtime."):
                    del sys.modules[module_name]
            raise CliError("Could not import the Perform launcher API from {}: {}".format(scripts_path, exc), exit_code=4, code="runtime_import_failed") from exc
    else:
        original_path = list(sys.path)
        original_modules = set(sys.modules)
        try:
            sys.path.insert(0, scripts_path)
            _validate_runtime_api(importlib.import_module("toolkit_perform_runtime"))
            launcher_api = importlib.import_module("toolkit_perform_runtime.launcher_api")
        except Exception as exc:
            for module_name in list(sys.modules):
                if module_name not in original_modules and (module_name == "toolkit_perform_runtime" or module_name.startswith("toolkit_perform_runtime.")):
                    del sys.modules[module_name]
            if isinstance(exc, CliError):
                raise
            raise CliError("Could not import the Perform runtime from {}: {}".format(scripts_path, exc), exit_code=4, code="runtime_import_failed") from exc
        finally:
            sys.path[:] = original_path
        return launcher_api


def load_runtime(plugin_root_argument, codex_executable, cwd, original_cwd, env=None):
    """Load a selected Perform runtime and retain one resolved Codex program."""
    if plugin_root_argument is not None:
        if plugin_root_argument == "":
            raise CliError("--plugin-root must name a nonempty directory.", code="invalid_directory")
        _plugin_root, scripts = validate_plugin_root(resolve_directory(plugin_root_argument))
        return import_runtime(scripts), None
    resolved_codex = resolve_codex_executable(codex_executable, original_cwd, env=env)
    _plugin_root, scripts = discover_plugin_root(resolved_codex, cwd, env=env)
    return import_runtime(scripts), resolved_codex


def replace_process(argv, env=None):
    """Replace the launcher with one exact Unicode-safe process invocation."""
    environment = dict(os.environ if env is None else env)
    if os.name == "posix":
        encoded = [argument.encode("utf-8", errors="surrogateescape") for argument in argv]
        encoded_environment = {key.encode("utf-8", errors="surrogateescape"): value.encode("utf-8", errors="surrogateescape") for key, value in environment.items()}
        os.execve(encoded[0], encoded, encoded_environment)
    else:
        os.execve(argv[0], argv, environment)
