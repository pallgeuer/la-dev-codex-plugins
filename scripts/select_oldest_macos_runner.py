#!/usr/bin/env python3
"""Select the oldest non-deprecated GA macOS Intel runner from image metadata."""

import re
import sys

TABLE_HEADER = ("Image", "Architecture", "YAML Label", "Included Software")
VERSION_RE = re.compile(r"^macOS ([0-9]+)(?:\s|<)")
SEPARATOR_RE = re.compile(r"^:?-+:?$")


class RunnerSelectionError(ValueError):
    """Runner-image metadata cannot produce one safe macOS Intel label."""


def _table_cells(line):
    """Return stripped cells from one Markdown table row."""
    if not line.startswith("|") or not line.endswith("|"):
        return None
    return tuple(cell.strip() for cell in line[1:-1].split("|"))


def _image_table_rows(metadata):
    """Return rows from the runner-images availability table."""
    lines = metadata.splitlines()
    header_index = next((index for index, line in enumerate(lines) if _table_cells(line) == TABLE_HEADER), None)
    if header_index is None:
        raise RunnerSelectionError("runner-images metadata does not contain the expected image table")
    if header_index + 1 >= len(lines):
        raise RunnerSelectionError("runner-images metadata is missing the image-table separator")
    separator = _table_cells(lines[header_index + 1])
    if separator is None or len(separator) != len(TABLE_HEADER) or any(SEPARATOR_RE.fullmatch(cell) is None for cell in separator):
        raise RunnerSelectionError("runner-images metadata contains an invalid image-table separator")

    rows = []
    for line in lines[header_index + 2 :]:
        cells = _table_cells(line)
        if cells is None:
            break
        if len(cells) != len(TABLE_HEADER):
            raise RunnerSelectionError("runner-images metadata contains a malformed image-table row")
        rows.append(cells)
    return rows


def select_oldest_macos_intel_runner(metadata):
    """Return the oldest ordinary non-deprecated GA macOS Intel label."""
    candidates = {}
    for image, architecture, labels, _software in _image_table_rows(metadata):
        if not image.startswith("macOS ") or architecture != "x64":
            continue
        lowered_image = image.lower()
        if "deprecated" in lowered_image or "preview" in lowered_image:
            continue
        version_match = VERSION_RE.match(image)
        if version_match is None:
            raise RunnerSelectionError("runner-images metadata contains an unrecognized macOS image name")
        version = int(version_match.group(1))
        expected_label = "macos-{}-intel".format(version)
        available_labels = re.findall(r"`([^`]+)`", labels)
        if expected_label not in available_labels:
            continue
        intel_labels = [label for label in available_labels if re.fullmatch(r"macos-[0-9]+-intel", label) is not None]
        if intel_labels != [expected_label]:
            raise RunnerSelectionError("runner-images metadata contains ambiguous macOS {} Intel labels".format(version))
        if version in candidates:
            raise RunnerSelectionError("runner-images metadata contains duplicate eligible macOS {} rows".format(version))
        candidates[version] = expected_label
    if not candidates:
        raise RunnerSelectionError("runner-images metadata contains no ordinary non-deprecated GA macOS Intel runner")
    return candidates[min(candidates)]


def main():
    """Read runner metadata from stdin and print the selected label."""
    try:
        label = select_oldest_macos_intel_runner(sys.stdin.read())
    except RunnerSelectionError as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 1
    print(label)
    return 0


if __name__ == "__main__":
    sys.exit(main())
