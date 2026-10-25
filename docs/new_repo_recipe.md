# New repository setup recipe

These instructions are for Codex, starting in an empty directory. Keep setup orchestration in this file; the other guides are concise references for people. Use this recipe when starting in an empty directory. Describe the intended repository to Codex and ask it to follow this file. Start in Plan mode with high or xhigh reasoning when available. Plan mode is read-only: create files only after the implementation plan is agreed and execution is enabled.

This recipe orders the complete setup; the linked guides contain its required templates and commands. Follow every applicable requirement rather than treating the templates as inspiration. Make exceptions only for explicit user decisions or stated applicability conditions, and record their reasons. Existing repositories should preserve working files and decisions instead of blindly replacing them.

## 1. Agree on the intended result

Ask the user for a brief covering purpose, users, eventual capabilities/content, immediate setup scope, and work to defer. Read supplied notes first, distinguishing historical ideas from current requirements. Interview until consequential uncertainties are resolved.

Settle the project/distribution/import/CLI names, initial version, remote owner/name/visibility, license and attribution, runtime/platform compatibility, installation scope, and release model. Licensing and visibility are separate decisions; private repositories may still require a license. Do not invent scientific functionality, a CLI, migration, or publication scope merely to fill a template.

Use the guide's solo direct-main workflow and minimal automation unless the user explicitly chooses otherwise. Explain review/branch-protection, action tags versus reviewed SHAs, and manual versus automated dependency updates when relevant. For a versioned Python/GitHub project, prepare the manual annotated-tag release runbook with validated wheel/sdist/checksum assets; an explicitly chosen alternative needs a concrete runbook too. PyPI and hosted documentation require their own decisions. Writing a runbook is not permission to release.

Ask as many questions as needed. An unanswered, timed-out, skipped, dismissed, or automatically resolved question is not consent; recommended/preselected choices are not answers. Stop dependent work until an explicit answer arrives while continuing independent investigation. Preserve earlier authorization; do not ask again about the same already approved action.

## 2. Inspect and persist the implementation roadmap

Inspect existing/nested Git repositories, identity, instruction files, Codex home/version/settings, installed plugins, required tools, host compatibility, and authentication. Resolve discoverable facts before questioning the user. Preserve existing environments, user settings, and files.

At the first authorized implementation step, create `docs/devel/plans/repository_setup.md`. Record checkpoints, completed/pending tasks, decisions/approvals, discoveries, blockers, commands/results, and exact next actions. Maintain a precise deferred-work table: item, reason, and condition for resuming. Update it after checkpoints and before every restart or turn end. Keep scientific/product backlogs separate from this operational journal.

Inventory the actual executable paths/versions before dependent commands. Plugins can use an existing supported system Python; the project's modern Python/dev-tool environment is a separate choice. Check Codex/Python/Bash/Git/jq as required by the selected plugins, GitHub CLI for a GitHub remote, and local uv for a uv-based project. Use maintained [Git](https://git-scm.com/downloads), [jq](https://jqlang.org/download/), [GitHub CLI](https://github.com/cli/cli/blob/trunk/docs/install_linux.md), and [uv](https://docs.astral.sh/uv/getting-started/installation/) instructions when tools are missing. Distinguish OS packages, standalone installers, project dependencies, and plugins. Do not replace system Python, alter unrelated environments, or edit shell profiles without explicit authorization; verify any PATH refresh in the actual session.

For GitHub, check `gh --version`, `gh auth status --hostname github.com`, and `gh api user --jq .login`. If needed, have the user complete `gh auth login --hostname github.com --web` in their own terminal, selecting the agreed Git protocol. Git SSH success does not establish API authentication; preserve working keys rather than uploading new ones automatically. Never ask for passwords/tokens in chat. If administrator authentication is needed, prepare the exact reviewed command, save the journal, end the turn for the user's action, and verify its result after they respond. For older tools, check capabilities and preserve provider signature/fingerprint verification through a compatible isolated procedure; never skip trust checks or modify a personal keyring as a workaround.

Initialize Git when needed using the agreed branch and identity. Commit only the plans placeholder with these ignore rules:

```gitignore
/docs/devel/plans/*
!/docs/devel/plans/.gitkeep
```

Create `.gitkeep` and stage it explicitly; use `git add -f docs/devel/plans/.gitkeep` if required by inherited ignores. Keep plans and feedback reports local unless the user explicitly chooses otherwise. Never force-add the whole directory.

## 3. Finish Codex setup first

Follow [Marketplace plugin installation](installation.md) and [Recommended Codex setup](recommended_setup.md). Perform installation and CLI state checks now, but defer the installation guide's restart/smoke-test step until all configuration and instruction work below is ready for section 4. Inventory/install only the prerequisites actually required by the selected plugins/project, using maintained provider instructions and approval for system/global changes. Verify executable paths, host compatibility, and any PATH refresh. Do not ask for passwords/tokens in chat; save a resumable handoff if the user must complete authentication or administrator work in their terminal.

Pull repository `.codex/config.toml` and both applicable `AGENTS.md` templates forward from [Language-agnostic project setup](project_setup_agnostic.md) and [Python project setup](project_setup_python.md). Agree on their real commands/conventions before implementation; record not-yet-run command status in the journal, not permanent instructions. Inspect project trust. Include `~/.cache/pre-commit` in user-level and repository-level writable roots along with all required cache/tool paths; repository lists replace rather than extend the user list. Show exact sensitive-file diffs and obtain explicit authorization before writing them, preserving unrelated/stronger settings.

Inspect existing user instructions/config/rules before proposing changes. Show exact diffs, preserve stronger instructions, model choices, and unrelated settings, and obtain explicit approval before writing newly proposed user-level changes. Existing approval for the same exact change remains valid. If project trust is missing, show the resolved repository path and exact trust-entry diff; do not infer trust from matching settings or parseable TOML.

If a normal cache path is missing or read-only in the managed environment, stop and notify the user, then obtain the execution permission needed to initialize/use that normal cache. Do not use UV_CACHE_DIR, a temporary cache, or sandbox weakening to bypass the problem. Declaring a writable root and initializing its directory are separate facts.

**Reuse the AGENTS.md templates verbatim.** Start with the agnostic literal template and merge every applicable language-template point, combining headings without rewriting bullets. Substitute placeholders with agreed values. Do not paraphrase, shorten, combine, summarize, or stylistically rewrite points merely because equivalent wording seems clearer. Keep every applicable point. Make only the smallest targeted edits required by an explicit contradictory user decision; omit a point only when such a decision or a guide applicability condition permits it. Record each deviation and reason. Ask about uncertain conflicts rather than silently resolving them.

Create permanent instructions from the outset: stable purpose, current layout, concrete commands, and ongoing rules. Keep setup status, restart instructions, historical approvals, bootstrap caveats, and deferred setup tasks in the journal. Additional permanent rules must express real ongoing project requirements, not setup commentary. Compare the resulting file item by item with both templates before activation, accounting for each literal point, substitution, and justified deviation.

## 4. End the turn for activation

When applicable plugin/config/instruction setup is complete, save the journal and explain what needs reloading. End the turn and ask the user to restart the Codex host through their normal launch mode and resume the chat. Include the session-specific resume command when available and a fresh-chat handoff from the journal. Do not introduce `--no-daemon` as a generic precaution; inspect supported daemon/app restart controls if the host itself is stale.

If plugin content appears stale, verify the tracked marketplace ref and actual loaded files. Main-tracking installations can pick up changes after they merge into main; a pushed PR branch is insufficient, and pinned refs remain pinned. Restarting may refresh installed plugins but does not guarantee it. Use `codex plugin marketplace upgrade la-dev-codex-plugins` to refresh explicitly, then restart and verify. If still stale, follow the installation guide's reinstall steps for the selected plugins. Do not change versions, refs, or the user's launch mode merely as a precaution.

After resume, verify loaded instructions, project trust/effective config with `/debug-config` and `/status`, and the installation guide's non-destructive skill checks. Explicit-only skills may be absent from implicit discovery: use autocomplete or explicit invocation. Do not launch a Loupe review just to verify autocomplete. Reading installed files or seeing parseable config is not proof of activation. Diagnose failures, then use a fresh chat with the journal if resume remains stale. Do not continue dependent implementation until activation succeeds.

## 5. Complete the repository and verify it

Complete the remaining agnostic and applicable language guide requirements. Add editor/line-ending/secret-file hygiene and the 5 MiB enforced-file hook, preserving non-mutating manual/pre-push/CI stages. For Python, lock and actually sync the environment on the host, keep the pytest extra and xdist configured from the start, and use serial runs when useful. Configure runtime-package branch coverage by default, missing-code reporting, no percentage gate, and HTML/XML on demand; installing pytest-cov alone is incomplete. Enable guarded-CWD behavior only when tests warrant it.

Verify the actual locked environment installs on the host, not only that its dependencies resolve. Diagnose interpreter/architecture/glibc wheel compatibility and native transitive builds. A Rust-backed dependency such as LibCST can require a compiler on an older host; use [Rustup's instructions](https://rust-lang.github.io/rustup/installation/) only when needed and obtain approval before installation. Do not downgrade outside a parent's declared constraints to avoid a build. Keep approved PATH changes command-local unless profile edits were authorized, and record the concrete dependency chain, error, and resolution.

Keep the documented bare `--cov` followed by another option; a trailing bare flag can consume a positional path, while pytest-cov 7.1.0 passed `--cov=` as an empty package and warned. Do not suppress that warning or silently change the package scope/gate.

Create CHANGELOG.md with Release diffs before the first commit. In an untagged repository, keep the explicit TODO and fenced non-live v0.1.0/v0.2.0 examples; first-release preparation replaces them with real links. Do not invent a v0.0.0 tag or rewrite existing history. For versioned projects, create root RELEASE.md during setup using the [full template below](#release-runbook-template), fill every project placeholder, and verify actual commands and the separate exact-version/publication approval handoffs. Do not execute release commands as setup tests.

For distributable packages, build and inspect both archive formats and independently install/smoke-test each outside the checkout. Exclude local/agent state, including the plans directory and its placeholder. Verify mechanical formatter changes preserve structured metadata; locked dependencies do not alone guarantee host compatibility or byte-identical artifacts.

Verify the authenticated GitHub API identity and remote-name availability separately from Git transport credentials. Create the agreed remote empty: no generated competing README/license commit. Preserve an unexpected existing repository and ask before changing its setup. Push only the checked source, require CI success for its exact commit, run the applicable Perform setup audit, and resolve findings. Recheck permanent-template fidelity after any later instruction changes.

## 6. Finish and summarize deferred work

Update the journal with final commit/CI/remote evidence, guide deviations, and every remaining task. **Summarize all deferred work in the final response**, with each item's reason and concrete resumption condition; do not hide it only in a file. Distinguish intentionally deferred product/migration/publication work from blockers to the requested setup. Explicitly state when no deferred work remains.

Include remaining `docs/devel/plans/` cleanup as a deferred item. Codex may automatically remove clearly obsolete, self-created temporary artifacts such as an applied patch preview, one-off bootstrap helper, or redundant path pointer after verifying it is no longer needed. Preserve `.gitkeep`, useful plans/journals/handoffs, user-created material, reports awaiting extraction, and anything explicitly protected or uncertain. Record the files removed; for retained cleanup, state what must happen first, such as the user extracting a feedback report. If cleanup is already complete, report it as complete rather than inventing a pending task.

Keep the journal and other useful state resumable until their purposes are finished. Summarize outcomes, checks, remaining deferrals/cleanup, and relevant links. Continue ordinary development using [AI-supported repository development](ai_supported_development.md).

## Release runbook template

For a versioned Python package hosted on GitHub, create root `RELEASE.md` during complete setup using this manual GitHub release model: one wheel, one source distribution, and a checksum manifest. Do not postpone the runbook merely because no release exists or PyPI is not selected. The two explicit approval checkpoints are mandatory. No release workflow, PyPI publisher, or protected environment is required for this model. If the user instead chooses notes/tag only, multiple packages, a prerelease policy, or automated publication, agree on and adapt that model explicitly before finalizing the runbook.

Replace every setup-time placeholder before saving the repository's RELEASE.md:

- `YOUR-ORG/YOUR-REPOSITORY`: the actual GitHub owner/repository.
- `YOUR_DEFAULT_BRANCH`: the actual release/default branch.
- `YOUR_IMPORT_PACKAGE`: the import package and its source-directory component.
- `YOUR-DISTRIBUTION-NAME`: the package-metadata distribution name, which may differ from the import package.
- `YOUR_CHECK_WORKFLOW.yml`: the filename of the actual branch-check workflow. Verify its triggers and matrix; do not invent a workflow_dispatch preflight.
- `YOUR_ARCHIVE_VALIDATION_COMMAND`: a real, complete command that checks wheel/sdist metadata and boundaries and independently installs/smoke-tests each archive outside the checkout. Implement/validate the repository-only helper or concrete equivalent before finalizing this runbook; `uv build` and `twine check` alone are insufficient. This command must require exactly one wheel and one source archive and verify their versions against the installed package. The remaining template prose's "helper" refers to that validation implementation.

The template assumes the Python guide's dev dependency group, Hatchling version source at `src/YOUR_IMPORT_PACKAGE/_version.py`, an exported `__version__`, uv tooling, and `docs/devel/plans/` ignore rules. Adapt any explicitly different project layout or tools and the exact staging list. Version values, release SHAs, and CI run IDs are facts selected or discovered during each future release, not setup-time values to hardcode. Use ordinary Bash variable binding for the exact user-approved release_version; never treat an example version as approval. Do not execute tag/push/create commands while adopting or checking the template.

Copy the following complete runbook after replacing those values:

````markdown
# Release procedure

Run `$toolkit:perform publish-release` in Default mode to follow this runbook. Creating this document does not authorize a release. Stop for explicit confirmation of the exact version before editing release metadata, then stop again for explicit publication approval after preparation, CI, tagging, and preflight. End the turn at each approval checkpoint; an unanswered question is not consent.

Run commands from the repository root in Bash. Stop on any failed check. Keep the release variables across sections; after a session restart, reconstruct and verify their values from the approved version, tag, and commit rather than guessing.

## 1. Release model and sources of truth

This repository publishes manual GitHub releases at `YOUR-ORG/YOUR-REPOSITORY` from `YOUR_DEFAULT_BRANCH`. Each release has an annotated `vX.Y.Z` tag, curated changelog notes, one wheel, one source distribution, and `SHA256SUMS`. GitHub also supplies source snapshots. There is no PyPI publication or release/deployment workflow; `.github/workflows/YOUR_CHECK_WORKFLOW.yml` validates branch commits.

`src/YOUR_IMPORT_PACKAGE/_version.py` is the single version source. `pyproject.toml` configures Hatchling's dynamic version, dependencies, and distributions; `uv.lock` records the resolved environment. `CHANGELOG.md` supplies the release date, outcomes, and comparison links. `YOUR_ARCHIVE_VALIDATION_COMMAND` inspects and independently installs both archives. This runbook is repository-only and is not needed inside a distribution.

Use ordinary GitHub releases for `X.Y.Z` versions, including `0.x` versions. A prerelease requires a separately agreed version format and GitHub status; do not silently invent that policy. Never automatically increment a version after publishing.

## 2. Prerequisites

Require Git, uv, authenticated GitHub CLI with write access to this repository, and the standard `sha256sum`, `cmp`, and `mktemp` commands. Use uv's normal cache; follow the README's host-specific build prerequisites if syncing requires them. Ignored plans/reports must remain local.

```bash
git status --short
git branch --show-current
git remote get-url origin
git fetch origin --tags
git rev-parse HEAD origin/YOUR_DEFAULT_BRANCH
gh auth status --hostname github.com
gh release list --repo YOUR-ORG/YOUR-REPOSITORY
git tag --list 'v*' --sort=-version:refname
```

Proceed only on `YOUR_DEFAULT_BRANCH`, with a clean worktree and identical HEAD/origin/YOUR_DEFAULT_BRANCH commits. Review any unexpected files or remote changes; do not discard work, force-push, or switch branches automatically. Check remote tags as well as local tags before deciding that a version is available.

## 3. Inspect changes and choose the version

Select the previous published version using the actual release/tag history, not merely the lexically largest tag. Review its complete diff through HEAD, current documentation, and `Unreleased`. For the first release, review the initial commit, subsequent history, and current tracked contents; a diff from the first commit alone omits the foundation it introduced.

Propose the exact semantic version and explain it. An initial package version such as `0.1.0` need not be incremented merely because it is being released for the first time. **Stop and obtain explicit approval of that exact version before editing metadata.** Set `release_version` to that approved value, without a `v` prefix, then initialize:

```bash
release_repo=YOUR-ORG/YOUR-REPOSITORY
release_tag="v${release_version:?Set release_version to the exact user-approved version}"
```

Confirm that neither the local/remote tag nor the GitHub release already exists. If either does exist, inspect it and use the recovery section instead of overwriting it.

## 4. Prepare release metadata

Update `_version.py` only if the approved version differs. Run `uv lock`, inspect its diff, and sync the locked environment after version/dependency metadata changes. Review compatibility and usage documentation; change claims only when supported by the release.

Rewrite and compact `Unreleased` into concise user-facing outcomes. Consolidate overlapping entries, retain material features, fixes, compatibility changes, and migrations, and omit intermediate churn, test-only work, and stale descriptions of removed code. Review the result against the complete release diff and explicitly verify its accuracy before continuing to checks, commits, tags, or publication.

Move the verified entries into `## X.Y.Z (YYYY-MM-DD)` using the approved version and actual release-preparation date. Retain `## Unreleased` with `None.` and retain horizontal rules between the introduction, `Release diffs`, Unreleased, and every released version. Omit empty change categories; keep the existing change-type/category structure for real entries.

Replace the initial `Release diffs` TODO and example fence during first-release preparation. Use real repository/version values: Unreleased links to `compare/vX.Y.Z...HEAD`; the first version links to `releases/tag/vX.Y.Z`; each later version links to `compare/vPREVIOUS...vCURRENT`. Keep previous entries newest first. Prepare these links in the release commit before creating its tag: the new tag and release URLs become resolvable at the later tagging/publication steps. Do not create a synthetic `v0.0.0` tag or leave example versions in a released changelog.

Extract only the finalized version's entries for GitHub notes, excluding Unreleased, the comparison index, and other versions:

```bash
release_notes_path=docs/devel/plans/release-notes.md
mkdir -p docs/devel/plans
git check-ignore "$release_notes_path"
awk -v heading="## ${release_version} (" '
  index($0, heading) == 1 { active = 1; next }
  active && /^## / { exit }
  active && $0 != "---" { print }
' CHANGELOG.md > "$release_notes_path"
test -s "$release_notes_path"
```

Read the extracted notes and confirm they contain the complete approved release entry. Keep the notes file ignored; never stage the plans directory.

## 5. Run checks and build artifacts

Run this validation block now and repeat it during the tagged preflight in section 8. `uv build --clear` replaces generated build output; retain no stale artifacts as release candidates.

```bash
uv sync --locked --no-default-groups --group dev
uv lock --check
uv run --no-sync python -c 'import importlib.metadata, sys, YOUR_IMPORT_PACKAGE; assert YOUR_IMPORT_PACKAGE.__version__ == importlib.metadata.version("YOUR-DISTRIBUTION-NAME") == sys.argv[1]' "$release_version"
uv run --no-sync pre-commit run --all-files --hook-stage manual --show-diff-on-failure
git diff --check
uv build --clear
uv run --no-sync twine check dist/*.whl dist/*.tar.gz
YOUR_ARCHIVE_VALIDATION_COMMAND
uv run --no-sync la-dev-release-checksums --output dist/SHA256SUMS dist/*.whl dist/*.tar.gz
(cd dist && sha256sum --check SHA256SUMS)
```

Require exactly one wheel and one source archive, matching the approved version; the helper checks archive boundaries, installed identity, and licensing. Inspect filenames and metadata as well as command success. Generate checksums only after validation, in wheel-then-sdist order. On checksum generation failure, stop; never restore an old manifest as if it described new artifacts.

## 6. Commit, push, and wait for CI

Review the release diff and stage only its intended source/metadata/documentation files. Commit and push `YOUR_DEFAULT_BRANCH` without bypassing hooks. If hooks modify files, inspect and validate those changes before completing the commit.

```bash
git status --short
git add src/YOUR_IMPORT_PACKAGE/_version.py uv.lock CHANGELOG.md README.md
git diff --cached --check
git commit -m "release: prepare ${release_tag}"
git push origin YOUR_DEFAULT_BRANCH
release_commit=$(git rev-parse HEAD)
gh run list --repo "$release_repo" --workflow YOUR_CHECK_WORKFLOW.yml --commit "$release_commit"
```

Inspect the corresponding run with `gh run view RUN_ID --repo "$release_repo"`. Require the Checks workflow to succeed for this exact commit on all configured Python versions, and verify the remote YOUR_DEFAULT_BRANCH branch matches it. Do not reuse an older successful run or tag a commit while its CI is pending.

## 7. Create the immutable tag

Recheck tag/release absence remotely and the clean checkout identity immediately before creating the tag. Create an annotated tag on the verified SHA and push that tag only:

```bash
git tag -a "$release_tag" "$release_commit" -m "Release ${release_tag}"
git push origin "refs/tags/${release_tag}"
git cat-file -t "$release_tag"
git rev-parse "${release_tag}^{commit}"
git ls-remote --tags origin "refs/tags/${release_tag}" "refs/tags/${release_tag}^{}"
```

The local object type must be `tag`; its peeled commit and the remote peeled commit must equal `release_commit`. Treat a pushed tag as immutable. Creating it is not permission to publish the GitHub release yet.

## 8. Run a nonpublishing preflight

Confirm a clean checkout and `HEAD == release_commit == release_tag^{commit}`. Repeat section 5's complete validation block against that identity. Branch CI already validates the release commit; this repository has no tag-triggered release workflow or `workflow_dispatch` publication preflight to invoke.

Retain the exact validated wheel, sdist, and manifest in `dist/`, and the reviewed notes in their ignored file. Verify artifact versions again and record their filenames and hashes. Do not rebuild or change these bytes after publication approval; changes require renewed validation and approval.

## 9. Approve publication

**Stop and end the turn for a second explicit approval.** Present the exact version, annotated tag, full commit SHA, successful CI URL, reviewed notes, artifact names/hashes, repository destination, and the command below. Explain that it creates a GitHub release and uploads the three assets, with no PyPI upload or deployment pipeline. Approval must cover this exact prepared result; it is separate from the version confirmation.

## 10. Publish and handle manual approval

After explicit approval, recheck tag identity, local checksums, reviewed notes, and release absence. Publish the retained artifacts without an implicit tag or autogenerated notes:

```bash
gh release create "$release_tag" dist/*.whl dist/*.tar.gz dist/SHA256SUMS \
  --repo "$release_repo" --verify-tag --title "$release_tag" --notes-file "$release_notes_path"
```

Asset upload and publication use separate API operations and can fail partially. Inspect state before retrying. No protected deployment approval is configured here; if a new/manual gate appears, identify the exact run or deployment, ask for the required action, and end the turn without polling until the user responds.

## 11. Verify every published surface

```bash
gh release view "$release_tag" --repo "$release_repo" --json url,tagName,isDraft,isPrerelease,body,assets
release_verify_dir=$(mktemp -d /tmp/release_verify_XXXXXX)
gh release download "$release_tag" --repo "$release_repo" --dir "$release_verify_dir" \
  --pattern '*.whl' --pattern '*.tar.gz' --pattern SHA256SUMS
cmp dist/SHA256SUMS "$release_verify_dir/SHA256SUMS"
(cd "$release_verify_dir" && sha256sum --check SHA256SUMS)
git status --short
```

Confirm a published, non-prerelease release with the exact tag, curated notes, and three expected uploaded assets; automatically generated source snapshots are separate. Recheck the remote tag SHA, released version/date, and all changelog comparison/release links. The downloaded manifest must match the retained manifest and verify the downloaded bytes, which were independently installation-tested before upload. These checksums detect byte mismatches; they are not signatures or independent proof of authorship.

Report the version, tag, commit, CI/release URLs, asset verification, and final branch/worktree state. Keep `Unreleased` available for future work. Do not bump the version again just to mark development as resumed.

## 12. Recover safely

- Before tagging: fix preparation/check failures, review and commit any corrections, push, and require fresh CI for the changed commit.
- After tagging but before publication: retain the tag and validated bytes. Resume only against that exact commit; if source corrections are needed, stop and ask for a new version rather than moving the tag.
- After an interrupted create/upload or a lost response: inspect the existing release, its draft/published status, tag, notes, and asset names/digests before retrying. Do not blindly create a second release or use an overwrite option. A matching unpublished draft may be completed only after confirming the approved bytes and scope; stop for uncertain or changed recovery decisions.
- After publication: do not silently replace published assets or rewrite the tag. A defective release needs an explicitly approved correction/new version. Preserve evidence and validated artifacts until recovery is settled.

Do not delete tags/releases, force-push, publish to another destination, or introduce release automation as an automatic recovery step.
````
