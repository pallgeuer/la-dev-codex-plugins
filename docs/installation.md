# Marketplace plugin installation

Install the marketplace once, then select either or both of its plugins. Marketplace installation is independent of installing the repository's [Python distribution](../PYPI.md).

## Add the marketplace

Choose whether to follow the latest repository state or pin the marketplace to a stable release, then run the corresponding command:

```bash
codex plugin marketplace add pallgeuer/la-dev-codex-plugins --ref main    # <-- Latest version
codex plugin marketplace add pallgeuer/la-dev-codex-plugins --ref vX.Y.Z  # <-- Stable fixed release tag
```

Marketplace refs are Git refs. Use `main` to follow the latest repository state, or use a release tag such as `vX.Y.Z` to pin to a stable fixed release. A `vX.Y.Z` tag identifies version `X.Y.Z` of the repository and therefore one fixed marketplace snapshot. Each plugin has an independent version in its manifest, so plugins in the same repository release may have different versions from each other and from the repository. Available repository release tags are listed on the [GitHub tags page](https://github.com/pallgeuer/la-dev-codex-plugins/tags).

## Install a plugin

Install whichever plugins you want from the marketplace. `la-review` contains [Loupe](loupe.md), while `toolkit` contains [Perform](codex_perform.md):

```bash
codex plugin add la-review@la-dev-codex-plugins
codex plugin add toolkit@la-dev-codex-plugins
```

Each command installs that plugin into the user-level Codex space (i.e. `~/.codex/plugins/cache/`, along with a record in `~/.codex/config.toml`), not into any one project in particular.

## Start Codex and verify the installation

Open Codex, or restart it if it is already running:

```bash
codex
```

Use `/plugins` to check the available plugins:

```text
/plugins
```

To check which skills are available, type `$` and inspect the autocompletion suggestions.

## Optional: Auto-allow the Loupe review script

The Loupe skill calls a bundled Python script in order to run the external review commands. This script unavoidably requires escalated sandbox permissions because it triggers `codex` and/or `claude` subprocesses, which both need write access to their respective user-level directories (e.g. `~/.codex/`) in order to function.

To avoid explicitly accepting the escalated sandbox permissions every time for that particular script, add the following line to `~/.codex/rules/default.rules`, replacing `YOUR_USER` with your user name and `X.Y.Z` with the installed `la-review` plugin version:

```text
prefix_rule(pattern=["/home/YOUR_USER/.codex/plugins/cache/la-dev-codex-plugins/la-review/X.Y.Z/skills/loupe/scripts/run_reviewers.py"], decision="allow")
```

See [Loupe's requirements](loupe.md#requirements) for the reviewer executables and the reason this permission is needed.

## Updating plugins

The update procedure depends on the marketplace ref you chose.

If you used `--ref main`, then Codex will auto-update and reinstall the latest versions of the plugins on startup, so simply restarting `codex` will often suffice. If not, you can manually update your installed plugins from this marketplace with for example:

```bash
codex plugin remove la-review@la-dev-codex-plugins
codex plugin remove toolkit@la-dev-codex-plugins
codex plugin marketplace upgrade la-dev-codex-plugins
codex plugin add la-review@la-dev-codex-plugins
codex plugin add toolkit@la-dev-codex-plugins
```

If you used `--ref vX.Y.Z`, `marketplace upgrade` keeps the marketplace frozen at exactly that ref instead of upgrading it. To move to a newer release, replace the whole marketplace ref:

```bash
codex plugin remove la-review@la-dev-codex-plugins
codex plugin remove toolkit@la-dev-codex-plugins
codex plugin marketplace remove la-dev-codex-plugins
codex plugin marketplace add pallgeuer/la-dev-codex-plugins --ref vX.Y.Z  # <-- New release tag
codex plugin add la-review@la-dev-codex-plugins
codex plugin add toolkit@la-dev-codex-plugins
```

The example assumes that both plugins are installed. When using only one, remove and reinstall that plugin; before replacing the marketplace, remove every plugin currently installed from it.

If you no longer know which ref you used, inspect the marketplace installation metadata with a command such as the following (the exact path may change in future Codex releases):

```bash
cat ~/.codex/.tmp/marketplaces/la-dev-codex-plugins/.codex-marketplace-install.json
```

Remember to check after an update whether you need to update `~/.codex/rules/default.rules` with the latest `la-review` semantic version.

After installing the plugins, see [Recommended Codex setup](recommended_setup.md) for optional user-level instructions and configuration that complement them.
