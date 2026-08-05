"""Shared guarded lifecycle, restoration, and corruption tests."""

import pathlib

import pytest

SHARED_CONFIG = """[pytest]
la_dev_cwd_isolation_unmarked = shared_guarded
"""


def test_downstream_session_module_and_function_fixtures_are_contained(run_isolation, monkeypatch, tmp_path):
    record = tmp_path / "fixture-cwds.txt"
    monkeypatch.setenv("FIXTURE_CWD_RECORD", str(record))
    result = run_isolation(
        """
import os
import pathlib
import pytest

RECORD = pathlib.Path(os.environ["FIXTURE_CWD_RECORD"])

def _record(label):
    with RECORD.open("a", encoding="ascii") as handle:
        handle.write("{}={}\\n".format(label, pathlib.Path.cwd()))

@pytest.fixture(scope="session", autouse=True)
def session_fixture():
    _record("session-setup")
    yield
    _record("session-final")

@pytest.fixture(scope="module", autouse=True)
def module_fixture():
    _record("module-setup")
    yield
    _record("module-final")

@pytest.fixture(autouse=True)
def function_fixture():
    _record("function-setup")
    yield
    _record("function-final")

def test_body():
    _record("test")
""",
        config=SHARED_CONFIG,
    )
    result.assert_outcomes(passed=1)
    entries = [line.split("=", 1) for line in record.read_text(encoding="ascii").splitlines()]
    assert [label for label, _path in entries] == ["session-setup", "module-setup", "function-setup", "test", "function-final", "module-final", "session-final"]
    assert len({path for _label, path in entries}) == 1


@pytest.mark.parametrize("shared", [False, True])
def test_private_isolation_layers_inside_broader_fixture_scopes(run_isolation, monkeypatch, tmp_path, shared):
    record = tmp_path / "layered-fixture-cwds.txt"
    monkeypatch.setenv("LAYERED_FIXTURE_RECORD", str(record))
    result = run_isolation(
        """
import os
import pathlib
import pytest

RECORD = pathlib.Path(os.environ["LAYERED_FIXTURE_RECORD"])

def _record(label):
    with RECORD.open("a", encoding="ascii") as handle:
        handle.write("{}={}\\n".format(label, pathlib.Path.cwd()))

@pytest.fixture(scope="session", autouse=True)
def session_fixture():
    root = pathlib.Path(os.environ["TMPDIR"]) if pathlib.Path.cwd().name == "cwd" else pathlib.Path.cwd()
    resource = root / "session-resource"
    resource.write_text("session", encoding="ascii")
    _record("session-setup")
    yield resource
    _record("session-final")
    assert resource.read_text(encoding="ascii") == "session"

@pytest.fixture(scope="module", autouse=True)
def module_fixture():
    root = pathlib.Path(os.environ["TMPDIR"]) if pathlib.Path.cwd().name == "cwd" else pathlib.Path.cwd()
    resource = root / "module-resource"
    resource.write_text("module", encoding="ascii")
    _record("module-setup")
    yield resource
    _record("module-final")
    assert resource.read_text(encoding="ascii") == "module"

@pytest.fixture(autouse=True)
def function_fixture():
    _record("function-setup")
    active = pathlib.Path.cwd()
    yield
    assert pathlib.Path.cwd() == active
    _record("function-final")

@pytest.mark.isolated_cwd
def test_01_private(session_fixture, module_fixture):
    _record("private-test")
    assert session_fixture.is_file()
    assert module_fixture.is_file()

def test_02_outer(session_fixture, module_fixture):
    _record("outer-test")
    assert session_fixture.is_file()
    assert module_fixture.is_file()
""",
        config=SHARED_CONFIG if shared else None,
    )
    result.assert_outcomes(passed=2)
    entries = [(label, pathlib.Path(path)) for label, path in (line.split("=", 1) for line in record.read_text(encoding="ascii").splitlines())]
    paths = {}
    for label, path in entries:
        paths.setdefault(label, []).append(path)
    broad_path = paths["session-setup"][0]
    assert paths["module-setup"] == [broad_path]
    assert paths["session-final"] == [broad_path]
    assert paths["module-final"] == [broad_path]
    assert paths["private-test"][0].name == "cwd"
    assert paths["private-test"][0] != broad_path
    assert paths["outer-test"] == [broad_path]
    assert paths["function-setup"] == [paths["private-test"][0], broad_path]
    assert paths["function-final"] == [paths["private-test"][0], broad_path]


def test_private_isolation_is_active_before_downstream_fixture_setup(run_isolation, monkeypatch, tmp_path):
    record = tmp_path / "private-fixture-cwds.txt"
    monkeypatch.setenv("PRIVATE_FIXTURE_CWD_RECORD", str(record))
    result = run_isolation(
        """
import os
import pathlib
import pytest

RECORD = pathlib.Path(os.environ["PRIVATE_FIXTURE_CWD_RECORD"])

@pytest.fixture(autouse=True)
def downstream_fixture():
    with RECORD.open("a", encoding="ascii") as handle:
        handle.write("setup={}\\n".format(pathlib.Path.cwd()))
    yield
    with RECORD.open("a", encoding="ascii") as handle:
        handle.write("final={}\\n".format(pathlib.Path.cwd()))

@pytest.mark.isolated_cwd
def test_private(isolated_cwd):
    with RECORD.open("a", encoding="ascii") as handle:
        handle.write("test={}\\n".format(pathlib.Path.cwd()))
    assert pathlib.Path.cwd() == isolated_cwd
""",
        config=SHARED_CONFIG,
    )
    result.assert_outcomes(passed=1)
    entries = [line.split("=", 1) for line in record.read_text(encoding="ascii").splitlines()]
    assert [label for label, _path in entries] == ["setup", "test", "final"]
    assert len({path for _label, path in entries}) == 1
    assert pathlib.Path(entries[0][1]).name == "cwd"


@pytest.mark.parametrize(("statement", "returncode"), [("pytest.exit('intentional stop', returncode=7)", 7), ("raise KeyboardInterrupt", 2)])
def test_interrupt_unwind_restores_and_cleans_without_false_escape(run_isolation, monkeypatch, tmp_path, statement, returncode):
    record = tmp_path / "interrupt-boundary.txt"
    monkeypatch.setenv("INTERRUPT_BOUNDARY_RECORD", str(record))
    result = run_isolation(
        """
import os
import pathlib
import pytest

def test_interrupt():
    pathlib.Path(os.environ["INTERRUPT_BOUNDARY_RECORD"]).write_text(str(pathlib.Path.cwd().parent), encoding="ascii")
    {statement}
""".format(statement=statement),
        config=SHARED_CONFIG,
    )
    assert result.ret == returncode
    output = "\n".join(result.stdout.lines + result.stderr.lines)
    assert "escaped its guarded working directory" not in output
    assert "Traceback (most recent call last)" not in output
    assert not pathlib.Path(record.read_text(encoding="ascii")).exists()


@pytest.mark.parametrize("child_name", ["cwd", "tmp"])
def test_preserved_private_replacement_blocks_outer_shared_cleanup(run_isolation, monkeypatch, tmp_path, remove_preserved_boundary, child_name):
    external = tmp_path / ("private-{}-replacement".format(child_name))
    external.mkdir()
    (external / "sentinel.txt").write_text("keep", encoding="ascii")
    record = tmp_path / ("preserved-private-{}.txt".format(child_name))
    monkeypatch.setenv("PRESERVED_PRIVATE_EXTERNAL", str(external))
    monkeypatch.setenv("PRESERVED_PRIVATE_RECORD", str(record))
    result = run_isolation(
        """
import os
import pathlib

def test_replace_private_child(isolated_cwd):
    private_boundary = isolated_cwd.parent
    shared_boundary = private_boundary.parent.parent
    target = private_boundary / {child_name!r}
    pathlib.Path(os.environ["PRESERVED_PRIVATE_RECORD"]).write_text("{{}}\\n{{}}\\n".format(shared_boundary, private_boundary), encoding="ascii")
    if pathlib.Path.cwd() == target:
        os.chdir(str(private_boundary))
    target.rename(private_boundary / ({child_name!r} + "-original"))
    pathlib.Path(os.environ["PRESERVED_PRIVATE_EXTERNAL"]).rename(target)
""".format(child_name=child_name),
        config=SHARED_CONFIG,
    )
    result.assert_outcomes(passed=1, errors=1)
    output = "\n".join(result.stdout.lines + result.stderr.lines)
    assert "nested private cleanup was incomplete" in output
    shared_boundary, private_boundary = (pathlib.Path(value) for value in record.read_text(encoding="ascii").splitlines())
    assert shared_boundary.is_dir()
    assert (private_boundary / child_name / "sentinel.txt").read_text(encoding="ascii") == "keep"
    assert (private_boundary / (child_name + "-original")).is_dir()
    remove_preserved_boundary(shared_boundary)


def test_shared_cleanup_restores_unreadable_temporary_descendants(run_isolation, monkeypatch, tmp_path):
    record = tmp_path / "unreadable-shared-boundary.txt"
    monkeypatch.setenv("UNREADABLE_SHARED_RECORD", str(record))
    result = run_isolation(
        """
import os
import pathlib

def test_create_unreadable_temporary_tree():
    shared_tmp = pathlib.Path(os.environ["TMPDIR"])
    pathlib.Path(os.environ["UNREADABLE_SHARED_RECORD"]).write_text(str(shared_tmp.parent), encoding="ascii")
    locked = shared_tmp / "locked"
    locked.mkdir()
    nested = locked / "nested"
    nested.mkdir()
    (nested / "sentinel.txt").write_text("remove", encoding="ascii")
    nested.chmod(0o300)
    locked.chmod(0o000)
""",
        config=SHARED_CONFIG,
    )
    result.assert_outcomes(passed=1)
    assert not pathlib.Path(record.read_text(encoding="ascii")).exists()


def test_shared_cleanup_survives_test_and_fixture_outcomes(run_isolation, monkeypatch, tmp_path):
    record = tmp_path / "failure-boundary.txt"
    monkeypatch.setenv("SHARED_FAILURE_RECORD", str(record))
    result = run_isolation(
        """
import os
import pathlib
import pytest

@pytest.fixture
def setup_failure():
    raise RuntimeError("setup failure")

@pytest.fixture
def teardown_failure():
    yield
    raise RuntimeError("teardown failure")

def _record():
    pathlib.Path(os.environ["SHARED_FAILURE_RECORD"]).write_text(str(pathlib.Path.cwd().parent), encoding="ascii")

def test_01_success():
    _record()

def test_02_assertion_failure():
    assert False

def test_03_call_failure():
    raise RuntimeError("call failure")

def test_04_skip():
    pytest.skip("skip")

def test_05_setup_failure(setup_failure):
    pass

def test_06_teardown_failure(teardown_failure):
    pass
""",
        config=SHARED_CONFIG,
    )
    result.assert_outcomes(passed=2, failed=2, skipped=1, errors=2)
    assert not pathlib.Path(record.read_text(encoding="ascii")).exists()


def test_shared_escape_fails_after_fixture_finalization_and_next_test_reenters(run_isolation):
    result = run_isolation(
        """
import os
import pathlib

SHARED = None

def test_01_escape():
    global SHARED
    SHARED = pathlib.Path.cwd()
    os.chdir(os.environ["TMPDIR"])

def test_02_reentered():
    assert pathlib.Path.cwd() == SHARED
""",
        config=SHARED_CONFIG,
    )
    result.assert_outcomes(passed=2, errors=1)
    result.stdout.fnmatch_lines(["*shared guarded test escaped its guarded working directory*"])


def test_shared_temporary_state_is_reasserted_after_fixture_finalizer_mutation(run_isolation):
    result = run_isolation(
        """
import os
import pathlib
import tempfile
import pytest

SHARED_TMP = None

@pytest.fixture
def mutate_after_test():
    yield
    for name in ("TMPDIR", "TEMP", "TMP"):
        os.environ[name] = "/fixture-finalizer-leak"
    tempfile.tempdir = "/fixture-finalizer-cache"

def test_01_mutates_process_temporary_state(mutate_after_test):
    global SHARED_TMP
    SHARED_TMP = pathlib.Path(os.environ["TMPDIR"])
    for name in ("TMPDIR", "TEMP", "TMP"):
        os.environ[name] = "/direct-leak"
    tempfile.tempdir = "/direct-cache"

def test_02_next_shared_test_starts_canonical():
    assert {os.environ[name] for name in ("TMPDIR", "TEMP", "TMP")} == {str(SHARED_TMP)}
    assert tempfile.tempdir is None
    assert pathlib.Path(tempfile.gettempdir()) == SHARED_TMP

def test_03_private_test_snapshots_canonical_shared_state(isolated_cwd):
    assert pathlib.Path(os.environ["TMPDIR"]) == isolated_cwd.parent / "tmp"

def test_04_shared_state_is_canonical_after_private_test():
    assert {os.environ[name] for name in ("TMPDIR", "TEMP", "TMP")} == {str(SHARED_TMP)}
    assert tempfile.tempdir is None
""",
        config=SHARED_CONFIG,
    )
    result.assert_outcomes(passed=4)


@pytest.mark.parametrize(
    ("action", "expected"),
    [
        ("(cwd / 'config').chmod(0o700)", "shared policy entry has mode 0700 instead of 0500"),
        ("(cwd / 'config/guard.ini').chmod(0o600)", "shared policy entry has mode 0600 instead of 0400"),
        ("(cwd / 'config/guard.ini').chmod(0o600); (cwd / 'config/guard.ini').write_text('mutated', encoding='ascii')", "shared policy file contents changed"),
        ("cwd.chmod(0o700); (cwd / 'unexpected.txt').write_text('extra', encoding='ascii'); cwd.chmod(0o500)", "shared policy contains unexpected entry"),
        ("(boundary / 'anchor.txt').chmod(0o600); (boundary / 'anchor.txt').write_text('mutated', encoding='ascii')", "shared policy file contents changed"),
        ("(boundary / 'unexpected.txt').write_text('extra', encoding='ascii')", "shared policy contains unexpected entry"),
    ],
)
def test_shared_integrity_manifest_reports_policy_corruption_at_session_cleanup(run_isolation, monkeypatch, tmp_path, action, expected):
    record = tmp_path / "integrity-boundary.txt"
    monkeypatch.setenv("SHARED_INTEGRITY_RECORD", str(record))
    result = run_isolation(
        """
import os
import pathlib

def test_01_corrupt():
    cwd = pathlib.Path.cwd()
    boundary = cwd.parent
    tmp = pathlib.Path(os.environ["TMPDIR"])
    pathlib.Path(os.environ["SHARED_INTEGRITY_RECORD"]).write_text(str(boundary), encoding="ascii")
    {action}

def test_02_policy_corruption_does_not_block_reentry():
    assert pathlib.Path.cwd().is_dir()
""".format(action=action),
        config=SHARED_CONFIG,
        conftest="""
def pytest_la_dev_cwd_isolation_shared_policy(config):
    return {
        "boundary_files": {"anchor.txt": "anchor"},
        "poison_files": {"config/guard.ini": "guard"},
    }
""",
    )
    assert result.ret == 1
    result.assert_outcomes(passed=2)
    output = "\n".join(result.stdout.lines + result.stderr.lines)
    assert "Shared guarded session teardown failed" in output
    assert expected in output
    assert not pathlib.Path(record.read_text(encoding="ascii")).exists()


@pytest.mark.parametrize(
    ("action", "expected"),
    [
        ("cwd.chmod(0o700)", "mode 0700 instead of 0500"),
        ("tmp.chmod(0o711)", "mode 0711 instead of 0700"),
    ],
)
def test_shared_root_mode_corruption_fails_immediately(run_isolation, action, expected):
    result = run_isolation(
        """
import os
import pathlib

def test_01_corrupt_root_mode():
    cwd = pathlib.Path.cwd()
    tmp = pathlib.Path(os.environ["TMPDIR"])
    {action}

def test_02_must_not_enter_corrupted_layout():
    raise AssertionError("corrupted shared layout was entered")
""".format(action=action),
        config=SHARED_CONFIG,
    )
    result.assert_outcomes(passed=1, errors=2)
    output = "\n".join(result.stdout.lines + result.stderr.lines)
    assert expected in output


def test_exact_policy_verification_stays_off_the_per_test_hot_path(run_isolation):
    result = run_isolation(
        """
import la_dev_codex_plugins.pytest_isolation.plugin as isolation_plugin

def test_01_no_policy_scan_during_setup():
    assert isolation_plugin.POLICY_VERIFICATION_CALLS == 0

def test_02_no_policy_scan_between_tests():
    assert isolation_plugin.POLICY_VERIFICATION_CALLS == 0
""",
        config=SHARED_CONFIG,
        conftest="""
import la_dev_codex_plugins.pytest_isolation.plugin as isolation_plugin

isolation_plugin.POLICY_VERIFICATION_CALLS = 0
original_verify_policy_tree = isolation_plugin._verify_policy_tree

def count_policy_verification(*args, **kwargs):
    isolation_plugin.POLICY_VERIFICATION_CALLS += 1
    return original_verify_policy_tree(*args, **kwargs)

isolation_plugin._verify_policy_tree = count_policy_verification
""",
    )
    result.assert_outcomes(passed=2)


def test_cleanup_diagnostics_do_not_escape_hookwrappers_under_warning_errors(run_isolation):
    result = run_isolation(
        """
import pathlib

def test_corrupt_shared_mode():
    pathlib.Path.cwd().chmod(0o700)
""",
        "-W",
        "error",
        config=SHARED_CONFIG,
    )
    assert result.ret == 1
    output = "\n".join(result.stdout.lines + result.stderr.lines)
    assert "Shared guarded session teardown failed" in output
    assert "Traceback (most recent call last)" not in output
    assert "PluggyTeardownRaisedWarning" not in output


@pytest.mark.parametrize("corruption", ["deleted", "replaced"])
def test_corrupted_shared_guard_fails_closed_and_boundary_is_preserved(run_isolation, monkeypatch, tmp_path, corruption, remove_preserved_boundary):
    record = tmp_path / "corrupt-boundary.txt"
    monkeypatch.setenv("SHARED_CORRUPT_RECORD", str(record))
    if corruption == "deleted":
        action = "shutil.rmtree(str(cwd))"
        expected = "could not safely open shared guarded working directory"
    else:
        action = "os.chdir(os.environ['TMPDIR']); cwd.rename(cwd.parent / 'original-cwd'); cwd.mkdir(); cwd.chmod(0o500)"
        expected = "shared guarded working directory changed identity"
    result = run_isolation(
        """
import os
import pathlib
import shutil

def test_01_corrupt():
    cwd = pathlib.Path.cwd()
    pathlib.Path(os.environ["SHARED_CORRUPT_RECORD"]).write_text(str(cwd.parent), encoding="ascii")
    cwd.chmod(0o700)
    {action}

def test_02_fails_closed_before_entry():
    raise AssertionError("corrupted guard was entered")
""".format(action=action),
        config=SHARED_CONFIG,
    )
    assert result.ret != 0
    output = "\n".join(result.stdout.lines + result.stderr.lines)
    assert expected in output
    boundary = pathlib.Path(record.read_text(encoding="ascii"))
    assert boundary.is_dir()
    if corruption == "replaced":
        assert (boundary / "cwd").is_dir()
        assert (boundary / "original-cwd").is_dir()
    remove_preserved_boundary(boundary)


def test_boundary_ancestor_symlink_substitution_fails_before_reentry_and_is_preserved(run_isolation, monkeypatch, tmp_path):
    record = tmp_path / "boundary-symlink-record.txt"
    monkeypatch.setenv("BOUNDARY_SYMLINK_RECORD", str(record))
    result = run_isolation(
        """
import os
import pathlib

def test_replace_boundary_with_symlink():
    boundary = pathlib.Path.cwd().parent
    genuine = boundary.with_name(boundary.name + "-genuine")
    boundary.rename(genuine)
    boundary.symlink_to(genuine, target_is_directory=True)
    sentinel = genuine / "sentinel.txt"
    sentinel.write_text("keep", encoding="ascii")
    pathlib.Path(os.environ["BOUNDARY_SYMLINK_RECORD"]).write_text("{}\\n{}\\n{}\\n".format(boundary, genuine, sentinel), encoding="ascii")

def test_must_not_reenter():
    raise AssertionError("symlinked boundary was entered")
""",
        config=SHARED_CONFIG,
    )
    assert result.ret != 0
    output = "\n".join(result.stdout.lines + result.stderr.lines)
    assert "could not safely open shared isolation boundary" in output
    boundary, genuine, sentinel = (pathlib.Path(value) for value in record.read_text(encoding="ascii").splitlines())
    assert boundary.is_symlink()
    assert genuine.is_dir()
    assert sentinel.read_text(encoding="ascii") == "keep"


@pytest.mark.parametrize("corruption", ["deleted", "replaced", "symlink"])
def test_corrupted_shared_tmp_fails_before_private_allocation(run_isolation, monkeypatch, tmp_path, corruption, remove_preserved_boundary):
    external = tmp_path / "external-target"
    external.mkdir()
    record = tmp_path / "tmp-corruption-record.txt"
    monkeypatch.setenv("TMP_CORRUPTION_EXTERNAL", str(external))
    monkeypatch.setenv("TMP_CORRUPTION_RECORD", str(record))
    if corruption == "deleted":
        action = "shutil.rmtree(str(shared_tmp))"
    elif corruption == "replaced":
        action = "shared_tmp.rename(shared_tmp.parent / 'original-tmp'); shared_tmp.mkdir()"
    else:
        action = "shared_tmp.rename(shared_tmp.parent / 'original-tmp'); shared_tmp.symlink_to(external, target_is_directory=True)"
    result = run_isolation(
        """
import os
import pathlib
import shutil
import pytest

def test_01_corrupt_tmp():
    shared_tmp = pathlib.Path(os.environ["TMPDIR"])
    external = pathlib.Path(os.environ["TMP_CORRUPTION_EXTERNAL"])
    {action}
    pathlib.Path(os.environ["TMP_CORRUPTION_RECORD"]).write_text(str(shared_tmp.parent), encoding="ascii")

@pytest.mark.isolated_cwd
def test_02_must_not_allocate_private(isolated_cwd):
    raise AssertionError("private boundary was allocated after shared tmp corruption")
""".format(action=action),
        config=SHARED_CONFIG,
    )
    assert result.ret != 0
    output = "\n".join(result.stdout.lines + result.stderr.lines)
    assert "shared temporary directory" in output
    assert not list(external.iterdir())
    boundary = pathlib.Path(record.read_text(encoding="ascii"))
    assert boundary.is_dir()
    if corruption == "replaced":
        assert (boundary / "tmp").is_dir()
        assert (boundary / "original-tmp").is_dir()
    if corruption == "symlink":
        assert (boundary / "tmp").is_symlink()
    remove_preserved_boundary(boundary)


def test_replaced_shared_boundary_is_preserved_without_deleting_replacement(run_isolation, monkeypatch, tmp_path):
    record = tmp_path / "replaced-boundary-record.txt"
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    monkeypatch.setenv("REPLACED_BOUNDARY_RECORD", str(record))
    result = run_isolation(
        """
import os
import pathlib

def test_replace_boundary_path():
    boundary = pathlib.Path.cwd().parent
    genuine = boundary.with_name(boundary.name + "-genuine")
    boundary.rename(genuine)
    boundary.mkdir(mode=0o700)
    sentinel = boundary / "unrelated-sentinel.txt"
    sentinel.write_text("keep", encoding="ascii")
    pathlib.Path(os.environ["REPLACED_BOUNDARY_RECORD"]).write_text("{}\\n{}\\n".format(genuine, sentinel), encoding="ascii")
""",
        config=SHARED_CONFIG,
    )
    assert result.ret != 0
    genuine, sentinel = (pathlib.Path(value) for value in record.read_text(encoding="ascii").splitlines())
    assert genuine.is_dir()
    assert sentinel.read_text(encoding="ascii") == "keep"
