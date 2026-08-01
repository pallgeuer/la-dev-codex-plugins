"""Pytest configuration layout contracts."""

import ast
import pathlib

REPOSITORY_ROOT = pathlib.Path(__file__).resolve().parents[2]
TESTS_ROOT = REPOSITORY_ROOT / "tests"


def test_tests_do_not_import_ambiguous_conftest_modules():
    violations = []
    for path in sorted(TESTS_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            imports_conftest = isinstance(node, ast.Import) and any(alias.name == "conftest" for alias in node.names)
            imports_from_conftest = isinstance(node, ast.ImportFrom) and node.level == 0 and node.module == "conftest"
            if imports_conftest or imports_from_conftest:
                violations.append("{}:{}".format(path.relative_to(REPOSITORY_ROOT), node.lineno))
    assert not violations, "Bare conftest imports are ambiguous across pytest versions:\n{}".format("\n".join(violations))
