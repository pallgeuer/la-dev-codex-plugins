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

Run Codex Perform tests:

```bash
uvx --python 3.8 --from pytest==8.3.5 pytest tests/codex_perform/
```

Run shared behavioral contracts:

```bash
uvx --python 3.8 --from pytest==8.3.5 pytest tests/contracts/
```

Run all plugin tests, or one existing plugin test family:

```bash
uvx --python 3.8 --from pytest==8.3.5 pytest tests/plugins/
uvx --python 3.8 --from pytest==8.3.5 pytest tests/plugins/la-review/skills/loupe/
uvx --python 3.8 --from pytest==8.3.5 pytest tests/plugins/toolkit/skills/perform/
```

Run the Python-distribution contract:

```bash
uvx --python 3.8 --from pytest==8.3.5 pytest tests/python_distribution/test_contract.py
```

Run the focused reusable-tool suites:

```bash
uvx --python 3.8 --from pytest==8.3.5 pytest tests/markdown_tables/
uvx --python 3.8 --from pytest==8.3.5 pytest tests/release_checksums/
```

The release-checksum suite covers exact UTF-8/LF bytes, POSIX permissions, symlink and hard-link identity, stale-output invalidation, atomic replacement, file `fsync`, and failure cleanup. Run individual files when localizing library or CLI failures:

```bash
uvx --python 3.8 --from pytest==8.3.5 pytest tests/release_checksums/test_core.py
uvx --python 3.8 --from pytest==8.3.5 pytest tests/release_checksums/test_cli.py
```

Run the exhaustive pytest-isolation behavior suite with the repository baseline and current pytest:

```bash
uvx --python 3.8 --from pytest==8.3.5 pytest tests/pytest_isolation/
uvx --python 3.10 --from pytest==9.1.1 pytest tests/pytest_isolation/
```

Run repository contracts and repository-script tests:

```bash
uvx --python 3.8 --from pytest==8.3.5 pytest tests/repo/
uvx --python 3.8 --from pytest==8.3.5 pytest tests/scripts/
```

Run the dependency-free supported-platform smoke checks with the active Python interpreter:

```bash
python3 tests/platform/supported_platform_smoke.py
```

This smoke program covers shipped action discovery and inspection, atomic catalogue writes, the source-activated launcher, bounded process termination, Loupe's Bash subprocess path, and dependency-free UTF-8/LF release-checksum placement with symlink and hard-link identity checks. It is deliberately compatible with Python 3.6 and uses only the standard library so that CI can run it with Ubuntu 18.04's native interpreter. Keep this no-dependency proof separate from every pytest smoke.

Ubuntu CI runs the smoke once with the C locale and once with C.UTF-8. The C-locale run completes the checksum workflow with an ASCII artifact name and verifies that an unrepresentable Unicode text path raises the documented `ReleaseChecksumError`; the C.UTF-8 run completes the same workflow with a Unicode artifact name. Reproduce both modes on a host that provides C.UTF-8 with:

```bash
LANG=C LC_ALL=C python3 tests/platform/supported_platform_smoke.py
LANG=C.UTF-8 LC_ALL=C.UTF-8 python3 tests/platform/supported_platform_smoke.py
```

Build and validate the exact Python source and wheel distributions:

```bash
rm -rf build dist src/la_dev_codex_plugins.egg-info
uvx --python 3.10 --from build==1.5.0 python -m build
uvx --python 3.10 --from twine==6.2.0 twine check dist/*
python3 scripts/validate_python_distribution.py dist --version "$(sed -n 's/^version = //p' setup.cfg)"
```

These commands create ignored build artifacts in the checkout. The validator requires one minimal sdist and one `py3-none-any` wheel, rejects unconditional runtime dependencies and unexpected files, verifies the exact optional extras and console entry points, and verifies that the installed bootstrap re-executes isolated Python. The `Python package release` workflow performs this build only for manual release preflights and published GitHub Releases.

After building, install the wheel into a disposable virtual environment and run the distribution smoke checks:

```bash
python3 -m venv /tmp/la-dev-codex-plugins-package-test
/tmp/la-dev-codex-plugins-package-test/bin/python -m pip install --no-index --no-deps dist/*.whl
PATH="/tmp/la-dev-codex-plugins-package-test/bin:$PATH" /tmp/la-dev-codex-plugins-package-test/bin/python tests/python_distribution/smoke_installed_package.py --expected-version "$(sed -n 's/^version = //p' setup.cfg)" --plugin-root plugins/toolkit
```

Only after the base `--no-index --no-deps` smoke passes, add a fixed pytest and exercise the explicitly loaded installed plugin:

```bash
/tmp/la-dev-codex-plugins-package-test/bin/python -m pip install pytest==8.3.5
/tmp/la-dev-codex-plugins-package-test/bin/python tests/python_distribution/smoke_pytest_isolation.py --expected-pytest-version 8.3.5
```

CI repeats the installed-plugin smoke with pytest 7.0.1 in the Ubuntu 18.04/Python 3.6 environment, pytest 8.3.5 on the oldest supported macOS Intel runner, and pytest 9.1.1 on the current macOS Arm64 runner. The smoke checks inert default behavior, explicit private modes, configured shared reuse and root policy files, layered session/module/function fixture lifetimes, pytest temporary-artifact retention, private precedence and return to the shared guard, session restoration and cleanup, exact guarded permissions, and leak detection without assuming those permissions prevent root writes. The macOS jobs use separate virtual environments so the dependency-free platform smoke always runs before pytest is installed. To reproduce the minimum combination in the Ubuntu 18.04 container:

```bash
docker run --rm --env PYTHONDONTWRITEBYTECODE=1 --volume "$PWD:/workspace:ro" --workdir /workspace ubuntu:18.04 bash -c "apt-get update && apt-get install --yes python3-venv && python3 -m venv /tmp/pytest-venv && /tmp/pytest-venv/bin/pip install pytest==7.0.1 && LANG=C LC_ALL=C PYTHONPATH=/workspace/src /tmp/pytest-venv/bin/python tests/python_distribution/smoke_pytest_isolation.py --expected-pytest-version 7.0.1"
```

The Python-package release workflow also downloads the exact validated wheel into a current macOS Arm64 job, installs it without package-index access or dependencies, and runs `smoke_installed_package.py`. Publication depends on this macOS wheel smoke as well as the Ubuntu installation checks.

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

Use `-t=3.6-` rather than trying to run the exhaustive pytest suite under Python 3.6. Vermin analyzes the complete runtime source, source launcher, and installed bootstrap for minimum Python-version requirements, while `tests/platform/supported_platform_smoke.py` and `tests/python_distribution/smoke_installed_package.py` supply focused dependency-free runtime execution under Python 3.6. The dedicated `smoke_pytest_isolation.py` separately covers the optional plugin with fixed pytest.

## Recommended pre-commit check

Run all local auto-fixing hooks:

```bash
uvx --python 3.10 --from pre-commit==4.6.0 pre-commit run --all-files
```

Run the exact read-only checks used by CI's main pre-commit job:

```bash
uvx --python 3.10 --from pre-commit==4.6.0 pre-commit run --all-files --hook-stage manual
```

Validate the published hook manifest and exercise both Markdown-table hooks explicitly:

```bash
uvx --python 3.10 --from pre-commit==4.6.0 pre-commit validate-manifest .pre-commit-hooks.yaml
uvx --python 3.10 --from pre-commit==4.6.0 pre-commit run markdown-tables-fix --all-files
uvx --python 3.10 --from pre-commit==4.6.0 pre-commit run markdown-tables-check --all-files --hook-stage manual
```

Also run the supported-platform smoke program and macOS selector locally as shown above. CI repeats the smoke checks on the supported baseline and forward-compatibility operating-system targets.

Pre-commit only considers files known to Git. Stage new files before running the all-files checks so that they are included. If an auto-fixing hook changes files, stage the fixes and run the checks again.

Install both the auto-fixing pre-commit hook and the read-only pre-push hook:

```bash
uvx --python 3.10 --from pre-commit==4.6.0 pre-commit install --install-hooks
```
