# Language-agnostic project setup

For an empty directory, start with the [New repository setup recipe](https://github.com/pallgeuer/la-dev-codex-plugins/blob/main/docs/new_repo_recipe.md), which pulls Codex configuration and permanent instructions forward before a single early activation checkpoint. These are required setup steps unless an explicit user decision or a stated applicability condition changes them. Record every deviation. For an existing repository, merge requirements without overwriting working choices.

Use this guide after completing [Marketplace plugin installation](https://github.com/pallgeuer/la-dev-codex-plugins/blob/main/docs/installation.md) and [Recommended Codex setup](https://github.com/pallgeuer/la-dev-codex-plugins/blob/main/docs/recommended_setup.md). Apply it from the repository root, merge with existing files instead of overwriting them, and review `git status` before and after each section.

For a Python repository, complete the shared setup together with [Python project setup](project_setup_python.md). After setup, use [AI-supported repository development](https://github.com/pallgeuer/la-dev-codex-plugins/blob/main/docs/ai_supported_development.md) for the normal development loop.

## 1. Create the root project documents

Create `README.md` with the headings that apply:

```markdown
# Project name

One sentence stating what the project does and for whom.

## Installation

Exact installation or setup commands.

## Usage

One minimal working example, followed by links to detailed documentation.

## Compatibility

Supported platforms, runtimes, and important exclusions.

## Documentation

Links to user and developer documentation.

## Contributing

Link to CONTRIBUTING.md, when present.

## License

License name and link to the license file.
```

Keep installation and the first example usable without reading the whole file. Omit `Contributing` when the project does not accept contributions. Decide licensing explicitly, independently of repository visibility. A private repository can still require a license and attribution. Use the agreed license text/metadata and explicit later-version permission when requested; do not invent per-file license headers. For a distributed or open-source project, add the appropriate `LICENSE` or `LICENSE.md`.

For a versioned project, create `CHANGELOG.md` before the first commit. The Release diffs section is required even before any tags exist:

````markdown
# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and the project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## Release diffs

TODO: Replace this placeholder with real release/comparison links when preparing the first version tag. No version tags exist yet. The following is an example only; these versions and links do not describe existing releases:

```text
Unreleased: https://github.com/YOUR-ORG/YOUR-REPOSITORY/compare/v0.2.0...HEAD
v0.2.0: https://github.com/YOUR-ORG/YOUR-REPOSITORY/compare/v0.1.0...v0.2.0
v0.1.0: https://github.com/YOUR-ORG/YOUR-REPOSITORY/releases/tag/v0.1.0
```

---

## Unreleased

None.
````

Create `## Release diffs` during repository setup, before the first commit, even when no version tags exist. Before the first tag, keep an explicit TODO and put example URLs inside a `text` fence so they cannot be mistaken for existing releases. Do not invent version tags or create a synthetic `v0.0.0` baseline just to populate the section. Do not rewrite an existing first commit to retrofit this structure.

Replace `None.` with `Added`, `Changed`, `Fixed`, or `Removed` sections when noteworthy work lands. Keep entries about shipped outcomes, not intermediate implementation churn. Separate the introduction, release diffs, `Unreleased`, and every released-version section with horizontal rules, and retain `Unreleased` even when empty.

During first-release preparation, replace the TODO/example block with real links in the release commit before tagging: `Unreleased` compares the approved first tag with HEAD; the earliest version links to its GitHub release. For subsequent releases, compare each new tag with the previous release tag and update the Unreleased base to the new tag. Use the actual approved versions, not the example numbers. The new tag/release links become resolvable during tagging/publication; verify them then. No placeholder example may remain in a released changelog.

For example, a minimal complete changelog with two releases can use level-four category headings within the standard change-type sections:

```markdown
# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and the project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## Release diffs

- **Unreleased:** https://github.com/YOUR-ORG/YOUR-REPOSITORY/compare/v0.2.0...HEAD
- **v0.2.0:** https://github.com/YOUR-ORG/YOUR-REPOSITORY/compare/v0.1.0...v0.2.0
- **v0.1.0:** https://github.com/YOUR-ORG/YOUR-REPOSITORY/releases/tag/v0.1.0

---

## Unreleased

### Changed

#### Configuration

- Changed default value of `foo` config from 20 to 30.

---

## 0.2.0 (2026-08-12)

### Added

#### Command-line interface

- Added `--check` for non-mutating validation.

#### Configuration

- Added config `foo` to control the maximum number of bars.

### Fixed

#### Configuration

- Fixed relative paths being resolved from the process working directory instead of the configuration file.

---

## 0.1.0 (2026-07-01)

### Added

#### Initial release

- Added the documented public API and command-line interface.
```

Replace the repository, versions, dates, categories, and outcomes with the project facts. Preserve the `Unreleased` section even when it is empty.

`CONTRIBUTING.md` is optional. Add it for a shared or open-source repository and include exact environment setup, repository layout, focused and complete checks, documentation commands, dependency policy, and pull-request expectations.

For a versioned project, [create `RELEASE.md` during setup](#9-create-releasemd-for-versioned-projects), even before its first release. The bundled `publish-release` Perform action requires this file and follows it as the project-specific release authority.

## 2. Add development document and scratch locations

Create the durable and temporary locations:

```bash
mkdir -p docs/devel/plans
touch docs/devel/plans/.gitkeep
touch TODO.txt
```

Use `docs/devel/` for committed implementation specifications, audits, and repeatable workflows. Use `docs/devel/plans/` for temporary plans, progress journals, and AI handoff notes. Use root `TODO.txt` only as a private scratchpad; durable work belongs in an issue, test, specification, action, or changelog entry.

During setup, maintain `docs/devel/plans/repository_setup.md` from the first authorized implementation step. Record scope, decisions/approvals, checkpoints, commands/results, blockers, exact next actions, and a deferred-work table with each item's reason and resumption condition. Update it at checkpoints and before every restart or turn end. Plan mode remains read-only: create the journal once execution is authorized. Keep setup history here, not in permanent AGENTS.md. At completion, summarize every remaining deferral, including any plans-directory cleanup. Remove only clearly disposable temporary artifacts you created; preserve `.gitkeep`, useful/protected journals and reports, and anything uncertain. Record what was removed and why anything remains.

## 3. Add a concise `.gitignore`

Start with this block and add only outputs the project actually creates:

```gitignore
.DS_Store
.idea/
.vscode/
*.swp
*.swo
/.codex/toolkit_perform_actions/action_catalogue.md
/docs/devel/plans/*
!/docs/devel/plans/.gitkeep
/TODO.txt
.env
.env.*
!.env.example
```

Then stage the placeholder explicitly:

```bash
git add docs/devel/plans/.gitkeep
```

If inherited ignore rules still hide the placeholder, use `git add -f docs/devel/plans/.gitkeep`. Verify that only the placeholder is tracked; never stage the entire plans directory. Keep intentionally safe `.env.example` content free of credentials, and avoid blanket image/JSON ignores that would hide source fixtures.

Language-specific caches, environments, and build outputs belong in the corresponding language setup rather than a copied all-purpose ignore template.

## 4. Add repository-level Codex configuration

Create `.codex/config.toml`:

```toml
approval_policy = "on-request"
model_reasoning_effort = "medium"
plan_mode_reasoning_effort = "high"
sandbox_mode = "workspace-write"
web_search = "live"

[sandbox_workspace_write]
network_access = true
writable_roots = [
  "~/.cache/gh",
  "~/.cache/pre-commit",
]
```

The file records project defaults and enables repository-local Perform action discovery. The example permits GitHub CLI and pre-commit cache writes; add other narrow writable cache roots only for tools the project uses. A repository-level `writable_roots` value replaces, rather than extends, the user- or system-level list. Therefore repeat every external writable path needed while working in this repository, such as the pip and uv paths from the recommended user setup, instead of listing only the repository-specific additions. Disable live search or command network access when the repository's security requirements do not permit them.

Before claiming this layer is active, complete the [project-trust and activation checks](https://github.com/pallgeuer/la-dev-codex-plugins/blob/main/docs/recommended_setup.md#project-trust-and-activation). Review the exact user-level trust/configuration diff before applying it; preserve unrelated settings and prior approvals.

## 5. Create a concise `AGENTS.md`

Start with this permanent repository-instruction structure. Keep the opening purpose statement short and stable; describe current capabilities, future roadmaps, and implementation status in the README or focused project documentation. Keep setup checkpoints, restart handoffs, historical approvals, and deferred setup tasks in the temporary setup journal or entry recipe rather than adding them to permanent instructions.

Everything outside angle brackets is reusable literal guidance. Replace every `<...>` item with project-specific content and remove any placeholder that does not apply:

```markdown
# Repository instructions

This repository is for <brief description of the repository's purpose>.

## Project layout

- Keep this project layout in `AGENTS.md` up-to-date as new project structure emerges.
- <List each first-party source, test, documentation, and generated-output root.>
- `docs/devel/plans/` contains ignored temporary plans, journals, and AI handoffs.
- <Identify the supported public interfaces and their sources of truth.>

## Commands

- <Record the exact canonical setup, formatting, linting, type-checking, test, documentation, and full-check commands after those commands exist.>

## Code style

- NEVER manually wrap code/comments/in-code documentation during code writing and edits; allow the formatters to later enforce line length.
- Use ASCII-only project source; represent required non-ASCII values with escapes. Markdown files may use literal non-ASCII when required, but should still make obvious near-equivalent ASCII replacements where suitable.
- Use sentence case for Markdown headings and table headers; capitalize only the first word, the first word after a colon, and proper nouns.

## Tests

- Put stable behavior and important failure modes under automated test; do not lock incidental wording or implementation details unless they are the public contract.
- After changing behavior, run applicable functional tests in addition to formatting, linting, type checking, and compatibility checks.
- Do not lock incidental text into test assertions. If tests fail only because wording changed, determine whether the wording is a public contract and ask when unclear; do not blindly revert the wording.

## Workflows

- Do not change project versions during ordinary development; update them only when the user explicitly requests a version bump or release.
- Interview me for relevant details when making plans, unless the details are quite clear already from the provided information.
- When changing a public interface, update its tests, documentation, examples, and changelog entry in the same change.
- Concisely document significant completed work in CHANGELOG.md under the Unreleased section, using Added/Changed/Fixed/Removed headings, short general level-four category headings, outcome bullets beneath those category headings, and horizontal rules between top-level changelog sections.
- Use a solo direct-main workflow with minimal remote automation. Do not add publication, update bots, branch protection, or a hosted documentation site without a new decision.
```

Replace the angle-bracketed placeholders and add exact commands as tools are configured. Preserve the reusable literal wording when filling placeholders; change other wording only for a meaningful project requirement. Do not duplicate the literal plans-directory entry when expanding the layout placeholder. The solo direct-main workflow is the starting default; explicitly adapt that instruction when the user chooses a different branching, review, automation, or publication policy. The standard plans directory remains temporary operational state, not the project's permanent backlog. The ASCII-only line is a deliberate portability policy; omit it if the project intentionally uses Unicode source. Keep judgment-heavy details in focused `docs/devel/` files and link them from `AGENTS.md` with a clear trigger. Do not restate formatter or linter configuration in prose. See [AI-supported repository development](https://github.com/pallgeuer/la-dev-codex-plugins/blob/main/docs/ai_supported_development.md) for deciding whether a convention belongs in a tool, test, specification, instruction, or Perform action.

## 6. Install baseline pre-commit checks

### Establish editor and source-file hygiene

The complete setup includes the following files and hooks. Preserve existing settings; adapt only for an explicit project decision and record the deviation. For an existing repository, review line-ending normalization separately instead of causing an unrelated mass rewrite.

Create `.editorconfig`:

```ini
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
indent_style = space
indent_size = 4
trim_trailing_whitespace = true

[*.{yml,yaml,json}]
indent_size = 2

[*.md]
trim_trailing_whitespace = false
```

Create `.gitattributes`:

```gitattributes
* text=auto eol=lf
```

Keep binary classification and any deliberate existing attributes. Formatter configuration remains authoritative for source formatting. Keep credentials, environments, build output, research data, and model weights outside version control unless a concrete storage/layout requirement has been agreed. Private-key detection is useful hygiene, not a complete secret scanner.

Install [pre-commit](https://pre-commit.com/) using the project environment or an isolated tool runner. Create `.pre-commit-config.yaml`, replacing `vX.Y.Z` with a released tag of this repository:

```yaml
minimum_pre_commit_version: "4.6.0"
default_install_hook_types: [pre-commit, pre-push]

repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v6.0.0
    hooks:
      - id: check-json
        stages: [pre-commit, pre-push, manual]
      - id: check-toml
        stages: [pre-commit, pre-push, manual]
      - id: check-yaml
        stages: [pre-commit, pre-push, manual]
      - id: check-merge-conflict
        stages: [pre-commit, pre-push, manual]
      - id: detect-private-key
        stages: [pre-commit, pre-push, manual]
      - id: check-added-large-files
        args: [--maxkb=5120, --enforce-all]
        stages: [pre-commit, pre-push, manual]
      - id: end-of-file-fixer
        stages: [pre-commit]
      - id: trailing-whitespace
        args: [--markdown-linebreak-ext=md]
        stages: [pre-commit]

  - repo: https://github.com/pallgeuer/la-dev-codex-plugins
    rev: vX.Y.Z
    hooks:
      - id: markdown-tables-fix
        stages: [pre-commit]
      - id: markdown-tables-check
        stages: [pre-push, manual]
```

Install both hook types and verify the non-mutating stage:

```bash
pre-commit install
pre-commit install --hook-type pre-push
pre-commit run --all-files --hook-stage manual
```

Every code repository should add an appropriate formatter and linter, and normally tests and type checks, before considering setup complete. Add those hooks in the language-specific guide. Commit-time hooks may fix files; pre-push, manual, and CI hooks should only check.

The large-file hook enforces 5 MiB (5,242,880 bytes) on every file passed to it, including modified files because of `--enforce-all`; an all-files manual/CI invocation checks tracked files throughout the repository. Exactly 5 MiB is allowed. A larger file prints its path/size and fails the commit, pre-push, or manual/CI check without deleting/truncating it. Deliberately agree on a narrow exception, revised limit, external storage, or Git LFS for a legitimate larger file; do not silently bypass checks. The hook excludes paths marked `filter=lfs`, but this example does not configure LFS. File-size hygiene is separate from a data/model storage policy.

Whitespace fixers run only at commit time and preserve deliberate Markdown line breaks. Manual/pre-push/CI stages must not rewrite files; add check-only whitespace validation if that is required, not these fixers at a non-mutating stage.

## 7. Add repeatable Perform actions when needed

When a contextual task recurs, or a project convention cannot be enforced reliably by a standard tool, script, or test, create `.codex/toolkit_perform_actions/actions.json`:

```json
{
  "version": 1,
  "ignore_actions": [],
  "actions": {
    "audit-project-convention": {
      "agnostic": {
        "gloss": "Audit the project-specific convention",
        "model": "default",
        "reasoning_effort": "medium",
        "goal_mode": false,
        "plan_mode": false,
        "plan_reasoning_effort": "medium",
        "no_edits": true,
        "prompt_vars": {},
        "prompt": "Audit the repository against docs/devel/project_convention.md. Produce an enumerated findings list with exact evidence and concrete corrections.",
        "requires_interactive": false,
        "custom_codex_args": [],
        "notes": ""
      }
    }
  }
}
```

Keep actions narrow and make their success verifiable. Prefer automation over an action when the rule can be checked deterministically. See [Codex Perform](https://github.com/pallgeuer/la-dev-codex-plugins/blob/main/docs/codex_perform.md) for variants, variables, overrides, and launch modes.

Generate the effective catalogue after adding or changing actions:

```text
$toolkit:perform update-action-catalogue
```

To generate it directly without spending another Codex turn, source the marketplace checkout's activation script once in each new Bash session and run the standalone catalogue command from the target repository:

```bash
# Locate it when necessary:
find "${CODEX_HOME:-$HOME/.codex}" -path "*/la-dev-codex-plugins/activate.sh"

# Often this is ~/.codex/.tmp/marketplaces/la-dev-codex-plugins/activate.sh.
source /PATH/TO/la-dev-codex-plugins/activate.sh
codex-perform catalogue
```

The script must be sourced, not executed. The default standalone command produces the same repository catalogue as the in-chat action.

The default output, `.codex/toolkit_perform_actions/action_catalogue.md`, is generated and should remain git-ignored.

## 8. Add CI when the repository has a remote

For a Python project, follow [Add Python CI](project_setup_python.md#10-add-python-ci) after completing the Python setup instead of copying the generic installation step below. That workflow recreates the locked development environment, including its pinned pre-commit installation, and runs the same manual-stage checks through `uv`.

CI should run the same non-mutating complete check used locally. For a non-GitHub remote, configure that remote's CI service to run:

```bash
pre-commit run --all-files --hook-stage manual
```

### If the project uses a GitHub remote

Create `.github/workflows/checks.yml`:

```yaml
name: Checks

on:
  pull_request:
  push:
    branches: ["**"]

permissions:
  contents: read

jobs:
  pre-commit:
    runs-on: ubuntu-latest
    steps:
      - name: Check out repository
        uses: actions/checkout@v6
      - name: Install pre-commit
        run: python3 -m pip install pre-commit==4.6.0
      - name: Run non-mutating checks
        run: pre-commit run --all-files --hook-stage manual --show-diff-on-failure
```

Replace the installation step with the project's locked environment once one exists. Grant extra workflow permissions only to the job that needs them.

## 9. Create `RELEASE.md` for versioned projects

For versioned projects, create root `RELEASE.md` during repository setup even when no release exists yet; this is part of complete setup, not a task to postpone until publication. The `publish-release` Perform action reads this exact filename. Creating the runbook does not authorize a version change, tag, GitHub release, or package upload. Settle release destinations, assets, and automation separately; private repositories and projects without PyPI can still use a lightweight manual GitHub release. For a uv-based Python package, the [full manual GitHub template](https://github.com/pallgeuer/la-dev-codex-plugins/blob/main/docs/project_setup_python.md#manual-github-releases-without-pypi) in the Python setup guide provides an annotated-tag, wheel/sdist, and checksum procedure without a deployment workflow. Other languages should supply equivalent concrete validation/build commands. Keep the two explicit version/publication approvals from the ordered procedure below.

Setup acceptance must verify that RELEASE.md exists when this model is selected, its paths/commands are real and contain no unresolved template placeholders, and CHANGELOG.md already contains Release diffs. For an untagged repository, verify the TODO/examples are clearly labeled. For a tagged repository, require real version links. Validate document structure and command availability without executing any release operation as a setup test.

Write commands for the actual repository; do not leave a generic checklist that requires the releaser to invent paths or publication steps. Use these headings in order:

1. **Release model and sources of truth:** Version file, tag format, changelog, build configuration, release destinations, and whether publication is automated.
2. **Prerequisites:** Required branch, clean-worktree rule, credentials, CLI authentication, and protected-environment access.
3. **Inspect changes and choose the version:** Compare with the previous tag. Codex or the releaser proposes the exact semantic version, then obtains explicit user confirmation before editing version metadata.
4. **Prepare release metadata:** Update every version declaration, finalize `CHANGELOG.md`, review user documentation, and regenerate any tracked derived files. Make rewriting and compacting the completed `Unreleased` changelog a mandatory, explicit checkpoint rather than an incidental part of moving its entries into the new version section. Require the releaser to rewrite the version's changelog entries compactly for external users, consolidate overlapping entries around final shipped outcomes, retain all material features, fixes, compatibility changes, and migrations, and omit implementation churn, superseded intermediate behavior, test-only work, and stale changes to code that no longer exists. Remove empty change categories, preserve horizontal rules between top-level changelog sections, and make the version section suitable for use as release notes. Instruct the releaser to review the rewritten section against the complete release diff, explicitly verify that this compaction is complete and accurate, and stop without continuing to checks, commits, tags, or publication until that verification succeeds.
   Update Release diffs in the release commit: remove any pre-tag TODO/examples, compare Unreleased from the new approved tag to HEAD, add the new version's comparison (or the first version's release link), preserve older links, and verify the newly introduced URLs after tagging/publication.
5. **Run checks and build artifacts:** Use the same locked full checks as CI, inspect artifact contents, and smoke-test installed artifacts.
6. **Commit, push, and wait for CI:** Record the exact release commit and require the corresponding CI run to succeed.
7. **Create the immutable tag:** Create and push an annotated tag on the verified commit. Never move a published tag.
8. **Run a nonpublishing preflight:** Exercise the real build and validation pipeline against the tag without publishing.
9. **Approve publication:** Summarize the exact version, tag, commit, artifacts, destinations, and pipeline. Obtain a second explicit user confirmation before creating a release or running an upload that triggers publication.
10. **Publish and handle manual approval:** State which command or event triggers publication. When a protected deployment needs human approval, show the exact run to approve and stop until the user responds.
11. **Verify every public surface:** Check the release, artifact index, installed version, checksums or signatures, documentation, and final repository state.
12. **Recover safely:** Cover failure before tagging, after tagging but before publication, partial publication, lost responses, and defective immutable artifacts.

Mention the bundled action near the beginning:

```markdown
Run `$toolkit:perform publish-release` to execute this runbook. The action must stop for the exact-version confirmation, the final publication confirmation, and any protected-environment approval required below.
```

Language-specific setup should extend the build, publication, verification, and recovery sections without changing these checkpoints.

## 10. Optionally add a Zensical documentation site

Skip this section when the repository does not need a published documentation site. A typical layout is:

```text
docs_site/                         # Hand-authored site pages
docs/public/                       # Published specifications
docs/devel/                        # Internal development documents
tools/docs/generate_zensical.py    # Project-specific generator, when Python is used
zensical.template.toml             # Tracked authored configuration
.generated/                        # Git-ignored generated input tree
zensical.generated.toml            # Git-ignored generated configuration
site/                              # Git-ignored built site
```

The generator may be written in Python or any other project-appropriate language and may live at another clearly documented path. Keep authored and generated files separate. Run generation before `zensical build --strict`; do not run them in parallel. Add a GitHub Pages workflow only when the project uses a GitHub remote and wants Pages deployment.

When the project has a generated Zensical input tree, add this conditional instruction to `AGENTS.md` and replace the placeholder with the exact project command:

```markdown
- Do not run `<DOCUMENT-GENERATION-COMMAND>` and `zensical build` in parallel; the build reads the generated tree that the generator refreshes.
```

## 11. Verify the setup

Run the manual pre-commit stage, inspect the complete diff, and check that git-ignored scratch/generated files are not staged:

```bash
pre-commit run --all-files --hook-stage manual
git diff --check
git status --short --ignored
```

Audit the result without edits:

```text
$toolkit:perform audit-project-setup[agnostic]
```

For Python, continue with [Python project setup](project_setup_python.md). Otherwise continue with [AI-supported repository development](https://github.com/pallgeuer/la-dev-codex-plugins/blob/main/docs/ai_supported_development.md).

## Completion and deferred work

Before handoff, verify the required files and real commands, template fidelity, normal cache access, installed hook types, and applicable tests/CI for the exact commit. For versioned projects, require Release diffs and a concrete release runbook. Summarize every remaining task with its reason and resumption condition, including cleanup of docs/devel/plans. Remove only clearly obsolete temporary artifacts created for this setup; preserve the tracked placeholder, protected reports, useful handoffs, and uncertain/user-created material. Record removals and retained cleanup items in the journal and final response. See the [entry recipe](https://github.com/pallgeuer/la-dev-codex-plugins/blob/main/docs/new_repo_recipe.md#6-finish-and-summarize-deferred-work).
