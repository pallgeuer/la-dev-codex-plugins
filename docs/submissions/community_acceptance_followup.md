# Coordinated release after community acceptance

This checklist begins when Loupe is merged into `openai/community-plugins`. Acceptance means the pull request is merged and the package is present on the upstream default branch; approval alone is not sufficient. Perform's review response is under review in [pull request #26](https://github.com/openai/community-plugins/pull/26). Make one source release only after both plugins are accepted. The current source baseline is repository `0.5.5`, Loupe `0.2.5`, and Perform `0.4.5`; the revised community pull requests propose Loupe `0.2.6` and Perform `0.4.6` before that source release.

## After Loupe is accepted

- [ ] Verify [Loupe pull request #25](https://github.com/openai/community-plugins/pull/25) is merged, its required checks and CDE approval were recorded, and the upstream default branch contains the intended `la-review` package, catalog entry, and working install path.
- [ ] Record the merge commit, accepted package version, date, and install verification in [Loupe's submission dossier](loupe.md) and the [shared channel status](published_channels.md). Distinguish community-marketplace inclusion from the already published official OpenAI directory listing.
- [ ] Keep the accepted package content and review feedback available for the source backport. Do not release the source repository while Perform's community contribution remains unaccepted.

## After Perform is accepted

- [ ] Verify [Perform pull request #26](https://github.com/openai/community-plugins/pull/26) is merged with required checks and CDE approval; inspect its upstream package, catalog entry, version, and install path.
- [ ] Verify the accepted Perform package still exposes selected-definition source and precedence before execution, fails closed for malformed action files and invalid variants, and preserves exact valid sibling selection.
- [ ] Record Perform's merge commit, accepted version, date, and install verification in [Perform's submission dossier](perform.md) and the shared channel status.
- [ ] Compare both accepted upstream plugin trees against the source repository's current plugin trees. Backport accepted package behavior, metadata, and documentation into their respective source plugin roots. Keep upstream-only test infrastructure in the community repository and add or adjust source pytest coverage only for behavior that changed.
- [ ] Confirm each source plugin tree matches its accepted upstream package in all intended shipped files. Explain any channel-specific differences before release. Update the source product guides and `CHANGELOG.md` under `Unreleased` for material outcomes.

## One source release

- [ ] Run the affected Loupe and Perform functional suites, compatibility checks, and the complete non-mutating pre-commit check documented in [TESTING.md](../../TESTING.md). If any shipped plugin script changed, also run the required all-files pre-commit check and applicable behavior tests. Resolve failures before starting a release.
- [ ] Follow [RELEASE.md](../../RELEASE.md) from its first step. Classify repository-only changes and both plugins independently, then obtain the runbook's explicit confirmation of the exact repository and plugin versions before editing version declarations. Loupe `0.2.6` is the proposed community version; final release versions depend on the complete accepted diff and release rules.
- [ ] Complete the release validation, annotated tag, nonpublishing package preflight, final publication approval, GitHub Release, PyPI workflow, and post-publication verification required by `RELEASE.md`. Preserve existing tags and archives.
- [ ] Build and reproduce complete Loupe and Perform ZIPs from the immutable release tag. Record each digest, file inventory, release source, and validation evidence in its submission dossier.

## Published channel follow-up

- [ ] At the release runbook's channel-update checkpoint, ask which already published channels to update for each changed plugin. Follow the user's opt-in choices and the current instructions in [Published discovery channels](published_channels.md).
- [ ] For Loupe, if an official-directory update is authorized, upload the complete new ZIP to its existing published identity, track checks and review, explicitly publish after approval, and verify the public entry.
- [ ] For Perform, account for the `0.4.5` official-directory decision declining public inclusion. Ask separately whether to appeal that decision, pursue a new submission if the current channel rules permit, or leave the directory untouched; do not treat its draft as an existing published listing.
- [ ] For each authorized Codex Plugin Marketplace update, submit the new immutable tag-tree URL, then verify the existing listing and install command.
- [ ] Compare the merged Community Plugins packages with the released source trees. If the release changes a package beyond what community maintainers accepted, prepare one focused update PR for that plugin; otherwise record the accepted upstream version without a duplicate submission.
- [ ] Update both dossiers and the shared status table with exact dates, versions, artifact digests, submission or merge IDs, approval and publication states, and verified listing URLs.

## Retire this checklist

- [ ] Once both accepted packages, the coordinated source release, and all authorized channel updates have been verified and recorded in the dossiers and shared status table, remove this temporary checklist and its links from those records. Keep any still-open submission or publication work in the relevant dossier before removing it.
