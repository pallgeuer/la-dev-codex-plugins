"""Isolated source-checkout bootstrap for the Perform launcher."""

import importlib
import pathlib
import sys


def main():
    """Load and run the launcher from this bootstrap's source checkout."""
    source_root = str(pathlib.Path(__file__).resolve().parents[1] / "src")
    sys.path.insert(0, source_root)
    perform = importlib.import_module("la_dev_codex_plugins.codex_perform.cli")
    return perform.main()


if __name__ == "__main__":
    sys.exit(main())
