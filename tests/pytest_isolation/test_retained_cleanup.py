"""Pytest-retained isolation lifecycle and compatibility tests."""

import pathlib
import tempfile

import pytest

RETAINED_CONFIG = """[pytest]
la_dev_cwd_isolation_cleanup = pytest_retained
tmp_path_retention_policy = all
tmp_path_retention_count = 3
"""


@pytest.mark.parametrize("value", ["", "unknown", "PYTEST_RETAINED", " pytest_retained", "pytest_retained "])
def test_invalid_cleanup_mode_fails_before_execution_or_allocation(run_isolation, value):
    result = run_isolation(
        """
def test_must_not_run():
    raise AssertionError("invalid cleanup mode reached test execution")
""",
        "-o",
        "la_dev_cwd_isolation_cleanup={}".format(value),
        conftest="""
import la_dev_codex_plugins.pytest_isolation.plugin as isolation_plugin

def forbidden_create_boundary(*args, **kwargs):
    raise AssertionError("invalid cleanup mode allocated a boundary")

isolation_plugin._create_boundary = forbidden_create_boundary
""",
    )
    assert result.ret != 0
    output = result.stdout.str() + result.stderr.str()
    assert "la_dev_cwd_isolation_cleanup" in output
    assert repr(value) in output
    assert "eager" in output
    assert "pytest_retained" in output
    assert "invalid cleanup mode reached test execution" not in output
    assert "invalid cleanup mode allocated a boundary" not in output


@pytest.mark.parametrize(
    ("settings", "conflict"),
    [
        ("tmp_path_retention_policy = failed\ntmp_path_retention_count = 3", "tmp_path_retention_policy"),
        ("tmp_path_retention_policy = none\ntmp_path_retention_count = 3", "tmp_path_retention_policy"),
        ("tmp_path_retention_policy = all\ntmp_path_retention_count = 0", "tmp_path_retention_count"),
    ],
)
def test_incompatible_retention_fails_before_execution_or_allocation(run_isolation_without_basetemp, pytestconfig, settings, conflict):
    try:
        pytestconfig.getini("tmp_path_retention_policy")
        pytestconfig.getini("tmp_path_retention_count")
    except ValueError:
        raise pytest.skip.Exception("pytest does not expose configurable temporary-path retention") from None
    result = run_isolation_without_basetemp(
        """
def test_must_not_run(isolated_cwd):
    raise AssertionError("unsafe retention reached test execution")
""",
        config="[pytest]\nla_dev_cwd_isolation_cleanup = pytest_retained\n{}\n".format(settings),
    )
    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert "la_dev_cwd_isolation_cleanup" in output
    assert conflict in output
    assert "outlives the session" in output
    assert "unsafe retention reached test execution" not in output


def test_retained_uses_fixed_or_configured_numbered_retention_without_basetemp(run_isolation_without_basetemp, monkeypatch, tmp_path, remove_preserved_boundary):
    record = tmp_path / "numbered-retained.txt"
    monkeypatch.setenv("RETAINED_RECORD", str(record))
    result = run_isolation_without_basetemp(
        """
import os
import pathlib

def test_retained(isolated_cwd):
    pathlib.Path(os.environ["RETAINED_RECORD"]).write_text(str(isolated_cwd.parent), encoding="ascii")
""",
        config="[pytest]\nla_dev_cwd_isolation_cleanup = pytest_retained\n",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    boundary = pathlib.Path(record.read_text(encoding="ascii"))
    assert boundary.is_dir()
    remove_preserved_boundary(boundary)


def test_explicit_basetemp_allows_other_retention_settings(run_isolation, tmp_path, remove_preserved_boundary):
    base_temp = tmp_path / "explicit-compatible-base"
    result = run_isolation(
        """
def test_retained(isolated_cwd):
    assert isolated_cwd.parent.parent.name == "explicit-compatible-base"
""",
        "--basetemp={}".format(base_temp),
        config="""[pytest]
la_dev_cwd_isolation_cleanup = pytest_retained
tmp_path_retention_policy = none
tmp_path_retention_count = 0
""",
    )
    result.assert_outcomes(passed=1)
    boundaries = list(base_temp.glob("la-dev-pytest-isolation-*"))
    assert len(boundaries) == 1
    remove_preserved_boundary(boundaries[0])


@pytest.mark.parametrize("configured", [False, True])
def test_default_and_explicit_eager_cleanup_are_equivalent(run_isolation, monkeypatch, tmp_path, configured):
    record = tmp_path / ("explicit-eager.txt" if configured else "default-eager.txt")
    monkeypatch.setenv("EAGER_RECORD", str(record))
    config = "[pytest]\nla_dev_cwd_isolation_cleanup = eager\n" if configured else None
    result = run_isolation(
        """
import os
import pathlib

def test_eager(isolated_cwd):
    pathlib.Path(os.environ["EAGER_RECORD"]).write_text(str(isolated_cwd.parent), encoding="ascii")
""",
        config=config,
    )
    result.assert_outcomes(passed=1)
    boundary = pathlib.Path(record.read_text(encoding="ascii"))
    assert not boundary.exists()


def test_standalone_private_retained_boundary_uses_base_temp_and_restores_state(run_isolation, monkeypatch, tmp_path, remove_preserved_boundary):
    record = tmp_path / "standalone-retained.txt"
    restored = tmp_path / "standalone-restored.txt"
    base_temp = tmp_path / "standalone-base"
    monkeypatch.setenv("RETAINED_RECORD", str(record))
    monkeypatch.setenv("RESTORED_RECORD", str(restored))
    result = run_isolation(
        """
import os
import pathlib

def test_retained(isolated_cwd):
    boundary = isolated_cwd.parent
    pathlib.Path(os.environ["RETAINED_RECORD"]).write_text(str(boundary), encoding="ascii")
    (boundary / "tmp" / "artifact.txt").write_text("retained", encoding="ascii")
""",
        "--basetemp={}".format(base_temp),
        config=RETAINED_CONFIG,
        conftest="""
import os
import pathlib
import tempfile

INITIAL_CWD = os.getcwd()
INITIAL_ENVIRONMENT = {name: (name in os.environ, os.environ.get(name)) for name in ("TMPDIR", "TEMP", "TMP")}
INITIAL_TEMPDIR = tempfile.tempdir

def pytest_unconfigure(config):
    assert os.getcwd() == INITIAL_CWD
    assert {name: (name in os.environ, os.environ.get(name)) for name in INITIAL_ENVIRONMENT} == INITIAL_ENVIRONMENT
    assert tempfile.tempdir is INITIAL_TEMPDIR
    pathlib.Path(os.environ["RESTORED_RECORD"]).write_text("restored", encoding="ascii")
""",
    )
    result.assert_outcomes(passed=1)
    boundary = pathlib.Path(record.read_text(encoding="ascii"))
    assert boundary.parent == base_temp
    assert (boundary / "tmp" / "artifact.txt").read_text(encoding="ascii") == "retained"
    assert restored.read_text(encoding="ascii") == "restored"
    remove_preserved_boundary(boundary)


def test_retained_shared_and_nested_private_boundaries_survive_without_cleanup_error(run_isolation, monkeypatch, tmp_path, remove_preserved_boundary):
    record = tmp_path / "shared-retained.txt"
    base_temp = tmp_path / "shared-base"
    monkeypatch.setenv("RETAINED_RECORD", str(record))
    result = run_isolation(
        """
import os
import pathlib

SHARED = None

def test_01_shared_boundary_is_reused():
    global SHARED
    SHARED = pathlib.Path.cwd().parent
    pathlib.Path(os.environ["RETAINED_RECORD"]).write_text(str(SHARED) + "\\n", encoding="ascii")

def test_02_same_shared_boundary():
    assert pathlib.Path.cwd().parent == SHARED

def test_03_nested_private(isolated_cwd):
    private = isolated_cwd.parent
    assert private.parent == SHARED / "tmp"
    with pathlib.Path(os.environ["RETAINED_RECORD"]).open("a", encoding="ascii") as handle:
        handle.write(str(private) + "\\n")
""",
        "--basetemp={}".format(base_temp),
        config=RETAINED_CONFIG + "la_dev_cwd_isolation_unmarked = shared_guarded\n",
    )
    result.assert_outcomes(passed=3)
    output = result.stdout.str() + result.stderr.str()
    assert "incomplete" not in output
    shared, private = (pathlib.Path(value) for value in record.read_text(encoding="ascii").splitlines())
    assert shared.parent == base_temp
    assert shared.is_dir()
    assert private.is_dir()
    remove_preserved_boundary(shared)


def test_retained_identity_replacement_fails_and_preserves_tree(run_isolation, monkeypatch, tmp_path, remove_preserved_boundary):
    record = tmp_path / "replaced-retained.txt"
    base_temp = tmp_path / "replaced-base"
    monkeypatch.setenv("RETAINED_RECORD", str(record))
    result = run_isolation(
        """
import os
import pathlib

def test_replace_cwd(isolated_cwd):
    boundary = isolated_cwd.parent
    original = boundary / "original-cwd"
    os.chdir(str(boundary))
    isolated_cwd.rename(original)
    isolated_cwd.mkdir()
    (isolated_cwd / "replacement.txt").write_text("keep", encoding="ascii")
    pathlib.Path(os.environ["RETAINED_RECORD"]).write_text(str(boundary), encoding="ascii")
""",
        "--basetemp={}".format(base_temp),
        config=RETAINED_CONFIG,
    )
    assert result.ret == 1
    output = result.stdout.str() + result.stderr.str()
    assert "working directory changed identity" in output
    boundary = pathlib.Path(record.read_text(encoding="ascii"))
    assert (boundary / "cwd" / "replacement.txt").read_text(encoding="ascii") == "keep"
    assert (boundary / "original-cwd").is_dir()
    remove_preserved_boundary(boundary)


def test_retained_private_mode_corruption_fails_and_preserves_tree(run_isolation, monkeypatch, tmp_path, remove_preserved_boundary):
    record = tmp_path / "mode-retained.txt"
    base_temp = tmp_path / "mode-base"
    monkeypatch.setenv("RETAINED_RECORD", str(record))
    result = run_isolation(
        """
import os
import pathlib

def test_change_mode(isolated_cwd):
    isolated_cwd.chmod(0o755)
    pathlib.Path(os.environ["RETAINED_RECORD"]).write_text(str(isolated_cwd.parent), encoding="ascii")
""",
        "--basetemp={}".format(base_temp),
        config=RETAINED_CONFIG,
    )
    assert result.ret == 1
    output = result.stdout.str() + result.stderr.str()
    assert "recorded isolation entry has mode 0755 instead of 0700" in output
    boundary = pathlib.Path(record.read_text(encoding="ascii"))
    assert boundary.is_dir()
    remove_preserved_boundary(boundary)


def test_retained_shared_policy_corruption_fails_and_preserves_tree(run_isolation, monkeypatch, tmp_path, remove_preserved_boundary):
    record = tmp_path / "policy-retained.txt"
    base_temp = tmp_path / "policy-base"
    monkeypatch.setenv("RETAINED_RECORD", str(record))
    result = run_isolation(
        """
import os
import pathlib

def test_corrupt_policy():
    cwd = pathlib.Path.cwd()
    policy = cwd / "config" / "guard.ini"
    policy.chmod(0o600)
    policy.write_text("mutated", encoding="ascii")
    policy.chmod(0o400)
    pathlib.Path(os.environ["RETAINED_RECORD"]).write_text(str(cwd.parent), encoding="ascii")
""",
        "--basetemp={}".format(base_temp),
        config=RETAINED_CONFIG + "la_dev_cwd_isolation_unmarked = shared_guarded\n",
        conftest="""
def pytest_la_dev_cwd_isolation_shared_policy(config):
    return {
        "boundary_files": {"anchor.txt": "anchor"},
        "poison_files": {"config/guard.ini": "guard"},
    }
""",
    )
    assert result.ret == 1
    output = result.stdout.str() + result.stderr.str()
    assert "shared policy file contents changed" in output
    boundary = pathlib.Path(record.read_text(encoding="ascii"))
    assert (boundary / "cwd" / "config" / "guard.ini").read_text(encoding="ascii") == "mutated"
    assert (boundary / "anchor.txt").read_text(encoding="ascii") == "anchor"
    remove_preserved_boundary(boundary)


def test_reusing_explicit_base_temp_prunes_prior_retained_boundary(run_isolation, monkeypatch, tmp_path):
    record = tmp_path / "prior-retained.txt"
    base_temp = tmp_path / "reused-base"
    monkeypatch.setenv("RETAINED_RECORD", str(record))
    first = run_isolation(
        """
import os
import pathlib

def test_first(isolated_cwd):
    pathlib.Path(os.environ["RETAINED_RECORD"]).write_text(str(isolated_cwd.parent), encoding="ascii")
""",
        "--basetemp={}".format(base_temp),
        config=RETAINED_CONFIG,
    )
    first.assert_outcomes(passed=1)
    prior = pathlib.Path(record.read_text(encoding="ascii"))
    assert prior.is_dir()
    second = run_isolation(
        """
import os
import pathlib

def test_second(tmp_path):
    prior = pathlib.Path(os.environ["RETAINED_RECORD"]).read_text(encoding="ascii")
    assert not pathlib.Path(prior).exists()
    assert tmp_path.exists()
""",
        "--basetemp={}".format(base_temp),
        config=RETAINED_CONFIG,
    )
    second.assert_outcomes(passed=1)


def test_process_pool_executor_completes_with_retained_cleanup(run_isolation, monkeypatch, tmp_path, remove_preserved_boundary):
    record = tmp_path / "forkserver-retained.txt"
    monkeypatch.setenv("RETAINED_RECORD", str(record))
    with tempfile.TemporaryDirectory(prefix="la-dev-pytest-forkserver-") as temporary_directory:
        base_temp = pathlib.Path(temporary_directory)
        result = run_isolation(
            """
import concurrent.futures
import multiprocessing
import os
import pathlib

def square(value):
    return value * value

def test_executor(isolated_cwd):
    pathlib.Path(os.environ["RETAINED_RECORD"]).write_text(str(isolated_cwd.parent), encoding="ascii")
    context = multiprocessing.get_context("forkserver")
    with concurrent.futures.ProcessPoolExecutor(max_workers=1, mp_context=context) as executor:
        assert executor.submit(square, 7).result() == 49
""",
            "--basetemp={}".format(base_temp),
            config=RETAINED_CONFIG,
        )
        result.assert_outcomes(passed=1)
        output = result.stdout.str() + result.stderr.str()
        for unexpected in ("FileNotFoundError", "resource_tracker", "Exception ignored in atexit callback", "finalizer_registry", "_forkserver"):
            assert unexpected not in output
        boundary = pathlib.Path(record.read_text(encoding="ascii"))
        assert boundary.is_dir()
        remove_preserved_boundary(boundary)
