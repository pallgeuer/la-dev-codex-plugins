# Repository instructions

This repository is a Codex plugin marketplace.

## Package layout

- Marketplace file: `.agents/plugins/marketplace.json`
- Plugin roots: `plugins/<plugin-name>/`
- Plugin manifests: `plugins/<plugin-name>/.codex-plugin/plugin.json`
- Skill roots: `plugins/<plugin-name>/skills/<skill-name>/`
- Skill scripts: `plugins/<plugin-name>/skills/<skill-name>/scripts/`
- Skill tests: `tests/plugins/<plugin-name>/skills/<skill-name>/`
- Codex Perform tests: `tests/codex_perform/`
- Shared behavioral contracts: `tests/contracts/`
- Supported-platform smoke tests: `tests/platform/`
- Python distribution tests: `tests/python_distribution/`
- Repository contracts: `tests/repo/`
- Repository script tests: `tests/scripts/`

Tests must not be placed inside `plugins/<plugin-name>/` unless a test fixture is intentionally part of the runtime plugin payload.
Do not write or generate test assertions that lock in exact wording or wording components of `actions.json` entries.
Do not lock incidental text into test assertions. If tests fail only because wording changed, determine whether the wording is a public contract and ask when unclear; do not blindly revert the wording.

## Release versioning

Do not change repository or plugin versions during ordinary development; update them only when the user explicitly requests a version bump or release. The rules below govern those explicit versioning and release tasks; they do not authorize automatic development-time bumps.

The repository and every plugin have independent semantic versions. The repository version is declared in `setup.cfg` and `src/la_dev_codex_plugins/__init__.py` and displayed in the opening sentence of `README.md`; all three values must match. Each plugin version is declared in its own `plugins/<plugin-name>/.codex-plugin/plugin.json` manifest and does not need to match the repository or any other plugin.

Marketplace release refs should be annotated Git tags named `vX.Y.Z`, where `X.Y.Z` is the repository version, and listed at https://github.com/pallgeuer/la-dev-codex-plugins/tags.

For every release, classify repository-only changes independently from plugin changes. Bump each changed existing plugin according to the repository's release classifications and leave unchanged plugin versions untouched. A backward-compatible, narrowly scoped capability addition is an `enhancement` and receives a patch bump; reserve a `feature` minor bump for a substantial public capability or workflow expansion. A new plugin identity starts at `0.1.0` and is not incremented for its first release. A renamed plugin is a removed identity plus a new identity rather than a continuation of the old plugin version.

Bump the repository exactly once using the highest effective bump required by repository-only changes, structural marketplace changes, and changed plugins. Adding a plugin requires at least a repository minor bump. Removing or renaming a plugin is a breaking repository change. A plugin patch contributes a repository patch, and a plugin minor contributes a repository minor. A plugin major contributes a repository major when the repository is at or above `1.0.0`, but contributes a repository minor while the repository remains below `1.0.0`. As with every component in initial development, a breaking repository change below `1.0.0` advances the repository minor; moving the repository to `1.0.0` is reserved for an explicit declaration that its public interface is stable.

## Python runtime requirements for plugin scripts

Python scripts shipped inside any plugin must support Python 3.6+ and must run with only the Python standard library. Assume the runtime can be any system Python from Ubuntu 18.04 onward (Python 3.6+). Do not use syntax, standard-library APIs, or typing features that require Python 3.7+.

Do not add non-standard Python runtime dependencies for shipped plugin scripts.

Test-only dependencies are allowed only through the fixed-version `uvx` commands documented in `TESTING.md`.

## Python distribution runtime requirements

Runtime code shipped in the `la-dev-codex-plugins` Python distribution must support Python 3.6+ and use only the Python standard library. The base distribution has no mandatory dependencies.

The sole permitted third-party runtime import is `pytest` in `src/la_dev_codex_plugins/pytest_isolation/plugin.py`. This is an optional integration boundary: `src/la_dev_codex_plugins/pytest_isolation/__init__.py` must not import the plugin eagerly, and no other distribution runtime code or plugin script may import it, directly or indirectly.

Ubuntu 18.04 or newer and macOS 14 or newer are officially supported. Compatibility with other POSIX Linux distributions is intended but is not part of the official support guarantee. Native Windows and WSL are not supported, tested, or maintained.

Keep the wheel and sdist manifests minimal. The wheel must not contain plugin payloads, tests, repository helpers, or source-only activation files. The sdist may additionally contain only `tests/python_distribution/smoke_*.py` plus the files required to build and describe the distribution.

## Required checks after editing plugin scripts

After changing any file under `plugins/*/skills/*/scripts/`, run:

```bash
uvx --python 3.10 --from pre-commit==4.6.0 pre-commit run --all-files
```

As part of the pre-commit hooks, Vermin checks minimum Python-version compatibility. After changing behavior, run applicable functional tests in addition to formatting, linting, type checking, and compatibility checks.

Refer to `TESTING.md` for more details on linting, formatting, type checking, unit testing, and version compatibility check commands. [Recommended pre-commit check](TESTING.md#recommended-pre-commit-check) also lists example commands to check JSON files.

## Code style

- NEVER manually wrap code/comments/in-code documentation during code writing and edits; allow the formatters to later enforce line length.
- Use ASCII-only project source; represent required non-ASCII values with escapes. Markdown files may use literal non-ASCII when required, but should still make obvious near-equivalent ASCII replacements where suitable (e.g. do keep the literal middle-dot separators in the final Loupe review).
- Use sentence case for Markdown headings and table headers; capitalize only the first word, the first word after a colon, and proper nouns.
- Do not import functions directly into the local namespace; import the containing module and call functions through it (for example, `from X import Y` followed by `Y.func()`, or `import X.Y` followed by `X.Y.func()`, or `import X.Y as Z` followed by `Z.func()`). Classes, exceptions, types, and constants may be imported directly. Direct function imports are allowed in `__init__.py` files (or other clearly sole-purpose public API files) solely to re-export functions as part of the package's public API.
- Write concise, meaningful docstrings. Module docstrings should identify what the file/package is, not say that it "provides support" or "implements" something. Attribute documentation must explain the role, semantics, units, source, or downstream use of the attribute; never restate the identifier with filler like "The foo value" or "The FOO enum member."

## Workflows

- Interview me for relevant details when making plans, unless the details are quite clear already from the provided information.
- When changing function signatures or class attributes, update all affected docstrings in the same change.
