#!/usr/bin/env python3
"""Inspect or render one strict Perform action selector."""

import argparse
import json
import sys
from pathlib import Path

import toolkit_perform_runtime as runtime


def _bundled_actions_dir():
    """Resolve the installed skill's adjacent bundled action directory."""
    return str(Path(__file__).resolve().parent.parent / "assets" / "toolkit_perform_actions")


def _parser():
    """Build the stable strict-action argument parser."""
    parser = argparse.ArgumentParser(description="Inspect or render one strict Perform action selector.")
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--inspect", metavar="ACTION[LANGUAGE]", help="Inspect one canonical strict selector.")
    operation.add_argument("--request-json", choices=("-",), help="Read one versioned inspect/render request from stdin.")
    parser.add_argument("--cwd", default=str(Path.cwd()), help="Working directory used for conventional local discovery.")
    parser.add_argument("--json", action="store_true", help="Emit the versioned JSON response envelope.")
    return parser


def _print_diagnostics(diagnostics):
    """Print concise human diagnostics outside the authoritative prompt."""
    visible = [diagnostic for diagnostic in diagnostics if diagnostic.severity in ("warning", "error")]
    if not visible:
        return
    print("Diagnostics:", file=sys.stderr)
    for diagnostic in visible:
        location = diagnostic.source_file or "discovery"
        if diagnostic.json_path:
            location += diagnostic.json_path
        print("- {} {}: {} ({})".format(diagnostic.severity, diagnostic.code, diagnostic.message, location), file=sys.stderr)


def _emit_json(catalog, status, result):
    """Write one stable versioned response envelope."""
    print(json.dumps(runtime.response_envelope(catalog, status, result), sort_keys=True, indent=2, ensure_ascii=False))


def _exit_code(status):
    """Map authoritative JSON status to the documented shell classes."""
    if status in ("ok", "built_in_help"):
        return 0
    if status == "fatal_catalog":
        return 3
    return 2


def _human_result(operation, result):
    """Print prompt data to stdout and user-facing notes separately."""
    if operation == "inspect":
        print(result["base_prompt"])
    else:
        print(result["prompt"])
    if result.get("notes"):
        print("Notes: {}".format(result["notes"]), file=sys.stderr)


def main(argv=None):
    """Load the catalog and fulfill one strict inspect or stdin-render request."""
    args = _parser().parse_args(argv)
    try:
        if args.inspect is not None:
            request = {"schema_version": runtime.SCHEMA_VERSION, "operation": "inspect", "selector": args.inspect}
        else:
            raw = sys.stdin.buffer.read(runtime.MAX_REQUEST_BYTES + 1)
            request = runtime.decode_request_bytes(raw)
        request = runtime.validate_request(request)
        catalog = runtime.load_action_catalog(bundled_dir=_bundled_actions_dir(), cwd=args.cwd)
        result = runtime.process_request(catalog, request)
    except runtime.CatalogRequestError as exc:
        status = exc.status
        result = exc.to_dict()
        if "catalog" in locals():
            if args.json:
                _emit_json(catalog, status, result)
            else:
                print(exc.message, file=sys.stderr)
                _print_diagnostics(catalog.diagnostics)
        elif args.json:
            print(json.dumps({"schema_version": runtime.SCHEMA_VERSION, "status": status, "discovery": {}, "diagnostics": [], "result": result}, sort_keys=True, indent=2, ensure_ascii=False))
        else:
            print(exc.message, file=sys.stderr)
        return _exit_code(status)
    except Exception as exc:
        if args.json:
            print(json.dumps({"schema_version": runtime.SCHEMA_VERSION, "status": "runtime_error", "discovery": {}, "diagnostics": [], "result": {"message": str(exc)}}, sort_keys=True, indent=2))
        else:
            print("Unexpected Perform runtime failure: {}".format(exc), file=sys.stderr)
        return 4

    if args.json:
        _emit_json(catalog, "ok", result)
    else:
        _human_result(request["operation"], result)
        _print_diagnostics(catalog.diagnostics)
    return 0


if __name__ == "__main__":
    sys.exit(main())
