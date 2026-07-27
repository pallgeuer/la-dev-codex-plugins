"""Isolated source-checkout bootstrap for the Perform launcher."""

import importlib
import sys
from pathlib import Path


def main():
    """Load and run the launcher from this bootstrap's source checkout."""
    source_root = str(Path(__file__).resolve().parents[2])
    sys.path.insert(0, source_root)
    perform = importlib.import_module("la_dev_codex_plugins.cli.perform")
    return perform.main()


if __name__ == "__main__":
    sys.exit(main())
