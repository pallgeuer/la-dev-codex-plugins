# New repository setup recipe

Use this recipe when starting in an empty directory. Describe the intended repository to Codex and ask it to follow this file. Start in Plan mode with high or xhigh reasoning when available. Plan mode is read-only: create files only after the implementation plan is agreed and execution is enabled.

This recipe orders the complete setup; the linked guides contain its required templates and commands. Follow every applicable requirement rather than treating the templates as inspiration. Make exceptions only for explicit user decisions or stated applicability conditions, and record their reasons. Existing repositories should preserve working files and decisions instead of blindly replacing them.

## 1. Agree on the intended result

Ask the user for a brief covering purpose, users, eventual capabilities/content, immediate setup scope, and work to defer. Read supplied notes first, distinguishing historical ideas from current requirements. Interview until consequential uncertainties are resolved.

Settle the project/distribution/import/CLI names, initial version, remote owner/name/visibility, license and attribution, runtime/platform compatibility, installation scope, and release model. Licensing and visibility are separate decisions; private repositories may still require a license. Do not invent scientific functionality, a CLI, migration, or publication scope merely to fill a template.

Use the guide's solo direct-main workflow and minimal automation unless the user explicitly chooses otherwise. Explain review/branch-protection, action tags versus reviewed SHAs, and manual versus automated dependency updates when relevant. For a versioned Python/GitHub project, prepare the manual annotated-tag release runbook with validated wheel/sdist/checksum assets; an explicitly chosen alternative needs a concrete runbook too. PyPI and hosted documentation require their own decisions. Writing a runbook is not permission to release.

Ask as many questions as needed. An unanswered, timed-out, skipped, dismissed, or automatically resolved question is not consent; recommended/preselected choices are not answers. Stop dependent work until an explicit answer arrives while continuing independent investigation. Preserve earlier authorization; do not ask again about the same already approved action.

## 2. Inspect and persist the implementation roadmap

Inspect existing/nested Git repositories, identity, instruction files, Codex home/version/settings, installed plugins, required tools, host compatibility, and authentication. Resolve discoverable facts before questioning the user. Preserve existing environments, user settings, and files.

At the first authorized implementation step, create `docs/devel/plans/repository_setup.md`. Record checkpoints, completed/pending tasks, decisions/approvals, discoveries, blockers, commands/results, and exact next actions. Maintain a precise deferred-work table: item, reason, and condition for resuming. Update it after checkpoints and before every restart or turn end. Keep scientific/product backlogs separate from this operational journal.

Initialize Git when needed using the agreed branch and identity. Commit only the plans placeholder with these ignore rules:

```gitignore
/docs/devel/plans/*
!/docs/devel/plans/.gitkeep
```

Create `.gitkeep` and stage it explicitly; use `git add -f docs/devel/plans/.gitkeep` if required by inherited ignores. Keep plans and feedback reports local unless the user explicitly chooses otherwise. Never force-add the whole directory.

## 3. Finish Codex setup first

Follow [Marketplace plugin installation](installation.md) and [Recommended Codex setup](recommended_setup.md). Inventory/install only the prerequisites actually required by the selected plugins/project, using maintained provider instructions and approval for system/global changes. Verify executable paths, host compatibility, and any PATH refresh. Do not ask for passwords/tokens in chat; save a resumable handoff if the user must complete authentication or administrator work in their terminal.

Pull repository `.codex/config.toml` and both applicable `AGENTS.md` templates forward from [Language-agnostic project setup](project_setup_agnostic.md) and [Python project setup](project_setup_python.md). Agree on their real commands/conventions before implementation; record not-yet-run command status in the journal, not permanent instructions. Inspect project trust. Include `~/.cache/pre-commit` in user-level and repository-level writable roots along with all required cache/tool paths; repository lists replace rather than extend the user list. Show exact sensitive-file diffs and obtain explicit authorization before writing them, preserving unrelated/stronger settings.

**Reuse the AGENTS.md templates verbatim.** Start with the agnostic literal template and merge every applicable language-template point, combining headings without rewriting bullets. Substitute placeholders with agreed values. Do not paraphrase, shorten, combine, summarize, or stylistically rewrite points merely because equivalent wording seems clearer. Keep every applicable point. Make only the smallest targeted edits required by an explicit contradictory user decision; omit a point only when such a decision or a guide applicability condition permits it. Record each deviation and reason. Ask about uncertain conflicts rather than silently resolving them.

Create permanent instructions from the outset: stable purpose, current layout, concrete commands, and ongoing rules. Keep setup status, restart instructions, historical approvals, bootstrap caveats, and deferred setup tasks in the journal. Additional permanent rules must express real ongoing project requirements, not setup commentary. Compare the resulting file item by item with both templates before activation, accounting for each literal point, substitution, and justified deviation.

## 4. End the turn for activation

When applicable plugin/config/instruction setup is complete, save the journal and explain what needs reloading. End the turn and ask the user to restart the Codex host through their normal launch mode and resume the chat. Include the session-specific resume command when available and a fresh-chat handoff from the journal. Do not introduce `--no-daemon` as a generic precaution; inspect supported daemon/app restart controls if the host itself is stale.

After resume, verify loaded instructions, project trust/effective config with `/debug-config` and `/status`, and the installation guide's non-destructive skill checks. Explicit-only skills may be absent from implicit discovery: use autocomplete or explicit invocation. Do not launch a Loupe review just to verify autocomplete. Reading installed files or seeing parseable config is not proof of activation. Diagnose failures, then use a fresh chat with the journal if resume remains stale. Do not continue dependent implementation until activation succeeds.

## 5. Complete the repository and verify it

Complete the remaining agnostic and applicable language guide requirements. Add editor/line-ending/secret-file hygiene and the 5 MiB enforced-file hook, preserving non-mutating manual/pre-push/CI stages. For Python, lock and actually sync the environment on the host, keep the pytest extra and xdist configured from the start, and use serial runs when useful. Configure runtime-package branch coverage by default, missing-code reporting, no percentage gate, and HTML/XML on demand; installing pytest-cov alone is incomplete. Enable guarded-CWD behavior only when tests warrant it.

Create CHANGELOG.md with Release diffs before the first commit. In an untagged repository, keep the explicit TODO and fenced non-live v0.1.0/v0.2.0 examples; first-release preparation replaces them with real links. Do not invent a v0.0.0 tag or rewrite existing history. For versioned projects, create root RELEASE.md during setup using the guide's full template, fill every project placeholder, and verify actual commands and the separate exact-version/publication approval handoffs. Do not execute release commands as setup tests.

For distributable packages, build and inspect both archive formats and independently install/smoke-test each outside the checkout. Exclude local/agent state, including the plans directory and its placeholder. Verify mechanical formatter changes preserve structured metadata; locked dependencies do not alone guarantee host compatibility or byte-identical artifacts.

Verify the authenticated GitHub API identity and remote-name availability separately from Git transport credentials. Create the agreed remote empty: no generated competing README/license commit. Preserve an unexpected existing repository and ask before changing its setup. Push only the checked source, require CI success for its exact commit, run the applicable Perform setup audit, and resolve findings. Recheck permanent-template fidelity after any later instruction changes.

## 6. Finish and summarize deferred work

Update the journal with final commit/CI/remote evidence, guide deviations, and every remaining task. **Summarize all deferred work in the final response**, with each item's reason and concrete resumption condition; do not hide it only in a file. Distinguish intentionally deferred product/migration/publication work from blockers to the requested setup. Explicitly state when no deferred work remains.

Include remaining `docs/devel/plans/` cleanup as a deferred item. Codex may automatically remove clearly obsolete, self-created temporary artifacts such as an applied patch preview, one-off bootstrap helper, or redundant path pointer after verifying it is no longer needed. Preserve `.gitkeep`, useful plans/journals/handoffs, user-created material, reports awaiting extraction, and anything explicitly protected or uncertain. Record the files removed; for retained cleanup, state what must happen first, such as the user extracting a feedback report. If cleanup is already complete, report it as complete rather than inventing a pending task.

Keep the journal and other useful state resumable until their purposes are finished. Summarize outcomes, checks, remaining deferrals/cleanup, and relevant links. Continue ordinary development using [AI-supported repository development](ai_supported_development.md).
