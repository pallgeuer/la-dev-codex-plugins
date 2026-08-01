"""Command-line interface for deterministic release checksum manifests."""

import argparse
import sys

from .. import __version__
from .. import _filesystem as filesystem
from . import core

_PREFIX = "la-dev-release-checksums:"


def _write_all(stream, payload, allow_none=False):
    offset = 0
    while offset < len(payload):
        written = stream.write(payload[offset:])
        if written is None and allow_none:
            return
        if not isinstance(written, int) or written <= 0 or written > len(payload) - offset:
            raise OSError("stdout returned an invalid write count")
        offset += written


def _write_manifest_stdout(manifest):
    data = manifest.encode("utf-8", "strict")
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is None:
        _write_all(sys.stdout, manifest, allow_none=True)
        flush = getattr(sys.stdout, "flush", None)
        if flush is not None:
            flush()
        return
    _write_all(buffer, data)
    buffer.flush()


def main(argv=None):
    """Generate one SHA-256 manifest and return the CLI status."""
    parser = argparse.ArgumentParser(prog="la-dev-release-checksums", description="Generate a deterministic SHA-256 manifest for release artifacts.")
    parser.add_argument("--output", required=True, help="Manifest output path.")
    parser.add_argument("--version", action="version", version="%(prog)s {}".format(__version__))
    parser.add_argument("artifacts", metavar="ARTIFACT", nargs="+", help="Release artifacts in manifest order.")
    arguments = parser.parse_args(argv)
    try:
        manifest = core.write_sha256_manifest(arguments.artifacts, arguments.output)
    except core.ReleaseChecksumError as exc:
        print("{} {}".format(_PREFIX, filesystem.escape_display_text(exc)), file=sys.stderr)
        return 1
    try:
        _write_manifest_stdout(manifest)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        print("{} Could not write manifest to stdout: {}".format(_PREFIX, filesystem.escape_display_text(exc)), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
