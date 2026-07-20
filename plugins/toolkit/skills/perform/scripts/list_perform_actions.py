#!/usr/bin/env python3
"""List effective Perform actions as compact JSON."""

import sys
from pathlib import Path

import toolkit_perform_runtime as runtime


def _parser():
    """Build the stable bundled-script argument parser."""
    parser = runtime.JsonArgumentParser(description="List effective Perform action variants as compact JSON.")
    parser.add_argument("--name", action="store_once", help="Narrow to one exact bare action name.")
    parser.add_argument("--fallback", action="store_once", nargs=0, const=True, default=False, help="List the full catalog when --name has no effective variants.")
    parser.add_argument("--cwd", action="store_once", default=str(Path.cwd()), help="Working directory used for conventional local discovery.")
    return parser


def main(argv=None):
    """Discover, load, and list actions with an optional one-call fallback."""
    parser = _parser()
    args = parser.parse_args(argv)
    if args.fallback and args.name is None:
        parser.error("--fallback requires --name.")

    def command(context):
        catalog = context.load_catalog(args.cwd)
        summaries = catalog.list_actions(name=args.name)
        if args.name is not None and not summaries and args.fallback:
            summaries = catalog.list_actions()
        result = {"variants": [summary.to_dict() for summary in summaries]}
        if catalog.precedence_incomplete:
            error = runtime.CatalogRequestError("fatal_catalog", "Catalog precedence is incomplete; fix the fatal discovery or file diagnostic before executing an action.")
            return runtime.CliOutcome(result=result, error=error)
        if args.name is not None and not summaries:
            error = runtime.CatalogRequestError("not_found", "No effective variants found for action name {!r}.".format(args.name))
            return runtime.CliOutcome(error=error)
        return runtime.CliOutcome(result=result)

    return runtime.run_cli(command)


if __name__ == "__main__":
    sys.exit(main())
