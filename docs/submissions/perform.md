# Perform public submission dossier

This dossier is the source of truth for the independent Perform Action Toolkit public listing. Copy field values exactly unless the portal documents a changed constraint. The authoritative execution-time process is the [official OpenAI submission guide](https://developers.openai.com/plugins/deploy/submission).

## Release identity and artifact

| Field                           | Value                                                                                               |
|---------------------------------|-----------------------------------------------------------------------------------------------------|
| Repository release              | `0.5.5` / tag `v0.5.5`                                                                              |
| Plugin ID and version           | `toolkit` `0.4.5`                                                                                   |
| Immutable source                | `https://github.com/pallgeuer/la-dev-codex-plugins/tree/v0.5.5/plugins/toolkit`                     |
| Archive                         | `toolkit-0.4.5.zip`                                                                                 |
| Archive source                  | Deterministic sorted ZIP of `plugins/toolkit` from tag `v0.5.5` with top-level directory `toolkit/` |
| SHA-256                         | `a19a519eb666b00de4b4120b411c761e70d4d13ba7400fc8b51f208c1a06240a`                                  |
| File list and uncompressed size | 45 entries; 301,323 bytes uncompressed; recorded below                                              |
| Submission type                 | Skills only through complete plugin ZIP upload                                                      |

Do not upload an archive built from an uncommitted tree or replace an archive after recording its digest.

Archive entries:

```text
toolkit/
toolkit/.codex-plugin/
toolkit/.codex-plugin/plugin.json
toolkit/.codexignore
toolkit/LICENSE
toolkit/README.md
toolkit/SECURITY.md
toolkit/assets/
toolkit/assets/composer-icon.svg
toolkit/assets/logo-dark.svg
toolkit/assets/logo.svg
toolkit/skills/
toolkit/skills/perform/
toolkit/skills/perform/SKILL.md
toolkit/skills/perform/agents/
toolkit/skills/perform/agents/openai.yaml
toolkit/skills/perform/assets/
toolkit/skills/perform/assets/toolkit_perform_actions/
toolkit/skills/perform/assets/toolkit_perform_actions/actions.json
toolkit/skills/perform/references/
toolkit/skills/perform/references/action_files.md
toolkit/skills/perform/references/codex_skill.md
toolkit/skills/perform/references/project_setup_agnostic.md
toolkit/skills/perform/references/project_setup_python.md
toolkit/skills/perform/references/standalone_cli.md
toolkit/skills/perform/scripts/
toolkit/skills/perform/scripts/get_perform_action.py
toolkit/skills/perform/scripts/list_perform_actions.py
toolkit/skills/perform/scripts/toolkit_perform_runtime/
toolkit/skills/perform/scripts/toolkit_perform_runtime/__init__.py
toolkit/skills/perform/scripts/toolkit_perform_runtime/_launcher_version.py
toolkit/skills/perform/scripts/toolkit_perform_runtime/_values.py
toolkit/skills/perform/scripts/toolkit_perform_runtime/action_catalogue.py
toolkit/skills/perform/scripts/toolkit_perform_runtime/api.py
toolkit/skills/perform/scripts/toolkit_perform_runtime/catalog.py
toolkit/skills/perform/scripts/toolkit_perform_runtime/cli.py
toolkit/skills/perform/scripts/toolkit_perform_runtime/diagnostics.py
toolkit/skills/perform/scripts/toolkit_perform_runtime/discovery.py
toolkit/skills/perform/scripts/toolkit_perform_runtime/launcher_api.py
toolkit/skills/perform/scripts/toolkit_perform_runtime/launching.py
toolkit/skills/perform/scripts/toolkit_perform_runtime/paths.py
toolkit/skills/perform/scripts/toolkit_perform_runtime/rendering.py
toolkit/skills/perform/scripts/toolkit_perform_runtime/standalone.py
toolkit/skills/perform/scripts/toolkit_perform_runtime/validation.py
toolkit/skills/perform/scripts/write_perform_action_catalogue.py
```

Use `toolkit-0.4.5.zip` as the complete plugin package for the ZIP-first submission flow and package-level distribution. It contains one `toolkit/` plugin root, an accepted `.codex-plugin/plugin.json` compatibility manifest that declares `"skills": "./skills/"`, and no `mcpServers`, `mcp.json`, or `.mcp.json`. The current portal accepts this compatibility layout even though the newer portable layout with root `plugin.json` is recommended for newly authored packages. Do not replace this recorded release archive merely to change formats.

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

Release notes: Initial public submission of Perform Action Toolkit 0.4.5 from repository release 0.5.5. The package preserves the existing `$toolkit:perform` selectors, catalogue layering, variable binding, and strict-failure behavior and supplies complete directory metadata, user-facing starter prompts, local-execution safeguards, standalone package documents, public policies, and distinct SVG branding; it does not add a hosted service or change runtime behavior.

## Validation record

Completed before draft creation:

- Release commit `50186b266ec6eaade6a39e1cec120f0984216a3a`, remote annotated tag `v0.5.5`, published GitHub Release, and PyPI `0.5.5` distribution verified.
- The deterministic archive was reproduced byte-for-byte in two independent builds; its SHA-256, complete file list, and 301,323-byte uncompressed size are recorded above.
- The clean extracted package exactly matched `plugins/toolkit` at `v0.5.5`, passed manifest and package-boundary validation, and contained no symlinks, caches, generated reports, secrets, or local paths.
- The release changed Perform's version, directory metadata, and bundled project-setup reference only. Its action runtime is byte-for-byte unchanged, and the complete `v0.5.5` release CI passed on every supported runner.
- Every listing, policy, support, and immutable source URL returned HTTP 200 without authenticated requests.
- The logo and composer icon passed SVG validation and remained recognizable at directory and composer sizes on light and dark backgrounds.

## Published channel records

The shared status and future-release procedures are in [Published discovery channels](published_channels.md).

### Official OpenAI plugin directory

No valid Perform draft or submission ID exists. On 2026-09-29, the publisher portal exposed only the `With MCP` form and required an MCP server at final validation, so an OpenAI Support ticket was submitted and no invalid workaround was used. On 2026-09-30, the portal and official guide changed to a unified **Upload new or existing plugin** flow. Release `0.4.5` was then prepared specifically for that importer with the preferred long description and user-facing starter prompts.

The verified `toolkit-0.4.5.zip` is ready for initial upload as a skills-only package. The portal should import its complete read-only listing metadata and one `perform` skill without creating an MCP setup task.

### Codex Plugin Marketplace

- Initial source: `https://github.com/pallgeuer/la-dev-codex-plugins/tree/v0.5.4/plugins/toolkit`
- Initial submission ID: `828e9134-a244-4a8a-bea2-dd5f3e6e6675`
- Initial displayed submission time: 2026-09-29 15:43
- Updated source: `https://github.com/pallgeuer/la-dev-codex-plugins/tree/v0.5.5/plugins/toolkit`
- Update submission ID: `6f7d98ba-8508-48b5-b431-8e788e4a11b5`
- Updated: 2026-09-30
- Authentication: personal owner match
- Automated result: repository and plugin approved, clean scan, no stored findings
- Public listing: `https://www.codex-marketplace.com/plugins/toolkit`
- Verified public version: `0.4.5`
- Install command: `npx codex-marketplace add pallgeuer/la-dev-codex-plugins/plugins/toolkit --plugin`

The direct public page was live on 2026-09-29. On 2026-09-30, submitting the new immutable tag tree updated the existing listing to `0.4.5` with the intended expanded description and displayed update date. The unpinned install source retrieved the `0.4.5` manifest from `main`; the general Browse response still had not indexed the entry.

### Hashgraph Awesome Codex Plugins

Perform is not submitted. HOL Plugin Scanner 3.9.0 reported 96/100, grade A, with policy and verification passing and no critical, high, medium, or low findings against the released package root. The channel still requires a repository-root entry even though this repository contains two independent plugin packages. Await maintainer guidance on `https://github.com/hashgraph-online/awesome-codex-plugins/issues/430#issuecomment-5891778025` before opening a pull request.

### OpenAI Community Plugins

- Prepared upstream base: `62844ca1cd865b76c7fed7180fc1ffef16e9167b`
- Contributor fork: `https://github.com/pallgeuer/community-plugins`
- Branch: `add-perform-toolkit`
- Commit: `bbab6f73a1215efcc03e53cdb69c59224cab3676`
- Pull request: `https://github.com/openai/community-plugins/pull/26`
- Current status on 2026-09-29: open, CLA passed, review required, no reviews

The contribution contains the exact `v0.5.4` Perform package plus its matching marketplace entry, root master test command, unit/integration/security tests, and single-job workflow. `npm run validate:marketplace`, `npm run test:toolkit` with five tests, and `npm run validate` passed. The complete marketplace dispatcher reached a pre-existing Autodesk Fusion storage check that rejects the managed sandbox's service-owned `/` ancestry; clean-host CI remains authoritative for that upstream-wide gate. The existing repository-wide CLA signature from Loupe PR #25 was recognized automatically, so no duplicate signature comment was posted.

Submitted pull-request title: `Add Perform Action Toolkit plugin`

Submitted pull-request body:

```markdown
## Summary

Add Perform Action Toolkit 0.4.4 for developers who want to discover reusable Codex actions, select an exact variant, bind required variables, preview the final workflow, and execute it with strict failure behavior.

The installable package is copied from `pallgeuer/la-dev-codex-plugins` release `v0.5.4` without package-content changes.

## Plugin impact

Users explicitly invoke `$toolkit:perform`. Bundled Python scripts use only the standard library to discover bundled, system, user, and repository action catalogues; list variants; inspect exact selectors; and render prompts. The skill previews the canonical selector, notes, and exact prompt before Codex executes the chosen action. The scripts do not themselves execute an action.

The selected action definition and the active Codex session determine which repository files, local tools, or network destinations a run may access. Perform itself has no hosted service, plugin-owned account, authentication flow, telemetry collector, credential store, or external data store. Direct prompt-variable values are nonsecret process arguments and may be visible to process or audit tooling; users are instructed to pass references to protected values rather than secrets.

Runtime prerequisites are Python 3.6+ using only the standard library and Codex 0.137.0+; Git is an optional repository-discovery aid. This contribution adds no npm or other third-party runtime dependency. The package is MIT licensed and includes its license and security policy.

The contribution adds offline cold-package tests for catalogue listing, strict selection, missing-variable failure, and rendering. Unknown strict selectors, missing variables, catalogue failures, incompatible qualifications, and unavailable goal mode stop without substituting or executing another workflow.

## Verification

- `npm run validate:marketplace` - passed
- `npm run test:toolkit` - passed, 5 tests
- `npm run validate` - passed
- The complete marketplace dispatcher passed all suites reached in the local sandbox. Its pre-existing Autodesk Fusion storage test cannot run under the sandbox service-owned `/` ancestry; the authoritative clean-host CI run remains required.
- The copied `plugins/toolkit` tree exactly matches tag `v0.5.4`.
- Source release archive SHA-256: `3f76504358c65c071dcdd873d55a7dc38a482cdebf2e9f03e66a77aaa484a704`

No credentials, customer data, private URLs, personal paths, dependency changes, or third-party-notice changes are included.

## Reviewer notes

Please review the per-action permission boundary carefully: Perform selects and previews actions, while each action definition and the active Codex permissions govern its eventual read, write, tool, and network behavior. The automated contribution tests do not execute configured actions or contact external services.
```
