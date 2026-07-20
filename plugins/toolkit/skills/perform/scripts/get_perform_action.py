#!/usr/bin/env python3
"""Inspect or render one strict Perform action as compact JSON."""

import sys
from pathlib import Path

import toolkit_perform_runtime as runtime


def _parser():
    """Build the strict-action direct-argument parser."""
    parser = runtime.JsonArgumentParser(description="Inspect or render one strict Perform action as compact JSON.")
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--inspect", action="store_once", metavar="ACTION[LANGUAGE]", help="Inspect one canonical strict selector.")
    operation.add_argument("--render", action="store_once", metavar="ACTION[LANGUAGE]", help="Render one canonical strict selector.")
    parser.add_argument("--var", action="append", default=[], metavar="%NAME%=VALUE", help="Bind one prompt variable; repeat for multiple variables.")
    parser.add_argument("--qualification", action="store_once", help="Append one compatible qualification during rendering.")
    parser.add_argument("--cwd", action="store_once", default=str(Path.cwd()), help="Working directory used for conventional local discovery.")
    return parser


def _parse_variables(bindings):
    """Parse repeated placeholder=value arguments without evaluating values."""
    variables = {}
    for binding in bindings:
        placeholder, separator, value = binding.partition("=")
        if not separator:
            raise runtime.CatalogRequestError("invalid_variable_argument", "Every --var argument must use %Name%=VALUE syntax.")
        if placeholder in variables:
            raise runtime.CatalogRequestError("duplicate_variable_argument", "Prompt variable {!r} was supplied more than once.".format(placeholder))
        variables[placeholder] = value
    return variables


def main(argv=None):
    """Load the catalog and fulfill one strict inspect or render request."""
    parser = _parser()
    args = parser.parse_args(argv)
    if args.inspect is not None and (args.var or args.qualification is not None):
        parser.error("--var and --qualification are valid only with --render.")

    def command(context):
        variables = _parse_variables(args.var)
        catalog = context.load_catalog(args.cwd)
        if args.inspect is not None:  # noqa: SIM108 - Keep operation dispatch readable.
            result = catalog.inspect(args.inspect).to_dict()
        else:
            result = catalog.render(args.render, variables, qualification=args.qualification).to_dict()
        return runtime.CliOutcome(result=result)

    return runtime.run_cli(command)


if __name__ == "__main__":
    sys.exit(main())
