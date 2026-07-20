# Perform user guide

Perform turns reusable prompts stored in JSON action files into explicitly invoked Codex actions. Use this guide to run existing actions, add personal or repository actions, customize bundled actions, and diagnose configuration problems.

## Contents

- [Run an action](#run-an-action)
- [Create your first action](#create-your-first-action)
- [Choose where actions live](#choose-where-actions-live)
- [Understand precedence](#understand-precedence)
- [Action-file format](#action-file-format)
- [Action variants and inheritance](#action-variants-and-inheritance)
- [Prompt variables](#prompt-variables)
- [Execution modes and notes](#execution-modes-and-notes)
- [Override or remove actions](#override-or-remove-actions)
- [Complete examples](#complete-examples)
- [Troubleshooting](#troubleshooting)

## Run an action

Perform runs only when you explicitly invoke `$toolkit:perform`.

List all available action variants without running one:

```text
$toolkit:perform
```

Run a known action by name:

```text
$toolkit:perform find-todos
```

Select one exact language variant:

```text
$toolkit:perform find-todos[agnostic]
```

Describe the desired action in natural language:

```text
$toolkit:perform list the todos in tools/
```

Ask for help:

```text
$toolkit:perform help
$toolkit:perform how do repository action overrides work?
```

An **action** is a named reusable workflow. A **variant** is one language-qualified form of that action. Its canonical selector is `ACTION[LANGUAGE]`, such as `check-config[json]`. The reserved language `agnostic` means that the variant is language-independent.

Selection follows these rules:

- A canonical selector is strict. If `check-config[rust]` does not exist, Perform does not silently run another variant.
- A known bare action name narrows selection to variants of that action. When several variants exist, explicit wording and relevant repository context determine the language; `agnostic` is preferred when there is no positive language evidence. Perform asks when the choice remains ambiguous and no `agnostic` variant exists.
- An unknown name or a natural-language request is matched against action names, languages, glosses, variable descriptions, and the requested scope. Perform declines instead of running a weak match.
- Extra wording may supply prompt variables or make one small compatible qualification, such as limiting a repository-wide audit to `tools/`. It cannot turn the action into a different task or weaken its constraints.

## Create your first action

Create a direct `*.json` file in your user action directory:

```text
$CODEX_HOME/toolkit_perform_actions/
```

When `CODEX_HOME` is unset or empty, use:

```text
~/.codex/toolkit_perform_actions/
```

For example, save this as `50-personal.json`:

```json
{
  "version": 1,
  "actions": {
    "review-tests": {
      "agnostic": {
        "gloss": "Review tests for a requested area",
        "model": "default",
        "reasoning_effort": "medium",
        "goal_mode": false,
        "plan_mode": false,
        "plan_reasoning_effort": "medium",
        "no_edits": true,
        "prompt_vars": {
          "%Area%": "Repository-relative file or directory to review."
        },
        "prompt": "Review the tests for %Area%. Identify important missing cases and explain why each case matters.",
        "prefer_interactive": true,
        "custom_codex_args": [],
        "notes": "This action reports gaps without editing files."
      }
    }
  }
}
```

Then invoke it with the variable value in the request:

```text
$toolkit:perform review-tests src/auth/
```

Perform inspects the selected action before binding `%Area%`. If the request does not provide a value that can be determined reliably, Codex asks for it instead of inventing one.

## Choose where actions live

Perform reads direct JSON files from up to four action directories, from lowest to highest precedence:

1. **Bundled:** the perform skill's `assets/toolkit_perform_actions/` directory.
2. **System:** `/etc/codex/toolkit_perform_actions/` on Unix, enabled only when `/etc/codex/config.toml` is a regular file.
3. **User:** `$CODEX_HOME/toolkit_perform_actions/`, defaulting to `~/.codex/toolkit_perform_actions/` when `CODEX_HOME` is unset or empty. A user `config.toml` is not required.
4. **Repository:** `<repository-root>/.codex/toolkit_perform_actions/`, enabled only when `<repository-root>/.codex/config.toml` is a regular file.

Only files directly inside those directories participate; subdirectories are not searched. Filenames must end in the lowercase suffix `.json`.

Repository actions come from the single resolved VCS root containing the current working directory. A nested `.codex/toolkit_perform_actions/` directory is not loaded unless its directory is itself the resolved repository root. Git, Mercurial, and Sapling repository markers are recognized when resolving the root.

An explicit nonempty `CODEX_HOME` must name an existing readable directory. A relative value is resolved from the current working directory. A missing or unreadable explicit path is an error; Perform does not fall back to `~/.codex` in that case.

A leading `~` in `CODEX_HOME` is expanded. Environment-variable-looking text inside its value is treated literally rather than expanded. If two source paths resolve through symlinks to the same directory, that directory is loaded once at the higher of the two precedence levels.

Missing optional action directories are normal. However, an applicable directory that exists but cannot be read blocks action execution because higher-precedence overrides cannot be determined safely.

Prefer user or repository overrides to editing bundled files, which belong to the installed plugin and may change when the plugin is updated.

## Understand precedence

All files from a lower-precedence directory are applied before files from a higher-precedence directory:

```text
bundled < system < user < repository
```

Within one directory, filenames are ordered by their exact UTF-8 bytes, and later filenames have higher precedence. Prefix filenames with numbers such as `10-team.json`, `50-personal.json`, and `90-overrides.json` when their order matters. Ordering is case-sensitive and is not locale-aware.

The override identity is the exact `(action name, language)` pair. Overriding `check-config[json]` does not replace `check-config[yaml]`.

## Action-file format

Every action file is UTF-8 JSON with this root shape:

```json
{
  "version": 1,
  "ignore_actions": [],
  "actions": {}
}
```

- `version` is required and must be the JSON integer `1`.
- `actions` is required and must be an object. It may be empty.
- `ignore_actions` is optional and defaults to an empty list.
- Unknown root fields, duplicate JSON keys, invalid UTF-8, or invalid JSON make the entire file unusable.

Each action value must be a nonempty object of language variants, and each variant definition must be a nonempty object of action fields.

Action names use lowercase ASCII letters, digits, `.`, `_`, and `-`, must start with a letter or digit, and match `^[a-z0-9][a-z0-9._-]*$`.

Language names use lowercase ASCII letters, digits, `.`, `+`, `_`, and `-`, must start with a letter or digit, and match `^[a-z0-9][a-z0-9.+_-]*$`.

The action name `help` is reserved for immutable built-in help. Action files cannot define, override, or ignore it.

### Action fields

A complete variant contains every field below. An `agnostic` variant must always be complete. A language-specific variant may omit inherited fields as described in [Action variants and inheritance](#action-variants-and-inheritance).

| Field | Meaning and valid value |
| --- | --- |
| `gloss` | A concise, nonempty single-line description without control or line-separator characters, used when listing and selecting the action. |
| `model` | `"default"` or a model identifier made from ASCII letters, digits, `.`, `_`, `:`, `+`, `/`, and `-`, starting with a letter or digit. |
| `reasoning_effort` | The requested effort outside Plan mode, such as `low`, `medium`, `high`, or `xhigh`. Use a lowercase identifier starting with a letter. |
| `goal_mode` | Boolean. When true, Perform creates a goal whose objective is the final rendered prompt. |
| `plan_mode` | Boolean. When true, the action can run only while Plan mode is active. |
| `plan_reasoning_effort` | The requested effort in Plan mode, using the same format as `reasoning_effort`. |
| `no_edits` | Boolean. When true, Perform automatically prefixes the final prompt with `No edits. `. |
| `prompt_vars` | An object mapping placeholders such as `%Area%` to concise, nonempty single-line descriptions. Use `{}` when no variables are needed. |
| `prompt` | The nonempty prompt Codex will follow after variable substitution and other rendering. Newlines are allowed and preserved. |
| `prefer_interactive` | Boolean metadata expressing an interactivity preference. |
| `custom_codex_args` | A list of nonempty Codex argument strings. Use `[]` when none are needed. |
| `notes` | User-facing text shown verbatim before execution. Use `""` when no note is needed. |

`goal_mode` and `plan_mode` cannot both be true. When `plan_mode` is false, `reasoning_effort` and `plan_reasoning_effort` must be equal.

When `no_edits` is true, do not start `prompt` with `No edits.`; Perform adds that sentence exactly once.

The current in-chat perform skill does not change or comment on `model`, `reasoning_effort`, `plan_reasoning_effort`, `prefer_interactive`, or `custom_codex_args`. These fields remain required action metadata. `custom_codex_args` cannot override `model`, `model_reasoning_effort`, `plan_mode_reasoning_effort`, or any descendant of those configuration keys; use the structured fields instead. It also cannot contain empty strings, NUL characters, malformed `-c`/`--config` assignments, or `-m`/`--model` overrides.

Invalid fields usually remove only the affected variant, allowing independent valid variants and files to remain usable. Root-level file errors make the whole file unusable.

## Action variants and inheritance

An action contains a nonempty object keyed by language:

```json
{
  "version": 1,
  "actions": {
    "check-config": {
      "agnostic": {
        "gloss": "Check configuration files",
        "model": "default",
        "reasoning_effort": "medium",
        "goal_mode": false,
        "plan_mode": false,
        "plan_reasoning_effort": "medium",
        "no_edits": true,
        "prompt_vars": {},
        "prompt": "Check the applicable configuration files.",
        "prefer_interactive": true,
        "custom_codex_args": [],
        "notes": ""
      },
      "json": {
        "gloss": "Check JSON configuration files",
        "prompt": "Check the applicable JSON configuration files."
      },
      "yaml": {
        "gloss": "Check YAML configuration files",
        "prompt": "Check the applicable YAML configuration files."
      }
    }
  }
}
```

This produces `check-config[agnostic]`, `check-config[json]`, and `check-config[yaml]`. The `json` and `yaml` variants inherit every omitted field from `agnostic`.

Inheritance and overrides are shallow:

- A supplied field replaces the inherited value completely. `prompt_vars` objects and `custom_codex_args` lists are not merged.
- A later `agnostic` definition is a complete replacement for the earlier base. Existing language-specific patches are then rematerialized against the new base.
- A later language-specific definition overlays earlier fields for that same language and inherits its remaining fields from the current `agnostic` base.
- A language-specific variant may exist without `agnostic`, but it must then provide every action field itself.
- If a partial language-specific variant has no valid base, it is not available.

Whenever a variant changes `prompt` or `prompt_vars`, its materialized declarations and placeholders must still agree.

## Prompt variables

Placeholder names match `%[A-Za-z][A-Za-z0-9_]*%`. Every placeholder-shaped token in the materialized prompt must be declared in `prompt_vars`, and every declared variable must occur in the prompt.

Repeated variables and multiple variables are supported:

```json
"prompt_vars": {
  "%InputFile%": "File to read.",
  "%Audience%": "Audience for the result."
},
"prompt": "Read %InputFile%, summarize it for %Audience%, and cite %InputFile%."
```

Bindings must provide every declared variable as a nonempty string and cannot introduce undeclared variables. Substitution is literal and happens once. Quotes, backticks, dollar signs, percent signs, Unicode, newlines, and placeholder-looking text inside a supplied value are not evaluated or expanded again.

Variables are substituted only in `prompt`, not in `notes` or in an invocation qualification.

## Execution modes and notes

The mode flags select exactly one execution mode:

| `plan_mode` | `goal_mode` | Required behavior |
| --- | --- | --- |
| false | false | Run in Default mode. |
| true | false | Run only when Plan mode is already active. |
| false | true | Start in Default mode, render the final prompt, then create and run a goal with that exact prompt as its objective. |

Perform does not switch between Default and Plan mode automatically. If the selected action requires a different mode, Codex asks you to switch modes and invoke it again.

Any unfinished goal blocks every executable Perform action, including Default-mode and Plan-mode actions. Finish or clear the active goal, then invoke the action again. A completed goal does not block a new invocation.

For a Goal-mode action, the exact goal objective includes variable substitutions, the automatic `No edits. ` prefix when configured, and any compatible qualification. It never includes the selector, notes, diagnostics, or explanatory text. If the current surface cannot create a goal, Perform stops and provides the exact `/goal` prompt for manual submission instead of running the action outside Goal mode.

Nonempty `notes` are displayed verbatim before execution and may be repeated when still relevant in a final or blocked response. Notes are operational guidance for the user, not instructions for Codex: they do not affect selection, are not obeyed as part of the action, and never enter the rendered prompt. Keep actual action requirements in `prompt`.

## Override or remove actions

Higher-precedence files can replace action variants, partially customize language-specific variants, or remove inherited definitions.

`ignore_actions` accepts bare action names and canonical selectors:

```json
{
  "version": 1,
  "ignore_actions": [
    "old-action",
    "check-config[json]"
  ],
  "actions": {}
}
```

- A bare name removes every currently accumulated variant and language patch for that action.
- A canonical selector removes only that language.
- Ignores are applied before definitions in the same file, so one file can discard inherited content and then define a clean replacement.
- A later file or higher-precedence source can reintroduce an ignored action.
- Ignoring a missing action is valid and silent.
- Invalid ignore entries are diagnosed without preventing other valid entries in that file from applying.

## Complete examples

### Personal override with a language variant

Save this in `$CODEX_HOME/toolkit_perform_actions/50-personal.json` or the default `~/.codex/toolkit_perform_actions/50-personal.json`:

```json
{
  "version": 1,
  "ignore_actions": [],
  "actions": {
    "find-todos": {
      "agnostic": {
        "gloss": "Enumerate unfinished work with local exclusions",
        "model": "default",
        "reasoning_effort": "medium",
        "goal_mode": false,
        "plan_mode": false,
        "plan_reasoning_effort": "medium",
        "no_edits": true,
        "prompt_vars": {},
        "prompt": "Scan the repository for unfinished, temporary, obsolete, or cleanup-related work. Exclude vendor/ and generated/.",
        "prefer_interactive": true,
        "custom_codex_args": [],
        "notes": "This user override excludes vendor/ and generated/."
      },
      "python": {
        "gloss": "Enumerate unfinished Python work",
        "prompt": "Scan Python source and tests for unfinished, temporary, obsolete, or cleanup-related work. Exclude vendor/ and generated/."
      }
    }
  }
}
```

The complete `agnostic` definition replaces the bundled base. `python` inherits all fields except its supplied `gloss` and `prompt`.

### Repository action and ignores

At the resolved repository root, create the regular marker `.codex/config.toml`, then save this as `.codex/toolkit_perform_actions/90-project.json`:

```json
{
  "version": 1,
  "ignore_actions": [
    "ascii-only",
    "find-todos[python]"
  ],
  "actions": {
    "project-audit": {
      "agnostic": {
        "gloss": "Audit this repository's project rules",
        "model": "default",
        "reasoning_effort": "high",
        "goal_mode": false,
        "plan_mode": false,
        "plan_reasoning_effort": "high",
        "no_edits": true,
        "prompt_vars": {
          "%Area%": "Repository-relative area to audit."
        },
        "prompt": "Audit %Area% against all applicable project rules and report exact file and line references.",
        "prefer_interactive": true,
        "custom_codex_args": [],
        "notes": "Specify the area to audit when invoking this action."
      }
    }
  }
}
```

This removes every inherited `ascii-only` variant, removes only `find-todos[python]`, and adds `project-audit[agnostic]` at repository precedence.

## Troubleshooting

Use `$toolkit:perform` to list the effective catalog and `$toolkit:perform help` to ask about configuration. Perform reports configuration diagnostics with the relevant file and JSON location whenever possible.

Common causes of missing or blocked actions include:

- The file is not a direct child of an active `toolkit_perform_actions` directory or does not end in `.json`.
- Repository actions lack a regular `.codex/config.toml` at the resolved VCS root.
- An explicit `CODEX_HOME` does not exist or cannot be read.
- A JSON file has duplicate keys, invalid syntax, invalid UTF-8, unknown root fields, or an unsupported version; the entire file is ignored.
- A variant is incomplete, contains an unknown or invalid field, has conflicting modes, or has prompt-variable declarations that do not match its materialized prompt; that variant is unavailable while independent valid content can remain usable.
- A partial language variant has no valid `agnostic` base.
- A higher-precedence ignore or override removed or replaced the expected variant.
- An applicable source directory cannot be read. Listing may show partial results, but Perform blocks execution because the final precedence is unknown.
- Plan mode is wrong for the selected action or an unfinished goal is active.

The immutable `help[agnostic]` entry remains available even when mutable action configuration has fatal problems.
