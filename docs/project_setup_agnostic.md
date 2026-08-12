# Language-agnostic project setup

Use this recipe after completing [Marketplace plugin installation](https://github.com/pallgeuer/la-dev-codex-plugins/blob/main/docs/installation.md) and [Recommended Codex setup](https://github.com/pallgeuer/la-dev-codex-plugins/blob/main/docs/recommended_setup.md). Apply it from the repository root, merge with existing files instead of overwriting them, and review `git status` before and after each section.

For a Python repository, complete this guide first and then continue with [Python project setup](project_setup_python.md). After setup, use [AI-supported repository development](https://github.com/pallgeuer/la-dev-codex-plugins/blob/main/docs/ai_supported_development.md) for the normal development loop.

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

Keep installation and the first example usable without reading the whole file. Omit `Contributing` when the project does not accept contributions. For a private repository, omit `License` unless a license or usage policy is actually needed; for a distributed or open-source project, add the appropriate `LICENSE` or `LICENSE.md`.

For a versioned project, create `CHANGELOG.md`:

```markdown
# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and the project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## Unreleased

None.
```

Replace `None.` with `Added`, `Changed`, `Fixed`, or `Removed` sections when noteworthy work lands. Add comparison links when the first release is prepared. Keep entries about shipped outcomes, not intermediate implementation churn. Separate the introduction, release diffs, `Unreleased`, and every released-version section with horizontal rules.

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

If the project publishes releases or artifacts, [create `RELEASE.md` for a released project](#9-create-releasemd-for-a-released-project). The bundled `publish-release` Perform action requires this file and follows it as the project-specific release authority.

## 2. Add development document and scratch locations

Create the durable and temporary locations:

```bash
mkdir -p docs/devel/plans
touch docs/devel/plans/.gitkeep
touch TODO.txt
```

Use `docs/devel/` for committed implementation specifications, audits, and repeatable workflows. Use `docs/devel/plans/` for temporary plans, progress journals, and AI handoff notes. Use root `TODO.txt` only as a private scratchpad; durable work belongs in an issue, test, specification, action, or changelog entry.

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
```

Then stage the placeholder explicitly:

```bash
git add docs/devel/plans/.gitkeep
```

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
]
```

The file records project defaults and enables repository-local Perform action discovery. The example permits GitHub CLI cache writes; add other narrow writable cache roots only for tools the project uses. A repository-level `writable_roots` value replaces, rather than extends, the user- or system-level list. Therefore repeat every external writable path needed while working in this repository, such as the pip and uv paths from the recommended user setup, instead of listing only the repository-specific additions. Disable live search or command network access when the repository's security requirements do not permit them.

## 5. Create a concise `AGENTS.md`

Start with this structure:

Everything outside angle brackets is reusable literal guidance. Replace every `<...>` item with project-specific content and remove any placeholder that does not apply:

```markdown
# Repository instructions

## Project layout

- <List each first-party source, test, documentation, and generated-output root.>
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
```

Replace the angle-bracketed placeholders and add exact commands as tools are configured. The ASCII-only line is a deliberate portability policy; omit it if the project intentionally uses Unicode source. Keep judgment-heavy details in focused `docs/devel/` files and link them from `AGENTS.md` with a clear trigger. Do not restate formatter or linter configuration in prose. See [AI-supported repository development](https://github.com/pallgeuer/la-dev-codex-plugins/blob/main/docs/ai_supported_development.md) for deciding whether a convention belongs in a tool, test, specification, instruction, or Perform action.

## 6. Install baseline pre-commit checks

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

## 9. Create `RELEASE.md` for a released project

Write commands for the actual repository; do not leave a generic checklist that requires the releaser to invent paths or publication steps. Use these headings in order:

1. **Release model and sources of truth:** Version file, tag format, changelog, build configuration, release destinations, and whether publication is automated.
2. **Prerequisites:** Required branch, clean-worktree rule, credentials, CLI authentication, and protected-environment access.
3. **Inspect changes and choose the version:** Compare with the previous tag. Codex or the releaser proposes the exact semantic version, then obtains explicit user confirmation before editing version metadata.
4. **Prepare release metadata:** Update every version declaration, finalize `CHANGELOG.md`, review user documentation, and regenerate any tracked derived files. Make rewriting and compacting the completed `Unreleased` changelog a mandatory, explicit checkpoint rather than an incidental part of moving its entries into the new version section. Require the releaser to rewrite the version's changelog entries compactly for external users, consolidate overlapping entries around final shipped outcomes, retain all material features, fixes, compatibility changes, and migrations, and omit implementation churn, superseded intermediate behavior, test-only work, and stale changes to code that no longer exists. Remove empty change categories, preserve horizontal rules between top-level changelog sections, and make the version section suitable for use as release notes. Instruct the releaser to review the rewritten section against the complete release diff, explicitly verify that this compaction is complete and accurate, and stop without continuing to checks, commits, tags, or publication until that verification succeeds.
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
