# Language-Agnostic Development Codex Plugins

This repository is a Codex plugin marketplace, version 0.1.6.

It currently exposes the following plugins:

- **Language-Agnostic Review** (`la-review`)
  - Includes the **Loupe** skill (`loupe`)
    - Invoke with `$la-review:loupe`
    - Default review scope is current uncommitted changes, unless otherwise specified
- **Action Toolkit** (`toolkit`)
  - Includes the **Perform** skill (`perform`)
    - Runs reusable, configurable Codex actions from layered JSON action files
    - Invoke with `$toolkit:perform`
    - Select an exact `ACTION[LANGUAGE]` variant, use a bare action name, or describe a task that clearly matches an available action

## Install

### Add the marketplace

Choose whether to follow the latest repository state or pin the marketplace to a stable release, then run the corresponding command:

```bash
codex plugin marketplace add pallgeuer/la-dev-codex-plugins --ref main    # <-- Latest version
codex plugin marketplace add pallgeuer/la-dev-codex-plugins --ref vX.Y.Z  # <-- Stable fixed release tag
```

Marketplace refs are Git refs. Use `main` to follow the latest repository state, or use a release tag such as `vX.Y.Z` to pin to a stable fixed release. A `vX.Y.Z` tag identifies version `X.Y.Z` of the repository and therefore one fixed marketplace snapshot. Each plugin has an independent version in its manifest, so plugins in the same repository release may have different versions from each other and from the repository. Available repository release tags are listed on the [GitHub tags page](https://github.com/pallgeuer/la-dev-codex-plugins/tags).

### Install a plugin

Install whichever plugins you want from the marketplace. For example:

```bash
codex plugin add la-review@la-dev-codex-plugins
codex plugin add toolkit@la-dev-codex-plugins
```

Each command installs that plugin into the user-level Codex space (i.e. `~/.codex/plugins/cache/`, along with a record in `~/.codex/config.toml`), not into any one project in particular.

### Start Codex and verify the installation

Open Codex, or restart it if it is already running:

```bash
codex
```

Use `/plugins` to check the available plugins:

```text
/plugins
```

To check which skills are available, type `$` and inspect the autocompletion suggestions.

### Optional: Auto-allow the Loupe review script

The Loupe skill calls a bundled Python script in order to run the external review commands. This script unavoidably requires escalated sandbox permissions because it triggers `codex` and/or `claude` subprocesses, which both need write access to their respective user-level directories (e.g. `~/.codex/`) in order to function.

To avoid explicitly accepting the escalated sandbox permissions every time for that particular script, add the following line to `~/.codex/rules/default.rules`, replacing `YOUR_USER` with your user name and `X.Y.Z` with the installed `la-review` plugin version:

```text
prefix_rule(pattern=["/home/YOUR_USER/.codex/plugins/cache/la-dev-codex-plugins/la-review/X.Y.Z/skills/loupe/scripts/run_reviewers.py"], decision="allow")
```

### Updating plugins

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
codex plugin marketplace remove la-dev-codex-plugins
codex plugin marketplace add pallgeuer/la-dev-codex-plugins --ref vX.Y.Z  # <-- New release tag
codex plugin add la-review@la-dev-codex-plugins
```

If you no longer know which ref you used, inspect the marketplace installation metadata with a command such as the following (the exact path may change in future Codex releases):

```bash
cat ~/.codex/.tmp/marketplaces/la-dev-codex-plugins/.codex-marketplace-install.json
```

Remember to check after an update whether you need to update `~/.codex/rules/default.rules` with the latest `la-review` semantic version!

## Recommended further setup

### User-level instructions

This repository includes a recommended [user-level AGENTS.md file](AGENTS_user.md) with global Codex instructions that complement the plugins. Review and adapt it as desired, or directly copy it into your Codex home directory:

```bash
cp AGENTS_user.md ~/.codex/AGENTS.md
```

Codex applies `~/.codex/AGENTS.md` as user-level guidance across all your projects. If that file already exists, merge the recommendations into it instead of overwriting your existing instructions.

### User-level configuration

The following generic defaults are a practical starting point for `~/.codex/config.toml`:

```toml
approval_policy = "on-request"
sandbox_mode = "workspace-write"
model_reasoning_effort = "medium"
plan_mode_reasoning_effort = "high"

[history]
persistence = "save-all"
max_bytes = 52428800
```

You can additionally opt in to live web search and outbound network access for sandboxed commands. Merge these entries into the appropriate locations rather than duplicating TOML tables; `web_search` is a top-level setting.

```toml
web_search = "live"

[sandbox_workspace_write]
network_access = true
```

Command network access allows package managers such as `pip`, `uv`, `npm`, and `cargo` to query registries and download dependencies. Live web search and command network access both increase exposure to untrusted external content, so enable them deliberately.

You can also opt in to pinning a preferred model with the following top-level setting:

```toml
model = "gpt-5.6-sol"
```

Use `/model` within Codex to select an available model and add or update this setting automatically, especially when switching to a newer model.

For Python development, add these writable roots to the same `[sandbox_workspace_write]` table to let `pip` and `uv` reuse their caches and let `uv` manage downloaded tools and Python installations:

```toml
writable_roots = [
  "~/.cache/pip",
  "~/.cache/uv",
  "~/.local/share/uv",
]
```

The following is one possible TUI setup for a detailed status line and informative terminal title:

```toml
[tui]
status_line = ["project-name", "git-branch", "model-with-reasoning", "run-state", "task-progress", "context-used", "total-input-tokens", "total-output-tokens", "five-hour-limit", "weekly-limit", "thread-title", "session-id"]
terminal_title = ["activity", "project-name"]
```

## Using plugins

### Loupe skill

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

### Perform skill

List the configured actions without executing one:

```text
$toolkit:perform
```

Run a known action by its bare name:

```text
$toolkit:perform find-todos
$toolkit:perform find-todos in tools/
```

Select an exact language variant (`agnostic` means language-independent; another action might provide variants such as `python`):

```text
$toolkit:perform find-todos[agnostic]
```

Select an action with a clear natural-language request:

```text
$toolkit:perform list the todos in tools/
```

Read or query the built-in action-file help with:

```text
$toolkit:perform help
$toolkit:perform help How can I define custom repo-specific actions?
```

Perform discovers direct `*.json` files from these `toolkit_perform_actions` directories, in increasing precedence:

- The action directory bundled with the installed skill
- On Unix, `/etc/codex/toolkit_perform_actions/`, when `/etc/codex/config.toml` is a regular file
- `$CODEX_HOME/toolkit_perform_actions/`, defaulting to `~/.codex/toolkit_perform_actions/` when `CODEX_HOME` is unset or empty
- `<repository-root>/.codex/toolkit_perform_actions/`, when `<repository-root>/.codex/config.toml` is a regular file

See the [complete Perform user guide](plugins/toolkit/skills/perform/references/action-files.md) for action creation, fields, precedence, variants, inheritance, variables, execution modes, overrides, ignores, and troubleshooting. The installed skill exposes the same guide interactively through `$toolkit:perform help`.

## Development

See `TESTING.md`.

The shipped plugin scripts and package source code must support Python 3.6+ and must use only the Python standard library.
