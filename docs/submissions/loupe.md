# Loupe public submission dossier

This dossier is the source of truth for the independent Loupe Code Review public listing. Copy field values exactly unless the portal documents a changed constraint. The authoritative execution-time process is the [official OpenAI submission guide](https://developers.openai.com/plugins/deploy/submission).

## Release identity and artifact

| Field                           | Value                                                                                                   |
|---------------------------------|---------------------------------------------------------------------------------------------------------|
| Repository release              | `0.5.5` / tag `v0.5.5`                                                                                  |
| Plugin ID and version           | `la-review` `0.2.5`                                                                                     |
| Immutable source                | `https://github.com/pallgeuer/la-dev-codex-plugins/tree/v0.5.5/plugins/la-review`                       |
| Archive                         | `la-review-0.2.5.zip`                                                                                   |
| Archive source                  | Deterministic sorted ZIP of `plugins/la-review` from tag `v0.5.5` with top-level directory `la-review/` |
| SHA-256                         | `a32dfe358b85c200b228e8013192b391cc86ad6b0a0939a62e99c32600a74bb8`                                      |
| File list and uncompressed size | 19 entries; 57,182 bytes uncompressed; recorded below                                                   |
| Submission type                 | Skills only through complete plugin ZIP upload                                                          |

Do not upload an archive built from an uncommitted tree or replace an archive after recording its digest.

Archive entries:

```text
la-review/
la-review/.codex-plugin/
la-review/.codex-plugin/plugin.json
la-review/.codexignore
la-review/LICENSE
la-review/README.md
la-review/SECURITY.md
la-review/assets/
la-review/assets/composer-icon.svg
la-review/assets/logo-dark.svg
la-review/assets/logo.svg
la-review/skills/
la-review/skills/loupe/
la-review/skills/loupe/SKILL.md
la-review/skills/loupe/agents/
la-review/skills/loupe/agents/openai.yaml
la-review/skills/loupe/scripts/
la-review/skills/loupe/scripts/collect_review_diff.py
la-review/skills/loupe/scripts/run_reviewers.py
```

Use `la-review-0.2.5.zip` as the complete plugin package for the ZIP-first submission flow and package-level distribution. It contains one `la-review/` plugin root, an accepted `.codex-plugin/plugin.json` compatibility manifest that declares `"skills": "./skills/"`, and no `mcpServers`, `mcp.json`, or `.mcp.json`. The current portal accepts this compatibility layout even though the newer portable layout with root `plugin.json` is recommended for newly authored packages. Do not replace this recorded release archive merely to change formats.

## Public listing fields

| Portal field       | Exact value                                                                                |
|--------------------|--------------------------------------------------------------------------------------------|
| Plugin name        | Loupe Code Review                                                                          |
| Short description  | Verified multi-reviewer review                                                             |
| Developer identity | Philipp Allgeuer (verified individual)                                                     |
| Category           | Developer Tools                                                                            |
| Website            | `https://github.com/pallgeuer/la-dev-codex-plugins/blob/main/docs/loupe.md`                |
| Support            | `https://github.com/pallgeuer/la-dev-codex-plugins/issues`                                 |
| Privacy policy     | `https://github.com/pallgeuer/la-dev-codex-plugins/blob/main/PRIVACY.md`                   |
| Terms              | `https://github.com/pallgeuer/la-dev-codex-plugins/blob/main/TERMS.md`                     |
| Logo               | `plugins/la-review/assets/logo.svg`                                                        |
| Availability       | All countries and regions offered by the portal                                            |
| Authentication     | None supplied by the plugin; reviewer CLIs use the user's existing provider authentication |

### Long description

Run independent specialist reviewers on a working tree, branch, commit, range, or pull request, then verify and consolidate their evidence into one structured review. Loupe uses bounded parallel Codex reviewers and can optionally add Claude reviewers when the user's authenticated Claude CLI is available, providing cross-provider diversity without requiring a separate Loupe account. Configure provider-specific reasoning effort while preserving reviewer attribution, duplicate relationships, rejected claims, and partial failures.

Loupe runs locally under the user's Codex session and permissions. It has no hosted service, developer authentication flow, telemetry collector, or external data store. Reviewers may inspect repository content and send it to the user's configured Codex or Claude provider, so users must be authorized to disclose the review material.

### Capabilities

- Run independent specialist reviewers.
- Verify and consolidate review evidence.
- Review working trees, branches, commits, ranges, and pull requests.
- Use bounded parallel review with configurable provider and reviewer reasoning effort.
- Preserve rejected, unresolved, duplicate, failed, and timed-out reviewer outcomes in the final audit trail.

### Prerequisites and platforms

- Stable Codex CLI 0.137.0 or newer.
- Python 3.6 or newer using only the standard library for shipped scripts.
- Bash, Git, and `jq`.
- At least one installed and authenticated `codex` or `claude` reviewer executable; install both for provider diversity.
- Ubuntu 18.04 or newer, or macOS 14 or newer. Native Windows and WSL are not supported.

## Starter prompts

1. `Review my current uncommitted changes with independent reviewers and verify every finding.`
2. `Review the last commit with Loupe, emphasizing correctness and design evidence.`
3. `Review PR #123 with Loupe and consolidate duplicate or unsupported findings.`

## Positive tests

### 1. Default working-tree review

- User prompt: `$la-review:loupe`
- Fixture: A Git repository with a small reviewable staged, unstaged, or untracked source change; Python 3.6+, Bash, Git, `jq`, and at least one authenticated reviewer CLI.
- Expected workflow: Resolve the default scope to all uncommitted changes, capture the verification diff, launch every available specialist reviewer once in parallel, verify each candidate, and consolidate the result without modifying the repository.
- Expected result shape: A diff summary, status and elapsed time for every eligible reviewer, continuously numbered findings with evidence and recommendations, duplicate relationships where applicable, and explicit failure or no-finding states.
- Pass criteria: The report is bounded to the working-tree scope, every candidate is verified or retained as unsure, and no code or Git state is changed.

### 2. Branch comparison

- User prompt: `$la-review:loupe feature/reviewer-fixture branch`
- Fixture: A Git repository where `feature/reviewer-fixture` exists and differs from its base branch by a small known change.
- Expected workflow: Resolve and capture the requested branch comparison, pass that same scope to each eligible reviewer, and verify only findings relevant to the branch change.
- Expected result shape: The normal consolidated review with a branch-scoped diff summary and reviewer sections.
- Pass criteria: Evidence comes from the named branch comparison and Loupe does not silently substitute the current working tree or another branch.

### 3. Named commit

- User prompt: `$la-review:loupe commit <fixture-sha>`
- Fixture: A Git repository containing a known commit whose SHA replaces `<fixture-sha>` and whose change is small enough for deterministic inspection.
- Expected workflow: Resolve the exact commit, capture its relevant change set, run the eligible reviewers once, and verify their candidates against that commit.
- Expected result shape: The normal consolidated review tied to the named commit.
- Pass criteria: The report excludes unrelated earlier, later, and uncommitted changes.

### 4. Pull request

- User prompt: `$la-review:loupe PR #<fixture-pr-number>`
- Fixture: A GitHub-backed Git repository with an accessible pull request whose number replaces `<fixture-pr-number>`; any GitHub context required by the active reviewer tools is available.
- Expected workflow: Resolve the pull-request metadata and diff, pass the pull-request scope to the reviewers, and verify the candidates against that scope.
- Expected result shape: The normal consolidated review with pull-request context and evidence.
- Pass criteria: Loupe uses the requested pull request and fails clearly rather than reviewing another scope if the pull request cannot be resolved.

### 5. Reasoning-effort override

- User prompt: `$la-review:loupe last commit; low Claude effort, medium Codex effort`
- Fixture: A Git repository with a reviewable last commit, plus authenticated `claude` and `codex` executables.
- Expected workflow: Keep the effort instruction out of the review scope, translate it to the supported provider effort overrides, launch the fixed bounded reviewer set, and review only the last commit.
- Expected result shape: The normal consolidated review with both providers represented when available.
- Pass criteria: Claude receives `low`, Codex receives `medium`, no unsupported reviewer-count behavior is invented, and the scope remains the last commit.

## Negative tests

### 1. Not a Git repository

- Scenario: Run `$la-review:loupe` in a directory outside a Git worktree.
- Expected safe behavior: Stop with a clear Git-repository prerequisite failure before fabricating a diff or review.
- Why completion is unsafe: Loupe cannot resolve or verify its required review scope without the repository context.

### 2. Missing scope target

- Scenario: Run `$la-review:loupe commit 0000000000000000000000000000000000000000` in a repository where that object does not exist.
- Expected safe behavior: Report the exact scope-resolution failure and do not run a review of the working tree or another commit.
- Why completion is unsafe: Substituting another scope would present evidence about code the user did not request.

### 3. Ambiguous competing scopes

- Scenario: Run `$la-review:loupe review the last commit or PR #123, whichever looks relevant`.
- Expected safe behavior: Ask the user to choose one precise scope and do not launch reviewers.
- Why completion is unsafe: Guessing between unrelated Git scopes would make the review target and evidence unreliable.

## Reviewer notes and release notes

Loupe is a skills-only local developer tool with no MCP server, hosted backend, plugin-owned account, or plugin-owned data store. The active session creates a temporary diff and reviewer-output file, removes them after an uncomplicated successful review, and reports their local directory when diagnostic retention is necessary. Child reviewer CLIs use the user's existing authentication, configuration, quota, and provider policies. The skill never installs missing tools and runs successfully with reduced diversity when only one supported provider is available.

Release notes: Initial public submission of Loupe Code Review 0.2.5 from repository release 0.5.5. The package preserves the existing `$la-review:loupe` workflow and supplies complete directory metadata, user-facing starter prompts, optional Claude reviewer disclosure, standalone package documents, public policies, and distinct SVG branding; it does not add a hosted service or change runtime behavior.

## Validation record

Completed before draft creation:

- Release commit `50186b266ec6eaade6a39e1cec120f0984216a3a`, remote annotated tag `v0.5.5`, published GitHub Release, and PyPI `0.5.5` distribution verified.
- The deterministic archive was reproduced byte-for-byte in two independent builds; its SHA-256, complete file list, and 57,182-byte uncompressed size are recorded above.
- The clean extracted package exactly matched `plugins/la-review` at `v0.5.5`, passed manifest and package-boundary validation, and contained no symlinks, caches, generated reports, secrets, or local paths.
- The release changed Loupe's version and directory metadata only. Its previously smoke-tested review scripts are byte-for-byte unchanged, and the complete `v0.5.5` release CI passed on every supported runner.
- Every listing, policy, support, and immutable source URL returned HTTP 200 without authenticated requests.
- The logo and composer icon passed SVG validation and remained recognizable at directory and composer sizes on light and dark backgrounds.

## Published channel records

The shared status and future-release procedures are in [Published discovery channels](published_channels.md).

### Official OpenAI plugin directory

No valid Loupe draft or submission ID exists. On 2026-09-29, the publisher portal exposed only the `With MCP` form and required an MCP server at final validation, so an OpenAI Support ticket was submitted and no invalid workaround was used. On 2026-09-30, the portal and official guide changed to a unified **Upload new or existing plugin** flow. Release `0.2.5` was then prepared specifically for that importer with the preferred long description and user-facing starter prompts.

The verified `la-review-0.2.5.zip` is ready for initial upload as a skills-only package. The portal should import its complete read-only listing metadata and one `loupe` skill without creating an MCP setup task.

### Codex Plugin Marketplace

- Submitted source: `https://github.com/pallgeuer/la-dev-codex-plugins/tree/v0.5.4/plugins/la-review`
- Submission ID: `18247881-7092-45da-921b-47841d9f0ee4`
- Displayed submission time: 2026-09-29 15:36
- Authentication: personal owner match
- Automated result: repository and plugin approved, clean scan, no stored findings
- Public listing: `https://www.codex-marketplace.com/plugins/la-review`
- Verified public version: `0.2.4`
- Install command: `npx codex-marketplace add pallgeuer/la-dev-codex-plugins/plugins/la-review --plugin`

The direct public page was live on 2026-09-29 with the intended publisher, description, version, and install command. The general Browse response had not indexed the entry yet.

### Hashgraph Awesome Codex Plugins

Loupe is not submitted. HOL Plugin Scanner 3.9.0 reported 96/100, grade A, with policy and verification passing and no critical, high, medium, or low findings against the released package root. The channel still requires a repository-root entry even though this repository contains two independent plugin packages. Await maintainer guidance on `https://github.com/hashgraph-online/awesome-codex-plugins/issues/430#issuecomment-5891778025` before opening a pull request.

### OpenAI Community Plugins

- Prepared upstream base: `62844ca1cd865b76c7fed7180fc1ffef16e9167b`
- Contributor fork: `https://github.com/pallgeuer/community-plugins`
- Branch: `add-la-review`
- Commit: `1c4e575d48b479c8240cf9d772af2555e9ab0949`
- Pull request: `https://github.com/openai/community-plugins/pull/25`
- CLA signature: `https://github.com/openai/community-plugins/pull/25#issuecomment-5892082519`
- Current status on 2026-09-29: open, CLA passed, review required, no reviews

The contribution contains the exact `v0.5.4` Loupe package plus its matching marketplace entry, root master test command, unit/integration/security tests, and single-job workflow. `npm run validate:marketplace`, `npm run test:la-review` with five tests, and `npm run validate` passed. The complete marketplace dispatcher reached a pre-existing Autodesk Fusion storage check that rejects the managed sandbox's service-owned `/` ancestry; clean-host CI remains authoritative for that upstream-wide gate.

Submitted pull-request title: `Add Loupe Code Review plugin`

Submitted pull-request body:

```markdown
## Summary

Add Loupe Code Review 0.2.4 for developers who want independent specialist reviews of a working tree, branch, commit, range, or pull request with evidence verification and consolidated results.

The installable package is copied from `pallgeuer/la-dev-codex-plugins` release `v0.5.4` without package-content changes.

## Plugin impact

Users explicitly invoke `$la-review:loupe`. The skill reads Git metadata and repository content for the requested scope. Its bundled Python helpers capture a bounded diff in a private temporary directory and launch the user's available `codex` and/or `claude` reviewer CLIs through Bash and `jq`; Loupe does not edit, stage, or commit repository files.

An invoked reviewer may send repository diffs or related inspected content to the user's configured OpenAI or Anthropic provider under that user's existing authentication, account, quota, and provider policies. Loupe has no hosted service, plugin-owned account, telemetry collector, credential store, or external data store. Temporary diff and reviewer-result files are removed after an uncomplicated successful run and retained with their path reported when diagnostics are needed.

Runtime prerequisites are Python 3.6+ using only the standard library, Bash, Git, `jq`, and at least one authenticated `codex` or `claude` executable. This contribution adds no npm or other third-party runtime dependency. The package is MIT licensed and includes its license and security policy.

The contribution adds an offline cold-package test that uses a disposable local Git fixture and never launches external reviewers. Missing Git context, invalid scopes, unavailable reviewer tools, invalid effort values, reviewer failures, and timeouts fail explicitly rather than silently selecting another scope or fabricating a successful review.

## Verification

- `npm run validate:marketplace` - passed
- `npm run test:la-review` - passed, 5 tests
- `npm run validate` - passed
- The complete marketplace dispatcher passed all suites reached in the local sandbox. Its pre-existing Autodesk Fusion storage test cannot run under the sandbox service-owned `/` ancestry; the authoritative clean-host CI run remains required.
- The copied `plugins/la-review` tree exactly matches tag `v0.5.4`.
- Source release archive SHA-256: `d1ada402268bae53014df044e8511bc5438fe90313d4ae7ab1d1f1ea5fb96193`

No credentials, customer data, private URLs, personal paths, dependency changes, or third-party-notice changes are included.

## Reviewer notes

Please review the off-machine provider boundary carefully: repository material is disclosed only when the user explicitly invokes Loupe and only through the user's locally configured reviewer CLIs. The automated contribution tests do not contact either provider.
```
