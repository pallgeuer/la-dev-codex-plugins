"""Locale-independent output rendering for the Perform launcher."""

import json
import os
import sys
import unicodedata

_BASH_SAFE_BYTES = frozenset(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_@%+=:,./-")


def write_text(value, stream=None):
    """Write text as UTF-8 independently of the process locale."""
    target = sys.stdout if stream is None else stream
    encoded = value.encode("utf-8", errors="backslashreplace")
    if hasattr(target, "buffer"):
        target.buffer.write(encoded)
    else:
        target.write(encoded.decode("utf-8"))


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


def print_list(payload):
    """Print action summaries as a small human-readable table."""
    variants = payload["variants"]
    lines = []
    if not variants:
        lines.append("No matching Perform actions.")
    else:
        width = max(len(variant["selector"]) for variant in variants)
        lines.append("{:<{}}  {}".format("SELECTOR", width, "GLOSS"))
        for variant in variants:
            lines.append("{:<{}}  {}".format(variant["selector"], width, variant["gloss"]))
            for name, description in variant.get("prompt_vars", {}).items():
                lines.append("{:<{}}  {}: {}".format("", width, name, description))
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


def print_dry_run(invocation):
    """Print a complete human dry-run and exact Bash argv."""
    write_json(invocation.to_dict(), pretty=True)
    write_text("bash command:\n{}\n".format(bash_command(invocation.argv)))


def _stderr_supports_color():
    """Return whether automatic prompt color is appropriate."""
    return sys.stderr.isatty() and "NO_COLOR" not in os.environ and os.environ.get("TERM") != "dumb"


def display_prelaunch(spec):
    """Show safely escaped notes, action args, and prompt on stderr."""
    config = spec.config
    pieces = []
    if config.notes:
        pieces.append(escape_terminal_text(config.notes))
        if not config.notes.endswith("\n"):
            pieces.append("\n")
    pieces.append("PERFORM: {}\n".format(config.selector))
    if config.custom_codex_args:
        pieces.append("CODEX ACTION ARGS: {}\n".format(bash_command(config.custom_codex_args)))
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
