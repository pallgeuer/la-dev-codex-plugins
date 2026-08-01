# Markdown table formatting

`la-dev-codex-plugins` includes a dependency-free library, command, and published pre-commit hooks for canonical Markdown pipe tables. GitHub Flavored Markdown is the rendering baseline, while the source layout follows PyCharm's readable fully bordered and aligned presentation. The formatter is deliberately table-specific; it does not format headings, links, anchors, or general Markdown structure.

The implementation follows the [GFM table extension](https://github.github.com/gfm/#tables-extension-), the relevant CommonMark block rules, [PyCharm's Markdown table support](https://www.jetbrains.com/help/pycharm/markdown.html#tables), and the portability guidance in markdownlint MD055, MD056, and MD058.

## Canonical style

Canonical tables have leading and trailing pipes, one boundary space in header and body cells, no padding spaces in the delimiter row, and one shared source width per column:

```markdown
| Heading | Other |
|:--------|------:|
| Value   |  Text |
```

Every delimiter cell retains at least three dashes. A short aligned column is enlarged enough for its three dashes and alignment colons, and header/body cells are padded to the same slot width. Left and unaligned columns pad after content, right-aligned columns pad before it, and centered columns split padding with an odd extra space after the content.

Width is deterministic Python `len` over Unicode code points, not terminal display width. Combining marks, variation selectors, zero-width joiners, emoji components, East Asian wide characters, controls, and tabs each count as one code point. Existing content is never Unicode-normalized, and only ASCII spaces are inserted. Consequently, canonical source is stable and idempotent but may not appear visually aligned in every editor or font.

Only ASCII spaces and tabs at cell edges are structural padding. Nonbreaking spaces and every other Unicode character at an edge remain content. Meaningful internal whitespace and escaped content are preserved.

## Recognized input and safe repairs

Multi-column input may omit or inconsistently use outer pipes when unescaped internal pipes make cell ownership unambiguous. One-column tables require both borders. The formatter can safely:

- add and regularize outer borders;
- expand one- or two-dash delimiter cells and add missing trailing delimiter cells;
- add missing trailing empty body cells;
- normalize indentation, alignment, padding, and delimiter widths; and
- insert one safe container-correct blank line around top-level and blockquote tables.

An odd run of backslashes escapes a pipe; an even run leaves it structural. In accordance with GFM, unescaped pipes remain structural inside code spans, links, emphasis, and raw inline HTML. A pipe intended as cell content must be explicitly escaped, including inside backticks.

The parser protects fenced and indented code, all seven CommonMark HTML block classes, and leading YAML or TOML front matter, including unclosed regions. Fence and HTML opening and closing respect explicit blockquote and list-container ownership, including indentation relative to a list continuation; an unclosed block ends when its owning container ends. It supports top-level tables with zero through three spaces of indentation, consistently explicit blockquotes, and list tables beginning at the exact continuation column of an established list item. It does not guess through lazy list continuation, tab-derived nesting, inconsistent container ownership, or a table header on the same physical line as a list marker or ATX heading.

Blank lines are added only where the recognized boundary is safe. Existing blank lines are never removed. List-contained tables and tables following a contiguous possible lazy-list block receive no preceding boundary change. A one-column table followed by a plausible pipe-less row receives no following boundary change. These conservative omissions avoid changing list ownership or evicting a row into a paragraph.

An excess delimiter or body cell is unsafe because repairing it could discard or reassign content. The complete affected table remains byte-for-byte equivalent at the text level, a `malformed` issue is reported, and independently safe tables elsewhere in the document can still be formatted. Invalid delimiter-like prose that does not consist entirely of delimiter cells is ordinary Markdown rather than a malformed candidate.

These policies intentionally differ from pydocformatter's earlier repository helper: this package repairs conservative border variations, preserves non-ASCII edge whitespace, enforces three delimiter dashes and equal source slots, rejects ambiguous container indentation, protects HTML/front matter, supports explicit quote/list containers, isolates failures per table, and uses bounded Git discovery plus atomic file replacement.

## Library API

Import the public API from `la_dev_codex_plugins.markdown_tables`:

```python
from la_dev_codex_plugins import markdown_tables

result = markdown_tables.format_markdown_tables(source, path="docs/example.md")
if result.changed:
    print(result.text)
for issue in result.issues:
    print(issue.path, issue.line_number, issue.message)
```

The partial APIs are:

- `parse_markdown_tables(text)`: return all safely parsed tables and raise `MarkdownTableError` when any malformed candidate exists;
- `format_markdown_tables(text, path=None)`: return safe partial formatting plus every unresolved issue;
- `markdown_table_issues(text, path=None)`: expose proposed changes as `format` issues together with unresolved `malformed` issues;
- `format_markdown_tables_file(path, check=False)`: inspect one file and write all safe changes unless checking;
- `tracked_markdown_paths(root=None)`: return absolute tracked Markdown paths from the nearest enclosing Git worktree; and
- `normalize_markdown_tables(text)` and `normalize_markdown_tables_file(path, check=False)`: strict conveniences that refuse partial output or writes when malformed input remains.

Public result types are `MarkdownTable`, `MarkdownTableRow`, `MarkdownTableChange`, `MarkdownTableIssue`, `MarkdownTableFormatResult`, and `MarkdownTableError`. Line numbers are one-based physical lines; table ranges are inclusive. Rows retain their exact physical source text without the line ending and expose immutable structurally trimmed cells. Tables retain the exact raw substring, shared container prefix, table indentation, rows, and one alignment value (`none`, `left`, `right`, or `center`) per header cell. A `MarkdownTableChange` has `kind`, `message`, `line_number`, `path`, and `boundary_position`; the last field is `before` or `after` for a boundary change and `None` otherwise.

`MarkdownTableFormatResult.text` is the partial normalized text, `changed` records whether it differs from the input, and `has_errors` is exactly whether unresolved issues remain. Direct construction accepts `changed=False` and requires a Boolean. Equality and hashing include this observable state. Text-API paths are converted to `str` without filesystem resolution and propagated to changes and issues.

File APIs open one regular UTF-8 file with no-follow semantics and refuse a final-component symlink in both modes. They preserve a leading UTF-8 BOM, every existing `LF`, `CRLF`, or bare `CR` line ending, final-newline state, content outside explicit replacements, and existing mode bits. Fixes are computed in memory, the original mode is applied after writing the same-directory temporary regular file, and the destination identity is checked again immediately before the completed temporary is installed through atomic `os.replace`. A missing, replaced, symlinked, or otherwise changed destination fails without overwriting the new path. Portable POSIX APIs cannot make the final identity-check-and-rename pair conditional as one operation, so callers must still use a single writer per path. Ownership, timestamps, and extended attributes are not promised.

## Command

Install the base package and run:

```text
la-dev-markdown-tables [--check] [PATH ...]
la-dev-markdown-tables --version
la-dev-markdown-tables --help
```

Explicit paths are processed once in first-occurrence command-line order and are not suffix-restricted. With no paths, the command discovers the nearest Git root through bounded subprocess execution, reads NUL-delimited `git ls-files` output, selects present `.md` and `.markdown` paths case-insensitively, and processes them in repository-relative Git-path order.

Default mode writes safe changes and prints `Formatted Markdown tables: PATH` for each changed file. Check mode writes nothing and reports proposed changes. Malformed and operational diagnostics use `la-dev-markdown-tables: PATH:LINE: MESSAGE` on stderr; operational errors without a source line omit `:LINE`. Human-readable paths preserve printable Unicode but use backslash escapes for controls, format characters, surrogates, line separators, and literal backslashes so every record remains on one physical line.

Exit statuses are:

- `0`: clean check, or completed fix with no unresolved error;
- `1`: check mode found safe formatting changes and no malformed or operational error; and
- `2`: malformed input or an operational failure, taking precedence over status `1`.

Fix mode can therefore write independently safe changes and still return `2` for a malformed table left untouched in the same file.

## Pre-commit and CI

The repository publishes mutation and verification hooks. Downstream users must replace `vX.Y.Z` with an actual release tag containing the hooks:

```yaml
repos:
  - repo: https://github.com/pallgeuer/la-dev-codex-plugins
    rev: vX.Y.Z
    hooks:
      - id: markdown-tables-fix
```

Use the non-mutating alternative in CI or a manual verification stage:

```yaml
repos:
  - repo: https://github.com/pallgeuer/la-dev-codex-plugins
    rev: vX.Y.Z
    hooks:
      - id: markdown-tables-check
```

The hooks receive selected filenames and install only the dependency-free base package. Version 1 has no per-table directives and no formatter configuration file. Limit scope by passing explicit CLI paths or using pre-commit's path-level `exclude`, for example:

```yaml
      - id: markdown-tables-fix
        exclude: ^docs/vendor/
```

For local manual verification, run `la-dev-markdown-tables --check`. In CI, use the same command or the check hook so the job cannot mutate its checkout.
