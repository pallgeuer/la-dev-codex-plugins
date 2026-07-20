# Perform invocation behavior

This document is the maintainer-facing behavioral map for `$toolkit:perform`. User-facing action configuration belongs in the skill's [action-file guide](../../../plugins/toolkit/skills/perform/references/action-files.md).

Perform executes configured prompts in the current chat. Codex performs semantic selection and small qualification decisions; the bundled Python scripts provide deterministic discovery, validation, inheritance, substitution, and prompt assembly. They use only direct command arguments and compact JSON stdout.

## Invocation forms

| Form             | Example                                       | Behavior                                                        |
|------------------|-----------------------------------------------|-----------------------------------------------------------------|
| No arguments     | `$toolkit:perform`                            | List all effective variants and stop.                           |
| Strict selector  | `$toolkit:perform find-todos[agnostic] [...]` | Select exactly that action and language.                        |
| Bare action name | `$toolkit:perform find-todos [...]`           | Consider only variants of that known action.                    |
| Natural language | `$toolkit:perform list the todos in tools/`   | Select semantically across the effective catalog.               |
| Help             | `$toolkit:perform help [...]`                 | Read the bundled action-file guide without loading the catalog. |

Preserve the full text after `$toolkit:perform`. The first token controls routing; the complete text remains available for selection, variable binding, and at most one qualification.

## Routing and selection

### No arguments

Run the unfiltered listing script, display every effective variant, explain strict selectors, bare names, and natural-language selection briefly, surface diagnostics, and stop.

### Help first

When the first token is exactly `help` or `help[agnostic]`, including when a question follows it, bypass mutable catalog discovery and answer from `references/action-files.md`. A natural-language configuration question can still select `help[agnostic]` from a normal full listing.

### Strict selector first

A first token matching `ACTION[LANGUAGE]` is strict even when text follows. Inspect only that selector. A missing selector reports same-name alternatives when available and never falls back.

### Bare action-name first

Run one combined exact-name/fallback query:

```text
list_perform_actions.py --name='ACTION' --fallback
```

If exact-name variants exist, the response contains only them and selection remains permanently narrowed. If none exists, the same catalog load returns the full catalog for general semantic selection. This replaces the former failed-name call followed by a second unfiltered call.

### Any other first token

Run the unfiltered listing once and select semantically from all returned variants.

For a known bare action, select its sole variant automatically. With multiple variants, use positive language evidence from the invocation and relevant file/repository context; otherwise prefer `agnostic` when available or ask for the language. General soft selection compares selectors, glosses, prompt-variable descriptions, and explicit scope, and declines weak matches. Wording consumed only to select an action does not itself create a qualification.

## Compact script protocol

Once started, both entry scripts emit exactly one compact JSON value followed by one LF for every supported success and failure path. They write explicitly encoded UTF-8 bytes, independent of the ambient stdout codec: ordinary Unicode remains literal UTF-8, while lone surrogates are represented as JSON `\uXXXX` escapes. There is no `--json` switch, human result mode, stdin request, response envelope, success status, or schema version. The operating system can reject an invocation before process startup when platform-specific per-argument or aggregate argument-and-environment limits are exceeded; that external launch failure cannot emit JSON.

Both scripts accept `-h` and `--help`. An exact help flag anywhere in the argument vector, including alongside other arguments, returns exit code 0 and short-circuits to a compact JSON object containing argparse-formatted help:

```json
{"help":"usage: list_perform_actions.py ...\n"}
```

The `help` string is intended for display; its exact whitespace is not a stable machine schema. Long-option abbreviations are disabled. Repeating a singleton option is an `invalid_arguments` error; only `--var` is repeatable, and each placeholder may still be bound only once.

### List actions

```text
list_perform_actions.py [--name ACTION] [--fallback] [--cwd DIRECTORY]
```

`--fallback` requires `--name`. A success response contains only `variants` and optional `diagnostics`. Each variant contains `selector`, `gloss`, and nonempty `prompt_vars` when applicable. The complete response is one compact physical line:

```json
{"variants":[{"selector":"find-todos[agnostic]","gloss":"Enumerate all kinds of discernible TODOs in a repo"},{"selector":"md-goal[agnostic]","gloss":"Execute a markdown implementation plan in goal mode","prompt_vars":{"%MarkdownPlanFile%":"Markdown file containing details of the plan to implement."}}]}
```

### Inspect or render an action

```text
get_perform_action.py --inspect='ACTION[LANGUAGE]' [--cwd DIRECTORY]
get_perform_action.py --render='ACTION[LANGUAGE]' [--var='%Name%=VALUE' ...] [--qualification='TEXT'] [--cwd DIRECTORY]
```

An inspection response contains the exact automatically prefixed prompt and one mode enum. Empty optional keys are omitted:

```json
{"prompt":"No edits. Inspect this repository.","mode":"default"}
```

Parameterized actions add `prompt_vars`; actions with notes add `notes`:

```json
{"prompt":"Implement %PlanFile%.","mode":"goal","prompt_vars":{"%PlanFile%":"Markdown implementation plan."},"notes":"Follow the goal-resume procedure."}
```

Inspecting immutable built-in help is also a normal successful result, available even when catalog precedence is incomplete:

```json
{"help":"Read references/action-files.md for the immutable built-in help action."}
```

A successful render response contains only the authoritative prompt, plus diagnostics when present:

```json
{"prompt":"Implement docs/plan.md. BUT: Limit changes to tools/."}
```

Repeat `--var` for every binding. Split each binding at its first `=`, so subsequent equals signs remain in the value. Reject malformed or duplicate arguments, missing or extra variables, empty values, and NUL. Values otherwise remain literal, including spaces, leading dashes, quotes, Unicode, newlines, dollar signs, backticks, percent signs, and placeholder-looking text. After substitution and the automatic no-edits prefix, reject a rendered main prompt that contains only whitespace; individual whitespace-only values remain valid when other prompt text remains.

When composing a shell command, pass every dynamic option value in `--option='value'` form as one POSIX single-quoted argument and replace an embedded `'` with `'"'"'`. Never interpolate an unquoted value, use `eval`, evaluate it as shell syntax, or send JSON through stdin. Prefer a direct argument-vector API when one is available. Using the `--option=value` form ensures option-looking values remain data.

Argument values are observable through process inspection and may be captured by command launchers, audit systems, or process monitors. They are not a secret transport: callers must pass nonsecret references such as environment-variable names, credential-store identifiers, or protected file paths rather than credentials or tokens themselves. The runtime does not attempt unreliable secret-pattern detection.

### Errors and diagnostics

Failures add a compact structured error:

```json
{"error":{"code":"not_found","message":"No effective action matches strict selector example[rust]."},"available_variants":["example[python]"]}
```

Rendering `help[agnostic]` fails with `not_executable`. A render whose complete main prompt becomes whitespace fails with `empty_rendered_prompt`; neither failure appends or executes a qualification.

Warnings and errors from discovery/catalog validation are flattened into deduplicated human-ready strings containing severity, message, file, and JSON location:

```json
{"diagnostics":["error: Unknown version 1 action field 'promt'. (/path/actions.json/actions/check/agnostic/promt)"]}
```

Discovery structures, source metadata, reserved standalone-launcher settings, redundant names/languages, and empty optionals never cross the current compact CLI boundary. Materialization retains only effective field values, not per-field provenance. Model, effort, interactivity, and custom Codex argument fields remain required and validated for a future standalone CLI that runs actions outside a Codex chat.

Exit codes retain their behavioral classes:

- `0`: successful result, direct script help, or immutable built-in help result.
- `2`: invalid request, missing selector/action, or render validation failure.
- `3`: fatal catalog precedence state; never execute a configured action.
- `4`: unexpected runtime failure.

## Executable-action pipeline

1. Select one canonical selector using the routing rules above.
2. Inspect it with one direct `--inspect` call.
3. Check the required chat mode and ensure no unfinished goal is active.
4. Bind every declared prompt variable and decide whether one compatible qualification is needed.
5. When there are no variables and no qualification, treat the inspected prompt as final and skip rendering.
6. Otherwise render once with direct `--var` and optional `--qualification` arguments.
7. Show nonempty notes, then the exact final prompt as an unlabeled Markdown blockquote.
8. Create an exact Goal objective when required, then execute the prompt immediately and completely.

The prompt returned by inspection is already final for an unparameterized, unqualified action because the only remaining render transformations would be no-ops. Parameterized or qualified actions retain deterministic rendering.

## Modes and goals

Inspection maps action flags to one `mode` value:

| `plan_mode` | `goal_mode` | Inspection mode | Required behavior                                                  |
|-------------|-------------|-----------------|--------------------------------------------------------------------|
| false       | false       | `default`       | Default mode must already be active; execute directly.             |
| true        | false       | `plan`          | Plan mode must already be active; execute directly in Plan mode.   |
| false       | true        | `goal`          | Default mode must be active; create an exact goal after rendering. |
| true        | true        | Invalid         | Exclude the action variant during catalog validation.              |

Perform never changes between Default and Plan mode. Any unfinished goal blocks every executable action. It does not compare, reuse, complete, replace, or repurpose that goal.

For `goal`, the exact final prompt is the sole objective. It includes substitutions, the optional automatic `No edits. ` prefix, and any `BUT:` clause, but excludes the selector, notes, diagnostics, and quote markers. If goal creation is unavailable, stop and provide `/goal ` followed by the exact prompt rather than running outside Goal mode.

## Variables and qualifications

Bind all declared variables and no others. Substitution is literal and one-pass. Prompt-variable-looking text introduced by a value is not expanded recursively. Variables affect only the configured prompt, never notes or qualification text. Rendering stops with `empty_rendered_prompt` if substitution leaves the complete main prompt blank after trimming.

A qualification is one short, standalone imperative for a compatible scope/detail adjustment. Supply it without `BUT:`. After substitution and the automatic no-edits prefix, trim trailing whitespace only at the qualification boundary. Append exactly:

- ` BUT: QUALIFICATION` when the resulting main prompt contains no newline.
- `\nBUT: QUALIFICATION` when the resulting main prompt contains a newline, including one introduced by a variable.

Never use a qualification to add a second task, change the action's purpose, weaken constraints, restate the full prompt, or hide a missing variable.

## Prompt display and execution

Show notes verbatim first. Then show the exact final prompt with no label or selection narration. Prefix each nonempty line with `> ` and each blank line with `>` so the whole prompt is one Markdown blockquote. These prefixes are display-only.

Begin the action immediately after the quote. A complex action may start with a detailed task list. Collect nonfatal diagnostics across calls, deduplicate them, and report them as a compact side note in the final or blocked response; surface fatal diagnostics immediately.

## Invariants

- Explicit `$toolkit:perform` invocation is required.
- Strict selectors never fall back, and a known bare name narrows permanently.
- Explicit help avoids mutable catalog work.
- Unknown bare-name probing and full fallback use one catalog load.
- Unparameterized, unqualified actions do not perform a redundant render call.
- All user-derived render data travels in directly quoted nonsecret command arguments, never stdin JSON.
- The final prompt is authoritative, visible as a blockquote, and executed in the current chat.
- Notes, diagnostics, selectors, and setting metadata never enter the action prompt or Goal objective.
- Action-file version 1 and all configured fields remain unchanged.
