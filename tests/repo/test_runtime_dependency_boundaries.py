"""Runtime dependency boundary tests for shipped plugins and source packages."""

import ast
import pathlib
import sys
import sysconfig

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
PLUGINS_ROOT = REPO_ROOT / "plugins"
SRC_ROOT = REPO_ROOT / "src"
STANDALONE_RUNTIME_FILES = (
    REPO_ROOT / "package_scripts" / "codex-perform",
    REPO_ROOT / "source_launcher" / "codex_perform.py",
)
PYTEST_PLUGIN = SRC_ROOT / "la_dev_codex_plugins" / "pytest_isolation" / "plugin.py"
STRICT_STDLIB_ROOTS = (
    PLUGINS_ROOT,
    REPO_ROOT / "package_scripts",
    REPO_ROOT / "source_launcher",
    SRC_ROOT / "la_dev_codex_plugins" / "codex_perform",
    SRC_ROOT / "la_dev_codex_plugins" / "markdown_tables",
    SRC_ROOT / "la_dev_codex_plugins" / "release_checksums",
)


def _stdlib_top_level_modules():
    modules = set(sys.builtin_module_names)
    for raw_path in (sysconfig.get_path("stdlib"), sysconfig.get_path("platstdlib")):
        if raw_path is None:
            continue
        stdlib_path = pathlib.Path(raw_path)
        if not stdlib_path.is_dir():
            continue
        for child in stdlib_path.iterdir():
            if child.name in {"site-packages", "dist-packages", "__pycache__"}:
                continue
            if child.name.startswith("."):
                continue
            if child.is_file() and child.suffix == ".py":
                modules.add(child.stem)
            elif child.is_dir() and (child / "__init__.py").is_file():
                modules.add(child.name)
    return modules


def _local_top_level_modules(script_root):
    modules = set()
    for child in script_root.iterdir():
        if child.name.startswith("."):
            continue
        if child.is_file() and child.suffix == ".py":
            modules.add(child.stem)
        elif child.is_dir():
            modules.add(child.name)
    return modules


def _imported_top_level_modules(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend((node.lineno, alias.name.split(".", 1)[0]) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.append((node.lineno, node.module.split(".", 1)[0]))

    return modules


def _imported_absolute_modules(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.append((node.lineno, node.module))

    return modules


def _is_optional_pytest_import(module):
    return module in {"pytest", "la_dev_codex_plugins.pytest_isolation.plugin"} or module.startswith(("pytest.", "la_dev_codex_plugins.pytest_isolation.plugin."))


@pytest.mark.guarded_cwd
def test_shipped_plugin_scripts_import_only_stdlib_or_local_modules():
    stdlib_modules = _stdlib_top_level_modules()
    violations = []

    for script_root in sorted(PLUGINS_ROOT.glob("*/skills/*/scripts")):
        if not script_root.is_dir():
            continue
        allowed = stdlib_modules | _local_top_level_modules(script_root)
        for path in sorted(script_root.rglob("*.py")):
            for line, module in _imported_top_level_modules(path):
                if module not in allowed:
                    violations.append(f"{path.relative_to(REPO_ROOT)}:{line}: import {module}")

    assert not violations, "Non-stdlib imports in shipped plugin scripts:\n" + "\n".join(violations)


@pytest.mark.guarded_cwd
def test_src_package_imports_only_stdlib_or_local_modules():
    stdlib_modules = _stdlib_top_level_modules()
    allowed = stdlib_modules | _local_top_level_modules(SRC_ROOT)
    violations = []

    for path in sorted(SRC_ROOT.rglob("*.py")):
        for line, module in _imported_top_level_modules(path):
            if path == PYTEST_PLUGIN and module == "pytest":
                continue
            if module not in allowed:
                violations.append(f"{path.relative_to(REPO_ROOT)}:{line}: import {module}")

    assert not violations, "Non-stdlib imports in src package:\n" + "\n".join(violations)


def test_only_pytest_plugin_imports_pytest_or_the_plugin_module():
    violations = []

    for path in sorted(SRC_ROOT.rglob("*.py")):
        if path == PYTEST_PLUGIN:
            continue
        for line, module in _imported_absolute_modules(path):
            if _is_optional_pytest_import(module):
                violations.append(f"{path.relative_to(REPO_ROOT)}:{line}: import {module}")

    assert not violations, "Imports crossing the optional pytest boundary:\n" + "\n".join(violations)


def test_strict_runtime_paths_do_not_import_pytest_integration():
    violations = []

    for root in STRICT_STDLIB_ROOTS:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            for line, module in _imported_absolute_modules(path):
                if _is_optional_pytest_import(module):
                    violations.append(f"{path.relative_to(REPO_ROOT)}:{line}: import {module}")

    assert not violations, "Optional pytest imports in strict runtime paths:\n" + "\n".join(violations)


def test_standalone_launcher_files_import_only_stdlib_modules():
    stdlib_modules = _stdlib_top_level_modules()
    violations = []

    for path in STANDALONE_RUNTIME_FILES:
        for line, module in _imported_top_level_modules(path):
            if module not in stdlib_modules:
                violations.append(f"{path.relative_to(REPO_ROOT)}:{line}: import {module}")

    assert not violations, "Non-stdlib imports in standalone launcher files:\n" + "\n".join(violations)
