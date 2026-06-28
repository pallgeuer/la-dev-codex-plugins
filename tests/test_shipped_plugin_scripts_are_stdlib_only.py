import ast
import sys
import sysconfig
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGINS_ROOT = REPO_ROOT / "plugins"


def _stdlib_top_level_modules():
    modules = set(sys.builtin_module_names)
    for raw_path in (sysconfig.get_path("stdlib"), sysconfig.get_path("platstdlib")):
        if raw_path is None:
            continue
        stdlib_path = Path(raw_path)
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
