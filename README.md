# Language-Agnostic Development Codex Plugins

This repository is a Codex plugin marketplace.

It currently exposes the following plugins:

- **Language-Agnostic Review** (`la-review`)
  - Includes the **Loupe** skill (`loupe`)
  - Invoke with `$la-review:loupe`
  - Default review scope: Current uncommitted changes

## Install

Add this repository as a Codex marketplace:

```bash
codex plugin marketplace add pallgeuer/la-dev-codex-plugins --ref main    # <-- Latest version
codex plugin marketplace add pallgeuer/la-dev-codex-plugins --ref vX.Y.Z  # <-- Stable fixed release tag
```

Marketplace refs are Git refs. Use `main` to follow the latest repository state, or use a release tag such as `vX.Y.Z` to pin to a stable fixed release. Available release tags are listed on the [GitHub tags page](https://github.com/pallgeuer/la-dev-codex-plugins/tags). By convention, plugin versions in manifests are kept in sync with release tag versions, without the leading `v`.

Then install whichever plugins you want from that marketplace:

```bash
codex plugin add la-review@la-dev-codex-plugins
```

This installs the plugin into the user-level Codex space (i.e. `~/.codex/plugins/cache/`, along with a record in `~/.codex/config.toml`), not into any one project in particular.

If you used `--ref main`, then you can update an installed plugin in future using:

```bash
codex plugin remove la-review@la-dev-codex-plugins
codex plugin marketplace upgrade la-dev-codex-plugins
codex plugin add la-review@la-dev-codex-plugins
```

If you used `--ref vX.Y.Z`, then `marketplace upgrade` keeps the version frozen at exactly that instead of actually upgrading, so you need to update the whole marketplace ref:

```bash
codex plugin remove la-review@la-dev-codex-plugins
codex plugin marketplace remove la-dev-codex-plugins
codex plugin marketplace add pallgeuer/la-dev-codex-plugins --ref vX.Y.Z  # <-- New release tag
codex plugin add la-review@la-dev-codex-plugins
```

You can verify what ref the marketplace was added with in the past using something like (exact path may change in future Codex releases):

```bash
cat ~/.codex/.tmp/marketplaces/la-dev-codex-plugins/.codex-marketplace-install.json
```

Open/restart Codex and try it all out:

```bash
codex
```

You can check the available plugins using:

```text
/plugins
```

You can check which skills are available by typing `$` and checking the autocompletion.

The Loupe skill calls a bundled Python script in order to run the external review commands. This script unavoidably requires escalated sandbox permissions because it triggers `codex` and/or `claude` subprocesses, which both need write access to their respective user-level directories (e.g. `~/.codex/`) in order to function. To avoid needing to explicitly accept the escalated sandbox permissions every time for that particular script, you can add a rule that whitelists it by adding the following line to `~/.codex/rules/default.rules` (replace `YOUR_USER` and `X.Y.Z` as appropriate):

```text
prefix_rule(pattern=["/home/YOUR_USER/.codex/plugins/cache/la-dev-codex-plugins/la-review/X.Y.Z/skills/loupe/scripts/run_reviewers.py"], decision="allow")
```

## Use

Default review of current uncommitted changes:

```text
$la-review:loupe
```

Tip: Typing `$lou` and then accepting the Codex autocomplete suggestion is usually enough to insert the full `$la-review:loupe` invocation without typing it out manually.

Review just unstaged changes (should include untracked changes, but explicit is better than implicit):

```text
$la-review:loupe unstaged changes
$la-review:loupe unstaged and untracked changes
```

Review the last commit:

```text
$la-review:loupe last commit
```

Review a branch:

```text
$la-review:loupe feature/loupe-plugin branch
```

Review a pull request:

```text
$la-review:loupe PR #123
```

## Development

See `TESTING.md`.

The shipped plugin scripts must support Python 3.6+ and must use only the Python standard library.
