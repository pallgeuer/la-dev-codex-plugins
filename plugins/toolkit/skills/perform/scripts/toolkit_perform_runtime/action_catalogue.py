"""Stable Markdown catalogues for effective Perform actions."""

import contextlib
import os
import stat
import uuid
from pathlib import Path

from . import catalog as catalog_module
from .diagnostics import PerformRequestError

CATALOGUE_MARKER = "<!-- toolkit-perform-action-catalogue:v1 -->"
DEFAULT_CATALOGUE_PARTS = (".codex", "toolkit_perform_actions", "action_catalogue.md")


def _ascii_key(value):
    """Return the deterministic sort key for validated ASCII identifiers."""
    return value.encode("ascii")


def _escape_markdown_text(value):
    """Escape configured display text inside a Markdown table cell."""
    return value.replace("&", "&amp;").replace("\\", "&#92;").replace("|", "&#124;").replace("<", "&lt;").replace(">", "&gt;").replace("`", "&#96;")


def _format_prompt_vars(prompt_vars):
    """Format one prompt-variable mapping for a table cell."""
    if not prompt_vars:
        return "None"
    return "<br>".join("`{}`: {}".format(name, _escape_markdown_text(prompt_vars[name])) for name in sorted(prompt_vars, key=_ascii_key))


def _format_variant_values(summaries, value_getter, value_formatter):
    """Format shared or language-specific values for one base action."""
    values = [value_getter(summary) for summary in summaries]
    if all(value == values[0] for value in values[1:]):
        return value_formatter(values[0])
    return "<br>".join("`{}`: {}".format(summary.language, value_formatter(value)) for summary, value in zip(summaries, values))


def _render_markdown_table(headers, rows, alignments):
    """Render one source-aligned Markdown table."""
    widths = [len(header) for header in headers]
    for row in rows:
        widths = [max(width, len(value)) for width, value in zip(widths, row)]

    def padded_row(row):
        cells = [value.center(width) if alignment == "center" else value.ljust(width) for value, width, alignment in zip(row, widths, alignments)]
        return "| {} |".format(" | ".join(cells))

    separators = [":{}:".format("-" * width) if alignment == "center" else "-" * (width + 2) for width, alignment in zip(widths, alignments)]
    return [padded_row(headers), "|{}|".format("|".join(separators))] + [padded_row(row) for row in rows]


def render_action_catalogue(summaries):
    """Render effective action summaries as stable Markdown and counts."""
    grouped = {}
    for summary in summaries:
        grouped.setdefault(summary.name, []).append(summary)

    lines = [
        CATALOGUE_MARKER,
        "# Perform Action Catalogue",
        "",
        "This file lists the effective Perform actions available in the current Perform context.",
        "",
        "Regenerate it with `$toolkit:perform update-action-catalogue` or `codex-perform catalogue`. Use a bare action name when its language is clear, or an exact `ACTION[LANGUAGE]` selector. The `agnostic` language is language-independent.",
        "",
    ]
    rows = []
    variant_count = 0
    for name in sorted(grouped, key=_ascii_key):
        action_summaries = sorted(grouped[name], key=lambda summary: _ascii_key(summary.language))
        variant_count += len(action_summaries)
        languages = ", ".join("`{}`".format(summary.language) for summary in action_summaries)
        descriptions = _format_variant_values(action_summaries, lambda summary: summary.gloss, _escape_markdown_text)
        inputs = _format_variant_values(action_summaries, lambda summary: summary.prompt_vars, _format_prompt_vars)
        rows.append(("`{}`".format(name), languages, descriptions, inputs))
    lines.extend(_render_markdown_table(("Action", "Languages", "Description", "Required inputs"), rows, ("left", "center", "left", "left")))
    lines.append("")
    return "\n".join(lines), len(grouped), variant_count


def _repository_root(catalog):
    """Return the discovered repository root, if any."""
    discovery = getattr(catalog, "discovery", None)
    return None if discovery is None else discovery.repository_root


def resolve_action_catalogue_path(catalog, output=None):
    """Resolve one default or explicit catalogue target and path policy."""
    repository_root = _repository_root(catalog)
    if output is None:
        if repository_root is None:
            raise PerformRequestError("repository_not_found", "The default action catalogue path requires a discovered repository root.")
        return Path(repository_root).joinpath(*DEFAULT_CATALOGUE_PARTS), True
    if not isinstance(output, str) or not output or "\x00" in output:
        raise PerformRequestError("invalid_output", "The action catalogue output must be a nonempty path without NUL characters.")
    expanded = Path(output).expanduser()
    if expanded.is_absolute():
        return Path(os.path.abspath(str(expanded))), False  # noqa: PTH100 - Preserve the final path component for symlink rejection.
    if repository_root is None:
        raise PerformRequestError("repository_not_found", "A relative action catalogue path requires a discovered repository root.")
    return Path(os.path.abspath(str(Path(repository_root) / expanded))), False  # noqa: PTH100 - Preserve the final path component for symlink rejection.


def _prepare_parent(path, create_parent):
    """Create the default parent or validate one custom parent."""
    parent = path.parent
    if create_parent:
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise PerformRequestError("runtime_error", "Could not create the default action catalogue directory {}: {}.".format(parent, exc)) from exc
    if not parent.is_dir():
        raise PerformRequestError("output_parent_missing", "The action catalogue parent directory does not exist: {}.".format(parent))


def _existing_bytes(path):
    """Read an existing safe target or return None when it is absent."""
    if path.is_symlink():
        raise PerformRequestError("unsafe_output", "Refusing to replace a symbolic-link action catalogue target: {}.".format(path))
    if not path.exists():
        return None
    if not path.is_file():
        raise PerformRequestError("unsafe_output", "The action catalogue target is not a regular file: {}.".format(path))
    try:
        return path.read_bytes()
    except OSError as exc:
        raise PerformRequestError("runtime_error", "Could not read the existing action catalogue {}: {}.".format(path, exc)) from exc


def _has_catalogue_marker(content):
    """Return whether nonempty bytes carry the exact generated marker."""
    return bool(content) and content.splitlines()[0] == CATALOGUE_MARKER.encode("ascii")


def _atomic_write(path, content, previous_mode=None):
    """Atomically replace one catalogue with complete UTF-8 bytes."""
    descriptor = None
    temporary_path = None
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_BINARY"):
            flags |= os.O_BINARY
        while True:
            temporary_path = path.parent / ".action_catalogue.{}.tmp".format(uuid.uuid4().hex)
            try:
                descriptor = os.open(str(temporary_path), flags, 0o666)
                break
            except FileExistsError:
                continue
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = None
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if previous_mode is not None:
            temporary_path.chmod(previous_mode)
        temporary_path.replace(path)
        temporary_path = None
    except OSError as exc:
        raise PerformRequestError("runtime_error", "Could not write the action catalogue {}: {}.".format(path, exc)) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary_path is not None:
            with contextlib.suppress(OSError):
                temporary_path.unlink()


def write_action_catalogue(catalog, output=None):
    """Render and safely update one stable action catalogue."""
    if not isinstance(catalog, catalog_module.ActionCatalog):
        raise TypeError("catalog must be an ActionCatalog")
    if catalog.precedence_incomplete:
        raise PerformRequestError("fatal_catalog", "Catalog precedence is incomplete; fix the fatal discovery or file diagnostic before writing an action catalogue.")
    path, create_parent = resolve_action_catalogue_path(catalog, output=output)
    _prepare_parent(path, create_parent)
    rendered, action_count, variant_count = render_action_catalogue(catalog.list_actions())
    content = rendered.encode("utf-8")
    existing = _existing_bytes(path)
    if existing == content:
        changed = False
    else:
        if existing and not _has_catalogue_marker(existing):
            raise PerformRequestError("unsafe_output", "Refusing to replace a nonempty file without the Perform action catalogue marker: {}.".format(path))
        previous_mode = None if existing is None else stat.S_IMODE(path.stat().st_mode)
        _atomic_write(path, content, previous_mode=previous_mode)
        changed = True
    return {
        "path": str(path),
        "changed": changed,
        "action_count": action_count,
        "variant_count": variant_count,
    }


__all__ = (
    "CATALOGUE_MARKER",
    "DEFAULT_CATALOGUE_PARTS",
    "render_action_catalogue",
    "resolve_action_catalogue_path",
    "write_action_catalogue",
)
