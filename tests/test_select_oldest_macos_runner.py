"""Tests for dynamic selection of the oldest supported macOS Intel runner."""

import importlib.util
from pathlib import Path

import pytest

SELECTOR_PATH = Path(__file__).resolve().parents[1] / "scripts" / "select_oldest_macos_runner.py"


def load_selector():
    """Load the runner selector as an importable module."""
    spec = importlib.util.spec_from_file_location("select_oldest_macos_runner", SELECTOR_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("Could not load {}".format(SELECTOR_PATH))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def metadata(*rows, newline="\n"):
    """Build representative runner-images Markdown metadata."""
    lines = [
        "# Runner Images",
        "",
        "| Image | Architecture | YAML Label | Included Software |",
        "| --- | --- | --- | --- |",
        *rows,
        "",
        "## Announcements",
    ]
    return newline.join(lines)


def test_selects_oldest_non_deprecated_ga_intel_runner():
    selector = load_selector()
    contents = metadata(
        "| macOS 26<br>badge | x64 | `macos-latest-large`, `macos-26-intel`, `macos-26-large` | [macOS-26] |",
        "| macOS 26 Arm64<br>badge | arm64 | `macos-latest`, `macos-26` | [macOS-26-arm64] |",
        "| macOS 15<br>badge | x64 | `macos-15-large`, or `macos-15-intel` | [macOS-15] |",
        "| macOS 14 [![deprecated](badge)]<br>badge | x64 | `macos-14-large`, `macos-14-intel` | [macOS-14] |",
    )
    assert selector.select_oldest_macos_intel_runner(contents) == "macos-15-intel"


def test_selection_uses_numeric_version_order_and_accepts_crlf():
    selector = load_selector()
    contents = metadata(
        "| macOS 26<br>badge | x64 | `macos-26-intel` | [macOS-26] |",
        "| macOS 9 badge | x64 | `macos-9-intel` | [macOS-9] |",
        "| macOS 15<br>badge | x64 | `macos-15-intel` | [macOS-15] |",
        newline="\r\n",
    )
    assert selector.select_oldest_macos_intel_runner(contents) == "macos-9-intel"


def test_selection_excludes_preview_arm64_and_larger_runner_only_rows():
    selector = load_selector()
    contents = metadata(
        "| macOS 13 ![preview](badge)<br>badge | x64 | `macos-13-intel` | [macOS-13] |",
        "| macOS 14<br>badge | x64 | `macos-14-large` | [macOS-14] |",
        "| macOS 14 Arm64<br>badge | arm64 | `macos-14` | [macOS-14-arm64] |",
        "| macOS 15<br>badge | x64 | `macos-latest-large`, `macos-15-intel` | [macOS-15] |",
    )
    assert selector.select_oldest_macos_intel_runner(contents) == "macos-15-intel"


@pytest.mark.parametrize(
    ("contents", "message"),
    [
        ("# no table\n", "expected image table"),
        ("| Image | Architecture | YAML Label | Included Software |\n", "missing the image-table separator"),
        ("| Image | Architecture | YAML Label | Included Software |\n| invalid | --- | --- | --- |\n", "invalid image-table separator"),
        (metadata("| macOS 15<br>badge | x64 | `macos-15-intel` |"), "malformed image-table row"),
        (metadata("| macOS future<br>badge | x64 | `macos-future-intel` | [macOS-future] |"), "unrecognized macOS image name"),
        (metadata("| macOS 15<br>badge | x64 | `macos-15-intel`, `macos-26-intel` | [macOS-15] |"), "ambiguous macOS 15 Intel labels"),
        (metadata("| macOS 15<br>badge | x64 | `macos-15-intel` | [macOS-15] |", "| macOS 15<br>other | x64 | `macos-15-intel` | [macOS-15] |"), "duplicate eligible"),
        (metadata("| macOS 15 [![deprecated](badge)]<br>badge | x64 | `macos-15-intel` | [macOS-15] |"), "no ordinary non-deprecated"),
    ],
)
def test_selection_rejects_unusable_metadata(contents, message):
    selector = load_selector()
    with pytest.raises(selector.RunnerSelectionError, match=message):
        selector.select_oldest_macos_intel_runner(contents)
