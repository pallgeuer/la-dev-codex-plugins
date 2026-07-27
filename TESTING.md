# Testing

This repository uses fixed-version `uvx` commands for test tools. `uvx` runs each tool in an isolated cached environment; it does not create or use a project `.venv`.

The shipped plugin scripts must support Python 3.6+ and must use only the Python standard library. Functional tests run with Python 3.8, and Vermin checks that shipped plugin code remains compatible with Python 3.6+.

## Install uv

If `uvx` is already installed, skip this section.

macOS/Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Alternative with Homebrew:

```bash
brew install uv
```

Verify:

```bash
uvx --version
```

## Lint and format Python

Lint and apply safe fixes:

```bash
uvx --python 3.10 --from pre-commit==4.6.0 pre-commit run ruff-check-fix --all-files
```

Format:

```bash
uvx --python 3.10 --from pre-commit==4.6.0 pre-commit run ruff-format-fix --all-files
```

Read-only checks:

```bash
uvx --python 3.10 --from pre-commit==4.6.0 pre-commit run ruff-check --all-files --hook-stage manual
uvx --python 3.10 --from pre-commit==4.6.0 pre-commit run ruff-format-check --all-files --hook-stage manual
```

## Type check

Run ty with Python 3.8 semantics:

```bash
uvx --python 3.10 --from pre-commit==4.6.0 pre-commit run ty --all-files --hook-stage manual
```

## Run tests

Run all tests with Python 3.8:

```bash
uvx --python 3.10 --from pre-commit==4.6.0 pre-commit run pytest --all-files --hook-stage manual
```

Run only Loupe tests:

```bash
uvx --python 3.8 --from pytest==8.3.5 pytest tests/plugins/la-review/skills/loupe
```

Run only Perform tests:

```bash
uvx --python 3.8 --from pytest==8.3.5 pytest tests/plugins/toolkit/skills/perform
```

Run the source-only Perform launcher tests:

```bash
uvx --python 3.8 --from pytest==8.3.5 pytest tests/test_codex_perform_*.py
```

Run the release-version validator and declaration tests:

```bash
uvx --python 3.8 --from pytest==8.3.5 pytest tests/test_validate_release.py tests/test_versions.py
```

Validate the bundled Perform catalog after editing it:

```bash
python3 -m json.tool plugins/toolkit/skills/perform/assets/toolkit_perform_actions/actions.json > /dev/null
```

## Check Python 3.6+ compatibility

Run Vermin against the shipped plugin, repository helper, and package code:

```bash
uvx --python 3.10 --from pre-commit==4.6.0 pre-commit run vermin --all-files --hook-stage manual
```

Run it only for Loupe scripts:

```bash
uvx --python 3.8 --from vermin==1.8.0 vermin -t=3.6- --violations plugins/la-review/skills/loupe/scripts
```

Use `-t=3.6-` rather than trying to run the test suite under Python 3.6. The purpose here is to analyze the plugin scripts for minimum Python-version requirements; uv itself does not need to provide a Python 3.6 interpreter.

## Recommended pre-commit check

Run all local auto-fixing hooks:

```bash
uvx --python 3.10 --from pre-commit==4.6.0 pre-commit run --all-files
```

Run the exact read-only checks used by CI:

```bash
uvx --python 3.10 --from pre-commit==4.6.0 pre-commit run --all-files --hook-stage manual
```

Pre-commit only considers files known to Git. Stage new files before running the all-files checks so that they are included. If an auto-fixing hook changes files, stage the fixes and run the checks again.

Install both the auto-fixing pre-commit hook and the read-only pre-push hook:

```bash
uvx --python 3.10 --from pre-commit==4.6.0 pre-commit install --install-hooks
```
