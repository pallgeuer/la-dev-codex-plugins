"""Source-activated standalone launcher for Perform actions."""

import argparse
import sys
import tempfile
from pathlib import Path

from . import _perform_output as output
from . import _perform_runtime as launcher_runtime

COMMANDS = frozenset(("catalogue", "list", "run", "show"))
RUN_ONLY_DESTINATIONS = (
    "dry_run",
    "effort",
    "model",
    "non_interactive",
    "plan_effort",
    "qualification",
    "variables",
    "verbose",
)


class PerformArgumentParser(argparse.ArgumentParser):
    """Argument parser that raises launcher errors instead of exiting."""

    def __init__(self, *args, **kwargs):
        """Disable ambiguous long-option abbreviations."""
        kwargs["allow_abbrev"] = False
        super().__init__(*args, **kwargs)

    def error(self, message):
        """Raise one normal usage error."""
        raise launcher_runtime.CliError(message, code="invalid_arguments")


def normalize_argv(argv, parser=None):
    """Insert the default list or run command around shorthand invocations."""
    arguments = list(argv)
    argument_parser = build_parser() if parser is None else parser
    options_with_values = frozenset(option for action in argument_parser._actions if action.nargs != 0 for option in action.option_strings)
    if arguments == ["help"]:
        return ["--help"]
    positional_index = None
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument == "--":
            break
        if argument == "-h" or argument == "--help":
            return arguments
        if argument.startswith("--") and "=" in argument:
            index += 1
            continue
        if argument in options_with_values:
            index += 2
            continue
        if argument.startswith("-"):
            index += 1
            continue
        positional_index = index
        break
    if positional_index is None:
        return ["list", *arguments]
    if arguments[positional_index] in COMMANDS:
        return arguments
    return [*arguments[:positional_index], "run", *arguments[positional_index:]]


def split_codex_remainder(argv):
    """Split the explicit raw Codex remainder from launcher arguments."""
    arguments = list(argv)
    try:
        separator = arguments.index("--")
    except ValueError:
        return arguments, []
    return arguments[:separator], arguments[separator + 1 :]


def build_parser():
    """Build the complete standalone Perform command parser."""
    parser = PerformArgumentParser(prog="codex-perform", description="Discover, inspect, and launch configured Perform actions.")
    parser.add_argument("command", choices=sorted(COMMANDS), help="Catalogue, list, show, or run actions.")
    parser.add_argument("action", nargs="?", help="Bare action name or strict ACTION[LANGUAGE] selector.")
    parser.add_argument("--plugin-root", help="Explicit toolkit plugin root, bypassing installed-plugin discovery.")
    parser.add_argument("--codex", default="codex", help="Codex executable used for plugin discovery and launch.")
    parser.add_argument("--cwd", help="Directory used for action discovery and the launched Codex working root.")
    parser.add_argument("-l", "--language", help="Exact language variant or listing filter.")
    parser.add_argument("--var", dest="variables", action="append", default=[], metavar="NAME=VALUE", help="Bind one prompt variable; repeat for multiple variables.")
    parser.add_argument("--qualification", help="Append one compatible qualification while rendering.")
    parser.add_argument("--model", help="Override the action model.")
    parser.add_argument("--effort", help="Override normal model reasoning effort.")
    parser.add_argument("--plan-effort", help="Override Plan-mode reasoning effort.")
    parser.add_argument("--non-interactive", action="store_true", help="Launch noninteractive codex exec instead of interactive Codex.")
    parser.add_argument("--verbose", action="store_true", help="Show prelaunch context and Codex progress for an explicitly noninteractive run.")
    parser.add_argument("--dry-run", action="store_true", help="Display the complete launch without executing Codex.")
    parser.add_argument("--output", help="Action catalogue output path; relative paths resolve from the repository root and may use parent traversal.")
    parser.add_argument("--json", action="store_true", help="Use launcher JSON for catalogue/list/show/dry-run or select noninteractive Codex JSONL for a run.")
    return parser


def _reject_irrelevant_options(args, codex_args, parser):
    """Reject options that do not belong to the selected command."""
    if args.command == "run" and args.output is None:
        return
    defaults = parser.parse_args(["list"])
    used = []
    rejected_destinations = RUN_ONLY_DESTINATIONS if args.command != "run" else ()
    if args.command == "catalogue":
        rejected_destinations = (*rejected_destinations, "language")
        if args.action is not None:
            used.append("action")
    elif args.output is not None:
        used.append("output")
    for destination in rejected_destinations:
        value = getattr(args, destination)
        if value != getattr(defaults, destination):
            used.append(destination)
    if codex_args and args.command != "run":
        used.append("Codex arguments after --")
    if used:
        raise launcher_runtime.CliError("{} does not accept these options or arguments: {}.".format(args.command, ", ".join(used)), code="invalid_arguments")


def _run_command(args, codex_args, runtime, launcher, environment):
    """Prepare, inspect, or execute one selected action."""
    if args.action is None:
        raise launcher_runtime.CliError("run requires an action name or strict selector.", code="invalid_arguments")
    if args.verbose and not args.non_interactive:
        raise launcher_runtime.CliError("--verbose requires --non-interactive.", code="invalid_arguments")
    if args.verbose and args.json:
        raise launcher_runtime.CliError("--verbose cannot be combined with --json.", code="invalid_arguments")
    spec = launcher.prepare_launch(args.action, language=args.language, variable_bindings=args.variables, qualification=args.qualification)
    overrides = runtime.LaunchOverrides(
        model=args.model,
        reasoning_effort=args.effort,
        plan_reasoning_effort=args.plan_effort,
        non_interactive=args.non_interactive,
        extra_codex_args=codex_args,
        cwd=args.resolved_cwd,
        json_output=args.json,
    )
    codex_executable = args.resolved_codex or launcher_runtime.resolve_codex_executable(args.codex, args.original_cwd, env=environment)
    invocation = runtime.build_codex_invocation(spec, codex_executable=codex_executable, overrides=overrides)
    output_mode = "jsonl" if args.json else "verbose" if args.verbose else "final-only" if invocation.non_interactive else "interactive"
    if args.dry_run:
        if args.json:
            payload = invocation.to_dict()
            payload["output_mode"] = output_mode
            output.write_json(payload)
        else:
            output.print_dry_run(invocation, output_mode)
        return 0
    if output_mode == "final-only":
        return _run_final_only(invocation, spec, environment)
    output.display_prelaunch(spec)
    try:
        launcher_runtime.replace_process(invocation.argv, env=environment)
    except (OSError, UnicodeError, ValueError) as exc:
        raise launcher_runtime.CliError("Could not launch Codex: {}".format(exc), exit_code=4, code="launch_failed") from exc


def _run_final_only(invocation, spec, environment):
    """Run Codex with inherited stdout while hiding successful stderr."""
    sys.stderr.flush()
    sys.stdout.flush()
    try:
        with tempfile.TemporaryFile(mode="w+b") as captured_stderr:
            returncode = launcher_runtime.run_supervised_process(invocation.argv, env=environment, stderr=captured_stderr)
            if returncode != 0:
                output.display_prelaunch(spec)
                captured_stderr.seek(0)
                while True:
                    chunk = captured_stderr.read(8192)
                    if not chunk:
                        break
                    output.write_bytes(chunk, stream=sys.stderr)
                sys.stderr.flush()
            return returncode
    except (OSError, UnicodeError, ValueError) as exc:
        raise launcher_runtime.CliError("Could not launch Codex: {}".format(exc), exit_code=4, code="launch_failed") from exc


def _show_command(args, launcher):
    """Show built-in help or one complete effective action."""
    if args.action is None:
        raise launcher_runtime.CliError("show requires an action name or strict selector.", code="invalid_arguments")
    payload = launcher.show_action(args.action, language=args.language)
    if args.json:
        output.write_json(payload)
    else:
        output.write_json(payload, pretty=True)
    return 0


def _list_command(args, launcher):
    """List effective action summaries."""
    payload = launcher.list_actions(action=args.action, language=args.language)
    if args.json:
        output.write_json(payload)
    else:
        output.print_list(payload)
    return 3 if launcher.precedence_incomplete else 0


def _catalogue_command(args, launcher):
    """Write the effective action catalogue without launching Codex."""
    payload = launcher.write_action_catalogue(output=args.output)
    if args.json:
        output.write_json(payload)
    else:
        output.print_catalogue(payload)
    return 0


def _normalize_error(exc):
    """Convert one runtime exception to the launcher error contract."""
    if isinstance(exc, launcher_runtime.CliError):
        return exc
    status = getattr(exc, "status", None)
    if isinstance(status, str):
        return launcher_runtime.CliError(
            getattr(exc, "message", str(exc)),
            exit_code=3 if status == "fatal_catalog" else 4 if status == "runtime_error" else 2,
            code=status,
            alternatives=getattr(exc, "alternatives", None),
            diagnostics=getattr(exc, "diagnostics", None),
        )
    return launcher_runtime.CliError(str(exc), exit_code=4, code="runtime_error")


def main(argv=None):
    """Run the source-activated Perform launcher."""
    raw_arguments = list(sys.argv[1:] if argv is None else argv)
    raw_launcher_arguments, _raw_codex_args = split_codex_remainder(raw_arguments)
    json_requested = "--json" in raw_launcher_arguments
    try:
        parser = build_parser()
        normalized = normalize_argv(raw_arguments, parser=parser)
        launcher_arguments, codex_args = split_codex_remainder(normalized)
        args = parser.parse_args(launcher_arguments)
        args.original_cwd = str(Path.cwd())
        args.resolved_cwd = launcher_runtime.resolve_directory(args.cwd or args.original_cwd)
        environment = launcher_runtime.normalize_codex_environment(args.resolved_cwd)
        _reject_irrelevant_options(args, codex_args, parser)
        runtime, args.resolved_codex = launcher_runtime.load_runtime(args.plugin_root, args.codex, args.resolved_cwd, args.original_cwd, env=environment)
        launcher = runtime.load_standalone_launcher(args.resolved_cwd, env=environment)
        if args.command == "catalogue":
            return _catalogue_command(args, launcher)
        if args.command == "list":
            return _list_command(args, launcher)
        if args.command == "show":
            return _show_command(args, launcher)
        return _run_command(args, codex_args, runtime, launcher, environment)
    except Exception as exc:
        return output.emit_error(_normalize_error(exc), json_requested)


if __name__ == "__main__":
    sys.exit(main())
