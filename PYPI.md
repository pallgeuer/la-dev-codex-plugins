# Language-Agnostic Development Codex Plugins

`la-dev-codex-plugins` supplies dependency-free Python command-line tooling for the [Language-Agnostic Development Codex Plugins](https://github.com/pallgeuer/la-dev-codex-plugins) marketplace.

The current Python distribution installs `codex-perform`, a standalone launcher for actions configured by the marketplace's Toolkit plugin. It contains the slim launcher only: it does not install Codex, the marketplace, any Codex plugin, or the Toolkit action runtime and assets.

## Install in a virtual environment

Create and activate any Python 3.6+ virtual environment, then install the package:

```bash
python3 -m venv /PATH/TO/VENV
source /PATH/TO/VENV/bin/activate
python -m pip install la-dev-codex-plugins
codex-perform --version
codex-perform --help
```

The command is available while the virtual environment is active. It always uses that environment's Python interpreter and restarts it in isolated mode before importing the package, so the caller's current directory, `PYTHONPATH`, and user site-packages cannot replace the installed launcher.

The published pure-Python wheel supports Python 3.6 through current Python releases without runtime dependencies. On an older Python installation, use `--only-binary=:all:` if you want installation to fail rather than fall back to building the source distribution:

```bash
python -m pip install --only-binary=:all: la-dev-codex-plugins
```

## Install the Toolkit plugin separately

The default launcher flow requires the `toolkit` plugin from the `la-dev-codex-plugins` marketplace to be installed and enabled for the active `codex` executable and `CODEX_HOME`. See the [repository installation guide](https://github.com/pallgeuer/la-dev-codex-plugins#install) for marketplace and plugin installation.

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

The supported hosts are Ubuntu 18.04 or newer and macOS 14 or newer. Native Windows and WSL are not supported. For action configuration, CLI behavior, troubleshooting, and development documentation, use the [full repository documentation](https://github.com/pallgeuer/la-dev-codex-plugins).
