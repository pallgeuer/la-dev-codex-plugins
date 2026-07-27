"""Tests for Perform runtime loading and execution."""

import contextlib
import importlib
import io
import json
import os
import signal
import subprocess
import sys
import time
import types
import typing
from pathlib import Path

import pytest

import la_dev_codex_plugins.cli.perform as perform
from la_dev_codex_plugins.cli import _perform_runtime as perform_runtime

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPOSITORY_ROOT / "plugins" / "toolkit"


class ExecCalled(BaseException):
    """Test-only signal carrying a requested process replacement."""

    def __init__(self, executable, argv, environment=None):
        super().__init__(executable)
        self.executable = executable
        self.argv = argv
        self.environment = environment


class FakeProcess:
    """Popen test double for bounded plugin discovery."""

    def __init__(self, stdout=b"", stderr=b"", returncode=0, timeout_count=0):
        self.stdout = io.BytesIO(stdout)
        self.stderr = io.BytesIO(stderr)
        self.returncode = returncode
        self.timeout_count = timeout_count
        self.wait_calls = 0
        self.terminated = False
        self.killed = False

    def wait(self, timeout=None):
        """Return completion or synthesize one initial timeout."""
        self.wait_calls += 1
        if self.wait_calls <= self.timeout_count:
            raise perform_runtime.subprocess.TimeoutExpired("codex", 0 if timeout is None else timeout)
        return self.returncode

    def terminate(self):
        """Record graceful termination."""
        self.terminated = True

    def kill(self):
        """Record forced termination."""
        self.killed = True


def local_arguments(*arguments):
    """Return launcher arguments that explicitly use the checkout plugin."""
    return ["--plugin-root", str(PLUGIN_ROOT), *arguments]


def installed_payload(enabled=True, version="1.2.3"):
    """Return one valid installed-toolkit discovery payload."""
    return {
        "installed": [
            {
                "name": perform_runtime.PLUGIN_NAME,
                "marketplaceName": perform_runtime.MARKETPLACE_NAME,
                "version": version,
                "installed": True,
                "enabled": enabled,
            }
        ]
    }


@pytest.mark.parametrize(("returncode", "expected_status"), [(0, 0), (7, 7), (-15, 143)])
def test_supervised_process_normalizes_status_and_encodes_invocation(returncode, expected_status):
    observed = {}

    class SupervisedProcess:
        def wait(self, timeout=None):
            assert timeout is None
            return returncode

    def popen(argv, **kwargs):
        observed["argv"] = argv
        observed["kwargs"] = kwargs
        return SupervisedProcess()

    stderr = io.BytesIO()
    status = perform_runtime.run_supervised_process(("codex", "path\udc80"), {"VALUE": "\u03bb"}, stderr, popen_factory=popen)
    assert status == expected_status
    assert observed["argv"] == [b"codex", b"path\x80"]
    assert observed["kwargs"] == {"env": {b"VALUE": "\u03bb".encode("utf-8")}, "stderr": stderr, "start_new_session": True}


def test_supervised_process_interrupt_returns_shell_status(monkeypatch):
    stopped = []

    class SupervisedProcess:
        def wait(self, timeout=None):
            assert timeout is None
            raise KeyboardInterrupt

    process = SupervisedProcess()

    def stop_process_tree(observed_process, graceful_signal=None):
        assert observed_process is process
        stopped.append(graceful_signal)

    monkeypatch.setattr(perform_runtime, "_stop_process_tree", stop_process_tree)
    assert perform_runtime.run_supervised_process(("codex",), {}, io.BytesIO(), popen_factory=lambda *_args, **_kwargs: process) == 130
    assert stopped == [signal.SIGINT]


@pytest.mark.parametrize("signal_number", [signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT])
def test_supervised_process_forwards_signals_during_ignored_cleanup(monkeypatch, signal_number):
    handled_signals = [signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT]
    original_handlers = {number: object() for number in handled_signals}
    current_handlers = dict(original_handlers)
    stopped = []

    def fake_signal(number, handler):
        previous = current_handlers[number]
        current_handlers[number] = handler
        return previous

    class SupervisedProcess:
        def wait(self, timeout=None):
            assert timeout is None
            handler = current_handlers[signal_number]
            assert callable(handler)
            typing.cast(typing.Callable[[int, object], object], handler)(signal_number, None)
            raise AssertionError("the forwarded signal must interrupt the wait")

    process = SupervisedProcess()

    def stop_process_tree(observed_process, graceful_signal=None):
        assert observed_process is process
        assert all(current_handlers[number] == signal.SIG_IGN for number in handled_signals)
        stopped.append(graceful_signal)

    monkeypatch.setattr(perform_runtime.signal, "getsignal", lambda number: current_handlers[number])
    monkeypatch.setattr(perform_runtime.signal, "signal", fake_signal)
    monkeypatch.setattr(perform_runtime, "_stop_process_tree", stop_process_tree)
    assert perform_runtime.run_supervised_process(("codex",), {}, io.BytesIO(), popen_factory=lambda *_args, **_kwargs: process) == 128 + signal_number
    assert stopped == [signal_number]
    assert current_handlers == original_handlers


def test_supervised_process_termination_cleans_real_descendants(tmp_path):
    pid_file = tmp_path / "supervised-pids"
    grandchild_code = "import time; time.sleep(60)"
    child_code = "import os, subprocess, sys, time\ngrandchild = subprocess.Popen([sys.executable, '-c', {!r}])\nwith open({!r}, 'w') as stream:\n stream.write('{{}} {{}}'.format(os.getpid(), grandchild.pid))\ntime.sleep(60)".format(
        grandchild_code, str(pid_file)
    )
    supervisor_code = "import os, sys\nfrom la_dev_codex_plugins.cli import _perform_runtime as runtime\nraise SystemExit(runtime.run_supervised_process((sys.executable, '-c', {!r}), os.environ, sys.stderr.buffer))".format(
        child_code
    )
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(REPOSITORY_ROOT / "src")
    supervisor = subprocess.Popen([sys.executable, "-c", supervisor_code], cwd=str(REPOSITORY_ROOT), env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    supervised_pids = []
    try:
        deadline = time.monotonic() + 5
        pid_values = []
        while len(pid_values) != 2 and supervisor.poll() is None and time.monotonic() < deadline:
            if pid_file.is_file():
                pid_values = pid_file.read_text(encoding="ascii").split()
            time.sleep(0.01)
        assert len(pid_values) == 2
        supervised_pids = [int(value) for value in pid_values]
        os.kill(supervisor.pid, signal.SIGTERM)
        stdout, stderr = supervisor.communicate(timeout=5)
        assert supervisor.returncode == 143
        assert stdout == b""
        assert stderr == b""

        def process_is_running(pid):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return False
            stat = Path("/proc") / str(pid) / "stat"
            return not (stat.is_file() and stat.read_text(encoding="ascii").split()[2] == "Z")

        deadline = time.monotonic() + 3
        while any(process_is_running(pid) for pid in supervised_pids) and time.monotonic() < deadline:
            time.sleep(0.01)
        assert not any(process_is_running(pid) for pid in supervised_pids)
    finally:
        if supervisor.poll() is None:
            supervisor.kill()
            supervisor.communicate()
        for pid in supervised_pids:
            with contextlib.suppress(ProcessLookupError):
                os.kill(pid, signal.SIGKILL)


@pytest.mark.parametrize("payload", [b'{"installed":[]}\n', b'{\n  "installed": []\n}\n'])
def test_decode_codex_json_requires_exact_json(payload):
    assert perform_runtime.decode_codex_json(payload) == {"installed": []}


@pytest.mark.parametrize("payload", [b'WARNING: setup failed\n{"installed":[]}\n', b'{"installed":[]}\ntrailing\n', b"not JSON"])
def test_decode_codex_json_rejects_contaminated_or_invalid_output(payload):
    with pytest.raises(perform_runtime.CliError) as raised:
        perform_runtime.decode_codex_json(payload)
    assert raised.value.code == "plugin_discovery_failed"


def test_resolve_directory_distinguishes_invalid_and_unavailable_paths(monkeypatch, tmp_path):
    missing = tmp_path / "missing"
    with pytest.raises(perform_runtime.CliError) as missing_error:
        perform_runtime.resolve_directory(missing)
    assert missing_error.value.code == "invalid_directory"
    assert missing_error.value.exit_code == 2

    regular_file = tmp_path / "file"
    regular_file.write_text("", encoding="ascii")
    with pytest.raises(perform_runtime.CliError) as file_error:
        perform_runtime.resolve_directory(regular_file)
    assert file_error.value.code == "invalid_directory"
    assert file_error.value.exit_code == 2

    monkeypatch.setattr(perform_runtime.os, "access", lambda *_args: False)
    with pytest.raises(perform_runtime.CliError) as access_error:
        perform_runtime.resolve_directory(tmp_path)
    assert access_error.value.code == "directory_unavailable"
    assert access_error.value.exit_code == 4


def test_resolve_directory_reports_symlink_loops_as_unavailable(tmp_path):
    loop = tmp_path / "loop"
    loop.symlink_to(loop.name)
    with pytest.raises(perform_runtime.CliError) as raised:
        perform_runtime.resolve_directory(loop)
    assert raised.value.code == "directory_unavailable"
    assert raised.value.exit_code == 4


def test_normalize_codex_environment_anchors_relative_home_and_removes_empty(tmp_path):
    normalized = perform_runtime.normalize_codex_environment(str(tmp_path), env={"CODEX_HOME": "nested/../codex-home", "KEEP": "yes"})
    assert normalized == {"CODEX_HOME": str(tmp_path / "codex-home"), "KEEP": "yes"}
    assert perform_runtime.normalize_codex_environment(str(tmp_path), env={"CODEX_HOME": "", "KEEP": "yes"}) == {"KEEP": "yes"}


def test_normalize_codex_environment_expands_only_mapped_home(tmp_path, monkeypatch):
    ambient = tmp_path / "ambient"
    mapped = tmp_path / "mapped"
    monkeypatch.setenv("HOME", str(ambient))
    normalized = perform_runtime.normalize_codex_environment(str(tmp_path), env={"HOME": str(mapped), "CODEX_HOME": "~/codex"})
    assert normalized["CODEX_HOME"] == str(mapped / "codex")
    with pytest.raises(perform_runtime.CliError) as raised:
        perform_runtime.normalize_codex_environment(str(tmp_path), env={"CODEX_HOME": "~/codex"})
    assert raised.value.code == "directory_unavailable"


@pytest.mark.parametrize(
    ("mode", "expected_code"),
    [
        ("import_error", "runtime_import_failed"),
        ("api_mismatch", "runtime_api_incompatible"),
    ],
)
def test_import_runtime_restores_state_and_removes_partial_modules(monkeypatch, tmp_path, mode, expected_code):
    package = tmp_path / "toolkit_perform_runtime"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="ascii")
    partial_name = "toolkit_perform_runtime.transaction_test"
    original_path = list(sys.path)
    monkeypatch.delitem(sys.modules, "toolkit_perform_runtime", raising=False)
    monkeypatch.delitem(sys.modules, partial_name, raising=False)

    def fake_import(_name):
        sys.path.append("/import-side-effect")
        sys.modules[partial_name] = types.ModuleType(partial_name)
        if mode == "import_error":
            raise RuntimeError("broken import")
        return types.SimpleNamespace(LAUNCHER_API_VERSION=999)

    monkeypatch.setattr(perform_runtime.importlib, "import_module", fake_import)
    with pytest.raises(perform_runtime.CliError) as raised:
        perform_runtime.import_runtime(str(tmp_path))
    assert raised.value.code == expected_code
    assert sys.path == original_path
    assert partial_name not in sys.modules


def test_import_runtime_restores_path_after_success(monkeypatch, tmp_path):
    package = tmp_path / "toolkit_perform_runtime"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="ascii")
    partial_name = "toolkit_perform_runtime.success_test"
    original_path = list(sys.path)
    package_runtime = types.SimpleNamespace(LAUNCHER_API_VERSION=perform_runtime.LAUNCHER_API_VERSION)
    launcher_api = types.SimpleNamespace()
    monkeypatch.delitem(sys.modules, "toolkit_perform_runtime", raising=False)
    monkeypatch.delitem(sys.modules, partial_name, raising=False)

    def fake_import(name):
        sys.path.append("/import-side-effect")
        sys.modules[partial_name] = types.ModuleType(partial_name)
        return package_runtime if name == "toolkit_perform_runtime" else launcher_api

    monkeypatch.setattr(perform_runtime.importlib, "import_module", fake_import)
    try:
        assert perform_runtime.import_runtime(str(tmp_path)) is launcher_api
        assert sys.path == original_path
        assert partial_name in sys.modules
    finally:
        sys.modules.pop(partial_name, None)


def test_runtime_api_validator_rejects_incompatible_preloaded_runtime():
    with pytest.raises(perform_runtime.CliError) as raised:
        perform_runtime._validate_runtime_api(types.SimpleNamespace(LAUNCHER_API_VERSION=999))
    assert raised.value.code == "runtime_api_incompatible"


def test_runtime_package_root_import_is_lightweight():
    scripts = PLUGIN_ROOT / "skills" / "perform" / "scripts"
    code = (
        "import json, sys\n"
        "sys.path.insert(0, {!r})\n"
        "import toolkit_perform_runtime\n"
        "print(json.dumps(sorted(name for name in sys.modules if name == 'toolkit_perform_runtime' or name.startswith('toolkit_perform_runtime.'))))\n"
    ).format(str(scripts))

    completed = subprocess.run([sys.executable, "-I", "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, check=True)

    assert json.loads(completed.stdout) == ["toolkit_perform_runtime", "toolkit_perform_runtime._launcher_version"]


def test_launcher_api_exports_only_the_versioned_contract():
    scripts = PLUGIN_ROOT / "skills" / "perform" / "scripts"
    runtime_package = importlib.import_module("toolkit_perform_runtime")
    launcher_api = perform_runtime.import_runtime(str(scripts))

    assert runtime_package.__all__ == ("LAUNCHER_API_VERSION",)
    assert launcher_api.__all__ == (
        "LAUNCHER_API_VERSION",
        "ActionLaunchConfig",
        "ActionLaunchSpec",
        "CodexInvocation",
        "LaunchOverrides",
        "PerformRequestError",
        "StandaloneLauncher",
        "build_codex_invocation",
        "load_standalone_launcher",
    )


@pytest.mark.parametrize("manifest", [[], None, "toolkit"])
def test_validate_plugin_root_rejects_non_object_manifest(tmp_path, manifest):
    manifest_directory = tmp_path / ".codex-plugin"
    manifest_directory.mkdir()
    (manifest_directory / "plugin.json").write_text(json.dumps(manifest), encoding="ascii")
    with pytest.raises(perform_runtime.CliError) as raised:
        perform_runtime.validate_plugin_root(tmp_path)
    assert raised.value.code == "plugin_layout_invalid"


def test_discover_plugin_root_uses_bounded_exact_environment(monkeypatch, tmp_path):
    codex_home = tmp_path / "codex-home"
    plugin_root = codex_home / "plugins" / "cache" / perform_runtime.MARKETPLACE_NAME / perform_runtime.PLUGIN_NAME / "1.2.3"
    process = FakeProcess(stdout=json.dumps(installed_payload()).encode("utf-8"))
    observed = {}

    def popen(command, **kwargs):
        observed["command"] = command
        observed["kwargs"] = kwargs
        return process

    def fake_validate(path, expected_version=None):
        observed["path"] = Path(path)
        observed["version"] = expected_version
        return "root", "scripts"

    environment = {"CODEX_HOME": str(codex_home), "HOME": str(tmp_path / "home"), "PATH": "/bin"}
    monkeypatch.setattr(perform_runtime, "validate_plugin_root", fake_validate)
    assert perform_runtime.discover_plugin_root("my-codex", "/work", env=environment, popen_factory=popen) == ("root", "scripts")
    assert observed["command"] == ["my-codex", "plugin", "list", "--marketplace", perform_runtime.MARKETPLACE_NAME, "--json"]
    assert observed["kwargs"]["cwd"] == "/work"
    assert observed["kwargs"]["env"] == environment
    assert observed["kwargs"]["shell"] is False
    assert observed["path"] == plugin_root
    assert observed["version"] == "1.2.3"


@pytest.mark.parametrize("version", ["1.2.3-alpha.1", "1.2.3+build.7", "1.2.3-alpha+build"])
def test_discover_plugin_root_accepts_full_semver(monkeypatch, tmp_path, version):
    codex_home = tmp_path / "codex-home"
    process = FakeProcess(stdout=json.dumps(installed_payload(version=version)).encode("utf-8"))
    observed = {}

    def fake_validate(path, expected_version=None):
        observed["path"] = Path(path)
        observed["version"] = expected_version
        return "root", "scripts"

    monkeypatch.setattr(perform_runtime, "validate_plugin_root", fake_validate)
    environment = {"CODEX_HOME": str(codex_home), "HOME": str(tmp_path / "home")}
    assert perform_runtime.discover_plugin_root("codex", str(tmp_path), env=environment, popen_factory=lambda *_args, **_kwargs: process) == ("root", "scripts")
    assert observed["path"] == codex_home / "plugins" / "cache" / perform_runtime.MARKETPLACE_NAME / perform_runtime.PLUGIN_NAME / version
    assert observed["version"] == version


@pytest.mark.parametrize("version", ["/tmp/fake-plugin", "../fake-plugin", "1.2", "01.2.3", "1.2.3/../../fake-plugin", ""])
def test_discover_plugin_root_rejects_non_semver_versions(monkeypatch, tmp_path, version):
    process = FakeProcess(stdout=json.dumps(installed_payload(version=version)).encode("utf-8"))

    def unexpected_validation(*_args, **_kwargs):
        raise AssertionError("invalid versions must fail before layout validation")

    monkeypatch.setattr(perform_runtime, "validate_plugin_root", unexpected_validation)
    with pytest.raises(perform_runtime.CliError, match="SemVer") as raised:
        perform_runtime.discover_plugin_root("codex", str(tmp_path), env={"HOME": str(tmp_path)}, popen_factory=lambda *_args, **_kwargs: process)
    assert raised.value.code == "plugin_discovery_failed"


def test_discover_plugin_root_rejects_symlink_escape(monkeypatch, tmp_path):
    codex_home = tmp_path / "codex-home"
    cache_root = codex_home / "plugins" / "cache" / perform_runtime.MARKETPLACE_NAME / perform_runtime.PLUGIN_NAME
    cache_root.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (cache_root / "1.2.3").symlink_to(outside, target_is_directory=True)
    except OSError:
        return
    process = FakeProcess(stdout=json.dumps(installed_payload()).encode("utf-8"))

    def unexpected_validation(*_args, **_kwargs):
        raise AssertionError("escaped caches must fail before layout validation")

    monkeypatch.setattr(perform_runtime, "validate_plugin_root", unexpected_validation)
    with pytest.raises(perform_runtime.CliError, match="outside") as raised:
        perform_runtime.discover_plugin_root("codex", str(tmp_path), env={"CODEX_HOME": str(codex_home)}, popen_factory=lambda *_args, **_kwargs: process)
    assert raised.value.code == "plugin_discovery_failed"


def test_discover_plugin_root_rejects_disabled_plugin(tmp_path):
    process = FakeProcess(stdout=json.dumps(installed_payload(enabled=False)).encode("utf-8"))
    with pytest.raises(perform_runtime.CliError, match="disabled") as raised:
        perform_runtime.discover_plugin_root("codex", str(tmp_path), env={"HOME": str(tmp_path)}, popen_factory=lambda *_args, **_kwargs: process)
    assert raised.value.code == "plugin_disabled"


def test_discover_plugin_root_requires_mapped_home(tmp_path):
    process = FakeProcess(stdout=json.dumps(installed_payload()).encode("utf-8"))
    with pytest.raises(perform_runtime.CliError, match="HOME") as raised:
        perform_runtime.discover_plugin_root("codex", str(tmp_path), env={}, popen_factory=lambda *_args, **_kwargs: process)
    assert raised.value.code == "plugin_discovery_failed"


def test_plugin_discovery_reports_launch_failure(tmp_path):
    def fail_launch(*_args, **_kwargs):
        raise OSError("missing")

    with pytest.raises(perform_runtime.CliError, match="missing") as raised:
        perform_runtime.discover_plugin_root("codex", str(tmp_path), env={"HOME": str(tmp_path)}, popen_factory=fail_launch)
    assert raised.value.code == "plugin_discovery_failed"


@pytest.mark.parametrize(("stream", "payload"), [("stdout", b"x"), ("stderr", b"y")])
def test_plugin_discovery_rejects_oversized_streams(tmp_path, stream, payload):
    kwargs = {stream: payload * (perform_runtime.PLUGIN_DISCOVERY_OUTPUT_LIMIT + 1)}
    process = FakeProcess(**kwargs)
    with pytest.raises(perform_runtime.CliError, match="1048576 bytes") as raised:
        perform_runtime.discover_plugin_root("codex", str(tmp_path), env={"HOME": str(tmp_path)}, popen_factory=lambda *_args, **_kwargs: process)
    assert raised.value.code == "plugin_discovery_failed"


def test_relative_codex_executable_is_resolved_once_from_shell_directory(monkeypatch, tmp_path, capsys):
    shell_directory = tmp_path / "shell"
    launch_directory = tmp_path / "project"
    shell_directory.mkdir()
    launch_directory.mkdir()
    wrapper = shell_directory / "codex-wrapper"
    wrapper.write_text("#!/bin/sh\nexit 0\n", encoding="ascii")
    wrapper.chmod(0o755)
    monkeypatch.chdir(shell_directory)

    arguments = local_arguments("--codex", "./codex-wrapper", "--cwd", str(launch_directory), "ensure-ascii-only", "--dry-run", "--json")
    assert perform.main(arguments) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["argv"][0] == str(wrapper.resolve())
    assert payload["effective_settings"]["cwd"] == str(launch_directory)


def test_bare_codex_executable_is_resolved_from_mapped_path(monkeypatch, tmp_path):
    executable = tmp_path / "custom-codex"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="ascii")
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", "/missing")
    environment = {"PATH": str(tmp_path)}
    assert perform_runtime.resolve_codex_executable("custom-codex", str(tmp_path), env=environment) == str(executable.resolve())


def test_bare_codex_executable_preserves_path_symlink(monkeypatch, tmp_path):
    target = tmp_path / "codex-target"
    target.write_text("#!/bin/sh\nexit 0\n", encoding="ascii")
    target.chmod(0o755)
    executable = tmp_path / "custom-codex"
    executable.symlink_to(target.name)
    monkeypatch.setenv("PATH", "/missing")
    environment = {"PATH": str(tmp_path)}
    assert perform_runtime.resolve_codex_executable("custom-codex", str(tmp_path), env=environment) == str(executable)


def test_posix_process_replacement_encodes_unicode_and_surrogateescape(monkeypatch):
    observed = {}

    def fake_exec(executable, argv, environment):
        observed["executable"] = executable
        observed["argv"] = argv
        observed["environment"] = environment
        raise ExecCalled(executable, argv, environment)

    monkeypatch.setattr(perform_runtime.os, "execve", fake_exec)
    arguments = ("/tmp/codex", "\u03bb", "path\udc80")
    with pytest.raises(ExecCalled):
        perform_runtime.replace_process(arguments, env={"CODEX_HOME": "/tmp/home", "VALUE": "\u03bb"})
    assert observed["executable"] == b"/tmp/codex"
    assert observed["argv"] == [b"/tmp/codex", "\u03bb".encode("utf-8"), b"path\x80"]
    assert observed["environment"] == {b"CODEX_HOME": b"/tmp/home", b"VALUE": "\u03bb".encode("utf-8")}
