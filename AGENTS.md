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

## Release versioning

Do not bump the repository version or any plugin version during ordinary development or implementation work. Change versions only when the user explicitly requests a version bump or asks to prepare/make an actual release. The rules below govern those explicit versioning and release tasks; they do not authorize automatic development-time bumps.

The repository and every plugin have independent semantic versions. The repository version is declared in `setup.cfg` and `src/la_dev_codex_plugins/__init__.py` and displayed in the opening sentence of `README.md`; all three values must match. Each plugin version is declared in its own `plugins/<plugin-name>/.codex-plugin/plugin.json` manifest and does not need to match the repository or any other plugin.

Marketplace release refs should be annotated Git tags named `vX.Y.Z`, where `X.Y.Z` is the repository version, and listed at https://github.com/pallgeuer/la-dev-codex-plugins/tags.

For every release, classify repository-only changes independently from plugin changes. Bump each changed existing plugin according to semantic versioning and leave unchanged plugin versions untouched. A new plugin identity starts at `0.1.0` and is not incremented for its first release. A renamed plugin is a removed identity plus a new identity rather than a continuation of the old plugin version.

Bump the repository exactly once using the highest effective bump required by repository-only changes, structural marketplace changes, and changed plugins. Adding a plugin requires at least a repository minor bump. Removing or renaming a plugin is a breaking repository change. A plugin patch contributes a repository patch, and a plugin minor contributes a repository minor. A plugin major contributes a repository major when the repository is at or above `1.0.0`, but contributes a repository minor while the repository remains below `1.0.0`. As with every component in initial development, a breaking repository change below `1.0.0` advances the repository minor; moving the repository to `1.0.0` is reserved for an explicit declaration that its public interface is stable.

## Python runtime requirements for plugin scripts

Python scripts shipped inside any plugin must support Python 3.6+ and must run with only the Python standard library. Assume the runtime can be any system Python from Ubuntu 18.04 onward (Python 3.6+). Do not use syntax, standard-library APIs, or typing features that require Python 3.7+.

Do not add non-standard Python runtime dependencies for shipped plugin scripts.

Test-only dependencies are allowed only through the fixed-version `uvx` commands documented in `TESTING.md`.

## Python distribution runtime requirements

Runtime code shipped in the `la-dev-codex-plugins` Python distribution, including files under `src/` and `package_scripts/`, must support Python 3.6+ and use only the Python standard library. The source-only launcher under `source_launcher/` has the same requirements.

Do not add mandatory or optional runtime dependencies to the base distribution. A future tool that cannot satisfy the Python 3.6+ standard-library-only contract must use a separate distribution rather than weakening the `codex-perform` installation contract.

Keep the wheel and sdist manifests minimal. The wheel must not contain plugin payloads, tests, repository helpers, or source-only activation files. The sdist may additionally contain only the dedicated dependency-free tests under `tests/python_package_distribution/` and the files required to build and describe the distribution.

## Required checks after editing plugin scripts

After changing any file under `plugins/*/skills/*/scripts/`, run:

```bash
uvx --python 3.10 --from pre-commit==4.6.0 pre-commit run --all-files
```

As part of the pre-commit hooks, Vermin checks minimum Python-version compatibility, but this does not replace functional tests.

Refer to `TESTING.md` for more details on linting, formatting, type checking, unit testing, and version compatibility check commands. [Recommended pre-commit check](TESTING.md#recommended-pre-commit-check) also lists example commands to check JSON files.

## Code Style

- NEVER manually wrap code/comments/docstrings during code writing and edits; allow the formatters to later enforce line length.
- Use ASCII-only project source; represent required non-ASCII values with escapes. Markdown files may use literal non-ASCII when required (e.g. do keep the literal middle-dot separators in the final Loupe review).
- Avoid unqualified function imports like `from X.Y import func`; use `import X.Y` or `import X.Y as Y` and call via the module. Classes, exceptions, types, and constants may be imported directly. Unqualified imports may be acceptable in `__init__.py` files if they are used to define a clean public API interface.
- Write concise, meaningful docstrings. Module docstrings should identify what the file/package is, not say that it "provides support" or "implements" something. Attribute documentation must explain the role, semantics, units, source, or downstream use of the attribute; never restate the identifier with filler like "The foo value" or "The FOO enum member."

## Workflows

- Interview me for relevant details when making plans, unless the details are quite clear already from the provided information.
- When changing function signatures or class attributes, update all affected docstrings in the same change.
