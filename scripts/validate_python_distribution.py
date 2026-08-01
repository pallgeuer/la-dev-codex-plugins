#!/usr/bin/env python3
"""Validate the exact contents and metadata of Python distribution archives."""

import argparse
import email.parser
import pathlib
import sys
import tarfile
import zipfile

DISTRIBUTION_NAME = "la-dev-codex-plugins"
NORMALIZED_NAME = "la_dev_codex_plugins"
PACKAGE_FILES = {
    "la_dev_codex_plugins/__init__.py",
    "la_dev_codex_plugins/_filesystem.py",
    "la_dev_codex_plugins/_process.py",
    "la_dev_codex_plugins/codex_perform/__init__.py",
    "la_dev_codex_plugins/codex_perform/_output.py",
    "la_dev_codex_plugins/codex_perform/_runtime.py",
    "la_dev_codex_plugins/codex_perform/cli.py",
    "la_dev_codex_plugins/markdown_tables/__init__.py",
    "la_dev_codex_plugins/markdown_tables/cli.py",
    "la_dev_codex_plugins/markdown_tables/files.py",
    "la_dev_codex_plugins/markdown_tables/formatter.py",
    "la_dev_codex_plugins/markdown_tables/models.py",
    "la_dev_codex_plugins/markdown_tables/parser.py",
    "la_dev_codex_plugins/markdown_tables/selection.py",
    "la_dev_codex_plugins/pytest_isolation/__init__.py",
    "la_dev_codex_plugins/pytest_isolation/plugin.py",
    "la_dev_codex_plugins/release_checksums/__init__.py",
    "la_dev_codex_plugins/release_checksums/cli.py",
    "la_dev_codex_plugins/release_checksums/core.py",
}
CONSOLE_SCRIPTS = {
    "la-dev-markdown-tables": "la_dev_codex_plugins.markdown_tables.cli:main",
    "la-dev-release-checksums": "la_dev_codex_plugins.release_checksums.cli:main",
}
OPTIONAL_REQUIREMENTS = {
    'pytest>=7.0.1; extra == "dev"',
    'pytest>=7.0.1; extra == "pytest"',
}
SDIST_NON_PACKAGE_FILES = {
    "LICENSE",
    "MANIFEST.in",
    "PKG-INFO",
    "PYPI.md",
    "package_scripts/codex-perform",
    "pyproject.toml",
    "setup.cfg",
    "setup.py",
    "src/la_dev_codex_plugins.egg-info/PKG-INFO",
    "src/la_dev_codex_plugins.egg-info/SOURCES.txt",
    "src/la_dev_codex_plugins.egg-info/dependency_links.txt",
    "src/la_dev_codex_plugins.egg-info/entry_points.txt",
    "src/la_dev_codex_plugins.egg-info/requires.txt",
    "src/la_dev_codex_plugins.egg-info/top_level.txt",
    "tests/python_distribution/smoke_installed_package.py",
    "tests/python_distribution/smoke_pytest_isolation.py",
}
SDIST_FILES = SDIST_NON_PACKAGE_FILES | {"src/{}".format(path) for path in PACKAGE_FILES}


class DistributionValidationError(Exception):
    """Invalid Python distribution archive."""


def _require(condition, message):
    """Raise one distribution validation failure."""
    if not condition:
        raise DistributionValidationError(message)


def _metadata(data, label):
    """Parse and validate shared core metadata."""
    metadata = email.parser.BytesParser().parsebytes(data)
    _require(metadata.get("Name") == DISTRIBUTION_NAME, "{} has unexpected Name {!r}".format(label, metadata.get("Name")))
    _require(metadata.get("Requires-Python") == ">=3.6", "{} has unexpected Requires-Python {!r}".format(label, metadata.get("Requires-Python")))
    _require(metadata.get("License") == "MIT", "{} has unexpected License {!r}".format(label, metadata.get("License")))
    _require(set(metadata.get_all("Provides-Extra", [])) == {"dev", "pytest"}, "{} has unexpected optional extras {!r}".format(label, metadata.get_all("Provides-Extra")))
    _require(set(metadata.get_all("Requires-Dist", [])) == OPTIONAL_REQUIREMENTS, "{} has unexpected dependency declarations {!r}".format(label, metadata.get_all("Requires-Dist")))
    return metadata


def _entry_points(data, label):
    """Parse and validate installed console entry points."""
    entries = {}
    section = None
    for raw_line in data.decode("utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            _require(section == "console_scripts", "{} has unexpected entry-point group {!r}".format(label, section))
            continue
        _require(section == "console_scripts" and "=" in line, "{} has malformed entry point {!r}".format(label, raw_line))
        name, target = (part.strip() for part in line.split("=", 1))
        _require(name not in entries, "{} repeats console script {!r}".format(label, name))
        entries[name] = target
    _require(entries == CONSOLE_SCRIPTS, "{} has unexpected console scripts {!r}".format(label, entries))


def _validate_wheel(path, version):
    """Validate one pure-Python wheel and return its archive members."""
    expected_filename = "{}-{}-py3-none-any.whl".format(NORMALIZED_NAME, version)
    _require(path.name == expected_filename, "Expected wheel {}, found {}".format(expected_filename, path.name))
    dist_info = "{}-{}.dist-info".format(NORMALIZED_NAME, version)
    data_root = "{}-{}.data".format(NORMALIZED_NAME, version)
    expected = set(PACKAGE_FILES)
    expected.update(
        {
            "{}/METADATA".format(dist_info),
            "{}/RECORD".format(dist_info),
            "{}/WHEEL".format(dist_info),
            "{}/entry_points.txt".format(dist_info),
            "{}/licenses/LICENSE".format(dist_info),
            "{}/top_level.txt".format(dist_info),
            "{}/scripts/codex-perform".format(data_root),
        }
    )
    with zipfile.ZipFile(str(path)) as archive:
        names = set(archive.namelist())
        _require(names == expected, "Wheel contents differ from the required manifest: missing={}, unexpected={}".format(sorted(expected - names), sorted(names - expected)))
        metadata = _metadata(archive.read("{}/METADATA".format(dist_info)), "wheel metadata")
        _require(metadata.get("Version") == version, "Wheel metadata version {!r} does not match {!r}".format(metadata.get("Version"), version))
        wheel_text = archive.read("{}/WHEEL".format(dist_info)).decode("utf-8")
        _require("Root-Is-Purelib: true\n" in wheel_text, "Wheel is not marked as purelib")
        _require("Tag: py3-none-any\n" in wheel_text, "Wheel does not contain the py3-none-any tag")
        _entry_points(archive.read("{}/entry_points.txt".format(dist_info)), "wheel entry points")
        bootstrap = archive.read("{}/scripts/codex-perform".format(data_root))
        _require(bootstrap.startswith(b"#!python\n"), "Installed bootstrap does not use the wheel #!python marker")
        _require(b'"-I", "-m", "la_dev_codex_plugins.codex_perform.cli"' in bootstrap, "Installed bootstrap does not re-execute the isolated Perform module")
    return expected


def _validate_sdist(path, version):
    """Validate one minimal source distribution and return its archive members."""
    expected_filename = "{}-{}.tar.gz".format(NORMALIZED_NAME, version)
    _require(path.name == expected_filename, "Expected sdist {}, found {}".format(expected_filename, path.name))
    expected_root = "{}-{}".format(NORMALIZED_NAME, version)
    with tarfile.open(str(path), mode="r:gz") as archive:
        members = archive.getmembers()
        _require(all(member.isdir() or member.isfile() for member in members), "Sdist must contain only directories and regular files")
        file_names = set()
        for member in members:
            member_path = pathlib.PurePosixPath(member.name)
            _require(member_path.parts and member_path.parts[0] == expected_root, "Sdist member escapes the expected root: {}".format(member.name))
            if member.isfile():
                file_names.add(str(pathlib.PurePosixPath(*member_path.parts[1:])))
        _require(file_names == SDIST_FILES, "Sdist contents differ from the required manifest: missing={}, unexpected={}".format(sorted(SDIST_FILES - file_names), sorted(file_names - SDIST_FILES)))
        package_info = archive.extractfile("{}/PKG-INFO".format(expected_root))
        if package_info is None:
            raise DistributionValidationError("Sdist does not contain PKG-INFO")
        metadata = _metadata(package_info.read(), "sdist metadata")
        _require(metadata.get("Version") == version, "Sdist metadata version {!r} does not match {!r}".format(metadata.get("Version"), version))
    return SDIST_FILES


def validate_distribution_directory(dist_directory, version):
    """Validate exactly one wheel and one sdist in a directory."""
    root = pathlib.Path(dist_directory)
    _require(root.is_dir(), "Distribution directory does not exist: {}".format(root))
    archives = sorted(path for path in root.iterdir() if path.is_file())
    wheels = [path for path in archives if path.suffix == ".whl"]
    sdists = [path for path in archives if path.name.endswith(".tar.gz")]
    _require(len(archives) == 2 and len(wheels) == 1 and len(sdists) == 1, "Distribution directory must contain exactly one wheel and one .tar.gz sdist")
    _validate_wheel(wheels[0], version)
    _validate_sdist(sdists[0], version)
    return wheels[0], sdists[0]


def main(argv=None):
    """Validate command-line distribution arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dist_directory")
    parser.add_argument("--version", required=True)
    args = parser.parse_args(argv)
    try:
        wheel, sdist = validate_distribution_directory(args.dist_directory, args.version)
    except (OSError, tarfile.TarError, zipfile.BadZipFile, DistributionValidationError) as error:
        print("error: {}".format(error), file=sys.stderr)
        return 1
    print("Python distributions are valid: {}, {}".format(wheel.name, sdist.name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
