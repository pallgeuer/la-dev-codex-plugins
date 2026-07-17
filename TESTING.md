# Testing

This repository uses fixed-version `uvx` commands for test tools.

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
uvx --python 3.8 --from ruff==0.15.22 ruff check --fix plugins src tests
```

Format:

```bash
uvx --python 3.8 --from ruff==0.15.22 ruff format plugins src tests
```

Read-only checks:

```bash
uvx --python 3.8 --from ruff==0.15.22 ruff check plugins src tests
uvx --python 3.8 --from ruff==0.15.22 ruff format --check plugins src tests
```

## Type check

Run ty with Python 3.8 semantics:

```bash
uvx --python 3.8 --from ty==0.0.60 --with pytest==8.3.5 ty check plugins src tests
```

## Run tests

Run all tests with Python 3.8:

```bash
uvx --python 3.8 --from pytest==8.3.5 pytest tests
```

Run only Loupe tests:

```bash
uvx --python 3.8 --from pytest==8.3.5 pytest tests/plugins/la-review/skills/loupe
```

## Check Python 3.6+ compatibility

Run Vermin against the shipped plugin and package code:

```bash
uvx --python 3.8 --from vermin==1.8.0 vermin -t=3.6- --violations plugins src
```

Run it only for Loupe scripts:

```bash
uvx --python 3.8 --from vermin==1.8.0 vermin -t=3.6- --violations plugins/la-review/skills/loupe/scripts
```

Use `-t=3.6-` rather than trying to run the test suite under Python 3.6. The purpose here is to analyze the plugin scripts for minimum Python-version requirements; uv itself does not need to provide a Python 3.6 interpreter.

## Pre-commit

Run the local hooks:

```bash
uvx --python 3.10 --from pre-commit==4.6.0 pre-commit run --all-files
```

Install the hook:

```bash
uvx --python 3.10 --from pre-commit==4.6.0 pre-commit install
```

## Recommended pre-commit check

Before committing changes to plugin scripts, run:

```bash
python3 -m json.tool .agents/plugins/marketplace.json > /dev/null
python3 -m json.tool plugins/la-review/.codex-plugin/plugin.json > /dev/null
python3 -m json.tool plugins/toolkit/.codex-plugin/plugin.json > /dev/null
python3 -m json.tool plugins/toolkit/skills/perform/actions/plan.json > /dev/null
python3 -m json.tool plugins/toolkit/skills/perform/actions/exec-plan.json > /dev/null
uvx --python 3.8 --from ruff==0.15.22 ruff check --fix plugins src tests
uvx --python 3.8 --from ruff==0.15.22 ruff format plugins src tests
uvx --python 3.8 --from ty==0.0.60 --with pytest==8.3.5 ty check plugins src tests
uvx --python 3.8 --from pytest==8.3.5 pytest tests
uvx --python 3.8 --from vermin==1.8.0 vermin -t=3.6- --violations plugins src
```
