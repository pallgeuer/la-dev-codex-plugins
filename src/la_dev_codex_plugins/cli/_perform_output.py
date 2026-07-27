"""Locale-independent output rendering for the Perform launcher."""

import json
import os
import shutil
import sys
import textwrap
import unicodedata

_BASH_SAFE_BYTES = frozenset(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_@%+=:,./-")
_DEFAULT_TABLE_WIDTH = 120
_MINIMUM_GLOSS_WIDTH = 40
_TABLE_COLUMN_SEPARATOR = "  "


def _write_encoded(value, target):
    """Write bytes exactly or as deterministic ASCII escapes."""
    if hasattr(target, "buffer"):
        target.buffer.write(value)
    else:
        text = value.decode("utf-8", errors="backslashreplace")
        target.write(text.encode("ascii", errors="backslashreplace").decode("ascii"))


def write_text(value, stream=None):
    """Write text as UTF-8 independently of the process locale."""
    target = sys.stdout if stream is None else stream
    _write_encoded(value.encode("utf-8", errors="backslashreplace"), target)


def write_bytes(value, stream=None):
    """Write exact bytes when possible and ASCII escapes otherwise."""
    target = sys.stdout if stream is None else stream
    _write_encoded(value, target)


def escape_terminal_text(value):
    """Return text whose untrusted controls are visible instead of active."""
    escaped = []
    for character in value:
        codepoint = ord(character)
        category = unicodedata.category(character)
        if character == "\n":
            escaped.append(character)
        elif character == "\\":
            escaped.append("\\\\")
        elif category.startswith("C") or category in ("Zl", "Zp"):
            if codepoint <= 0xFF:
                escaped.append("\\x{:02x}".format(codepoint))
            elif codepoint <= 0xFFFF:
                escaped.append("\\u{:04x}".format(codepoint))
            else:
                escaped.append("\\U{:08x}".format(codepoint))
        else:
            escaped.append(character)
    return "".join(escaped)


def _escape_json_terminal_controls(value):
    """Escape raw terminal controls while preserving JSON value semantics."""
    escaped = []
    for character in value:
        category = unicodedata.category(character)
        if character == "\n":
            escaped.append(character)
        elif category.startswith("C") or category in ("Zl", "Zp"):
            escaped.append(json.dumps(character, ensure_ascii=True)[1:-1])
        else:
            escaped.append(character)
    return "".join(escaped)


def write_json(value, stream=None, pretty=False):
    """Write semantically exact JSON without active terminal controls."""
    text = json.dumps(value, ensure_ascii=False, indent=2 if pretty else None, separators=None if pretty else (",", ":")) + "\n"
    write_text(_escape_json_terminal_controls(text), stream=stream)


def bash_quote(argument):
    """Quote one argument as exact terminal-safe Bash syntax."""
    encoded = argument.encode("utf-8", errors="surrogateescape")
    if encoded and all(byte in _BASH_SAFE_BYTES for byte in encoded):
        return encoded.decode("ascii")
    quoted = []
    for byte in encoded:
        if 32 <= byte < 127 and byte not in (39, 92):
            quoted.append(chr(byte))
        elif byte in (39, 92):
            quoted.append("\\{}".format(chr(byte)))
        else:
            quoted.append("\\{:03o}".format(byte))
    return "$'{}'".format("".join(quoted))


def bash_command(argv):
    """Return one exact terminal-safe Bash command for argv."""
    return " ".join(bash_quote(argument) for argument in argv)


def _terminal_width():
    """Return the available terminal width or the stable table default."""
    if not sys.stdout.isatty():
        return _DEFAULT_TABLE_WIDTH
    return shutil.get_terminal_size(fallback=(_DEFAULT_TABLE_WIDTH, 24)).columns


def _split_selector(selector):
    """Split one strict action selector into its name and language."""
    name, separator, language = selector.rpartition("[")
    if not separator or not language.endswith("]"):
        return selector, ""
    return name, language[:-1]


def _wrapped_lines(value, width, initial_indent="", subsequent_indent=""):
    """Wrap one table cell with explicit first and continuation indents."""
    return textwrap.wrap(value, width=width, initial_indent=initial_indent, subsequent_indent=subsequent_indent) or [initial_indent.rstrip()]


def print_list(payload):
    """Print action summaries as a small human-readable table."""
    variants = payload["variants"]
    lines = []
    if not variants:
        lines.append("No matching Perform actions.")
    else:
        rows = [(*_split_selector(variant["selector"]), variant) for variant in variants]
        name_width = max([len("NAME")] + [len(name) for name, _language, _variant in rows])
        language_width = max([len("LANGUAGE")] + [len(language) for _name, language, _variant in rows])
        gloss_indent = name_width + len(_TABLE_COLUMN_SEPARATOR) + language_width + len(_TABLE_COLUMN_SEPARATOR)
        gloss_width = max(_MINIMUM_GLOSS_WIDTH, _terminal_width() - gloss_indent)
        table_prefix = "{:<{}}{}{: <{}}{}".format("NAME", name_width, _TABLE_COLUMN_SEPARATOR, "LANGUAGE", language_width, _TABLE_COLUMN_SEPARATOR)
        continuation_prefix = " " * gloss_indent
        lines.append("{}GLOSS".format(table_prefix))
        for name, language, variant in rows:
            row_prefix = "{:<{}}{}{: <{}}{}".format(name, name_width, _TABLE_COLUMN_SEPARATOR, language, language_width, _TABLE_COLUMN_SEPARATOR)
            wrapped_gloss = _wrapped_lines(variant["gloss"], gloss_width)
            lines.append("{}{}".format(row_prefix, wrapped_gloss[0]))
            lines.extend("{}{}".format(continuation_prefix, line) for line in wrapped_gloss[1:])
            for variable_name, description in variant.get("prompt_vars", {}).items():
                variable_prefix = "{}: ".format(variable_name)
                if len(variable_prefix) < gloss_width:
                    wrapped_description = _wrapped_lines(description, gloss_width, initial_indent=variable_prefix, subsequent_indent=" " * len(variable_prefix))
                else:
                    wrapped_description = [variable_prefix.rstrip(), *_wrapped_lines(description, gloss_width)]
                lines.extend("{}{}".format(continuation_prefix, line) for line in wrapped_description)
    write_text("\n".join(lines) + "\n")
    for diagnostic in payload.get("diagnostics", []):
        write_text("Diagnostic: {}\n".format(escape_terminal_text(diagnostic)), stream=sys.stderr)


def print_catalogue(payload):
    """Print one human-readable action catalogue update result."""
    status = "Updated" if payload["changed"] else "Unchanged"
    path = escape_terminal_text(payload["path"])
    write_text("{} action catalogue: {} ({} actions, {} variants)\n".format(status, path, payload["action_count"], payload["variant_count"]))
    for diagnostic in payload.get("diagnostics", []):
        write_text("Diagnostic: {}\n".format(escape_terminal_text(diagnostic)), stream=sys.stderr)


def print_dry_run(invocation, output_mode):
    """Print a complete human dry-run and exact Bash argv."""
    payload = invocation.to_dict()
    payload["output_mode"] = output_mode
    write_json(payload, pretty=True)
    write_text("bash command:\n{}\n".format(bash_command(invocation.argv)))


def _stderr_supports_color():
    """Return whether automatic prompt color is appropriate."""
    return sys.stderr.isatty() and "NO_COLOR" not in os.environ and os.environ.get("TERM") != "dumb"


def display_prelaunch(spec, include_prompt=True):
    """Show safely escaped prelaunch context on stderr."""
    config = spec.config
    pieces = []
    if config.notes:
        pieces.append("NOTES TO USER:\n")
        pieces.append(escape_terminal_text(config.notes))
        if not config.notes.endswith("\n"):
            pieces.append("\n")
        pieces.append("\n")
    pieces.append("PERFORM: {}\n".format(config.selector))
    if config.custom_codex_args:
        pieces.append("CODEX ACTION ARGS: {}\n".format(bash_command(config.custom_codex_args)))
    if include_prompt:
        pieces.append("\nPROMPT:\n")
        prompt = escape_terminal_text(spec.rendered_prompt)
        if _stderr_supports_color():
            pieces.extend(("\033[32m", prompt, "\033[0m"))
        else:
            pieces.append(prompt)
        if not spec.rendered_prompt.endswith("\n"):
            pieces.append("\n")
    write_text("".join(pieces), stream=sys.stderr)
    sys.stderr.flush()
    sys.stdout.flush()


def emit_error(error, json_requested):
    """Write one launcher error and return its exit code."""
    if json_requested:
        write_json(error.to_dict())
    else:
        write_text("codex-perform: {}\n".format(escape_terminal_text(error.message)), stream=sys.stderr)
        if error.alternatives:
            write_text("Available variants: {}\n".format(", ".join(escape_terminal_text(alternative) for alternative in error.alternatives)), stream=sys.stderr)
        for diagnostic in error.diagnostics:
            write_text("Diagnostic: {}\n".format(escape_terminal_text(diagnostic)), stream=sys.stderr)
    return error.exit_code
