# Perform invocation behavior

This document is the maintainer-facing behavioral map for `$toolkit:perform`. It explains how an invocation is routed, selected, prepared, and executed by the current skill. User-facing action creation and customization belong in the skill's [action-file guide](../../../plugins/toolkit/skills/perform/references/action-files.md).

Perform does not launch another Codex process or invoke another skill as its dispatch mechanism. Codex selects and prepares an action in the current chat, while the bundled scripts provide deterministic discovery, validation, inspection, and prompt rendering.

## Invocation forms

| Form             | Example                                       | Behavior                                                                                 |
|------------------|-----------------------------------------------|------------------------------------------------------------------------------------------|
| No arguments     | `$toolkit:perform`                            | List all effective variants and stop.                                                    |
| Strict selector  | `$toolkit:perform find-todos[agnostic] [...]` | Select exactly that action and language.                                                 |
| Bare action name | `$toolkit:perform find-todos [...]`           | Consider only variants of that known action.                                             |
| Natural language | `$toolkit:perform list the todos in tools/`   | Select semantically across the effective catalog.                                        |
| Help             | `$toolkit:perform help [...]`                 | Read the user-facing action-file guide and answer without executing a configured prompt. |

The full text after `$toolkit:perform` is preserved. `[...]` represents optional text, usable to qualify or narrow the invocation. The first token controls routing, while the full text remains available for semantic selection, prompt-variable binding, and one optional compatible qualification.

## Routing algorithm

Routing uses the first token exactly as written.

### No arguments

List the complete effective catalog, including immutable `help[agnostic]`, and display every variant as `ACTION[LANGUAGE]: GLOSS`. Explain strict selectors, bare names, and natural-language selection briefly. Surface diagnostics and stop without inspecting or executing an action.

### Strict selector first

A first token matching `ACTION[LANGUAGE]` is strict even when more text follows. Resolve only that exact selector. A missing selector produces an error and same-name alternatives when available; it never falls back to another language or action.

Examples:

```text
$toolkit:perform find-todos[agnostic]
$toolkit:perform find-todos[agnostic] only scan tools/
```

In the second form, the remainder may qualify the exact selected action but cannot alter the selector.

### Bare action-name first

A lowercase first token matching the bare action-name grammar is initially looked up as an exact action name.

- If the name exists, selection is restricted to its variants. The remainder supplies language evidence, variable values, or a possible qualification.
- If the name does not exist, the failed name probe is not terminal. List the full catalog and use the complete original invocation for general semantic selection.

For example, `audit compliance with AGENTS.md` first probes an action named `audit`; if that name is absent, it can still soft-select `agents-md[agnostic]` from the full request.

### Any other first token

If the first token contains uppercase letters, punctuation, whitespace-invalid syntax, or anything else outside the bare-name and strict-selector grammars, list the full catalog directly and use the complete invocation for general semantic selection.

For example:

```text
$toolkit:perform Please audit compliance with AGENTS.md
```

### Help

Exact `help` and `help[agnostic]` bypass mutable catalog resolution. Strict help with a remainder also stays on the immutable help path:

```text
$toolkit:perform help[agnostic] explain repository overrides
```

`help` followed by a question uses the normal bare-name listing first, selects the sole built-in help variant, and then answers from the action-file guide. A natural-language configuration question may also soft-select help.

Help never enters the executable-action pipeline and cannot be replaced or disabled by action files.

## Selection behavior

The scripts narrow exact names and return deterministic action metadata; Codex performs semantic selection.

For a known bare action:

- Select its only variant automatically.
- With several variants, use positive evidence from the invocation and relevant repository or file context.
- Prefer `agnostic` when no language is positively identified and that variant exists.
- Ask for the missing language when several language-specific variants remain plausible and no `agnostic` variant exists.
- Never consider unrelated actions after a known name has narrowed the catalog.

For general soft selection, compare the complete request with action names, languages, glosses, prompt-variable descriptions, and explicit scope. Select only when the semantic fit is sufficient. Otherwise decline and explain why; mention a nearest action only when it is genuinely close.

Notes do not participate in selection beyond the listing metadata indicating that a note exists. Their contents are not action instructions.

Once a variant is selected, every later operation uses only its canonical selector.

## Executable-action pipeline

Every configured action follows the same lifecycle.

1. **Inspect the exact variant.** Ask the bundled runtime for its materialized base prompt, prompt-variable descriptions, mode fields, notes, provenance, and diagnostics. The base prompt already contains the automatic `No edits. ` prefix when configured.
2. **Check execution prerequisites.** Confirm that the current chat is in the required Default or Plan mode and that no unfinished goal is active. Stop before binding or rendering if either condition fails.
3. **Bind all prompt variables.** Determine each value from explicit user text and the inspected variable description. Ask for any value that cannot be determined reliably.
4. **Prepare at most one qualification.** Use none when the base prompt already covers the request. Otherwise allow only one small compatible scope or detail adjustment.
5. **Render deterministically.** Submit the canonical selector, the exact variable map, and either the one qualification or no qualification. The runtime performs literal one-pass substitution and final prompt assembly.
6. **Show notes.** Display nonempty notes verbatim before execution and repeat any still-relevant part in a final or blocked response. Keep them outside the prompt and do not treat them as Codex instructions.
7. **Enter Goal mode if required.** Create a goal only after the final prompt is known, using that prompt alone as the objective.
8. **Execute exactly.** Follow the returned prompt without rewriting it, adding wrappers, or weakening its constraints.

Inspection must succeed before Codex prepares variable bindings or a qualification. Rendering is authoritative: the returned final prompt, rather than the inspected base prompt or the original invocation, is what Codex executes.

The current skill must not change or comment on `model`, `reasoning_effort`, `plan_reasoning_effort`, `prefer_interactive`, or `custom_codex_args`. Those action fields do not create an informational mismatch branch in the current in-chat workflow.

## Execution modes

The two action flags select one valid execution path:

| `plan_mode` | `goal_mode` | Required state and behavior |
| --- | --- | --- |
| false | false | Default mode must already be active; execute the rendered prompt directly. |
| true | false | Plan mode must already be active; execute the rendered prompt directly in Plan mode. |
| false | true | Default mode must be active; render first, then initialize Goal mode with the exact final prompt. |
| true | true | Invalid action configuration. |

Perform never changes between Default and Plan mode itself. On a mismatch, ask the user to switch modes and invoke the action again, then stop.

An unfinished goal blocks **every** executable action, regardless of its requested mode and regardless of whether a Goal-mode action might render to the same objective. Perform does not compare objectives, reuse an active goal, complete it, replace it, or repurpose it. Ask the user to finish or clear the goal and invoke the action again. A completed goal does not block execution.

For `goal_mode: true`, the exact rendered prompt is the sole goal objective. It already includes the automatic no-edits prefix, all variable substitutions, and any appended qualification. Do not add the selector, notes, diagnostics, a token budget, or explanatory text.

If goal creation is unavailable, do not execute the action outside Goal mode. Show any still-relevant notes, explain the limitation, and provide `/goal ` followed by the exact rendered prompt for manual submission.

## Variables and qualifications

Bind every declared prompt variable and no others. Values come from explicit invocation text interpreted using the inspected placeholder description. Missing information causes a user question and stops the current attempt before rendering.

Variable values are literal data. They may contain shell-like text, quotes, Unicode, newlines, percent signs, or placeholder-shaped text without execution or recursive expansion.

A qualification is appropriate only for one small change that remains within the selected action's intent. It should be a short, standalone imperative rooted in the inspected base prompt.

Example:

```text
$toolkit:perform find-todos[agnostic] only scan tools/
```

The repository-wide TODO audit may be qualified with:

```text
Restrict the scan to tools/ rather than the entire repository.
```

The renderer appends the qualification as a `BUT:` clause. Codex supplies only the sentence, without the prefix.

Do not use a qualification to:

- Add a second task.
- Change the action's core purpose.
- Weaken `No edits.`, safety requirements, acceptance criteria, or other constraints.
- Restate or rewrite the entire prompt.
- Smuggle missing prompt-variable values into an unrelated instruction.

If the request cannot be expressed as one compatible small qualification, reject the selected action for that request rather than rendering a changed action.

## Help, failures, and diagnostics

Surface every unique warning or error returned by the scripts, including its file and JSON location when available. Keep diagnostics separate from prompts and notes.

A fatal catalog state means action precedence cannot be known safely, commonly because an explicitly configured root is missing or an applicable source is invalid or unreadable. Listing may still show partial results, but no configured action may be inspected, rendered, or executed. Immutable help remains available.

Nonfatal problems are isolated where possible. A malformed file can be ignored while valid sibling files remain usable; an invalid variant can be excluded while independent variants continue to work. Diagnostics unrelated to the selected action are still surfaced but never enter its prompt.

Strict-selector failure, ambiguous language selection, missing variables, mode mismatch, an active unfinished goal, an incompatible qualification, and unavailable goal creation all stop execution cleanly. None authorizes fallback to a different action or silent relaxation of the request.

## Behavioral examples

| Invocation or state | Result |
| --- | --- |
| `$toolkit:perform` | List variants and stop. |
| `$toolkit:perform find-todos[python]` when only `agnostic` exists | Report the strict miss and available same-name variants; do not fall back. |
| `$toolkit:perform check-config inspect JSON files` with `agnostic`, `json`, and `yaml` variants | Restrict to `check-config` and select `json` from positive language evidence. |
| `$toolkit:perform check-config` with the same variants | Select `agnostic` because no language is identified. |
| `$toolkit:perform format-source` with only `python` and `rust` variants | Ask for the language and wait. |
| `$toolkit:perform deploy production` with no adequate action | Decline without inspecting or executing an action. |
| `$toolkit:perform md-goal plans/implementation.md` in Default mode with no active goal | Bind the filename, render, show notes, create the exact goal, and execute. |
| `$toolkit:perform md-goal` | Inspect, discover the required filename is missing, and ask for it before rendering. |
| Any executable invocation while an unfinished goal is active | Ask the user to finish or clear the goal; do not render or execute. |
| A Plan-mode action invoked in Default mode | Ask the user to enter Plan mode and invoke it again. |
| A Default- or Goal-mode action invoked in Plan mode | Ask the user to return to Default mode and invoke it again. |
| `$toolkit:perform find-todos[agnostic] fix every TODO` | Reject the incompatible editing request because it changes the no-edits audit into another task. |

## Invariants

- Explicit invocation is required; Perform does not trigger configured actions on its own.
- Strict selectors never fall back.
- A known bare name narrows selection permanently for that invocation.
- Mutable action prompts are always inspected before binding and rendered before execution.
- User-derived bindings and qualifications are passed as data, never interpolated into shell commands.
- The final rendered prompt is authoritative and is executed in the current chat.
- `No edits.`, prompt-variable substitution, qualification assembly, inheritance, and validation are deterministic runtime behavior.
- Notes, diagnostics, selectors, and setting metadata never enter the action prompt or Goal objective.
- No unfinished goal may coexist with execution of any Perform action.
- The current skill does not launch a child Codex session, enforce launcher settings, or report setting mismatches.
