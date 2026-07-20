#!/usr/bin/env python3
"""List effective Perform actions in human or structured form."""

import argparse
import json
import sys
from pathlib import Path

import toolkit_perform_runtime as runtime


def _bundled_actions_dir():
    """Resolve the installed skill's adjacent bundled action directory."""
    return str(Path(__file__).resolve().parent.parent / "assets" / "toolkit_perform_actions")


def _parser():
    """Build the stable bundled-script argument parser."""
    parser = argparse.ArgumentParser(description="List effective Perform action variants.")
    parser.add_argument("--name", help="Narrow to one exact bare action name.")
    parser.add_argument("--cwd", default=str(Path.cwd()), help="Working directory used for conventional local discovery.")
    parser.add_argument("--json", action="store_true", help="Emit the versioned JSON response envelope.")
    return parser


def _print_diagnostics(diagnostics):
    """Print concise human diagnostics separately from action lines."""
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
    """Write one response envelope without logging noise."""
    print(json.dumps(runtime.response_envelope(catalog, status, result), sort_keys=True, indent=2, ensure_ascii=False))


def main(argv=None):
    """Discover, load, and list actions with documented exit-code classes."""
    args = _parser().parse_args(argv)
    try:
        catalog = runtime.load_action_catalog(bundled_dir=_bundled_actions_dir(), cwd=args.cwd)
        summaries = catalog.list_actions(name=args.name)
    except runtime.CatalogRequestError as exc:
        if "catalog" not in locals():
            print(exc.message, file=sys.stderr)
            return 4
        result = exc.to_dict()
        if args.json:
            _emit_json(catalog, exc.status, result)
        else:
            print(exc.message, file=sys.stderr)
            _print_diagnostics(catalog.diagnostics)
        return 2
    except Exception as exc:
        if args.json:
            print(json.dumps({"schema_version": runtime.SCHEMA_VERSION, "status": "runtime_error", "discovery": {}, "diagnostics": [], "result": {"message": str(exc)}}, sort_keys=True, indent=2))
        else:
            print("Unexpected Perform runtime failure: {}".format(exc), file=sys.stderr)
        return 4

    result = {"name_filter": args.name, "variants": [summary.to_dict() for summary in summaries]}
    if catalog.precedence_incomplete:
        status = "fatal_catalog"
        exit_code = 3
    elif args.name is not None and not summaries:
        status = "not_found"
        exit_code = 2
    else:
        status = "ok"
        exit_code = 0
    if args.json:
        _emit_json(catalog, status, result)
    else:
        for summary in summaries:
            print("{}: {}".format(summary.selector, summary.gloss))
        if status == "not_found":
            print("No effective variants found for action name {!r}.".format(args.name), file=sys.stderr)
        _print_diagnostics(catalog.diagnostics)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
