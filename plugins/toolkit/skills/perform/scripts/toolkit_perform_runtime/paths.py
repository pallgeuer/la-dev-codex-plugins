"""Filesystem paths for assets bundled with the Perform runtime."""

from pathlib import Path


def bundled_actions_dir():
    """Resolve the action directory bundled beside the Perform runtime."""
    return str(Path(__file__).resolve().parents[2] / "assets" / "toolkit_perform_actions")


__all__ = ("bundled_actions_dir",)
