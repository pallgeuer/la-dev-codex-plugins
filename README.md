# Language-Agnostic Development Codex Plugins

This repository is a Codex plugin marketplace.

It currently exposes the following plugins:

- **Language-Agnostic Review** (`la-review`)
  - Includes the **Loupe** skill (`loupe`)
  - Invoke with `$loupe`
  - Default review scope: Current uncommitted changes

## Install

Add this repository as a Codex marketplace:

```bash
codex plugin marketplace add pallgeuer/la-dev-codex-plugins --ref main    # <-- Latest version
codex plugin marketplace add pallgeuer/la-dev-codex-plugins --ref v0.1.0  # <-- Stable fixed version
```

Then open Codex:

```bash
codex
```

Open the plugin browser:

```text
/plugins
```

Select **Language-Agnostic Development Codex Plugins**, then install **Language-Agnostic Review**. This installs the plugin into the user-level Codex space (i.e. `~/.codex/plugins/cache/`, along with a record in `~/.codex/config.toml`), not into any one project in particular.

## Use

Default review of current uncommitted changes:

```text
$loupe
```

Review just unstaged changes (should include untracked changes, but explicit is better than implicit):

```text
$loupe unstaged changes
$loupe unstaged and untracked changes
```

Review the last commit:

```text
$loupe last commit
```

Review a branch:

```text
$loupe feature/loupe-plugin branch
```

Review a pull request:

```text
$loupe PR #123
```

## Development

See `TESTING.md`.

The shipped plugin scripts must support Python 3.6+ and must use only the Python standard library.
