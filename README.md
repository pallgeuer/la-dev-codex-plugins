# Language-Agnostic Development Codex Plugins

This repository is a Codex plugin marketplace.

It currently exposes one plugin:

- **Language-Agnostic Review** (`la-review`)
  - Includes the **Loupe** skill (`loupe`)
  - Invoke with `$loupe`
  - Default scope: current uncommitted changes

## Install

Add this repository as a Codex marketplace:

```bash
codex plugin marketplace add pallgeuer/la-dev-codex-plugins --ref main
```

Then open Codex:

```bash
codex
```

Open the plugin browser:

```text
/plugins
```

Select **Language-Agnostic Development Codex Plugins**, then install **Language-Agnostic Review**.

## Recommended pinned install

After a release tag exists, prefer a pinned install:

```bash
codex plugin marketplace add pallgeuer/la-dev-codex-plugins --ref v0.1.0
```

## Use

Default review of current uncommitted changes:

```text
$loupe
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
