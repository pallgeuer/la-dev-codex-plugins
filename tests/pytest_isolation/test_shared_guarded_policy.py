"""Configured shared-boundary policy behavior tests."""

import os
import pathlib

import pytest

import la_dev_codex_plugins.pytest_isolation.plugin as isolation_plugin

SHARED_CONFIG = """[pytest]
la_dev_cwd_isolation_unmarked = shared_guarded
"""


def test_default_shared_policy_is_used_without_provider(run_isolation):
    result = run_isolation(
        """
import pathlib

def test_default_policy():
    cwd = pathlib.Path.cwd()
    assert (cwd / "pyproject.toml").read_text(encoding="utf-8") == "[tool.la_dev_cwd_guard\\n"
""",
        config=SHARED_CONFIG,
    )
    result.assert_outcomes(passed=1)


def test_shared_policy_provider_is_called_once(run_isolation):
    result = run_isolation(
        """
def test_policy_loaded_once():
    pass
""",
        config=SHARED_CONFIG,
        conftest="""
CALLS = 0

def pytest_la_dev_cwd_isolation_shared_policy(config):
    global CALLS
    CALLS += 1
    if CALLS != 1:
        raise AssertionError("shared policy provider called more than once")
    return {"poison_files": {"guard.ini": "[invalid"}}
""",
    )
    result.assert_outcomes(passed=1)


@pytest.mark.parametrize("value", ["", "shared-guarded", "SHARED_GUARDED", " shared_guarded", "shared_guarded ", "unknown"])
def test_invalid_configuration_fails_before_execution_or_allocation(run_isolation, monkeypatch, tmp_path, value):
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    result = run_isolation(
        """
def test_must_not_run():
    raise AssertionError("invalid configuration reached test execution")
""",
        "-o",
        "la_dev_cwd_isolation_unmarked={}".format(value),
    )
    assert result.ret != 0
    result.stderr.fnmatch_lines(["*la_dev_cwd_isolation_unmarked*{!r}*allowed values*none*shared_guarded*".format(value)])
    assert not list(tmp_path.rglob("la-dev-pytest-isolation-*"))


@pytest.mark.parametrize(
    "mapping",
    [
        "[]",
        "{1: 'value'}",
        "{'value': b'bytes'}",
        "{'/absolute': 'value'}",
        "{'': 'value'}",
        "{'.': 'value'}",
        "{'nul\\x00path': 'value'}",
        "{'a/../b': 'value'}",
        "{'a/b': 'one', 'a//b': 'two'}",
        "{'a': 'file', 'a/b': 'child'}",
    ],
)
def test_invalid_shared_poison_policy_fails_once_before_allocation(run_isolation, monkeypatch, tmp_path, mapping):
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    result = run_isolation(
        """
def test_01_must_not_run():
    raise AssertionError("invalid poison policy reached test execution")

def test_02_must_not_run():
    raise AssertionError("invalid poison policy reached test execution")
""",
        config=SHARED_CONFIG,
        conftest="""
def pytest_la_dev_cwd_isolation_shared_policy(config):
    return {{"poison_files": {mapping}}}
""".format(mapping=mapping),
    )
    assert result.ret != 0
    stderr = "\n".join(result.stderr.lines)
    assert stderr.count("shared policy poison_files") == 1
    assert not list(tmp_path.rglob("la-dev-pytest-isolation-*"))


@pytest.mark.parametrize(
    ("policy", "expected"),
    [
        ("[]", "must return a mapping or None"),
        ("{1: {}}", "keys must be strings"),
        ("{'unknown': {}}", "unknown key(s): unknown"),
        ("{'boundary_files': []}", "boundary_files must be a mapping"),
    ],
)
def test_invalid_outer_shared_policy_is_one_usage_error(run_isolation, monkeypatch, tmp_path, policy, expected):
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    result = run_isolation(
        """
def test_01_must_not_run():
    raise AssertionError("invalid shared policy reached test execution")

def test_02_must_not_run():
    raise AssertionError("invalid shared policy reached test execution")

def test_03_must_not_run():
    raise AssertionError("invalid shared policy reached test execution")
""",
        config=SHARED_CONFIG,
        conftest="""
def pytest_la_dev_cwd_isolation_shared_policy(config):
    return {policy}
""".format(policy=policy),
    )
    assert result.ret != 0
    stderr = "\n".join(result.stderr.lines)
    assert stderr.count(expected) == 1
    assert "3 errors" not in stderr
    assert not list(tmp_path.rglob("la-dev-pytest-isolation-*"))


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("contents", "chr(0xD800)", "contents must be encodable as UTF-8"),
        ("path", "chr(0xD800)", "paths must be encodable by the filesystem"),
    ],
)
def test_unencodable_policy_values_fail_before_allocation(run_isolation, monkeypatch, tmp_path, field, value, expected):
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    mapping = "{'policy.txt': " + value + "}" if field == "contents" else "{" + value + ": 'value'}"
    result = run_isolation(
        "def test_must_not_run(): raise AssertionError('policy reached execution')\n",
        config=SHARED_CONFIG,
        conftest="""
def pytest_la_dev_cwd_isolation_shared_policy(config):
    return {{"poison_files": {mapping}}}
""".format(mapping=mapping),
    )
    assert result.ret != 0
    result.stderr.fnmatch_lines(["*{}*".format(expected)])
    assert not list(tmp_path.rglob("la-dev-pytest-isolation-*"))


@pytest.mark.parametrize("relative", ["cwd", "cwd/config.ini", "tmp", "tmp/config.ini"])
def test_boundary_policy_rejects_reserved_layout_paths(run_isolation, monkeypatch, tmp_path, relative):
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    result = run_isolation(
        "def test_must_not_run(): raise AssertionError('policy reached execution')\n",
        config=SHARED_CONFIG,
        conftest="""
def pytest_la_dev_cwd_isolation_shared_policy(config):
    return {{"boundary_files": {{{relative!r}: "value"}}}}
""".format(relative=relative),
    )
    assert result.ret != 0
    result.stderr.fnmatch_lines(["*boundary_files*reserved boundary path*"])
    assert not list(tmp_path.rglob("la-dev-pytest-isolation-*"))


@pytest.mark.parametrize("mapping", ["{}", "{'config/tool.ini': '[invalid', 'nested/deeper.txt': 'exact'}"])
def test_shared_poison_override_is_a_copied_complete_replacement(run_isolation, mapping):
    result = run_isolation(
        """
import pathlib
import stat

def test_replacement_policy():
    cwd = pathlib.Path.cwd()
    assert not (cwd / "pyproject.toml").exists()
    assert not (cwd / "late.txt").exists()
    expected = {mapping}
    for relative, contents in expected.items():
        path = cwd / relative
        assert path.read_text(encoding="utf-8") == contents
        assert stat.S_IMODE(path.stat().st_mode) == 0o400
    assert stat.S_IMODE(cwd.stat().st_mode) == 0o500
""".format(mapping=mapping),
        config=SHARED_CONFIG,
        conftest="""
import pytest

POLICY = {mapping}

def pytest_la_dev_cwd_isolation_shared_policy(config):
    return {{"poison_files": POLICY}}

@pytest.fixture(autouse=True)
def mutate_source_after_shared_setup():
    POLICY["late.txt"] = "too late"
""".format(mapping=mapping),
    )
    result.assert_outcomes(passed=1)


def test_boundary_and_guard_policy_support_neutral_ancestor_configuration(run_isolation):
    result = run_isolation(
        """
import pathlib
import stat
import pytest

def _assert_boundary_policy(boundary):
    config = boundary / "config" / "tool.toml"
    assert config.read_text(encoding="utf-8") == "[tool.project]\\n"
    assert stat.S_IMODE(config.stat().st_mode) == 0o400
    assert stat.S_IMODE(config.parent.stat().st_mode) == 0o500

@pytest.mark.isolated_cwd
def test_01_private_boundary_inherits_neutral_ancestor(isolated_cwd):
    shared_boundary = isolated_cwd.parent.parent.parent
    _assert_boundary_policy(shared_boundary)
    assert isolated_cwd.parent.parent == shared_boundary / "tmp"

def test_02_shared_guard_uses_independent_poison_policy():
    cwd = pathlib.Path.cwd()
    _assert_boundary_policy(cwd.parent)
    assert not (cwd / "pyproject.toml").exists()
    assert (cwd / "guard.ini").read_text(encoding="utf-8") == "[invalid"
""",
        config=SHARED_CONFIG,
        conftest="""
def pytest_la_dev_cwd_isolation_shared_policy(config):
    return {
        "boundary_files": {"config/tool.toml": "[tool.project]\\n"},
        "poison_files": {"guard.ini": "[invalid"},
    }
""",
    )
    result.assert_outcomes(passed=2)


def test_root_policy_is_global_under_partial_test_selection(run_isolation):
    source = """import pathlib

def test_global_policy():
    cwd = pathlib.Path.cwd()
    assert (cwd / "policy.ini").read_text(encoding="utf-8") == "global"
    assert (cwd.parent / "anchor.txt").read_text(encoding="utf-8") == "boundary"
"""
    result = run_isolation(
        None,
        "right",
        config=SHARED_CONFIG,
        conftest="""
def pytest_la_dev_cwd_isolation_shared_policy(config):
    return {"boundary_files": {"anchor.txt": "boundary"}, "poison_files": {"policy.ini": "global"}}
""",
        files={"left/test_left.py": source, "right/test_right.py": source},
    )
    result.assert_outcomes(passed=1)


@pytest.mark.parametrize("explicit_path", [False, True])
def test_nested_policy_provider_is_rejected_whether_loaded_early_or_during_collection(run_isolation, explicit_path):
    arguments = ("nested",) if explicit_path else ()
    result = run_isolation(
        None,
        *arguments,
        config=SHARED_CONFIG,
        files={
            "nested/conftest.py": """def pytest_la_dev_cwd_isolation_shared_policy(config):
    return {"poison_files": {"nested.ini": "nested"}}
""",
            "nested/test_nested.py": "def test_must_not_run(): raise AssertionError('nested policy reached execution')\n",
        },
    )
    assert result.ret != 0
    result.stderr.fnmatch_lines(["*pytest_la_dev_cwd_isolation_shared_policy*root conftest*plugin*nested*provider*"])


def test_nested_registered_object_policy_provider_is_rejected(run_isolation):
    result = run_isolation(
        None,
        "nested",
        config=SHARED_CONFIG,
        files={
            "nested/conftest.py": """import pytest

class NestedProvider:
    @pytest.hookimpl
    def pytest_la_dev_cwd_isolation_shared_policy(self, config):
        return {"poison_files": {"nested.ini": "nested"}}

def pytest_configure(config):
    config.pluginmanager.register(NestedProvider(), "nested-object-provider")
""",
            "nested/test_nested.py": "def test_must_not_run(): raise AssertionError('nested object policy reached execution')\n",
        },
    )
    assert result.ret != 0
    result.stderr.fnmatch_lines(["*pytest_la_dev_cwd_isolation_shared_policy*root conftest*plugin*nested*provider*"])


def test_root_registered_object_policy_provider_is_accepted(run_isolation):
    result = run_isolation(
        """
import pathlib

def test_root_object_policy():
    assert (pathlib.Path.cwd() / "root-object.ini").read_text(encoding="ascii") == "root"
""",
        config=SHARED_CONFIG,
        conftest="""import pytest

class RootProvider:
    @pytest.hookimpl
    def pytest_la_dev_cwd_isolation_shared_policy(self, config):
        return {"poison_files": {"root-object.ini": "root"}}

def pytest_configure(config):
    config.pluginmanager.register(RootProvider(), "root-object-provider")
""",
    )
    result.assert_outcomes(passed=1)


def test_early_plugin_named_conftest_is_accepted(run_isolation):
    result = run_isolation(
        """
import pathlib

def test_early_policy():
    assert (pathlib.Path.cwd() / "early.ini").read_text(encoding="ascii") == "early"
""",
        "-p",
        "early_provider.conftest",
        "test_isolation.py",
        config=SHARED_CONFIG,
        files={
            "early_provider/__init__.py": "",
            "early_provider/conftest.py": """def pytest_la_dev_cwd_isolation_shared_policy(config):
    return {"poison_files": {"early.ini": "early"}}
""",
        },
    )
    result.assert_outcomes(passed=1)


def test_multiple_early_plugin_policy_providers_fail_once(run_isolation):
    result = run_isolation(
        "def test_must_not_run(): raise AssertionError('multiple policies reached execution')\n",
        config=SHARED_CONFIG,
        conftest="pytest_plugins = ('policy_a', 'policy_b')\n",
        files={
            "policy_a.py": "def pytest_la_dev_cwd_isolation_shared_policy(config): return {'poison_files': {'a': 'a'}}\n",
            "policy_b.py": "def pytest_la_dev_cwd_isolation_shared_policy(config): return {'poison_files': {'b': 'b'}}\n",
        },
    )
    assert result.ret != 0
    stderr = "\n".join(result.stderr.lines)
    assert stderr.count("at most one non-None provider") == 1


def test_large_shared_policy_avoids_pairwise_collision_validation(run_isolation):
    result = run_isolation(
        """
import pathlib

def test_large_policy():
    cwd = pathlib.Path.cwd()
    assert (cwd / "file0000").read_text(encoding="utf-8") == "x"
    assert (cwd / "file0999").read_text(encoding="utf-8") == "x"
""",
        config=SHARED_CONFIG,
        conftest="""
def pytest_la_dev_cwd_isolation_shared_policy(config):
    return {"poison_files": {"file{:04d}".format(index): "x" for index in range(1000)}}
""",
    )
    result.assert_outcomes(passed=1)


def test_policy_verification_indexes_manifest_once(tmp_path):
    class CountingManifest(dict):
        def __init__(self, entries):
            super().__init__(entries)
            self.iterations = 0

        def __iter__(self):
            self.iterations += 1
            return super().__iter__()

    files = {"directory{:04d}/policy.ini".format(index): "x" for index in range(400)}
    manifest = CountingManifest(isolation_plugin._write_read_only_files(tmp_path, files))
    descriptor = os.open(str(tmp_path), isolation_plugin._directory_open_flags())
    failures = []
    try:
        isolation_plugin._verify_policy_tree(descriptor, tmp_path, manifest, failures)
        assert manifest.iterations == 1
        assert isolation_plugin._remove_directory_contents(descriptor, tmp_path, failures)
    finally:
        os.close(descriptor)
    assert failures == []


def test_deep_policy_and_temporary_trees_do_not_depend_on_python_recursion(run_isolation, monkeypatch, tmp_path):
    record = tmp_path / "deep-shared-boundary.txt"
    monkeypatch.setenv("DEEP_SHARED_RECORD", str(record))
    result = run_isolation(
        """
import os
import pathlib
import sys

def test_deep_temporary_tree():
    shared_tmp = pathlib.Path(os.environ["TMPDIR"])
    pathlib.Path(os.environ["DEEP_SHARED_RECORD"]).write_text(str(shared_tmp.parent), encoding="ascii")
    current = shared_tmp
    for _index in range(150):
        current = current / "temporary"
        current.mkdir()
    sys.setrecursionlimit(100)
""",
        config=SHARED_CONFIG,
        conftest="""import sys

def pytest_la_dev_cwd_isolation_shared_policy(config):
    relative = "/".join(["policy"] * 150 + ["guard.ini"])
    return {"poison_files": {relative: "guard"}}

def pytest_unconfigure(config):
    sys.setrecursionlimit(1000)
""",
    )
    result.assert_outcomes(passed=1)
    assert not pathlib.Path(record.read_text(encoding="ascii")).exists()


def test_materialized_shared_policy_retains_only_compact_integrity_manifest(run_isolation):
    result = run_isolation(
        """
def test_phase_only_policy_data_was_released(request):
    isolation = getattr(request.config, "_la_dev_cwd_isolation_session")
    assert isolation.boundary_files is None
    assert isolation.poison_files is None
    assert isolation.policy_hookimpls == frozenset()
    manifest = isolation.shared_state.integrity_manifest
    assert set(manifest) == {"boundary", "cwd"}
    assert manifest["boundary"]["anchor.txt"][0:2] == ("file", 0o400)
    assert manifest["cwd"]["guard.ini"][0:2] == ("file", 0o400)
    assert "large-secret-policy-contents" not in repr(manifest)
""",
        config=SHARED_CONFIG,
        conftest="""
def pytest_la_dev_cwd_isolation_shared_policy(config):
    return {
        "boundary_files": {"anchor.txt": "large-secret-policy-contents" * 1000},
        "poison_files": {"guard.ini": "large-secret-policy-contents" * 1000},
    }
""",
    )
    result.assert_outcomes(passed=1)
