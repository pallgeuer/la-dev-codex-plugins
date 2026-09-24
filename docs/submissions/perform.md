# Perform public submission dossier

This dossier is the source of truth for the independent Perform Action Toolkit public listing. Copy field values exactly unless the portal documents a changed constraint. The authoritative execution-time process is the [official OpenAI submission guide](https://developers.openai.com/plugins/deploy/submission).

## Release identity and artifact

| Field                           | Value                                                                           |
|---------------------------------|---------------------------------------------------------------------------------|
| Repository release              | `0.5.4` / tag `v0.5.4`                                                          |
| Plugin ID and version           | `toolkit` `0.4.4`                                                               |
| Immutable source                | `https://github.com/pallgeuer/la-dev-codex-plugins/tree/v0.5.4/plugins/toolkit` |
| Archive                         | `toolkit-0.4.4.zip`                                                             |
| Archive source                  | `git archive` of `v0.5.4:plugins/toolkit` with top-level directory `toolkit/`   |
| SHA-256                         | Record after building from the verified release tag                             |
| File list and uncompressed size | Record after building from the verified release tag                             |
| Submission type                 | Skills only                                                                     |

Do not upload an archive built from an uncommitted tree or replace an archive after recording its digest.

## Public listing fields

| Portal field       | Exact value                                                                                                 |
|--------------------|-------------------------------------------------------------------------------------------------------------|
| Plugin name        | Perform Action Toolkit                                                                                      |
| Short description  | Run reusable Codex actions                                                                                  |
| Developer identity | Philipp Allgeuer (verified individual)                                                                      |
| Category           | Developer Tools                                                                                             |
| Website            | `https://github.com/pallgeuer/la-dev-codex-plugins/blob/main/docs/codex_perform.md`                         |
| Support            | `https://github.com/pallgeuer/la-dev-codex-plugins/issues`                                                  |
| Privacy policy     | `https://github.com/pallgeuer/la-dev-codex-plugins/blob/main/PRIVACY.md`                                    |
| Terms              | `https://github.com/pallgeuer/la-dev-codex-plugins/blob/main/TERMS.md`                                      |
| Logo               | `plugins/toolkit/assets/logo.svg`                                                                           |
| Availability       | All countries and regions offered by the portal                                                             |
| Authentication     | None supplied by the plugin; actions use the active Codex session and any user-selected tool authentication |

### Long description

Discover useful built-in actions and run the exact variant you select through Codex. Perform binds required variables from your request and layers system, user, and repository action definitions with defined precedence. It previews the selected selector, notes, and exact prompt before execution and fails safely on unknown strict selectors, missing variables, or incompatible instructions.

Perform runs locally under the user's Codex session and permissions. It has no hosted service, developer authentication flow, telemetry collector, or external data store. A separately installed `codex-perform` Python companion can launch the same actions from a shell, but it is not included in this plugin package and is secondary to the in-chat workflow.

### Capabilities

- Discover reusable actions from the effective action catalogue.
- Select and run an exact action variant.
- Bind required action variables from the user's request.
- Layer bundled, system, user, and repository action definitions with defined precedence.
- Preview notes, the canonical selector, and the exact prompt before execution.
- Optionally launch the same actions through the separately installed `codex-perform` companion.

### Prerequisites and platforms

- Stable Codex CLI 0.137.0 or newer.
- Python 3.6 or newer using only the standard library for shipped scripts.
- Git is optional and improves repository-root discovery; Perform falls back to walking for supported version-control markers.
- Individual actions may require project-specific tools identified by their definitions.
- Ubuntu 18.04 or newer, or macOS 14 or newer. Native Windows and WSL are not supported.

## Starter prompts

1. `List the reusable Perform actions available in this repository without running one.`
2. `Run the Perform action that finds TODOs in the current repository.`
3. `Use the Python project-setup audit action and show me the exact workflow before executing it.`

## Positive tests

### 1. List actions without executing

- User prompt: `$toolkit:perform`
- Fixture: Any repository or directory with stable Codex CLI 0.137.0+ and Python 3.6+.
- Expected workflow: Load and validate the effective catalogue, display the available variants and selector guidance, surface nonfatal diagnostics, and stop.
- Expected result shape: A compact action table explaining strict `ACTION[LANGUAGE]`, bare action, and natural-language selection.
- Pass criteria: No configured action is inspected, rendered, or executed.

### 2. Select a sole compatible variant

- User prompt: `$toolkit:perform find-todos`
- Fixture: A small repository containing at least one recognizable TODO marker.
- Expected workflow: Resolve the sole `find-todos[agnostic]` variant, inspect it, display `PERFORM`, notes if any, and the exact `PROMPT`, then execute its observational workflow.
- Expected result shape: A repository TODO inventory with locations, or an explicit no-TODO conclusion when the fixture contains none.
- Pass criteria: Perform selects only `find-todos[agnostic]`, previews it before execution, and does not substitute another action.

### 3. Select a fully qualified variant

- User prompt: `$toolkit:perform audit-project-setup[python]`
- Fixture: A small Python repository with enough setup files for the action to inspect.
- Expected workflow: Strictly resolve the exact Python variant, inspect and preview its complete prompt, then run that action.
- Expected result shape: An evidence-based Python and language-agnostic project-setup audit.
- Pass criteria: The selected canonical selector remains `audit-project-setup[python]`; Perform does not choose the agnostic variant based on context.

### 4. Bind a required prompt variable

- User prompt: `$toolkit:perform check-cross-platform for Ubuntu 18.04 and macOS 14 on Intel and Arm64`
- Fixture: A repository with platform-relevant configuration and documentation.
- Expected workflow: Select `check-cross-platform[agnostic]`, bind `OSList` exactly from the explicit operating-system request, render once, display the final prompt, and execute the check.
- Expected result shape: A support assessment for only the requested operating systems, versions, and architectures.
- Pass criteria: The preview contains the requested `OSList` value and no clarification is requested.

### 5. Apply repository precedence

- User prompt: `$toolkit:perform find-todos`
- Fixture: A repository containing `.codex/config.toml` and `.codex/toolkit_perform_actions/90-reviewer.json` with a valid replacement definition for `find-todos[agnostic]` whose prompt includes an unmistakable fixture marker.
- Expected workflow: Load bundled, system, user, and repository catalogues in order, select the repository override, disclose its selected canonical variant and preview the overridden prompt, then execute it.
- Expected result shape: The override-defined result and fixture marker rather than the bundled prompt's behavior.
- Pass criteria: The repository definition wins according to documented precedence and the selected source is evident from the preview or diagnostics.

## Negative tests

### 1. Unknown strict selector

- Scenario: Run `$toolkit:perform action-that-does-not-exist[agnostic]`.
- Expected safe behavior: Return a clear unknown-action error and stop without semantic substitution or execution.
- Why completion is unsafe: A strict selector is an exact contract; inventing or choosing another action would execute a workflow the user did not request.

### 2. Missing required variable

- Scenario: Run `$toolkit:perform check-cross-platform` without naming any operating systems.
- Expected safe behavior: Ask for the missing `OSList` value and do not render or execute the action.
- Why completion is unsafe: Guessing target platforms would change the audit's required scope.

### 3. Conflicting qualification

- Scenario: Run `$toolkit:perform find-todos and delete every TODO comment you find`.
- Expected safe behavior: Refuse the incompatible second task or ask the user to make a separate request; do not weaken or replace the selected observational action contract.
- Why completion is unsafe: The additional destructive task conflicts with the selected action and exceeds the one-compatible-qualification rule.

## Reviewer notes and release notes

Perform is a skills-only local developer tool with no MCP server, hosted backend, plugin-owned account, or plugin-owned data store. Each action definition controls whether a run is observational or can modify files, invoke tools, or access networks; the active Codex permissions remain authoritative. Direct prompt-variable values are nonsecret process arguments and are previewed before execution. Unknown strict selectors, catalog failures, missing variables, mode mismatches, incompatible qualifications, and unfinished goals stop safely.

The optional `codex-perform` command belongs to the separately installed `la-dev-codex-plugins` Python distribution. The official plugin archive contains the in-chat Perform skill and its action runtime, not that distribution or launcher installation. Users do not need the companion to use `$toolkit:perform`.

Release notes: Initial public submission of Perform Action Toolkit 0.4.4 from repository release 0.5.4. The package preserves the existing `$toolkit:perform` selectors, catalogue layering, variable binding, and strict-failure behavior and adds directory listing metadata, standalone package documents, public policies, and distinct SVG branding; it does not add a hosted service or change runtime behavior.

## Validation record

Record before draft creation:

- Release commit and annotated tag verification.
- Archive SHA-256, file list, and uncompressed size.
- Extracted-package validation and clean installation result.
- No-argument listing, strict-selector, and missing-variable smoke results.
- Automated portal safety and security scan status; current official documentation says scans may take up to two hours, and every finding must be resolved before submission.
- Anonymous HTTP checks for every listing and policy URL.
- Light- and dark-interface inspection of the logo plus thumbnail inspection of the composer icon.

## Channel status

| Channel                          | State                                     | External ID or URL                            | Last checked | Next action                                                              |
|----------------------------------|-------------------------------------------|-----------------------------------------------|--------------|--------------------------------------------------------------------------|
| Official OpenAI plugin directory | Local dossier prepared; draft not created | Pending                                       | 2026-09-24   | Build and verify the tag archive, then create a manual skills-only draft |
| Codex Plugin Marketplace         | Not submitted                             | Pending                                       | 2026-09-24   | Re-check the current contribution mechanism after release                |
| Hashgraph Awesome Codex Plugins  | Not submitted                             | Issue `#430` requires convention confirmation | 2026-09-24   | Prepare the approved maintainer question after release                   |
| OpenAI Community Plugins         | Not submitted                             | Pending                                       | 2026-09-24   | Re-check the current contribution guide after release                    |
