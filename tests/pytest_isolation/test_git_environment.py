"""Git environment isolation, restoration, and commit-hook regressions."""

import json
import os
import pathlib
import shlex
import subprocess
import sys

import pytest

GIT_NAMES = (
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_CONFIG",
    "GIT_CONFIG_COUNT",
    "GIT_CONFIG_PARAMETERS",
    "GIT_DIR",
    "GIT_GRAFT_FILE",
    "GIT_IMPLICIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_NO_REPLACE_OBJECTS",
    "GIT_OBJECT_DIRECTORY",
    "GIT_PREFIX",
    "GIT_REPLACE_REF_BASE",
    "GIT_SHALLOW_FILE",
    "GIT_WORK_TREE",
)
OTHER_VALUES = {
    "GIT_AUTHOR_NAME": "Isolation Test",
    "GIT_TRACE": "0",
    "GIT_CONFIG_GLOBAL": "/caller/global-config",
    "GIT_CONFIG_SYSTEM": "/caller/system-config",
    "GIT_CONFIG_KEY_0": "test.inherited",
    "GIT_CONFIG_VALUE_0": "caller",
}


@pytest.fixture
def caller_git_environment(monkeypatch):
    """Seed repository-local variables with populated, empty, and absent states."""
    for index, name in enumerate(GIT_NAMES):
        if index % 3 == 0:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, "" if index % 3 == 1 else "caller-" + name)
    for name, value in OTHER_VALUES.items():
        monkeypatch.setenv(name, value)
    return {name: os.environ.get(name) for name in GIT_NAMES}


def restoration_conftest(record):
    """Record exact caller Git state after plugin shutdown, including failed runs."""
    return """
import json
import os
import pathlib

NAMES = {names!r}
INITIAL = {{name: os.environ.get(name) for name in NAMES}}

def pytest_unconfigure(config):
    actual = {{name: os.environ.get(name) for name in NAMES}}
    assert actual == INITIAL
    pathlib.Path({record!r}).write_text(json.dumps(actual), encoding="ascii")
""".format(names=GIT_NAMES, record=str(record))


@pytest.mark.parametrize("mode", ["isolated_cwd", "guarded_cwd", "shared"])
@pytest.mark.parametrize("policy", ["clear", "inherit"])
@pytest.mark.parametrize("cleanup", ["eager", "pytest_retained"])
def test_git_policy_applies_at_fixture_boundaries_and_restores_exact_state(run_isolation, caller_git_environment, tmp_path, mode, policy, cleanup):
    record = tmp_path / "restored.json"
    expected = dict.fromkeys(GIT_NAMES) if policy == "clear" else caller_git_environment
    final_broad = dict(expected if mode == "shared" else caller_git_environment)
    if mode == "shared" and policy == "clear":
        final_broad["GIT_INDEX_FILE"] = "explicit-test-index"
    result = run_isolation(
        """
import os
import pytest

EXPECTED = {expected!r}
OTHER = {other!r}

def assert_environment(expected):
    assert {{name: os.environ.get(name) for name in expected}} == expected
    assert {{name: os.environ.get(name) for name in OTHER}} == OTHER

@pytest.fixture(scope="module", autouse=True)
def broad_fixture():
    assert_environment({broad!r})
    yield
    assert_environment({final_broad!r})

@pytest.fixture(autouse=True)
def function_fixture():
    assert_environment(EXPECTED)
    yield
    assert os.environ.get("GIT_INDEX_FILE") == {final_index!r}

{marker}
def test_environment():
    assert_environment(EXPECTED)
    if {clear!r}:
        os.environ["GIT_INDEX_FILE"] = "explicit-test-index"
""".format(
            expected=expected,
            final_broad=final_broad,
            clear=policy == "clear",
            final_index="explicit-test-index" if policy == "clear" else expected["GIT_INDEX_FILE"],
            other=OTHER_VALUES,
            broad=expected if mode == "shared" else caller_git_environment,
            marker="" if mode == "shared" else "@pytest.mark." + mode,
        ),
        config="[pytest]\nla_dev_cwd_isolation_git_environment = {}\nla_dev_cwd_isolation_cleanup = {}\nla_dev_cwd_isolation_unmarked = {}\n".format(
            policy, cleanup, "shared_guarded" if mode == "shared" else "none"
        ),
        conftest=restoration_conftest(record) if policy == "clear" else None,
    )
    result.assert_outcomes(passed=1)
    if policy == "clear":
        assert json.loads(record.read_text(encoding="ascii")) == caller_git_environment


@pytest.mark.parametrize("policy", ["clear", "inherit"])
def test_unmarked_default_remains_inert(run_isolation, caller_git_environment, policy):
    result = run_isolation(
        """
import os

def test_unmarked():
    expected = {expected!r}
    assert {{name: os.environ.get(name) for name in expected}} == expected
""".format(expected=caller_git_environment),
        config="[pytest]\nla_dev_cwd_isolation_git_environment = {}\n".format(policy),
    )
    result.assert_outcomes(passed=1)


@pytest.mark.parametrize("shared", [False, True])
@pytest.mark.usefixtures("caller_git_environment")
def test_inherit_does_not_restore_test_mutations(run_isolation, shared):
    result = run_isolation(
        """
import os

def test_01_change(isolated_cwd):
    os.environ["GIT_INDEX_FILE"] = "test-owned-index"

def test_02_still_changed():
    assert os.environ["GIT_INDEX_FILE"] == "test-owned-index"
""",
        config="[pytest]\nla_dev_cwd_isolation_git_environment = inherit\nla_dev_cwd_isolation_unmarked = {}\n".format("shared_guarded" if shared else "none"),
        conftest="""
import os

def pytest_unconfigure(config):
    assert os.environ["GIT_INDEX_FILE"] == "test-owned-index"
""",
    )
    result.assert_outcomes(passed=2)


@pytest.mark.parametrize("shared", [False, True])
def test_git_state_restores_after_test_and_fixture_failures(run_isolation, caller_git_environment, tmp_path, shared):
    record = tmp_path / "restored.json"
    result = run_isolation(
        """
import os
import pytest

@pytest.fixture
def fails_setup():
    os.environ["GIT_INDEX_FILE"] = "setup"
    raise RuntimeError("setup failure")

@pytest.fixture
def fails_teardown():
    yield
    os.environ["GIT_INDEX_FILE"] = "teardown"
    raise RuntimeError("teardown failure")

@pytest.fixture(autouse=True)
def starts_clear(request):
    if request.node.name != "test_05_restored":
        assert "GIT_INDEX_FILE" not in os.environ

def test_01_assertion(isolated_cwd):
    os.environ["GIT_INDEX_FILE"] = "assertion"
    assert False

def test_02_skip(isolated_cwd):
    os.environ["GIT_INDEX_FILE"] = "skip"
    pytest.skip("intentional")

def test_03_fixture_setup(isolated_cwd, fails_setup):
    pass

def test_04_fixture_teardown(isolated_cwd, fails_teardown):
    pass

def test_05_restored():
    expected = {expected!r}
    assert {{name: os.environ.get(name) for name in expected}} == expected
""".format(expected=dict.fromkeys(GIT_NAMES) if shared else caller_git_environment),
        config="[pytest]\nla_dev_cwd_isolation_unmarked = {}\n".format("shared_guarded" if shared else "none"),
        conftest=restoration_conftest(record),
    )
    result.assert_outcomes(passed=2, failed=1, skipped=1, errors=2)
    assert json.loads(record.read_text(encoding="ascii")) == caller_git_environment


def test_shared_reactivation_clears_mutations_before_nested_private_and_broad_finalizers(run_isolation, caller_git_environment, tmp_path):
    record = tmp_path / "restored.json"
    result = run_isolation(
        """
import os
import pytest

NAMES = {names!r}

def assert_clear():
    assert all(name not in os.environ for name in NAMES)

@pytest.fixture(scope="module", autouse=True)
def broad_fixture():
    assert_clear()
    yield
    assert_clear()
    os.environ["GIT_DIR"] = "broad-finalizer"

@pytest.fixture(autouse=True)
def function_fixture():
    assert_clear()
    yield
    os.environ["GIT_INDEX_FILE"] = "function-finalizer"

def test_01_shared_mutation():
    os.environ.update(dict.fromkeys(NAMES, "shared-test"))

def test_02_shared_again():
    assert_clear()

def test_03_nested_private(isolated_cwd):
    assert_clear()
    os.environ.update(dict.fromkeys(NAMES, "private-test"))
""".format(names=GIT_NAMES),
        config="[pytest]\nla_dev_cwd_isolation_unmarked = shared_guarded\n",
        conftest=restoration_conftest(record),
    )
    result.assert_outcomes(passed=3)
    assert json.loads(record.read_text(encoding="ascii")) == caller_git_environment


@pytest.mark.parametrize("shared", [False, True])
@pytest.mark.parametrize(("statement", "returncode"), [("raise KeyboardInterrupt", 2), ("pytest.exit('stop', returncode=7)", 7)])
def test_git_state_restores_on_interrupt(run_isolation, caller_git_environment, tmp_path, shared, statement, returncode):
    record = tmp_path / "restored.json"
    result = run_isolation(
        """
import os
import pytest

def test_interrupt(isolated_cwd):
    os.environ["GIT_DIR"] = "interrupt"
    {statement}
""".format(statement=statement),
        config="[pytest]\nla_dev_cwd_isolation_unmarked = {}\n".format("shared_guarded" if shared else "none"),
        conftest=restoration_conftest(record),
    )
    assert result.ret == returncode
    assert json.loads(record.read_text(encoding="ascii")) == caller_git_environment


@pytest.mark.parametrize("shared", [False, True])
def test_partial_activation_failure_restores_git_state(run_isolation, caller_git_environment, tmp_path, shared):
    record = tmp_path / "restored.json"
    result = run_isolation(
        """
def test_never_runs(isolated_cwd):
    pass
""",
        config="[pytest]\nla_dev_cwd_isolation_unmarked = {}\n".format("shared_guarded" if shared else "none"),
        conftest=restoration_conftest(record)
        + """
import la_dev_codex_plugins.pytest_isolation.plugin as isolation_plugin

original_activate = isolation_plugin._activate_environment

def fail_activation(state):
    original_activate(state)
    raise OSError("injected activation failure")

isolation_plugin._activate_environment = fail_activation
""",
    )
    assert result.ret != 0
    assert "injected activation failure" in "\n".join(result.stdout.lines + result.stderr.lines)
    assert json.loads(record.read_text(encoding="ascii")) == caller_git_environment


@pytest.mark.parametrize("value", ["", "unknown", "Clear", " clear", "clear "])
def test_invalid_git_policy_is_rejected_before_allocation(run_isolation, tmp_path, value):
    record = tmp_path / "allocation"
    result = run_isolation(
        "def test_unused(): pass",
        "-o",
        "la_dev_cwd_isolation_git_environment=" + value,
        config="[pytest]\nla_dev_cwd_isolation_unmarked = shared_guarded\n",
        conftest="""
import pathlib
import la_dev_codex_plugins.pytest_isolation.plugin as isolation_plugin

def forbidden_allocation(*args, **kwargs):
    pathlib.Path({record!r}).touch()
    raise AssertionError("unexpected allocation")

isolation_plugin._create_boundary = forbidden_allocation
""".format(record=str(record)),
    )
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    assert "la_dev_cwd_isolation_git_environment" in "\n".join(result.stderr.lines)
    assert not record.exists()


@pytest.mark.isolated_cwd
def test_commit_all_hook_keeps_parallel_temporary_repositories_out_of_outer_index(isolated_cwd):
    """Exercise the absolute hook index with multiple repositories and xdist workers."""
    environment = dict(os.environ)
    for name in GIT_NAMES:
        environment.pop(name, None)
    environment["PYTHONPATH"] = str(pathlib.Path(__file__).resolve().parents[2] / "src")

    def git(*arguments):
        return subprocess.run(["git", *arguments], cwd=str(isolated_cwd), env=environment, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=30).stdout

    git("init", "-q")
    git("config", "user.name", "Outer Test")
    git("config", "user.email", "outer@example.com")
    git("config", "commit.gpgsign", "false")
    tracked = isolated_cwd / "tracked.txt"
    tracked.write_text("initial\n", encoding="ascii")
    git("add", "tracked.txt")
    git("-c", "core.hooksPath=/dev/null", "commit", "-qm", "initial")
    suite = isolated_cwd / "suite"
    suite.mkdir()
    (suite / "pytest.ini").write_text("[pytest]\n", encoding="ascii")
    (suite / "test_child.py").write_text(
        """
import pathlib
import subprocess
import pytest

@pytest.mark.parametrize("number", range(4))
def test_child_repository(isolated_cwd, number):
    def git(*args):
        return subprocess.run(["git", *args], cwd=str(isolated_cwd), check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True).stdout
    git("init", "-q")
    git("config", "user.name", "Child Test")
    git("config", "user.email", "child@example.com")
    git("config", "commit.gpgsign", "false")
    git("config", "core.hooksPath", "/dev/null")
    name = "child-{}.txt".format(number)
    (isolated_cwd / name).write_text("child", encoding="ascii")
    git("add", name)
    git("commit", "-qm", "child")
    assert git("ls-tree", "--name-only", "HEAD").splitlines() == [name]
""",
        encoding="ascii",
    )
    hook = isolated_cwd / ".git/hooks/pre-commit"
    command = [sys.executable, "-m", "pytest", "-p", "la_dev_codex_plugins.pytest_isolation.plugin", "-n", "2", "-q", str(suite)]
    hook.write_text(
        "#!/bin/sh\n"
        + shlex.quote(sys.executable)
        + " -c "
        + shlex.quote("import os, pathlib; index = pathlib.Path(os.environ['GIT_INDEX_FILE']); assert index.is_absolute(); pathlib.Path('hook-index-before').write_bytes(index.read_bytes())")
        + "\n"
        + " ".join(shlex.quote(argument) for argument in command)
        + " || exit $?\n"
        + shlex.quote(sys.executable)
        + " -c "
        + shlex.quote("import os, pathlib; assert pathlib.Path(os.environ['GIT_INDEX_FILE']).read_bytes() == pathlib.Path('hook-index-before').read_bytes()")
        + "\n",
        encoding="ascii",
    )
    hook.chmod(0o755)
    git("config", "core.hooksPath", str(hook.parent))
    tracked.write_text("changed\n", encoding="ascii")
    git("commit", "-a", "-qm", "changed")
    assert git("ls-tree", "--name-only", "HEAD").splitlines() == ["tracked.txt"]
    assert git("show", "HEAD:tracked.txt") == "changed\n"
    assert git("diff", "--cached", "--name-only") == ""
