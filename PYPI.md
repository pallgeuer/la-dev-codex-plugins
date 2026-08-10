# Language-Agnostic Development Codex Plugins

`la-dev-codex-plugins` supplies dependency-free Python command-line tooling and reusable development utilities from the [Language-Agnostic Development Codex Plugins](https://github.com/pallgeuer/la-dev-codex-plugins) repository.

The Python distribution installs three commands:

- `codex-perform`, a standalone launcher for actions configured by the marketplace's Toolkit plugin.
- `la-dev-markdown-tables`, a canonical Markdown pipe-table formatter and checker.
- `la-dev-release-checksums`, a deterministic, failure-safe SHA-256 manifest generator.

It also contains an explicitly loaded pytest-isolation plugin. The distribution does not install Codex, the marketplace, any Codex plugin, or the Toolkit action runtime and assets.

## Install in a virtual environment

Create and activate any Python 3.6+ virtual environment, then install the package:

```bash
python3 -m venv /PATH/TO/VENV
source /PATH/TO/VENV/bin/activate
python -m pip install la-dev-codex-plugins
codex-perform --version
la-dev-markdown-tables --version
la-dev-release-checksums --version
```

The command is available while the virtual environment is active. It always uses that environment's Python interpreter and restarts it in isolated mode before importing the package, so the caller's current directory, `PYTHONPATH`, and user site-packages cannot replace the installed launcher.

The published pure-Python wheel supports Python 3.6 through current Python releases. The base install has no mandatory dependencies; Codex Perform, Markdown tables, and release checksums use only the Python standard library. On an older Python installation, use `--only-binary=:all:` if you want installation to fail rather than fall back to building the source distribution:

```bash
python -m pip install --only-binary=:all: la-dev-codex-plugins
```

Install the optional pytest integration with either extra:

```bash
python -m pip install 'la-dev-codex-plugins[pytest]'
python -m pip install 'la-dev-codex-plugins[dev]'
```

Both extras currently add `pytest>=7.0.1`. The package does not register a `pytest11` entry point, so installing an extra never activates the plugin automatically; explicitly load `la_dev_codex_plugins.pytest_isolation.plugin` in the downstream suite. Loading alone leaves unmarked tests untouched. Suites can use private per-test `isolated_cwd` and `guarded_cwd` fixtures or markers, separately opt otherwise unmarked tests into one session-shared guarded CWD per pytest process, and customize that process-global shared boundary through a pytest hook. Boundaries use immediate verified cleanup by default; suites with interpreter-owned resources can opt into a pytest-retained lifecycle whose compatibility requirements and later-pruning tradeoffs are documented in the detailed guide.

Detailed documentation:

- [Codex Perform](https://github.com/pallgeuer/la-dev-codex-plugins/blob/main/docs/codex_perform.md)
- [Markdown tables](https://github.com/pallgeuer/la-dev-codex-plugins/blob/main/docs/markdown_tables.md)
- [Pytest working-directory isolation](https://github.com/pallgeuer/la-dev-codex-plugins/blob/main/docs/pytest_isolation.md)
- [Release checksums](https://github.com/pallgeuer/la-dev-codex-plugins/blob/main/docs/release_checksums.md)

## Install the Toolkit plugin separately

The default launcher flow requires the `toolkit` plugin from the `la-dev-codex-plugins` marketplace to be installed and enabled for the active `codex` executable and `CODEX_HOME`. See the [marketplace plugin installation guide](https://github.com/pallgeuer/la-dev-codex-plugins/blob/main/docs/installation.md) for marketplace and plugin installation.

At runtime, `codex-perform` asks Codex for the installed Toolkit version, validates its cache layout and manifest, checks the launcher API version, and imports the runtime from that selected plugin. The Python distribution and Toolkit plugin versions do not have to match exactly, but their launcher API versions must be compatible.

Use `--plugin-root` to select an explicit Toolkit plugin checkout during development:

```bash
codex-perform --plugin-root /PATH/TO/la-dev-codex-plugins/plugins/toolkit list
```

## Source-only alternative

Installing the Python package is optional. The repository also provides `activate.sh`, which defines the same command directly from a checkout and works with a read-only standard-library Python 3.6+ installation:

```bash
source /PATH/TO/la-dev-codex-plugins/activate.sh
codex-perform --version
```

`CODEX_PERFORM_PYTHON` selects the interpreter only for this source-only activation path. If a shell already contains the source-defined `codex-perform` function, that function takes precedence over an executable installed by a subsequently activated virtual environment; start a fresh shell or run `unset -f codex-perform` before using the venv command.

## Support

The officially supported hosts are Ubuntu 18.04 or newer and macOS 14 or newer. Compatibility with other POSIX Linux distributions is intended but is not part of the official support guarantee. Native Windows and WSL are not supported. For action configuration, CLI behavior, and troubleshooting, use the [Codex Perform documentation](https://github.com/pallgeuer/la-dev-codex-plugins/blob/main/docs/codex_perform.md). For marketplace and development documentation, use the [documentation index](https://github.com/pallgeuer/la-dev-codex-plugins/blob/main/docs/README.md).
