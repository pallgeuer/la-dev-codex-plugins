# Loupe public submission dossier

This dossier is the source of truth for the independent Loupe Code Review public listing. Copy field values exactly unless the portal documents a changed constraint. The authoritative execution-time process is the [official OpenAI submission guide](https://developers.openai.com/plugins/deploy/submission).

## Release identity and artifact

| Field                           | Value                                                                             |
|---------------------------------|-----------------------------------------------------------------------------------|
| Repository release              | `0.5.4` / tag `v0.5.4`                                                            |
| Plugin ID and version           | `la-review` `0.2.4`                                                               |
| Immutable source                | `https://github.com/pallgeuer/la-dev-codex-plugins/tree/v0.5.4/plugins/la-review` |
| Archive                         | `la-review-0.2.4.zip`                                                             |
| Archive source                  | `git archive` of `v0.5.4:plugins/la-review` with top-level directory `la-review/` |
| SHA-256                         | Record after building from the verified release tag                               |
| File list and uncompressed size | Record after building from the verified release tag                               |
| Submission type                 | Skills only                                                                       |

Do not upload an archive built from an uncommitted tree or replace an archive after recording its digest.

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

Run independent specialist reviewers on a working tree, branch, commit, range, or pull request, then verify and consolidate their evidence into one structured review. Configure reasoning effort while Loupe keeps reviewer execution bounded and preserves reviewer attribution, duplicate relationships, rejected claims, and partial failures.

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

Release notes: Initial public submission of Loupe Code Review 0.2.4 from repository release 0.5.4. The package preserves the existing `$la-review:loupe` workflow and adds directory listing metadata, standalone package documents, public policies, and distinct SVG branding; it does not add a hosted service or change runtime behavior.

## Validation record

Record before draft creation:

- Release commit and annotated tag verification.
- Archive SHA-256, file list, and uncompressed size.
- Extracted-package validation and clean installation result.
- Skill discovery and bounded working-tree smoke result.
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
