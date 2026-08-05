# Codex Perform

Codex Perform runs reusable actions configured by the Toolkit plugin. The same action catalogue is available through two interfaces:

- `$toolkit:perform` selects, prepares, shows, and executes an action inside the current Codex chat.
- `codex-perform` is a dependency-free standalone launcher installed by the repository's Python distribution or activated directly from a source checkout.

The Python distribution contains only the launcher. It does not install Codex, the marketplace, any plugin, or the Toolkit runtime and action assets. The launcher discovers an installed and enabled `toolkit@la-dev-codex-plugins` plugin and checks its launcher API compatibility. The Python distribution and plugin versions do not need to match when that API version is compatible.

See [Marketplace plugin installation](installation.md) to install and verify the required `toolkit` plugin separately.

## Use the Perform skill in Codex

List configured actions:

```text
$toolkit:perform
```

Run a known action by bare name, optionally with an explicit scope:

```text
$toolkit:perform find-todos
$toolkit:perform find-todos in tools/
```

Select an exact language variant:

```text
$toolkit:perform find-todos[agnostic]
```

Use a natural-language request when it clearly identifies an available action:

```text
$toolkit:perform list the todos in tools/
```

Read or query the installed Perform guides:

```text
$toolkit:perform help
$toolkit:perform help How can I define custom repo-specific actions?
```

The in-chat skill accepts strict `ACTION[LANGUAGE]` selectors, bare action names, and compatible natural-language selection. It binds declared prompt variables from explicit invocation text and asks for missing values. Text remaining after selection is used only when it is one short compatible scope or detail qualification; it cannot add another task, change the action's purpose, weaken constraints, or replace a missing variable.

For the complete in-chat workflow, see the [Codex Perform skill guide](../plugins/toolkit/skills/perform/references/codex_skill.md).

## Discover and customize actions

Perform discovers direct lowercase `*.json` files from these `toolkit_perform_actions` directories, from lowest to highest precedence:

1. The directory bundled with the installed skill: `/PATH/TO/skills/perform/assets/toolkit_perform_actions/`.
2. The system Codex configuration: `/etc/codex/toolkit_perform_actions/` on Unix.
3. The user Codex configuration: `$CODEX_HOME/toolkit_perform_actions/`, defaulting to `~/.codex/toolkit_perform_actions/` when `CODEX_HOME` is unset or empty.
4. The repository configuration: `<repository-root>/.codex/toolkit_perform_actions/`, enabled only when `<repository-root>/.codex/config.toml` exists.

Files from higher-precedence directories override lower-precedence definitions. Within one directory, filenames are applied in exact UTF-8 byte order, so names such as `10-team.json`, `50-personal.json`, and `90-overrides.json` can make ordering explicit.

An action is a named workflow and may have several language variants. `ACTION[LANGUAGE]` is the canonical selector, and `agnostic` is the language-independent variant. Language-specific variants inherit omitted fields from `agnostic`; later definitions replace or patch the same exact `(action, language)` identity. Inheritance is shallow: supplied objects and lists replace inherited values rather than merging them.

Use repository or user overrides instead of editing bundled action files. Repository discovery uses the single resolved VCS root containing the current working directory; nested action directories are not loaded unless they belong to that root.

The full schema, discovery behavior, precedence, inheritance, variables, overrides, ignores, examples, and troubleshooting are documented in [Perform action files and catalogues](../plugins/toolkit/skills/perform/references/action_files.md).

## Generate an action catalogue

Generate or update a stable Markdown quick reference for the effective actions:

```text
$toolkit:perform update-action-catalogue
$toolkit:perform update-action-catalogue docs/action_catalogue.md
```

The default output is `<repository-root>/.codex/toolkit_perform_actions/action_catalogue.md`. An explicit relative output is resolved from the repository root, may traverse into parent directories, and is not confined to the repository. Parent-directory symlinks are followed, but a symlink in the final target component is refused. Existing files are replaced only when they contain the generator's ownership marker.

The standalone equivalent is:

```bash
codex-perform catalogue
codex-perform catalogue --output docs/action_catalogue.md
```

## Install in a virtual environment

Create and activate a Python 3.6+ virtual environment, then install the distribution:

```bash
python3 -m venv /PATH/TO/VENV
source /PATH/TO/VENV/bin/activate
python -m pip install la-dev-codex-plugins
codex-perform --version
codex-perform --help
```

The command is available while that environment is active and always uses its interpreter. It re-executes that interpreter with `-I` before importing `la_dev_codex_plugins.codex_perform.cli`, so the caller's current directory, `PYTHONPATH`, and user site-packages cannot replace the installed launcher.

On an older Python installation, use `--only-binary=:all:` when installation should fail instead of attempting a source build:

```bash
python -m pip install --only-binary=:all: la-dev-codex-plugins
```

## Activate from a source checkout

No package installation is required for the source path. In each new Bash session, source the repository activation script:

```bash
# FIND IT:  find "${CODEX_HOME:-$HOME/.codex}" -path "*/la-dev-codex-plugins/activate.sh"
# OFTEN IS: source ~/.codex/.tmp/marketplaces/la-dev-codex-plugins/activate.sh
source /PATH/TO/la-dev-codex-plugins/activate.sh
```

This defines `codex-perform` as a shell function that launches the checkout through isolated Python. Executing `activate.sh` instead of sourcing it is an error.

For this source-only path, `CODEX_PERFORM_PYTHON` selects another Python 3.6+ standard-library interpreter:

```bash
CODEX_PERFORM_PYTHON=/usr/bin/python3 codex-perform list
```

The installed virtual-environment command deliberately ignores `CODEX_PERFORM_PYTHON`. If the source-defined shell function already exists, it takes precedence over an executable from a subsequently activated virtual environment. Start a fresh shell or run `unset -f codex-perform` before using the virtual-environment executable.

## Use the standalone CLI

The launcher accepts an explicit subcommand or treats the first non-command positional argument as an action:

```bash
codex-perform
codex-perform --help
codex-perform --version
codex-perform list
codex-perform catalogue
codex-perform show find-todos
codex-perform show help
codex-perform help
codex-perform help --question 'How do repository action overrides work?'
codex-perform find-todos
codex-perform find-todos --qualification 'Limit the search to tools/'
codex-perform find-todos --ni
codex-perform find-todos --non-interactive --verbose
codex-perform find-todos --json
codex-perform exec-md-goal --var 'MarkdownPlanFile=docs/plans/plan.md'
```

`list` searches the effective catalogue. `show` displays a complete materialized action without launching. `help` selects the immutable Perform documentation action, while `-h` and `--help` display launcher syntax. The standalone launcher accepts strict selectors and bare names but does not perform semantic natural-language selection.

Bind every declared action variable exactly once with repeatable literal `--var 'Name=VALUE'` arguments. `--qualification` adds one compatible scope or detail adjustment. For built-in help, the synonymous `--question` spelling adds a documentation question.

Runs are interactive by default:

- `--non-interactive` or `--ni` launches `codex exec`, shows the action and prompt on stderr, hides successful Codex progress, and leaves the final response on stdout.
- `--non-interactive --verbose` restores live progress.
- `--json` launches noninteractive Codex JSONL output while keeping launcher context on stderr.
- `--dry-run` builds and displays the complete invocation without executing Codex.

Plan-mode actions must run through `$toolkit:perform` in an existing Plan-mode chat. Goal actions use a normal bootstrap prompt that asks Codex to create a goal whose objective is the exact rendered action prompt.

Use `--plugin-root /PATH/TO/la-dev-codex-plugins/plugins/toolkit` during marketplace development to select a checkout explicitly. By default the launcher asks the selected Codex executable for the installed Toolkit plugin, validates its cache path and manifest, and imports only its versioned launcher-facing API.

For every option, output mode, exit code, process-supervision behavior, and launcher API detail, see the [Standalone Perform CLI and launcher API guide](../plugins/toolkit/skills/perform/references/standalone_cli.md).
