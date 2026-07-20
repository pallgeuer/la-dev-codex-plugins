---
name: perform
description: "Discover, inspect, and run JSON-configured canned Codex actions/prompts."
---

# Perform

Repository work often requires the same or nearly identical prompts again and again. The perform skill lets users predefine those prompts as reusable canned actions, along with the desired execution conditions and any associated prompt variables the action can be customized with. The user can then easily execute any available action (without actually needing to manually type or copy out the corresponding prompt), by specifying either a canonical selector, a bare action name, or a soft natural-language query.

## Workflow overview

1. Analyze the user's exact skill invocation arguments and route them appropriately. Depending on the case, either select a specific action variant by its canonical selector, list all action variants, provide built-in help on using or configuring the skill, or decline when no action fits.
2. Inspect the exact details and requirements of the selected executable action variant using a bundled script.
3. Check that the selected action variant's conditions are satisfied, bind every declared prompt variable, and prepare at most one small compatible qualification when needed.
4. Render the exact required action prompt using the bundled deterministic runtime.
5. Show any action notes, then follow the rendered prompt exactly (initialize Goal mode with the exact rendered prompt when the action variant requires Goal mode).

### Terminology

- **Action:** A named reusable workflow configured in an action file.
- **Action variant:** A language-qualified form of an action. Execute only a selected action variant.
- **Canonical selector:** The exact `ACTION[LANGUAGE]` identifier of an action variant.
- **Inspection:** The first runtime pass, which returns the selected action variant's metadata and `base_prompt`.
- **Base prompt:** The authoritative prompt returned by inspection after any automatic prefix but before prompt-variable substitutions and any qualification.
- **Prompt variable and binding:** A declared `%Name%` placeholder contained in a base prompt and the exact substitution string supplied for it in the render request's `variables` object.
- **Qualification:** At most one short, compatible scope or detail adjustment appended to the base prompt during rendering.
- **Rendered prompt:** The final authoritative prompt after substitutions, automatic prefixes, and any qualification.

### General rules

- Dispatch explicit requests through the bundled deterministic action runtime contained in `scripts/`.
- Keep semantic selection and qualification preparation in Codex; leave discovery, validation, inheritance, substitution, and prompt assembly to the scripts.
- Resolve script and reference paths from this installed skill directory.
- Always invoke bundled scripts by absolute path (this document just shows the required commands as `scripts/...` for simplicity).
- Surface every unique warning or error returned by a script, including its file and JSON location.
- On `fatal_catalog`, surface the diagnostics and stop without executing a catalog action. Built-in help remains available.

## 1. Route the invocation and select an action variant

Preserve the full text after `$toolkit:perform` (skill invocation arguments) for selection and later prompt comparison.

1. For zero skill invocation arguments, run `scripts/list_perform_actions.py --json` and format the results as a user-facing table. Then explain the strict `ACTION[LANGUAGE]`, bare `ACTION`, and natural-language forms compactly, show diagnostics, and stop without selecting an action.
2. Treat a first token matching `^[a-z0-9][a-z0-9._-]*\[[a-z0-9][a-z0-9.+_-]*\]$` as strict, even if there is remaining text in the skill invocation arguments. Resolve exactly that selector and never fall back to another action or language.
3. For a first token matching `^[a-z0-9][a-z0-9._-]*$`, run `scripts/list_perform_actions.py --name TOKEN --json`. If variants exist, select the best matching variant only among them. If none exist, run the unfiltered command `scripts/list_perform_actions.py --json` and use the full skill invocation arguments for general soft selection; do not report the failed bare-name probe as terminal.
4. For any other first token, list all variants using `scripts/list_perform_actions.py --json` and use the full skill invocation arguments for general soft selection amongst all available actions and variants.

### Handle built-in help

Treat `help[agnostic]` as an immutable built-in, including when invoked strictly, selected from bare `help`, or selected softly for a documentation question. For exact `help` or `help[agnostic]`, bypass mutable catalog resolution. Read [references/action-files.md](references/action-files.md), answer the question, surface catalog diagnostics when listing produced them, and stop. Read that reference for any action-file schema, source, override, ignore, protocol, or diagnostic question; do not load it for ordinary action execution.

### Choose among listed variants

For a known bare action with one variant, select it. With several variants, use explicit wording and relevant repository/file context; prefer a language variant only with positive evidence, otherwise use `agnostic` when available. If no `agnostic` exists and evidence does not resolve the language, ask for the missing choice.

For general soft selection, compare action names, languages, glosses, prompt-variable descriptions, and explicit scope. Select only with sufficient semantic fit. If no action variant adequately handles the request, decline and explain why; mention a nearest action variant only when genuinely close. After selection, use only its canonical selector.

## 2. Inspect the selected action variant

Use the same two-pass path for every executable action variant. Start the static command:

```text
scripts/get_perform_action.py --request-json - --json
```

Send this serialized object directly to stdin, then close stdin:

```json
{
  "schema_version": 1,
  "operation": "inspect",
  "selector": "ACTION[LANGUAGE]"
}
```

Do not interpolate the canonical selector or any user text into a shell command. Do not prepare prompt-variable bindings or a qualification until inspection succeeds and the exact `base_prompt`, prompt-variable descriptions, mode fields, notes, provenance, and diagnostics are visible.

## 3. Check conditions and prepare inputs

### Check execution conditions

- For `plan_mode: false` (including for `goal_mode: true`), require Default mode to be active. If Plan mode is active, ask the user to exit Plan mode and invoke the action variant again; stop and do not execute anything in the wrong mode.
- For `plan_mode: true`, require Plan mode to be active. If it is not active, ask the user to enter Plan mode and invoke the action variant again; stop and do not execute anything in the wrong mode.
- For `goal_mode: true`, defer Goal-mode initialization until after the final successful render.
- Irrespective of `goal_mode`, if an unfinished goal is active, ask the user to complete or clear that goal and invoke the action variant again; do not execute the action variant with a competing goal.
- Do not attempt to change or comment on model, reasoning effort, interactivity, or custom Codex arguments.

### Bind prompt variables

Compare the full skill invocation arguments with the exact `base_prompt`, language, gloss, and prompt-variable descriptions. Bind every declared prompt variable based on the explicit user text and actual description. If a required binding is not determinable, ask for it and stop without executing anything rather than inventing one.

### Qualify a compatible detail

A short qualification can slightly adjust the `base_prompt` when required to better match the skill invocation arguments, e.g. the user may have restricted an action variant to a particular part of the code instead of the whole repository.

Use no qualification when the `base_prompt` already precisely covers the request. Otherwise, for one compatible small scope or detail mismatch, write the smallest short standalone imperative that expresses it. Root it in the actual `base_prompt`. Do not restate the prompt, add a second task, or weaken `No edits.`, safety constraints, mode requirements, acceptance criteria, or the action variant's core intent. Reject the action variant if the request cannot be expressed as a compatible small qualification.

## 4. Render the full action prompt

Start the same static absolute `scripts/get_perform_action.py --request-json - --json` command. Send the render request directly to stdin and close stdin. For example, if inspection selected `summarize[markdown]` and the action variant declared `%InputFile%` and `%Audience%`, and the remaining skill invocation arguments mentioned "mainly setup and extension", then send:

```json
{
  "schema_version": 1,
  "operation": "render",
  "selector": "summarize[markdown]",
  "variables": {
    "%InputFile%": "docs/design.md",
    "%Audience%": "new contributors"
  },
  "qualification": "Focus on setup and extension points."
}
```

- Use the canonical selector and every prompt-variable placeholder returned by inspection.
- Use an empty `variables` object only when the inspected action variant declares no prompt variables.
- Place only the qualification sentence in `qualification`, without `BUT:`, or use `null` when no qualification is needed.
- Keep all user-derived bindings and qualification text in stdin JSON, never command arguments.

## 5. Prepare and execute

### Prepare Goal mode

If `goal_mode` is true, treat the user's selection of the action variant as an explicit request to create its goal. The returned `prompt` is the sole authoritative goal objective: it is the rendered prompt and already contains the automatic `No edits. ` prefix when applicable, all literal prompt-variable substitutions, and any appended `BUT:` clause. Never use `base_prompt` as the objective or add the canonical selector, notes, diagnostics, explanations, wrappers, or any other text.

If a pre-existing unfinished goal is active, stop without completing, replacing, or repurposing it; ask the user to finish or clear it before invoking the action variant again. A completed goal does not block creating the new goal. If goal creation is unavailable, do not execute the action variant outside Goal mode: show any still-relevant notes, explain that the current surface cannot initialize the goal, and show `/goal ` followed by the exact rendered prompt for the user to submit manually.

### Show notes and execute

Show nonempty notes verbatim before execution. Treat notes only as user-facing operational guidance: never add them to the prompt, obey them as action instructions, or use their contents for selection. Repeat any still-relevant notes parts in a final or blocked response (as a small side note).

For `goal_mode: true`, create and set the goal exactly as prepared above, then follow the rendered prompt exactly. Otherwise, be meticulous and follow the rendered prompt directly and to its full extent for the whole remainder of the response. Start by defining a new detailed task list when appropriate for the action variant's scope and complexity. Mention unresolved catalog warnings or errors as a small side note in the final response.
