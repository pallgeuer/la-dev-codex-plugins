# Python project setup

For an empty directory, start with the [New repository setup recipe](https://github.com/pallgeuer/la-dev-codex-plugins/blob/main/docs/new_repo_recipe.md). Complete [Language-agnostic project setup](project_setup_agnostic.md) together with this guide, preparing both AGENTS.md templates and Codex settings before the early activation checkpoint. The documented Python setup is required unless an explicit user decision or an applicability condition says otherwise; record deviations in the setup journal. This recipe assumes a modern `src/`-layout project managed with [uv](https://docs.astral.sh/uv/); merge it into an existing project rather than replacing working packaging or tool configuration blindly.

Replace every `YOUR_*` placeholder before running the copied configuration. The versions below are a reproducible snapshot based on [pydocformatter](https://github.com/pallgeuer/pydocformatter); research and pin current compatible releases when adopting the recipe.

## 1. Choose the package and compatibility identities

Write down these values before editing configuration (choose the appropriate Python version(s) to support):

```text
Distribution name: YOUR-DISTRIBUTION-NAME
Import package: YOUR_IMPORT_PACKAGE
Minimum Python: 3.12
Supported Python versions: 3.12 through current
Supported operating systems: YOUR_SUPPORTED_SYSTEMS
CLI command, if any: YOUR-CLI
Version source: src/YOUR_IMPORT_PACKAGE/_version.py
```

Use the distribution name in package metadata and PyPI URLs; use the import package in Python imports. Do not advertise an interpreter or platform as supported unless the code and direct dependencies are compatible and the claim has proportionate CI or documented best-effort status.

Create the basic layout:

```bash
mkdir -p src/YOUR_IMPORT_PACKAGE tests tools
touch src/YOUR_IMPORT_PACKAGE/__init__.py
printf '3.12\n' > .python-version
```

Put importable runtime code under `src/YOUR_IMPORT_PACKAGE/`, tests under `tests/`, and repository-only maintenance code under `tools/`. Keep generated output out of all three.

## 2. Extend `.gitignore`

Append the outputs the project uses:

```gitignore
.coverage
.coverage.*
/coverage.xml
.pytest_cache/
.ruff_cache/
.cache/
.pydocfmt_cache/
.venv/
__pycache__/
*.py[cod]
build/
dist/
htmlcov/
*.egg-info/
/.generated/
/site/
/zensical.generated.toml
```

The current `.cache/` entry is for ty's project-local cache. Once ty provides a supported cache-directory setting, configure and git-ignore a tool-specific location instead. Keep coverage/tool outputs ignored for this complete setup; remove an entry only when an explicitly agreed alternative does not create that output. Keep a deliberately committed lock file and authored documentation configuration out of the git-ignore list.

Replace the agnostic guide's illustrative `.codex/config.toml` with this complete Python-project version:

```toml
approval_policy = "on-request"
model_reasoning_effort = "medium"
plan_mode_reasoning_effort = "high"
sandbox_mode = "workspace-write"
web_search = "live"

[sandbox_workspace_write]
network_access = true
writable_roots = [
  "~/.cache/gh",
  "~/.cache/pip",
  "~/.cache/pre-commit",
  "~/.cache/uv",
  "~/.local/share/uv",
]
```

This repeats the GitHub CLI, pip, pre-commit, and uv paths deliberately because a repository-level `writable_roots` list replaces the user- or system-level list instead of extending it. Add every other external path this repository needs to the same list.

Before continuing, complete project trust and the early restart/activation checkpoint from the entry recipe; merely writing this file does not activate it.

## 3. Configure project metadata, dependencies, and builds

Create or merge these sections in `pyproject.toml` (example template):

```toml
[project]
name = "YOUR-DISTRIBUTION-NAME"
dynamic = ["version"]
authors = [{name = "YOUR NAME"}]
maintainers = [{name = "YOUR NAME"}]
description = "ONE-SENTENCE DESCRIPTION"
readme = "README.md"
license = "YOUR-SPDX-LICENSE"
license-files = ["LICENSE.md"]
requires-python = ">=3.12"
keywords = ["your", "search", "terms"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Programming Language :: Python",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3 :: Only",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Programming Language :: Python :: 3.14",
]
dependencies = []

[project.urls]
homepage = "https://github.com/YOUR-ORG/YOUR-REPOSITORY"
source = "https://github.com/YOUR-ORG/YOUR-REPOSITORY"
changelog = "https://github.com/YOUR-ORG/YOUR-REPOSITORY/blob/main/CHANGELOG.md"
documentation = "https://YOUR-DOCUMENTATION-URL/"
issues = "https://github.com/YOUR-ORG/YOUR-REPOSITORY/issues"

# Delete this table when the project installs no command.
[project.scripts]
YOUR-CLI = "YOUR_IMPORT_PACKAGE.cli:main"

[dependency-groups]
docs = [
    "la-dev-codex-plugins==0.5.5",
    "zensical==0.0.54",
]
test = [
    {include-group = "docs"},
    "la-dev-codex-plugins[pytest]==0.5.5",
    "pytest==9.1.1",
    "pytest-cov==7.1.0",
    "pytest-mock==3.15.1",
    "pytest-xdist==3.8.0",
]
dev = [
    {include-group = "test"},
    "pre-commit==4.6.2",
    "pydocformatter==1.2.1",
    "ruff==0.16.3",
    "twine==7.0.0",
    "ty==0.0.71",
]

[build-system]
requires = ["hatchling>=1.31.0"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/YOUR_IMPORT_PACKAGE"]

[tool.hatch.build.targets.sdist]
exclude = [
    ".github/",
    ".codex/",
    ".agents/",
    "AGENTS.md",
    "docs/devel/plans/",
    "tools/",
]

[tool.hatch.version]
path = "src/YOUR_IMPORT_PACKAGE/_version.py"
```

Remove URLs, scripts, license fields, classifiers, and dependency groups that genuinely do not apply. The metadata specification does not require a keyword case; prefer lowercase search terms such as `python`, `docstrings`, and `static-analysis`, retaining canonical capitalization only when it materially identifies a proper name or acronym. Browse the [complete current PyPI classifier list](https://pypi.org/classifiers/) and copy only classifiers that apply, with their exact spelling. Add a classifier for every supported Python version, but use `requires-python`, not classifiers, to constrain installation compatibility. Runtime dependencies should use the lowest compatible bounds needed by downstream resolvers; direct documentation, test, and development tools should use exact pins for reproducible repository work.

Create the version source:

```python
"""Package version."""

__version__ = "0.1.0"
```

Export it from `src/YOUR_IMPORT_PACKAGE/__init__.py` as `__version__`. Keep this file as the single version source and test that installed/built metadata agrees with it; also check version output when a CLI exists. A package without a CLI needs import-based smoke checks, not a placeholder command.

Resolve and commit the environment:

```bash
uv lock
uv sync --locked --no-default-groups --group dev
uv lock --check
uv tree
```

The `docs` group supplies Markdown-maintenance tools even when the project has no hosted documentation site; omit the site generator only when no site is selected. Keep `la-dev-codex-plugins[pytest]` in the test group from the start, at the same pinned version as the docs-group base dependency. Installing the extra declares the pytest dependency but does not activate guarded-CWD behavior; explicit plugin loading/configuration remains a separate test-behavior decision.

Use `uv run` for project commands. After every dependency edit, run `uv lock` to regenerate `uv.lock`; never edit the lock file manually. Review the resulting lock-file diff, resync with `uv sync --locked --no-default-groups --group dev`, and run the full checks before including the lockfile with the dependency change in its commit. Add a repository test such as `tests/test_dependency_pins.py` that parses `pyproject.toml` and fails when a direct `docs`, `test`, or `dev` string is not an exact `name==version` pin; allow only `{include-group = "..."}` table entries.

### Validate the real host environment

Run the locked sync successfully before treating resolution as installation evidence. Inspect native transitive dependencies, interpreter/architecture support, wheel platform/glibc tags, and source-build toolchains. For example, a formatter dependency may need a Rust-backed LibCST build on a host older than its available wheels. Do not assume plugin Python 3.6 runtime compatibility implies modern development tools run on that interpreter or host. Do not downgrade a transitive dependency outside its parent's declared constraints to avoid a compiler.

Use maintained provider instructions, such as [Rustup installation](https://rust-lang.github.io/rustup/installation/) when Rust is actually required; report the dependency chain/failure and obtain approval before installing a compiler or changing system/user state. Keep any agreed PATH adjustment command-local unless profile changes were explicitly authorized. Verify tool capabilities when provider commands fail on an older host, preserving signature/fingerprint checks rather than bypassing them. A successful lock, a successful sync, and a validated artifact are separate checkpoints. An isolated build-backend range and separately resolved hook environments also mean a committed lockfile does not promise byte-identical future artifacts.

## 4. Configure pytest

Configure pytest-xdist immediately with default `-n auto`, even for a tiny initial suite. Use `-n 0` where worker startup or debugging makes serial execution more useful; serial runs are not a reason to defer installing/configuring xdist. Start with:

```toml
[tool.pytest.ini_options]
addopts = ["-n", "auto", "--cov", "--cov-config=pyproject.toml", "--cov-report=term-missing"]
filterwarnings = ["error"]
testpaths = ["tests"]
```

Use module-level test functions, plain `assert`, fixtures, `pytest.raises`, `@pytest.mark.parametrize`, and `pytest-mock`. Use `uv run pytest -n 0 PATH` for focused serial debugging and `uv run pytest` for the configured parallel suite.

### Configure coverage from the start

Installing pytest-cov alone does not enable measurement. For this complete setup, collect branch coverage of the installed runtime package on every normal pytest run, including hooks and CI. Show missing lines/branches, generate HTML/XML on demand, and report results without a minimum-percentage gate. Do not silently invent a 90% or 100% threshold. An explicitly requested alternative policy must be recorded before changing these defaults.

Add the following sections; replace the import-package placeholder and include every runtime package. Tests and repository-only helpers stay outside the measured package scope:

```toml
[tool.coverage.run]
branch = true
source_pkgs = ["YOUR_IMPORT_PACKAGE"]
relative_files = true

[tool.coverage.report]
fail_under = 0
```

The pytest options above use bare `--cov` followed immediately by another option, so it enables collection without consuming a positional test path or overriding configured source selection. With pytest-cov 7.1.0, `--cov=` passed an empty package name to coverage and emitted an empty-module warning; do not suppress it. Keep source/branch policy in pyproject.toml, select that config explicitly, and let pytest-cov combine xdist workers. See [pytest-cov configuration](https://pytest-cov.readthedocs.io/en/latest/config.html), [xdist integration](https://pytest-cov.readthedocs.io/en/latest/xdist.html), and [coverage configuration](https://coverage.readthedocs.io/en/latest/config.html).

```bash
uv run pytest
uv run pytest -n 0
uv run coverage html
uv run coverage xml
```

The report commands reuse the most recent `.coverage` data and write ignored `htmlcov/index.html` and `coverage.xml`. Focused runs replace full-suite data; rerun the full suite before generating a full-suite report. Use `uv run pytest -n 0 --no-cov` for local debugging without measurement. Coverage is evidence of execution, not proof of test quality. Add subprocess/native-code measurement only when actual runtime behavior requires it.

### Decide whether working-directory isolation is useful

Enable shared guarded-CWD mode when tests should not depend on the repository root but could accidentally do so. It is especially useful when code discovers `pyproject.toml` or other configuration by walking from the current directory, uses relative input/output paths, launches subprocesses that inherit the CWD, or writes through `tempfile` APIs. The guard makes accidental repository reads and writes fail early while redirecting ordinary temporary files to a safe writable location.

You can skip shared guarding when the suite intentionally tests against the checkout as its working directory, a framework requires repository-root execution, every relevant test already chooses an explicit temporary CWD, or a small pure-unit suite performs no relative filesystem access or configuration discovery. Skipping it means omitting the plugin settings and root `conftest.py` below; ordinary pytest remains fully supported. You may also load the plugin only for selected tests and use its private fixtures without guarding every unmarked test.

To enable shared guarding, extend the pytest table:

```toml
[tool.pytest.ini_options]
addopts = ["-n", "auto", "--cov", "--cov-config=pyproject.toml", "--cov-report=term-missing"]
filterwarnings = ["error"]
testpaths = ["tests"]
la_dev_cwd_isolation_unmarked = "shared_guarded"
```

Create root `conftest.py`:

```python
"""Repository-wide pytest configuration."""

pytest_plugins = ("la_dev_codex_plugins.pytest_isolation.plugin",)
```

The default eager cleanup is the simplest choice. Use `la_dev_cwd_isolation_cleanup = "pytest_retained"` only when a cooperative resource keeps interpreter-owned files open until shutdown; that mode also needs pytest temporary-path retention configuration. See [Pytest working-directory isolation](https://github.com/pallgeuer/la-dev-codex-plugins/blob/main/docs/pytest_isolation.md) before enabling it.

For a test that deliberately needs a private writable CWD:

```python
def test_generates_file(isolated_cwd):
    output = isolated_cwd / "output.txt"
    output.write_text("result", encoding="utf-8")
```

Use `guarded_cwd` instead when a particular test must prove that it does not read from or write to its CWD.

## 5. Configure pydocformatter

Review formatter fixes around structured comments and metadata; successful reflow is not proof that machine-readable identifiers retain their meaning. Preserve deliberate separators when structured metadata is present, without inventing per-file license notices.

The following is pydocformatter's complete self-configuration and is a strong, intentionally strict starting point:

```toml
[tool.pydocfmt]
line-length = 120
indent-style = "space"
indent-width = 4
line-ending = "lf"
respect-gitignore = true
force-exclude = true
extend-select = [
    "no-blank-line-after-function-docstring",
    "summary-trailing-period",
    "non-imperative-summary",
    "summary-starts-with-this",
    "missing-public-module-attribute-documentation",
    "class-attribute-documentation-order",
    "module-attribute-documentation-order",
    "parameter-type-required",
    "return-type-required",
    "yield-type-required",
    "class-attribute-type-required",
    "module-attribute-type-required",
    "rule-codes-in-suppression-comments",
]
ignore = [
    "public-class-attribute-docstring-must-be-attached",
    "public-module-attribute-docstring-must-be-attached",
    "private-class-attribute-docstring-must-be-owner",
    "private-module-attribute-docstring-must-be-owner",
]
require-explicit = [
    "rule-codes-in-suppression-comments",
    "rule-names-in-suppression-comments",
]

[tool.pydocfmt.docstring]
convention = "google"
missing-documentation = "all-docstrings"
require-init-attribute-documentation = true

[tool.pydocfmt.comment]
detect-code = true
detect-expressions = true
join-standalone-lines = true
task-marker-mode = "hanging"

[tool.pydocfmt.per-file-ignores]
"tests/**/test_*.py" = ["PDF6"]

[tool.pydocfmt.per-file-settings]
"tests/**/test_*.py" = { docstring-missing-documentation = "has-section" }
```

Do not add custom extensions to the baseline without a project need. If the project genuinely uses `.rpy` Python files and `.mdx` Markdown files, merge this optional example into the tables above:

```toml
[tool.pydocfmt]
extend-include = ["*.rpy", "*.mdx"]

[tool.pydocfmt.extension]
rpy = "python"
mdx = "markdown"
```

Before adopting it:

- Set `convention` in `[tool.pydocfmt.docstring]` to the project's Google, NumPy, reStructuredText, or generic docstring convention.
- Choose `missing-documentation` in `[tool.pydocfmt.docstring]`. The example's `"all-docstrings"` value is a good fit for AI-oriented development, where consistently generating documentation for every eligible definition is inexpensive and gives later agents more local context, but it may impose too much writing and maintenance overhead on a primarily manual workflow. Separately decide whether `require-init-attribute-documentation = true` in the same table is appropriate for the project's attributes.
- Review `respect-gitignore` and `force-exclude` under `[tool.pydocfmt]`. With `force-exclude = true`, pydocformatter applies configured exclusions to explicitly passed paths, so do not repeat `--force-exclude` in commands that load this configuration.
- Review the type-requirement rules in `extend-select` under `[tool.pydocfmt]`, including `parameter-type-required`, `return-type-required`, `yield-type-required`, `class-attribute-type-required`, and `module-attribute-type-required`.
- Select one suppression-comment identity policy through the applicable rules in `extend-select` and `require-explicit` under `[tool.pydocfmt]`.
- Set `indent-style` and `indent-width` under `[tool.pydocfmt]`, and keep them consistent with Ruff and the existing source. The example uses four spaces.
- Decide whether `join-standalone-lines` in `[tool.pydocfmt.comment]` should combine adjacent ordinary prose comments into paragraphs before wrapping. Keep it enabled when manually wrapped comment lines should be reflowed as prose; disable it when adjacent comment lines must remain separate semantic lines.
- Sources assigned to Markdown automatically use `source-context = "fragment"` and `docstring-missing-documentation = "has-section"`. These language-aware defaults disable rules that assume a complete importable module or require docstrings for illustrative definitions while retaining completeness checks for documentation sections an example actually contains. Use a per-file entry with `source-context = "module"` and the desired missing-documentation policy only for documentation paths whose Python fences intentionally represent complete modules, and add the standalone `pydocfmt-skip` fence token only for intentionally malformed or deliberately nonconforming examples.
- Keep the default source-language assignments unless the project genuinely uses custom filename extensions: `.py`, `.pyi`, and `.pyw` are Python, while `.md` is Markdown. For a custom extension, add a separate `[tool.pydocfmt.extension]` table such as `rpy = "python"` or `mdx = "markdown"`. The mapping does not change directory discovery, so add matching `extend-include` patterns when direct directory checks should find those files. Every custom extension assigned to Markdown receives the same automatic language-aware defaults without a matching per-file pattern.
- Confirm that `[tool.pydocfmt.per-file-ignores]` and `[tool.pydocfmt.per-file-settings]` fit the project's test style and paths.
- Remove a rule from `ignore` under `[tool.pydocfmt]` only after resolving its incompatibility with the chosen attachment policy.

Run:

```bash
uv run pydocfmt check --fix
uv run pydocfmt check
```

## 6. Configure Ruff

Copy and adapt this broad, opinionated Ruff starting point:

```toml
[tool.ruff]
force-exclude = true
indent-width = 4
line-length = 200
output-format = "grouped"
preview = true
respect-gitignore = true
src = ["src", "tools"]

[tool.ruff.analyze]
preview = true

[tool.ruff.format]
docstring-code-format = true
indent-style = "space"
line-ending = "lf"
preview = true
quote-style = "double"
skip-magic-trailing-comma = true

[tool.ruff.lint]
select = [
    "A", "ANN", "ARG", "ASYNC",
    "B",
    "C4", "C90", "COM",
    "DTZ",
    "E", "EXE",
    "F", "FA", "FLY", "FURB",
    "G",
    "I", "ICN", "INP", "INT", "ISC",
    "LOG",
    "N",
    "PERF", "PGH", "PIE", "PLC", "PLE", "PLR", "PLW", "PT", "PYI",
    "RET", "RSE", "RUF",
    "S", "SIM", "SLOT",
    "T10", "TC", "TID", "TRY",
    "UP",
    "W",
    "YTT",
]
extend-select = [
    "boolean-positional-value-in-call",
]
ignore = [
    "D",
    "DOC",
    "any-type",
    "compare-to-empty-string",
    "doc-line-too-long",
    "indentation-with-invalid-multiple",
    "indentation-with-invalid-multiple-comment",
    "invalid-module-name",
    "line-too-long",
    "missing-trailing-comma",
    "multiple-leading-hashes-for-block-comment",
    "no-space-after-block-comment",
    "no-space-after-inline-comment",
    "over-indented",
    "prohibited-trailing-comma",
    "raise-vanilla-args",
    "read-whole-file",
    "start-process-with-partial-path",
    "suspicious-subprocess-import",
    "tab-indentation",
    "too-few-spaces-before-inline-comment",
    "unnecessary-dunder-call",
    "write-whole-file",
]
extend-unsafe-fixes = []
unfixable = []
dummy-variable-rgx = "^_$"
future-annotations = true
preview = true
task-tags = ["TODO", "FIXME", "XXX", "HACK", "BUG", "DEBUG", "NOTE", "OPTIMIZE", "REVIEW"]

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = [
    "assert",
]
"tests/**/test_*.py" = [
    "private-member-access",
]

[tool.ruff.lint.flake8-implicit-str-concat]
allow-multiline = true

[tool.ruff.lint.flake8-quotes]
docstring-quotes = "double"
inline-quotes = "double"
multiline-quotes = "double"

[tool.ruff.lint.flake8-tidy-imports]
ban-relative-imports = "parents"

[tool.ruff.lint.flake8-type-checking]
exempt-modules = ["typing", "typing_extensions", "collections.abc", "types", "pathlib"]
runtime-evaluated-decorators = ["dataclasses.dataclass"]

[tool.ruff.lint.isort]
combine-as-imports = false
force-sort-within-sections = false
known-first-party = ["YOUR_IMPORT_PACKAGE", "tests"]
length-sort = false
length-sort-straight = true
lines-after-imports = 2
no-sections = false
order-by-type = true
split-on-trailing-comma = false

[tool.ruff.lint.isort.import-heading]
future = "Future imports"
standard-library = "Standard library imports"
third-party = "Third-party imports"
first-party = "First-party imports"
local-folder = "Local imports"

[tool.ruff.lint.mccabe]
max-complexity = 50

[tool.ruff.lint.pep8-naming]
extend-ignore-names = ["[A-Z]", "[A-Z][A-Z]"]

[tool.ruff.lint.pycodestyle]
ignore-overlong-task-comments = true

[tool.ruff.lint.pylint]
allow-magic-value-types = ["str", "bytes", "int"]
max-args = 20
max-bool-expr = 20
max-branches = 30
max-locals = 50
max-nested-blocks = 15
max-positional-args = 6
max-public-methods = 80
max-returns = 30
max-statements = 300
max-statements-in-try = 25
```

Before adopting it:

- Set `src` under `[tool.ruff]` to every first-party source root, and replace `YOUR_IMPORT_PACKAGE` in `[tool.ruff.lint.isort].known-first-party` with the import package. Add other first-party packages only when they exist.
- Choose `line-length`, `indent-width`, and the `[tool.ruff.format]` values for indentation, line endings, and quotes, keeping shared settings consistent with pydocformatter. This example uses Ruff's `line-length = 200` for formatting but ignores `line-too-long`, so it does not enforce a universal 200-character ceiling.
- Decide whether `preview = true` under `[tool.ruff]`, `[tool.ruff.analyze]`, `[tool.ruff.format]`, and `[tool.ruff.lint]` is acceptable. Preview rules and formatter behavior can change between pinned Ruff releases; disable preview consistently if the project wants only stable behavior.
- Decide whether `boolean-positional-value-in-call` in `extend-select` matches the project's API style, and whether `future-annotations = true` matches its annotation and runtime-compatibility policy.
- Confirm the paths and rule-name exceptions in `[tool.ruff.lint.per-file-ignores]`. Allowing `assert` throughout tests is conventional for pytest; allowing `private-member-access` is a separate choice about white-box tests.
- Decide whether `[tool.ruff.format].docstring-code-format` should reformat Python examples in docstrings and whether `skip-magic-trailing-comma = true` matches the desired call and collection layout. Review the related trailing-comma ignores and `[tool.ruff.lint.isort].split-on-trailing-comma` together.
- Decide whether multiline implicit string concatenation and parent-relative imports are project conventions; adjust `[tool.ruff.lint.flake8-implicit-str-concat]`, `[tool.ruff.lint.flake8-tidy-imports]` accordingly.
- Review `[tool.ruff.lint.flake8-type-checking].exempt-modules` and `runtime-evaluated-decorators`. Add custom dataclass-like or framework decorators only when annotations beneath them are actually evaluated at runtime; remove exemptions the project does not need.
- Decide whether the `[tool.ruff.lint.isort]` sorting choices and `[tool.ruff.lint.isort.import-heading]` comments are desired. Import headings create persistent source comments and are not required for correct import grouping.
- Review `[tool.ruff.lint.pep8-naming].extend-ignore-names`; the example permits one- and two-letter uppercase names, which may be useful for type variables or mathematical notation but too broad for some projects. Add special naming patterns only for real conventions.
- Review `[tool.ruff.lint.pylint].allow-magic-value-types`; permitting all strings, bytes, and integers suppresses many magic-value findings and may be broader than the project wants.
- Treat `[tool.ruff.lint.mccabe].max-complexity` and the `[tool.ruff.lint.pylint]` limits as permissive migration values, not universal recommendations. Tighten them where they would flag genuinely hard-to-maintain code without forcing artificial decomposition.

Run:

```bash
uv run ruff check --fix
uv run ruff format
uv run ruff check
uv run ruff format --check
```

## 7. Configure ty

Copy and possibly adapt the complete configuration:

```toml
[tool.ty.src]
respect-ignore-files = true
```

Run:

```bash
uv run ty check --force-exclude
```

The project `requires-python` declaration supplies the baseline Python environment; verify that source roots, generated files, optional imports, and framework-specific behavior are analyzed as intended. Add configuration only for real project requirements rather than preemptive ignores.

Ty currently provides `--force-exclude` only on the CLI, with no equivalent TOML setting. Ordinary discovery already honors `exclude` and ignore files, but explicitly passed targets override them; retaining the flag makes the command safe if targets are appended later. The recommended pre-commit hook sets `pass_filenames: false`, so its entry does not need the flag. When ty supports the setting in TOML, configure it there and remove the redundant CLI flag.

## 8. Add the Python `AGENTS.md` instructions

Add these sections to the root `AGENTS.md`. If a same-named section already exists from the agnostic setup, merge the listed lines into it instead of repeating the heading. Replace the generic canonical-command placeholder with these concrete commands rather than retaining a duplicate list. Keep the agnostic purpose, layout, and workflow instructions, using the project's actual values. The example assumes this guide's dev dependency group and tool selection; adapt commands when the project explicitly chooses different groups or omits a tool. The build and distribution instructions apply to projects producing Python package distributions; omit them for projects that do not build distributions. Do not copy setup-only explanations into permanent instructions:

```markdown
## Commands

- Use uv for venv management and ALL Python execution. Install/sync with `uv sync --locked --no-default-groups --group dev`.
- Never run uv with a custom/temporary cache dir (e.g. UV_CACHE_DIR or --cache-dir); if cache-related uv failures occur then abort and notify the user.
- The venv has no pip; use `uv pip`, `uv tree`, or similar.
- After dependency edits, run `uv lock`, inspect the lock-file diff, sync the locked development environment, and verify it with `uv lock --check`. Include the generated lockfile with the dependency change when committing. Never edit `uv.lock` manually.
- Use pytest for running tests. Pytest uses pytest-xdist multiprocessing by default; pass `-n 0` for serial debugging or focused runs where worker startup is slower. Run the suite with `uv run pytest`.
- Format/lint with `uv run ruff check --fix`, `uv run pydocfmt check --fix`, and `uv run ruff format`, in that order. Verify with `uv run ruff check`, `uv run pydocfmt check`, and `uv run ruff format --check`.
- Type-check with `uv run ty check --force-exclude`.
- Use `uv run la-dev-markdown-tables` to fix Markdown table formatting and `uv run la-dev-markdown-tables --check` to verify it.
- Install hooks with `uv run pre-commit install` and `uv run pre-commit install --hook-type pre-push`. Commit hooks may fix files; manual, pre-push, and CI checks must not rewrite files.
- Run the complete non-mutating check with `uv run --no-sync pre-commit run --all-files --hook-stage manual --show-diff-on-failure` after syncing the locked environment. Also run `git diff --check` and inspect staged and ignored files.
- Build with `uv build --clear`; validate wheel and source archives with `uv run twine check dist/*`, inspect contents, and smoke-test independent installations outside the checkout.

## Code style

- Do not import functions directly into the local namespace; import the containing module and call functions through it (for example, `from X import Y` followed by `Y.func()`, or `import X.Y` followed by `X.Y.func()`, or `import X.Y as Z` followed by `Z.func()`). Classes, exceptions, types, and constants may be imported directly. Direct function imports are allowed in `__init__.py` files (or other clearly sole-purpose public API files) solely to re-export functions as part of the package's public API.
- Write concise, meaningful docstrings. Module docstrings should identify what the file/package is, not say that it "provides support" or "implements" something. Attribute documentation must explain the role, semantics, units, source, or downstream use of the attribute; never restate the identifier with filler like "The foo value" or "The FOO enum member."

## Tests

- Write tests as module-level pytest functions. Use plain `assert`, `pytest.raises`, fixtures, `@pytest.mark.parametrize`, and `pytest-mock`; do not add `unittest.TestCase` test classes.

## Workflows

- When changing function signatures or class attributes, update all affected docstrings in the same change.

## Packaging

- Keep wheel contents limited to installed runtime code, runtime data, licenses, and required metadata. Include in the source distribution the source, build metadata, license and user-documentation files, and tests and configuration needed to build, document, and validate the unpacked archive. Exclude CI and agent configuration, repository-only helpers, and local state unless a non-sensitive file is required by those checks; never package credentials or secrets.
- Exclude `docs/devel/plans/` from distributions, even its tracked placeholder.
```

Keep the existing `--force-exclude` detail in the canonical direct ty command while it is a CLI-only setting; a description of the pre-commit hook's no-filenames invocation does not need to occupy permanent instructions. Working-directory isolation remains an explicit testing decision rather than a default AGENTS.md rule. The order of the formatter commands matters, and the complete manual check is deliberately non-mutating. Validate these commands after the locked environment exists; bootstrap checkpoints and evidence belong in the setup journal.

## 9. Complete pre-commit

Append this local repository to the `repos` list created by the agnostic guide:

```yaml
  - repo: local
    hooks:
      - id: ruff-check-fix
        name: ruff check (fix)
        entry: uv run ruff check --fix
        language: system
        types_or: [python, pyi]
        stages: [pre-commit]

      - id: pydocfmt-fix
        name: pydocfmt (fix)
        entry: uv run pydocfmt check --fix
        language: system
        types_or: [python, pyi, markdown]
        files: (?i)\.(?:py|pyi|pyw|md)$
        stages: [pre-commit]

      - id: ruff-format-fix
        name: ruff format (fix)
        entry: uv run ruff format
        language: system
        types_or: [python, pyi]
        stages: [pre-commit]

      - id: ruff-check
        name: ruff check
        entry: uv run ruff check
        language: system
        types_or: [python, pyi]
        stages: [pre-push, manual]

      - id: pydocfmt-check
        name: pydocfmt (check)
        entry: uv run pydocfmt check
        language: system
        types_or: [python, pyi, markdown]
        files: (?i)\.(?:py|pyi|pyw|md)$
        stages: [pre-push, manual]

      - id: ruff-format-check
        name: ruff format (check)
        entry: uv run ruff format --check
        language: system
        types_or: [python, pyi]
        stages: [pre-push, manual]

      - id: ty
        name: ty
        entry: uv run ty check
        language: system
        pass_filenames: false
        stages: [pre-commit, pre-push, manual]

      - id: pytest
        name: pytest
        entry: uv run pytest
        language: system
        pass_filenames: false
        stages: [pre-commit, pre-push, manual]
```

The hooks are declared in nominal execution order. Commit-time hooks apply Ruff lint fixes, pydocformatter fixes, and then final Ruff formatting before running ty and pytest. Pre-push/manual runs the corresponding non-mutating checks in the same order before ty and pytest. The pydocformatter filters select the built-in `.py`, `.pyi`, `.pyw`, and `.md` filename forms case-insensitively; `types_or` requires pre-commit 2.9.0 or newer.

If a project configures extra pydocformatter extensions, override the hook's `files` regex to include them. When pre-commit's identify library already recognizes every added extension as Python or Markdown, changing `files` is sufficient. Otherwise, also use an appropriate broader type filter such as `types_or: [file]`, and let `files` be the actual extension filter. These hook overrides control the explicit paths passed by pre-commit; configure `[tool.pydocfmt.extension]` separately to assign each custom suffix to `python` or `markdown`. Add `extend-include` only when direct directory discovery must find the same suffixes.

For example, use only the widened `files` line when identify recognizes both extensions; otherwise override both fields as follows:

```yaml
- id: pydocfmt-check
  types_or: [file]
  files: (?i)\.(?:py|pyi|pyw|md|rpy|mdx)$
```

Keep the ty hook as bare `uv run ty check`: `pass_filenames: false` prevents pre-commit from appending explicit paths, so normal ty discovery honors configured exclusions and ignore files without `--force-exclude`. Add the flag only if the hook later names or receives explicit targets that must still be excluded.

The pytest hook also sets `pass_filenames: false` because pytest should select the suite through its configuration rather than receive changed source paths. With the [recommended pytest configuration](#4-configure-pytest), `uv run pytest` runs the configured pytest-xdist multiprocessing suite; use `uv run pytest -n 0` for serial debugging, focused runs where worker startup dominates, or tests that are not yet safe to distribute. Omit pytest-xdist and the `addopts` entry when the suite is too small to benefit or relies on process-global or external resources that cannot be isolated across workers.

The agnostic setup already supplies Markdown-table fix/check hooks. Commit-time hooks may mutate files; the manual stage used by CI is non-mutating. Run the complete suite until it passes without changing files:

```bash
uv run pre-commit run --all-files
uv run pre-commit run --all-files --hook-stage manual
```

## 10. Add Python CI

For any CI provider, create the locked environment and run the manual pre-commit stage:

```bash
uv sync --locked --no-default-groups --group dev
uv run --no-sync pre-commit run --all-files --hook-stage manual --show-diff-on-failure
```

Test the minimum and newest supported Python versions. Add operating-system, architecture, alternative-interpreter, or libc jobs only when the project claims that support or has a realistic compatibility risk. Do not infer support merely because one job passes on `ubuntu-latest`.

### If the project uses a GitHub remote

Replace the generic workflow's installation and check steps with:

```yaml
      - name: Install uv
        uses: astral-sh/setup-uv@v8.3.2
        with:
          enable-cache: true
      - name: Sync locked development environment
        run: uv sync --locked --no-default-groups --group dev
      - name: Run non-mutating checks
        run: uv run --no-sync pre-commit run --all-files --hook-stage manual --show-diff-on-failure
```

## 11. Prepare package-index documentation

For a package published to PyPI, prefer a dedicated `PYPI.md` when the GitHub README contains repository-only installation paths, relative links, plugin instructions, contributor material, or other content that renders poorly on a package index. Use `README.md` directly when the same file is correct in both locations.

A concise `PYPI.md` should contain:

```markdown
# Distribution name

One package-oriented description.

## Install

The exact `pip`, `uv`, or tool installation command.

## Quick start

One installed-package example.

## Documentation

Absolute links to full documentation, source, changelog, and issues.

## Compatibility

Supported Python versions and platforms.
```

When using it, change project metadata to:

```toml
[project]
readme = "PYPI.md"
```

Build and inspect both distributions before release:

```bash
uv build --clear
uv run twine check dist/*
uv run python -m zipfile -l dist/*.whl
uv run python -m tarfile -l dist/*.tar.gz
```

Smoke-test the wheel and sdist independently in isolated environments. Verify package version, imports, installed data, entry points, and one representative operation; tests running from the checkout do not prove the distributions are complete.

## 12. Publish to PyPI through GitHub trusted publishing

Skip this section when the project does not publish to PyPI or does not use a GitHub remote. Otherwise configure a PyPI trusted publisher for the repository and workflow, then create a GitHub environment named `pypi` with a required reviewer. That reviewer is the visible human approval between a validated release and irreversible package publication.

Create `.github/workflows/python-package-release.yml` and replace the placeholders:

```yaml
name: Python package release

on:
  workflow_dispatch:
    inputs:
      ref:
        description: Git ref to build and validate without publishing
        required: true
        default: main
        type: string
  release:
    types: [published]

permissions:
  contents: read

jobs:
  build:
    if: github.event_name == 'workflow_dispatch' || !github.event.release.prerelease
    runs-on: ubuntu-latest
    steps:
      - name: Check out release source
        uses: actions/checkout@v7
        with:
          fetch-depth: 0
          ref: ${{ github.event_name == 'release' && github.event.release.tag_name || inputs.ref }}
      - name: Install uv
        uses: astral-sh/setup-uv@v8.3.2
        with:
          enable-cache: true
      - name: Sync locked development environment
        run: uv sync --locked --no-default-groups --group dev
      - name: Validate lock and project checks
        run: |
          uv lock --check
          uv run --no-sync pre-commit run --all-files --hook-stage manual --show-diff-on-failure
      - name: Validate release identity
        if: github.event_name == 'release'
        shell: bash
        run: |
          tag="${{ github.event.release.tag_name }}"
          test "$(git cat-file -t "$tag")" = tag
          test "$(git rev-list -n 1 "$tag")" = "$(git rev-parse HEAD)"
          version="$(uv run --no-sync python -c 'from YOUR_IMPORT_PACKAGE import __version__; print(__version__)')"
          test "v$version" = "$tag"
      - name: Build and check distributions
        run: |
          uv build --clear
          uv run --no-sync twine check dist/*
      - name: Smoke-test wheel
        run: uvx --isolated --from ./dist/*.whl YOUR-CLI --version
      - name: Smoke-test source distribution
        run: uvx --isolated --from ./dist/*.tar.gz YOUR-CLI --version
      - name: Generate release checksums
        run: |
          mkdir -p release/packages
          mv dist/*.whl dist/*.tar.gz release/packages/
          uv run --no-sync la-dev-release-checksums --output release/SHA256SUMS release/packages/*.whl release/packages/*.tar.gz
      - name: Upload validated artifacts
        uses: actions/upload-artifact@v6
        with:
          name: python-package-distributions
          path: release/
          if-no-files-found: error
          retention-days: 7

  publish:
    if: github.event_name == 'release' && !github.event.release.prerelease
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: pypi
      url: https://pypi.org/p/YOUR-DISTRIBUTION-NAME
    permissions:
      id-token: write
    steps:
      - name: Download validated artifacts
        uses: actions/download-artifact@v8
        with:
          name: python-package-distributions
          path: release/
      - name: Publish distributions to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          packages-dir: release/packages/

  release-assets:
    if: github.event_name == 'release' && !github.event.release.prerelease
    needs: publish
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - name: Download validated artifacts
        uses: actions/download-artifact@v8
        with:
          name: python-package-distributions
          path: release/
      - name: Upload distributions and checksums to the GitHub Release
        env:
          GH_TOKEN: ${{ github.token }}
        run: gh release upload "${{ github.event.release.tag_name }}" release/packages/*.whl release/packages/*.tar.gz release/SHA256SUMS --repo "${{ github.repository }}"
```

Replace CLI smoke checks with installed-import checks when the package has no CLI. Preserve artifact order when generating checksums. The manual `workflow_dispatch` path builds and tests but cannot enter either publishing job. For stronger supply-chain control, pin third-party actions to reviewed commit SHAs and let Dependabot propose updates.

The checksum manifest is recommended for released Python artifacts. Generate it only after metadata, installation, and smoke validation, publish it beside the exact wheel and source archive, and never restore an older manifest after a failed generation. See [Release checksum manifests](https://github.com/pallgeuer/la-dev-codex-plugins/blob/main/docs/release_checksums.md).

## 13. Create the Python release runbook

### Manual GitHub releases without PyPI

For a versioned Python package hosted on GitHub, create root `RELEASE.md` during complete setup using this manual GitHub release model: one wheel, one source distribution, and a checksum manifest. Do not postpone the runbook merely because no release exists or PyPI is not selected. The two explicit approval checkpoints are mandatory. No release workflow, PyPI publisher, or protected environment is required for this model. If the user instead chooses notes/tag only, multiple packages, a prerelease policy, or automated publication, agree on and adapt that model explicitly before finalizing the runbook.

Replace every setup-time placeholder before saving the repository's RELEASE.md:

- `YOUR-ORG/YOUR-REPOSITORY`: the actual GitHub owner/repository.
- `YOUR_DEFAULT_BRANCH`: the actual release/default branch.
- `YOUR_IMPORT_PACKAGE`: the import package and its source-directory component.
- `YOUR-DISTRIBUTION-NAME`: the package-metadata distribution name, which may differ from the import package.
- `YOUR_CHECK_WORKFLOW.yml`: the filename of the actual branch-check workflow. Verify its triggers and matrix; do not invent a workflow_dispatch preflight.
- `YOUR_ARCHIVE_VALIDATION_COMMAND`: a real, complete command that checks wheel/sdist metadata and boundaries and independently installs/smoke-tests each archive outside the checkout. Implement/validate the repository-only helper or concrete equivalent before finalizing this runbook; `uv build` and `twine check` alone are insufficient. This command must require exactly one wheel and one source archive and verify their versions against the installed package. The remaining template prose's "helper" refers to that validation implementation.

The template assumes this guide's dev dependency group, Hatchling version source at `src/YOUR_IMPORT_PACKAGE/_version.py`, an exported `__version__`, uv tooling, and `docs/devel/plans/` ignore rules. Adapt any explicitly different project layout or tools and the exact staging list. Version values, release SHAs, and CI run IDs are facts selected or discovered during each future release, not setup-time values to hardcode. Use ordinary Bash variable binding for the exact user-approved release_version; never treat an example version as approval. Do not execute tag/push/create commands while adopting or checking the template.

Copy the following complete runbook after replacing those values:

````markdown
# Release procedure

Run `$toolkit:perform publish-release` in Default mode to follow this runbook. Creating this document does not authorize a release. Stop for explicit confirmation of the exact version before editing release metadata, then stop again for explicit publication approval after preparation, CI, tagging, and preflight. End the turn at each approval checkpoint; an unanswered question is not consent.

Run commands from the repository root in Bash. Stop on any failed check. Keep the release variables across sections; after a session restart, reconstruct and verify their values from the approved version, tag, and commit rather than guessing.

## 1. Release model and sources of truth

This repository publishes manual GitHub releases at `YOUR-ORG/YOUR-REPOSITORY` from `YOUR_DEFAULT_BRANCH`. Each release has an annotated `vX.Y.Z` tag, curated changelog notes, one wheel, one source distribution, and `SHA256SUMS`. GitHub also supplies source snapshots. There is no PyPI publication or release/deployment workflow; `.github/workflows/YOUR_CHECK_WORKFLOW.yml` validates branch commits.

`src/YOUR_IMPORT_PACKAGE/_version.py` is the single version source. `pyproject.toml` configures Hatchling's dynamic version, dependencies, and distributions; `uv.lock` records the resolved environment. `CHANGELOG.md` supplies the release date, outcomes, and comparison links. `YOUR_ARCHIVE_VALIDATION_COMMAND` inspects and independently installs both archives. This runbook is repository-only and is not needed inside a distribution.

Use ordinary GitHub releases for `X.Y.Z` versions, including `0.x` versions. A prerelease requires a separately agreed version format and GitHub status; do not silently invent that policy. Never automatically increment a version after publishing.

## 2. Prerequisites

Require Git, uv, authenticated GitHub CLI with write access to this repository, and the standard `sha256sum`, `cmp`, and `mktemp` commands. Use uv's normal cache; follow the README's host-specific build prerequisites if syncing requires them. Ignored plans/reports must remain local.

```bash
git status --short
git branch --show-current
git remote get-url origin
git fetch origin --tags
git rev-parse HEAD origin/YOUR_DEFAULT_BRANCH
gh auth status --hostname github.com
gh release list --repo YOUR-ORG/YOUR-REPOSITORY
git tag --list 'v*' --sort=-version:refname
```

Proceed only on `YOUR_DEFAULT_BRANCH`, with a clean worktree and identical HEAD/origin/YOUR_DEFAULT_BRANCH commits. Review any unexpected files or remote changes; do not discard work, force-push, or switch branches automatically. Check remote tags as well as local tags before deciding that a version is available.

## 3. Inspect changes and choose the version

Select the previous published version using the actual release/tag history, not merely the lexically largest tag. Review its complete diff through HEAD, current documentation, and `Unreleased`. For the first release, review the initial commit, subsequent history, and current tracked contents; a diff from the first commit alone omits the foundation it introduced.

Propose the exact semantic version and explain it. An initial package version such as `0.1.0` need not be incremented merely because it is being released for the first time. **Stop and obtain explicit approval of that exact version before editing metadata.** Set `release_version` to that approved value, without a `v` prefix, then initialize:

```bash
release_repo=YOUR-ORG/YOUR-REPOSITORY
release_tag="v${release_version:?Set release_version to the exact user-approved version}"
```

Confirm that neither the local/remote tag nor the GitHub release already exists. If either does exist, inspect it and use the recovery section instead of overwriting it.

## 4. Prepare release metadata

Update `_version.py` only if the approved version differs. Run `uv lock`, inspect its diff, and sync the locked environment after version/dependency metadata changes. Review compatibility and usage documentation; change claims only when supported by the release.

Rewrite and compact `Unreleased` into concise user-facing outcomes. Consolidate overlapping entries, retain material features, fixes, compatibility changes, and migrations, and omit intermediate churn, test-only work, and stale descriptions of removed code. Review the result against the complete release diff and explicitly verify its accuracy before continuing to checks, commits, tags, or publication.

Move the verified entries into `## X.Y.Z (YYYY-MM-DD)` using the approved version and actual release-preparation date. Retain `## Unreleased` with `None.` and retain horizontal rules between the introduction, `Release diffs`, Unreleased, and every released version. Omit empty change categories; keep the existing change-type/category structure for real entries.

Replace the initial `Release diffs` TODO and example fence during first-release preparation. Use real repository/version values: Unreleased links to `compare/vX.Y.Z...HEAD`; the first version links to `releases/tag/vX.Y.Z`; each later version links to `compare/vPREVIOUS...vCURRENT`. Keep previous entries newest first. Prepare these links in the release commit before creating its tag: the new tag and release URLs become resolvable at the later tagging/publication steps. Do not create a synthetic `v0.0.0` tag or leave example versions in a released changelog.

Extract only the finalized version's entries for GitHub notes, excluding Unreleased, the comparison index, and other versions:

```bash
release_notes_path=docs/devel/plans/release-notes.md
mkdir -p docs/devel/plans
git check-ignore "$release_notes_path"
awk -v heading="## ${release_version} (" '
  index($0, heading) == 1 { active = 1; next }
  active && /^## / { exit }
  active && $0 != "---" { print }
' CHANGELOG.md > "$release_notes_path"
test -s "$release_notes_path"
```

Read the extracted notes and confirm they contain the complete approved release entry. Keep the notes file ignored; never stage the plans directory.

## 5. Run checks and build artifacts

Run this validation block now and repeat it during the tagged preflight in section 8. `uv build --clear` replaces generated build output; retain no stale artifacts as release candidates.

```bash
uv sync --locked --no-default-groups --group dev
uv lock --check
uv run --no-sync python -c 'import importlib.metadata, sys, YOUR_IMPORT_PACKAGE; assert YOUR_IMPORT_PACKAGE.__version__ == importlib.metadata.version("YOUR-DISTRIBUTION-NAME") == sys.argv[1]' "$release_version"
uv run --no-sync pre-commit run --all-files --hook-stage manual --show-diff-on-failure
git diff --check
uv build --clear
uv run --no-sync twine check dist/*.whl dist/*.tar.gz
YOUR_ARCHIVE_VALIDATION_COMMAND
uv run --no-sync la-dev-release-checksums --output dist/SHA256SUMS dist/*.whl dist/*.tar.gz
(cd dist && sha256sum --check SHA256SUMS)
```

Require exactly one wheel and one source archive, matching the approved version; the helper checks archive boundaries, installed identity, and licensing. Inspect filenames and metadata as well as command success. Generate checksums only after validation, in wheel-then-sdist order. On checksum generation failure, stop; never restore an old manifest as if it described new artifacts.

## 6. Commit, push, and wait for CI

Review the release diff and stage only its intended source/metadata/documentation files. Commit and push `YOUR_DEFAULT_BRANCH` without bypassing hooks. If hooks modify files, inspect and validate those changes before completing the commit.

```bash
git status --short
git add src/YOUR_IMPORT_PACKAGE/_version.py uv.lock CHANGELOG.md README.md
git diff --cached --check
git commit -m "release: prepare ${release_tag}"
git push origin YOUR_DEFAULT_BRANCH
release_commit=$(git rev-parse HEAD)
gh run list --repo "$release_repo" --workflow YOUR_CHECK_WORKFLOW.yml --commit "$release_commit"
```

Inspect the corresponding run with `gh run view RUN_ID --repo "$release_repo"`. Require the Checks workflow to succeed for this exact commit on all configured Python versions, and verify the remote YOUR_DEFAULT_BRANCH branch matches it. Do not reuse an older successful run or tag a commit while its CI is pending.

## 7. Create the immutable tag

Recheck tag/release absence remotely and the clean checkout identity immediately before creating the tag. Create an annotated tag on the verified SHA and push that tag only:

```bash
git tag -a "$release_tag" "$release_commit" -m "Release ${release_tag}"
git push origin "refs/tags/${release_tag}"
git cat-file -t "$release_tag"
git rev-parse "${release_tag}^{commit}"
git ls-remote --tags origin "refs/tags/${release_tag}" "refs/tags/${release_tag}^{}"
```

The local object type must be `tag`; its peeled commit and the remote peeled commit must equal `release_commit`. Treat a pushed tag as immutable. Creating it is not permission to publish the GitHub release yet.

## 8. Run a nonpublishing preflight

Confirm a clean checkout and `HEAD == release_commit == release_tag^{commit}`. Repeat section 5's complete validation block against that identity. Branch CI already validates the release commit; this repository has no tag-triggered release workflow or `workflow_dispatch` publication preflight to invoke.

Retain the exact validated wheel, sdist, and manifest in `dist/`, and the reviewed notes in their ignored file. Verify artifact versions again and record their filenames and hashes. Do not rebuild or change these bytes after publication approval; changes require renewed validation and approval.

## 9. Approve publication

**Stop and end the turn for a second explicit approval.** Present the exact version, annotated tag, full commit SHA, successful CI URL, reviewed notes, artifact names/hashes, repository destination, and the command below. Explain that it creates a GitHub release and uploads the three assets, with no PyPI upload or deployment pipeline. Approval must cover this exact prepared result; it is separate from the version confirmation.

## 10. Publish and handle manual approval

After explicit approval, recheck tag identity, local checksums, reviewed notes, and release absence. Publish the retained artifacts without an implicit tag or autogenerated notes:

```bash
gh release create "$release_tag" dist/*.whl dist/*.tar.gz dist/SHA256SUMS \
  --repo "$release_repo" --verify-tag --title "$release_tag" --notes-file "$release_notes_path"
```

Asset upload and publication use separate API operations and can fail partially. Inspect state before retrying. No protected deployment approval is configured here; if a new/manual gate appears, identify the exact run or deployment, ask for the required action, and end the turn without polling until the user responds.

## 11. Verify every published surface

```bash
gh release view "$release_tag" --repo "$release_repo" --json url,tagName,isDraft,isPrerelease,body,assets
release_verify_dir=$(mktemp -d /tmp/release_verify_XXXXXX)
gh release download "$release_tag" --repo "$release_repo" --dir "$release_verify_dir" \
  --pattern '*.whl' --pattern '*.tar.gz' --pattern SHA256SUMS
cmp dist/SHA256SUMS "$release_verify_dir/SHA256SUMS"
(cd "$release_verify_dir" && sha256sum --check SHA256SUMS)
git status --short
```

Confirm a published, non-prerelease release with the exact tag, curated notes, and three expected uploaded assets; automatically generated source snapshots are separate. Recheck the remote tag SHA, released version/date, and all changelog comparison/release links. The downloaded manifest must match the retained manifest and verify the downloaded bytes, which were independently installation-tested before upload. These checksums detect byte mismatches; they are not signatures or independent proof of authorship.

Report the version, tag, commit, CI/release URLs, asset verification, and final branch/worktree state. Keep `Unreleased` available for future work. Do not bump the version again just to mark development as resumed.

## 12. Recover safely

- Before tagging: fix preparation/check failures, review and commit any corrections, push, and require fresh CI for the changed commit.
- After tagging but before publication: retain the tag and validated bytes. Resume only against that exact commit; if source corrections are needed, stop and ask for a new version rather than moving the tag.
- After an interrupted create/upload or a lost response: inspect the existing release, its draft/published status, tag, notes, and asset names/digests before retrying. Do not blindly create a second release or use an overwrite option. A matching unpublished draft may be completed only after confirming the approved bytes and scope; stop for uncertain or changed recovery decisions.
- After publication: do not silently replace published assets or rewrite the tag. A defective release needs an explicitly approved correction/new version. Preserve evidence and validated artifacts until recovery is settled.

Do not delete tags/releases, force-push, publish to another destination, or introduce release automation as an automatic recovery step.
````

### Extend the runbook for PyPI when selected

If the user explicitly chooses PyPI publication, extend the manual runbook with the automated pipeline from section 12. Keep the same two approvals. Only that path requires the workflow_dispatch/protected-environment steps below; do not invent them for a GitHub-only release. In the generic runbook from the agnostic setup, make these Python steps exact:

1. Name the package version file, `pyproject.toml`, `uv.lock`, `PYPI.md` or `README.md`, wheel name, source-archive name, tag form, PyPI project, and release workflow as sources of truth.
2. Have Codex inspect the complete diff since the previous tag and propose the next semantic version. Stop and obtain explicit user approval of that exact version before editing it.
3. Update the version source, changelog comparison links/date, classifiers, Python support text, package-index description, entry-point examples, and lock file when affected.
4. Run `uv lock --check`, the full manual pre-commit stage, documentation checks, `uv build --clear`, `twine check`, archive-content inspection, and independent wheel/sdist smoke tests.
5. Commit and push the release preparation, require CI success for that commit, create an annotated tag on it, and run the workflow's nonpublishing `workflow_dispatch` preflight against the tag.
6. Summarize the exact version, tag, commit, artifacts, GitHub Release, and PyPI trusted-publishing pipeline. Stop for a second explicit user approval before publishing the GitHub Release.
7. After the release event starts the workflow, show the exact pending `pypi` environment deployment, ask the user to approve it on GitHub, and end the turn. Do not poll while waiting for that manual action.
8. Resume only after new user input. Require the workflow to succeed, then verify GitHub assets, `SHA256SUMS`, PyPI files/metadata/provenance, and a fresh installation of the exact published version.
9. Never move a pushed tag or replace a PyPI filename. Retain exact validated artifacts after partial publication; a defective published artifact requires a new version.

For a non-GitHub project or an explicitly chosen direct-release process, keep the same two user confirmations and artifact validation. Publish the exact checked files with `uv publish dist/*.whl dist/*.tar.gz` or `twine upload`, retain credentials outside shell history, upload the artifacts and generated `SHA256SUMS` to the release destination, and perform the same public verification.

## 14. Verify the Python setup

Run the checks in increasing scope:

```bash
uv lock --check
uv run ruff check
uv run pydocfmt check
uv run ruff format --check
uv run ty check --force-exclude
uv run pytest -n 0
uv run pre-commit run --all-files --hook-stage manual
git diff --check
git status --short
```

For a distributable package, build, inspect, and independently smoke-test both distributions during setup, before any publication. Verify the configured coverage scope/branch mode and report-only policy, both serial/default pytest modes, and on-demand reports. Confirm Release diffs exists with clearly non-live pre-tag examples or real tag links, and that a filled RELEASE.md exists for a versioned project; do not execute release commands as a setup check. Inspect wheels/sdists for forbidden local/agent state, especially ignored plans and their tracked placeholder. Include a py.typed marker when the package promises inline types to downstream consumers; the marker declares typing support, not local checker activation. Format Markdown tables with `uv run la-dev-markdown-tables` and verify with `uv run la-dev-markdown-tables --check`.

Run the Python audit; it checks both this recipe and the prerequisite agnostic recipe:

```text
$toolkit:perform audit-project-setup[python]
```

Continue with [AI-supported repository development](https://github.com/pallgeuer/la-dev-codex-plugins/blob/main/docs/ai_supported_development.md).
