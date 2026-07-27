# Testing

This repository uses fixed-version `uvx` commands for test tools. `uvx` runs each tool in an isolated cached environment; it does not create or use a project `.venv`.

The shipped plugin scripts must support Python 3.6+ and must use only the Python standard library. Functional tests run with Python 3.8, Vermin checks that shipped plugin code remains compatible with Python 3.6+, and the dependency-free supported-platform smoke checks run in CI on Ubuntu 18.04 with Python 3.6, the oldest non-deprecated hosted macOS Intel runner with Python 3.8, and the current `macos-latest` Arm64 runner with the newest stable Python 3.x.

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

Run the dependency-free supported-platform smoke checks with the active Python interpreter:

```bash
python3 tests/supported_platform_smoke.py
```

This smoke program covers shipped action discovery and inspection, atomic catalogue writes, the source-activated launcher, bounded process termination, and Loupe's Bash subprocess path. It is deliberately compatible with Python 3.6 and uses only the standard library so that CI can run it with Ubuntu 18.04's native interpreter.

The macOS selector reads the official `actions/runner-images` availability table and fails closed if it cannot identify one ordinary non-deprecated GA Intel label:

```bash
curl -fsSL https://raw.githubusercontent.com/actions/runner-images/main/README.md | python3 scripts/select_oldest_macos_runner.py
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

Use `-t=3.6-` rather than trying to run the pytest suite under Python 3.6. Vermin analyzes the complete runtime source for minimum Python-version requirements, while `tests/supported_platform_smoke.py` supplies focused runtime execution under Python 3.6 without requiring uv or third-party test packages.

## Recommended pre-commit check

Run all local auto-fixing hooks:

```bash
uvx --python 3.10 --from pre-commit==4.6.0 pre-commit run --all-files
```

Run the exact read-only checks used by CI's main pre-commit job:

```bash
uvx --python 3.10 --from pre-commit==4.6.0 pre-commit run --all-files --hook-stage manual
```

Also run the supported-platform smoke program and macOS selector locally as shown above. CI repeats the smoke checks on the supported baseline and forward-compatibility operating-system targets.

Pre-commit only considers files known to Git. Stage new files before running the all-files checks so that they are included. If an auto-fixing hook changes files, stage the fixes and run the checks again.

Install both the auto-fixing pre-commit hook and the read-only pre-push hook:

```bash
uvx --python 3.10 --from pre-commit==4.6.0 pre-commit install --install-hooks
```
