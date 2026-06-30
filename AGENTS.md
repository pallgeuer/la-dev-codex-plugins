# Repository instructions

This repository is a Codex plugin marketplace.

## Package layout

- Marketplace file: `.agents/plugins/marketplace.json`
- Plugin roots: `plugins/<plugin-name>/`
- Plugin manifests: `plugins/<plugin-name>/.codex-plugin/plugin.json`
- Skill roots: `plugins/<plugin-name>/skills/<skill-name>/`
- Skill scripts: `plugins/<plugin-name>/skills/<skill-name>/scripts/`
- Skill tests: `tests/plugins/<plugin-name>/skills/<skill-name>/`

Tests must not be placed inside `plugins/<plugin-name>/` unless a test fixture is intentionally part of the runtime plugin payload.

## Python runtime requirements for plugin scripts

Python scripts shipped inside any plugin must support Python 3.6+ and must run with only the Python standard library. Assume the runtime can be any system Python from Ubuntu 18.04 onward (Python 3.6+). Do not use syntax, standard-library APIs, or typing features that require Python 3.7+.

Do not add non-standard Python runtime dependencies for shipped plugin scripts.

Test-only dependencies are allowed only through the fixed-version `uvx` commands documented in `TESTING.md`.

## Required checks after editing plugin scripts

After changing any file under `plugins/*/skills/*/scripts/`, run:

```bash
uvx --python 3.10 --from pre-commit==4.6.0 pre-commit run --all-files
```

As part of the pre-commit hooks, Vermin checks minimum Python-version compatibility, but this does not replace functional tests.

Refer to `TESTING.md` for more details on linting, formatting, type checking, unit testing, and version compatibility check commands. [Recommended pre-commit check](TESTING.md#recommended-pre-commit-check) also lists example commands to check JSON files.

## Code Style

- NEVER manually wrap code/comments/docstrings during code writing and edits; allow the formatters to later enforce line length.
- Use ASCII-only project source; represent required non-ASCII values with escapes. Markdown files may use literal non-ASCII when required.
- Avoid unqualified function imports like `from X.Y import func`; use `import X.Y` or `import X.Y as Y` and call via the module. Classes, exceptions, types, and constants may be imported directly.
- Write concise, meaningful docstrings. Module docstrings should identify what the file/package is, not say that it "provides support" or "implements" something. Attribute documentation must explain the role, semantics, units, source, or downstream use of the attribute; never restate the identifier with filler like "The foo value" or "The FOO enum member."

## Workflows

- Interview me for relevant details when making plans, unless the details are quite clear already from the provided information.
- When changing function signatures or class attributes, update all affected docstrings in the same change.
