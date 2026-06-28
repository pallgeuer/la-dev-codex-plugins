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

Python scripts shipped inside any plugin must support Python 3.6+ and must run with only the Python standard library.

Assume the runtime can be any system Python from Ubuntu 18.04 onward. Do not use syntax, standard-library APIs, or typing features that require Python 3.7+.

Do not add non-standard Python runtime dependencies for shipped plugin scripts.

Test-only dependencies are allowed only through the fixed-version `uvx` commands documented in `TESTING.md`.

## Required checks after editing plugin scripts

After changing any file under `plugins/*/skills/*/scripts/`, run:

```bash
uvx --python 3.8 --from pytest==8.3.5 pytest tests
uvx --from vermin==1.8.0 vermin -t=3.6- --violations plugins
```

Vermin checks minimum Python-version compatibility; it does not replace functional tests.

## Loupe invocation policy

Loupe is a direct-invocation skill. Prefer examples that invoke it as `$loupe`, especially for the default uncommitted-changes review.

Do not optimize Loupe metadata for implicit invocation unless the policy is intentionally changed.
