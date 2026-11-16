# Published discovery channels

This document is the cross-plugin source of truth for publishing and maintaining this repository's plugins through external discovery channels. Plugin-specific artifacts, listing copy, test cases, validation evidence, and submitted pull-request text belong in the [Loupe dossier](loupe.md) and [Perform dossier](perform.md).

Channel rules and user interfaces can change. Re-read each channel's authoritative instructions immediately before a submission, update, comment, or pull request. Keep each plugin independently installable and independently tracked; success or delay in one channel must not be treated as the status of another.

## Current status

| Channel                          | Loupe                                                                                                               | Perform                                                                                      | Waiting for                                                            | Last checked |
|----------------------------------|---------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------|------------------------------------------------------------------------|--------------|
| Official OpenAI plugin directory | `0.2.5` approved, published, and discoverable                                                                       | `0.4.5` not approved for the public directory: `plugins_6abd7373e7c48191881e21ff87014f38`    | No review pending; reply to the decision email if an appeal is desired | 2026-10-19   |
| Codex Plugin Marketplace         | `0.2.5` published: `https://www.codex-marketplace.com/plugins/la-review`                                            | `0.4.5` published: `https://www.codex-marketplace.com/plugins/toolkit`                       | Both direct pages reverified; Browse indexing not rechecked            | 2026-10-31   |
| Hashgraph Awesome Codex Plugins  | HOL proposal [#599](https://github.com/hashgraph-online/awesome-codex-plugins/pull/599) open; owner response posted | Same combined proposal; owner response posted                                                | Reconcile generator PRs #597/#586/#624; independent acceptance         | 2026-10-31   |
| OpenAI Community Plugins         | PR [#25](https://github.com/openai/community-plugins/pull/25) open; `0.2.6` plugin CI passed                        | PR [#26](https://github.com/openai/community-plugins/pull/26) open; `0.4.6` plugin CI passed | CDE review and disposition of unrelated dependency-audit failures      | 2026-10-31   |

The Codex Plugin Marketplace is an independent curated marketplace and is not the official OpenAI plugin directory. The OpenAI Community Plugins repository is also a separate Git-backed marketplace; inclusion there does not publish a plugin to OpenAI's universal directory.

The post-acceptance verification and coordinated Loupe/Perform source release are tracked in [Coordinated release after community acceptance](community_acceptance_followup.md). That checklist starts after Loupe merges and waits for Perform to merge before a source release; remove it after the recorded work is complete.

The current Loupe contribution is an initial pre-merge review revision, not an update to a merged community listing. Its proposed `0.2.6` package can temporarily lead the `0.2.5` source release; the coordinated release checklist reconciles the accepted package before other published channels are updated.

## Published release baseline

The current release prepared for complete plugin publication is repository release `0.5.5`, annotated tag `v0.5.5`, and release commit `50186b266ec6eaade6a39e1cec120f0984216a3a`.

| Plugin  | Plugin ID   | Published version | Immutable source                                                                  | Dossier                  |
|---------|-------------|-------------------|-----------------------------------------------------------------------------------|--------------------------|
| Loupe   | `la-review` | `0.2.5`           | `https://github.com/pallgeuer/la-dev-codex-plugins/tree/v0.5.5/plugins/la-review` | [loupe.md](loupe.md)     |
| Perform | `toolkit`   | `0.4.5`           | `https://github.com/pallgeuer/la-dev-codex-plugins/tree/v0.5.5/plugins/toolkit`   | [perform.md](perform.md) |

Both release archives were reproduced byte-for-byte, extracted into clean directories, compared with the tagged plugin trees, and exercised through plugin-specific smoke tests. The dossiers record the archive names, SHA-256 digests, complete file lists, portal copy, test cases, and validation details.

The first coordinated publication run used repository release `0.5.4`, annotated tag `v0.5.4`, and release commit `5e6c30b27f4be9acccb1fa4cc8d104e2681b3b03`. Those packages remain the immutable sources for the initial Codex Plugin Marketplace submissions and the pending OpenAI Community Plugins contributions. Release `0.5.5` advances Loupe to `0.2.5` and Perform to `0.4.5` with the preferred descriptions and user-facing starter prompts; it is now live on the Codex Plugin Marketplace and prepared for the official OpenAI directory.

## Steps taken for the initial publication

### Official OpenAI plugin directory

The [OpenAI submission guide](https://developers.openai.com/plugins/deploy/submission) changed on 2026-09-30 to match a new ZIP-first publisher portal. **Upload new or existing plugin** now accepts a complete package, imports its manifest metadata and skills, runs automated checks, accepts the resulting draft for review, and leaves publication as an explicit action after approval. Skills-only packages do not require an MCP server, MCP test cases, or a demo recording. The five positive cases, three negative cases, video, MCP connection, domain verification, and tool scan documented by the portal apply to plugins with remote MCP connections.

The initial preparation and blocked attempt on 2026-09-29 proceeded as follows for both plugins:

1. Prepared and verified a complete skills-only plugin ZIP containing `.codex-plugin/plugin.json`, the declared `skills/` tree, package documentation, license, security policy, and branding.
2. Prepared listing fields, starter prompts, optional skills-only test material, release notes, and public policy/support URLs in the plugin dossier.
3. Opened the signed-in publisher portal under the verified individual identity `Philipp Allgeuer`.
4. Found that **Create plugin** exposed only **With MCP**. That flow required an MCP server at final validation even when its Skills tab accepted uploaded skill bundles.
5. Stopped rather than adding a dummy MCP server or uploading a partial standalone-skill package in place of the complete plugin.
6. Submitted an OpenAI Support ticket describing the missing documented **Skills only** route.

On 2026-09-30, the portal replaced that form with the documented complete-package upload flow, resolving the blocker. Repository release `0.5.5` then produced `la-review-0.2.5.zip` and `toolkit-0.4.5.zip` with the preferred imported metadata. Each archive contains exactly one plugin root, an accepted `.codex-plugin/plugin.json` compatibility manifest, one declared skill tree, required square SVG branding, and no MCP configuration. The newer portable root `plugin.json` format is recommended for newly authored packages but is not required for these compatibility packages.

Loupe `0.2.5` was uploaded from the verified archive, passed the package checks with one reviewed non-blocking warning about its accurate optional Claude capability disclosure, and was submitted for review on 2026-09-30. OpenAI approved it, the publisher explicitly published it, and its directory availability was confirmed at `https://chatgpt.com/plugins?search=loupe`. Its portal identity is `plugins_6abd26efa26c8191bfe2f781bdde6ec2`, available to the authenticated publisher at `https://platform.openai.com/plugins/manage/plugins_6abd26efa26c8191bfe2f781bdde6ec2`.

Perform `0.4.5` was uploaded independently from the verified `toolkit-0.4.5.zip`. Its metadata and one bundled skill completed automated checks without issues, and the draft was submitted for review on 2026-09-30. Its portal identity is `plugins_6abd7373e7c48191881e21ff87014f38`, available to the authenticated publisher at `https://platform.openai.com/plugins/manage/plugins_6abd7373e7c48191881e21ff87014f38`. OpenAI subsequently emailed that the submission **was not approved for inclusion in the public directory at this time**. The stated reason was the directory's current focus on plugins with specialized capabilities and connected ChatGPT experiences while broader support for sharing and discovering skills is still being developed. The email offered an appeal by direct reply if the publisher has questions or believes the decision was an error. No appeal or revised official-directory submission is recorded. The decision email's date was not provided; the outcome was recorded on 2026-10-19.

### Codex Plugin Marketplace

The [marketplace documentation](https://www.codex-marketplace.com/docs) accepts a repository or direct tree URL and sends signed-in submissions through automated review before publication.

The plugins were submitted independently at `https://www.codex-marketplace.com/submit` using their immutable release-tree URLs:

| Plugin  | Submitted source                                                                  | Submission ID                          | Submitted                  | Automated result                                                  | Public listing                                        |
|---------|-----------------------------------------------------------------------------------|----------------------------------------|----------------------------|-------------------------------------------------------------------|-------------------------------------------------------|
| Loupe   | `https://github.com/pallgeuer/la-dev-codex-plugins/tree/v0.5.4/plugins/la-review` | `18247881-7092-45da-921b-47841d9f0ee4` | 2026-09-29 15:36 displayed | Personal owner match; repository and plugin approved; no findings | `https://www.codex-marketplace.com/plugins/la-review` |
| Perform | `https://github.com/pallgeuer/la-dev-codex-plugins/tree/v0.5.4/plugins/toolkit`   | `828e9134-a244-4a8a-bea2-dd5f3e6e6675` | 2026-09-29 15:43 displayed | Personal owner match; repository and plugin approved; clean scan  | `https://www.codex-marketplace.com/plugins/toolkit`   |

The public pages were subsequently verified to display Loupe `0.2.4` and Perform `0.4.4`, publisher `Philipp Allgeuer`, their intended descriptions, and these install commands:

```bash
npx codex-marketplace add pallgeuer/la-dev-codex-plugins/plugins/la-review --plugin
npx codex-marketplace add pallgeuer/la-dev-codex-plugins/plugins/toolkit --plugin
```

The direct pages were live when checked, but neither entry appeared in the general `/plugins` response yet. Treat that as browse/search indexing lag, not as an unpublished listing.

On 2026-09-30, the `v0.5.5` release changed both plugin manifests while the public pages remained at their originally submitted versions. The signed-in submission interface exposed no separate update or rescan control. Submitting each new immutable release-tree URL as type **PLUGIN** rescanned and updated the existing slug rather than creating a duplicate listing:

| Plugin  | Updated source                                                                    | Submission ID                          | Authentication       | Verified public result |
|---------|-----------------------------------------------------------------------------------|----------------------------------------|----------------------|------------------------|
| Loupe   | `https://github.com/pallgeuer/la-dev-codex-plugins/tree/v0.5.5/plugins/la-review` | `e33bdbf6-d3e5-40c8-81b7-05ec895610a8` | Personal owner match | `la-review` `0.2.5`    |
| Perform | `https://github.com/pallgeuer/la-dev-codex-plugins/tree/v0.5.5/plugins/toolkit`   | `6f7d98ba-8508-48b5-b431-8e788e4a11b5` | Personal owner match | `toolkit` `0.4.5`      |

Both direct pages immediately displayed the new version and intended long description. Perform displayed an updated date of 2026-09-30; Loupe retained its original displayed update date despite serving the new version and description. The unpinned install commands resolved the `main` branch packages and retrieved manifests for `0.2.5` and `0.4.5`. Neither plugin appeared in the general `/plugins` response when rechecked, so Browse/search discovery remains an independent indexing state.

### Hashgraph Awesome Codex Plugins

The [contribution guide](https://github.com/hashgraph-online/awesome-codex-plugins/blob/main/CONTRIBUTING.md) permits separate README entries for separately named nested plugins, each linking to the repository root. [PR #585](https://github.com/hashgraph-online/awesome-codex-plugins/pull/585) merged that clarification on 2026-10-27, resolving the question raised in [issue #430](https://github.com/hashgraph-online/awesome-codex-plugins/issues/430).

HOL opened the combined Loupe/Perform [proposal #599](https://github.com/hashgraph-online/awesome-codex-plugins/pull/599). The source owner [confirmed the names, descriptions, independent package paths, and current-main source](https://github.com/hashgraph-online/awesome-codex-plugins/pull/599#issuecomment-6542661494) on 2026-10-31. The checked source was `61bbb45a0875279b97aa916e9e2a5a5230b243b6`, declaring Loupe `0.2.5` and Perform `0.4.5` with unreleased changes beyond `v0.5.5`. Record the source commit alongside manifest versions because root links fetch the default branch.

As checked on 2026-10-31, #599 remained open without reviews. Acceptance depends on reconciliation and independent review of the overlapping generator PRs [#597](https://github.com/hashgraph-online/awesome-codex-plugins/pull/597) and [#586](https://github.com/hashgraph-online/awesome-codex-plugins/pull/586), plus the dark-logo correction [#624](https://github.com/hashgraph-online/awesome-codex-plugins/pull/624). The latter preserves declared `interface.logoDark` assets and is stacked on #597's safe path handling; retain that dependency when merging.

Patched bundles matched the source inventories and installed separately with passing offline helper checks. The [centralized scanner run](https://github.com/hashgraph-online/awesome-codex-plugins/actions/runs/41169480616) passed the contribution gate; remaining findings concern repository automation, the intentional absence of a dependency lockfile, and screenshot advisories. Deep skill scanners were unavailable. Final acceptance still requires retesting complete installed bundles on the reconciled generator and independent security review, including provider-backed invocation.

Next: track the three generator PRs, verify both independent package paths and declared assets on the final head, and await maintainer review. Source-owner confirmation of listing copy does not establish complete bundle acceptance.

### OpenAI Community Plugins

The [contribution guide](https://github.com/openai/community-plugins/blob/main/CONTRIBUTING.md) requires the plugin package, catalogue entry, package-local documentation, tests, a root `test:<plugin-name>` suite, a single plugin workflow, CLA verification, and CDE code-owner approval.

The following steps were completed:

1. Prepared two isolated contributions from upstream commit `62844ca1cd865b76c7fed7180fc1ffef16e9167b`, one plugin per branch and pull request.
2. Copied each plugin tree byte-for-byte from tag `v0.5.4` and added only its matching catalogue entry, root test command, focused tests, and single-job workflow.
3. Passed `npm run validate:marketplace`, each five-test plugin suite, and `npm run validate` for both contributions.
4. Ran the complete marketplace dispatcher as far as the local managed sandbox allowed. Its pre-existing Autodesk Fusion storage test rejected the sandbox's service-owned `/` ancestry; this limitation was disclosed in each PR body and clean-host CI remains authoritative.
5. Created the contributor fork `https://github.com/pallgeuer/community-plugins`.
6. Published and verified the independent branches and opened the pull requests:

| Plugin  | Branch                | Initial commit                             | Pull request                                          | Initial result                                |
|---------|-----------------------|--------------------------------------------|-------------------------------------------------------|-----------------------------------------------|
| Loupe   | `add-la-review`       | `1c4e575d48b479c8240cf9d772af2555e9ab0949` | `https://github.com/openai/community-plugins/pull/25` | Open; CLA passed; review required; no reviews |
| Perform | `add-perform-toolkit` | `bbab6f73a1215efcc03e53cdb69c59224cab3676` | `https://github.com/openai/community-plugins/pull/26` | Open; CLA passed; review required; no reviews |

7. After personally reading and agreeing to the Community Plugins CLA, the contributor authorized the exact signature comment on Loupe PR #25 at `https://github.com/openai/community-plugins/pull/25#issuecomment-5892082519`. The CLA bot recorded the signature. Perform PR #26 recognized the repository-wide signature automatically, so no duplicate comment was posted.

The exact submitted PR bodies and plugin-specific source/test evidence are retained in the plugin dossiers.

The October 19 review responses added Loupe data-flow/retention documentation and offline runner coverage, and Perform action-source visibility, fail-closed selection, boundary documentation, and isolated tests. Loupe retains write-capable child reviewer modes for test-based verification; CDE assessment of that boundary remains pending. Review-response heads are Loupe `7e63c1214d59c60cfe5cd3449e7546f871ac1ad0` and Perform `cb0c0505398cfe279a0502419928c44f21f243fd`.

As checked on 2026-10-31, both PRs remained open without reviews or new maintainer feedback. Plugin E2E suites, CLA, dependency review, marketplace catalogue/dispatcher, and runner-matrix jobs passed. Workflow approval is no longer a blocker. Autodesk Fusion and ReviewOps jobs fail at unrelated dependency audits; await maintainer disposition of those checks and CDE review.

CDE follow-ups were posted on 2026-10-31: [Loupe #25](https://github.com/openai/community-plugins/pull/25#issuecomment-6542656262) and [Perform #26](https://github.com/openai/community-plugins/pull/26#issuecomment-6542657988). Await responses, then use the [coordinated release checklist](community_acceptance_followup.md) to reconcile accepted changes while preserving newer source features.

## Updating channels after a new plugin release

Perform these steps separately for every plugin whose version changed. Do not update an unchanged plugin merely because the repository or another plugin was released.

### Shared release preflight

1. Complete the repository release according to [RELEASE.md](../../RELEASE.md), including the independent plugin version bump, repository version classification, annotated tag, GitHub release, and required validation.
2. Build the complete plugin archive from the immutable release tag, not from the working tree. Reproduce it independently and record its SHA-256 digest, entries, uncompressed size, and tag in the plugin dossier.
3. Extract the archive cleanly, compare it with the tagged plugin directory, validate its package boundary and manifest, and repeat the focused smoke test from the extracted package.
4. Update the dossier's listing copy, prerequisites, prompts, tests, release notes, artifact record, and per-channel history before starting any external update.
5. Re-read each channel's current instructions. Record approvals, IDs, URLs, review state, feedback, and final public version as the work proceeds.
6. Never replace or mutate an existing tag or published archive. If review feedback requires packaged-content changes, make a new release.

### Official OpenAI plugin directory

For a plugin that has not yet been accepted:

1. Open `https://platform.openai.com/plugins`, select **Upload new or existing plugin**, and choose the verified developer identity.
2. Upload the complete released plugin ZIP. Do not upload a standalone skill ZIP and do not add dummy MCP configuration.
3. Confirm the imported plugin ID, semantic version, listing metadata, URLs, starter prompts, branding, and skill inventory in **Metadata & Skills**.
4. Wait for metadata and skill safety checks to finish. Required skill scans can take up to two hours. Copy any findings into the development workflow; if a packaged field or skill must change, fix it in source, make a new release, and upload that complete ZIP rather than editing the released archive.
5. Ignore MCP connection, domain verification, MCP test-case, and video-walkthrough instructions for these skills-only plugins. Complete only the review details and policy attestations the portal actually requires.
6. Select the draft and **Submit for review**. Record the submission or draft identity, selected version, date, and review status in the plugin dossier and status table.
7. After approval, open the approved package version and select **Publish plugin**. Verify the public directory listing, version, prompts, assets, links, and install behavior before recording it as published.

For an existing official listing:

1. Open the existing plugin in `https://platform.openai.com/plugins` and select **Upload plugin** rather than creating another plugin identity.
2. Upload the newly verified complete ZIP, including every component that should remain. Confirm that its manifest name matches the existing plugin and its semantic version matches the new release.
3. Check the selected version in **Metadata & Skills**, wait for automated checks, and resolve required findings through another source release and complete ZIP when necessary.
4. Review the imported listing information, skills, starter prompts, availability, and release notes. Skills-only updates do not need MCP review cases or a demo recording.
5. Complete applicable review details and policy attestations, then submit the package version for review. Only one review can be active for a plugin at a time.
6. Track portal status and email. Prepare any response locally and do not modify the released tag in response to review feedback.
7. After approval, explicitly publish the approved replacement from the portal. Verify the directory page, exact version, prompts, assets, public links, and install behavior.
8. Update this status table and the plugin dossier with the new version, submission ID, review result, publication date, and listing URL.

OpenAI's submission documentation states that metadata, asset, bundled-skill, and packaged MCP-configuration changes require a new complete ZIP and package version. Adding or removing skills uses the existing plugin identity. Adding an MCP server to an existing skills-only plugin is not currently supported, so include an MCP server in the initial ZIP if that capability is planned. Hosted MCP tool changes follow a separate scan process and do not apply to Loupe or Perform.

### Codex Plugin Marketplace

The marketplace documents repository and direct-tree submissions but does not expose a separate author update or rescan control. A 2026-09-30 update confirmed that a new immutable tag-tree submission for an existing plugin ID updates its existing public slug after review.

1. Ensure the new release is on the repository's default branch and the plugin manifest there reports the released plugin version.
2. Open the existing public listing and verify whether its displayed version, description, publisher, links, and install command already match the release.
3. If the listing is stale, open `https://www.codex-marketplace.com/submit`, select the same artifact type, and submit the changed plugin's direct tree URL under the new immutable release tag. For example, use `https://github.com/<owner>/<repo>/tree/vX.Y.Z/plugins/<plugin-id>` with type **PLUGIN**.
4. Do not use a reusable `main` target for release updates. Although branch tree URLs are accepted, the submission system reuses an already approved exact target; a unique immutable tag URL both preserves the reviewed source and permits a fresh scan on every release.
5. Record the new submission ID, authentication result, review result, exact tag URL, plugin version, and date. If the submission is rejected, routed to manual review, or unexpectedly creates a second identity instead of updating the existing slug, stop and contact the marketplace maintainer before taking further action.
6. After approval, verify the existing direct page shows the new version and description. Test that the unpinned install command retrieves the released manifest from the default branch.
7. Verify the general Browse/search surface separately. A current direct page can precede Browse indexing, so record that lag without treating the plugin as unpublished.

### Hashgraph Awesome Codex Plugins

The supported convention is one separately named README entry per plugin, linking to the same source repository root. Both initial entries are already proposed in #599; continue that PR instead of opening duplicate submissions.

1. Re-read the guide and inspect the current listing, generator dependencies, and contribution gate. Keep source-owner copy confirmation separate from installed-bundle/security acceptance.
2. Record the exact source commit in addition to each manifest version. Root links fetch the default branch, which can contain unreleased changes.
3. Run the currently pinned scanner against that source and both actual package boundaries. Record findings and unavailable integrations; use the current admission threshold.
4. Verify the corrected and reconciled generator preserves distinct package paths, all declared assets, skill references, and complete file inventories. Recheck the pending generator fixes before final acceptance.
5. After a source release, inspect the actual mirror rather than assuming refresh. The current sync workflow runs on catalogue-side changes or manual dispatch; a source-side release alone does not trigger it. If stale, request the documented maintainer refresh on the existing thread before opening another PR.
6. After merge/refresh, verify each upstream package, catalogue identity, install flow, and any public registry listing independently. Record missing or pending surfaces without treating them as published.

### OpenAI Community Plugins

1. Fetch the latest `openai/community-plugins` `main` and review its current `CONTRIBUTING.md`, review-and-publish checklist, package layout, tests, and workflows.
2. Create one clean update branch per changed plugin from current upstream `main`; do not reuse the initial-publication branches.
3. Replace `plugins/<plugin-id>/` with the exact tree from the new immutable release tag. Update the matching `.agents/plugins/marketplace.json` entry and preserve the plugin ID.
4. Update the plugin's focused tests, package tests, security tests, root `test:<plugin-id>` script, and single plugin workflow only as required by the new version or current upstream conventions.
5. Compare the contributed plugin directory byte-for-byte with the tagged source. Run the changed-plugin master suite, marketplace validation, general validation, and any current review-and-publish checks. Record any genuinely external or host-specific gate rather than claiming it passed.
6. Push the focused branch to the contributor fork and open one PR for that plugin. State the old and new versions, behavior/data boundaries, exact tests, artifact digest, and any intentionally external gates.
7. Confirm the CLA check recognizes the existing signature. Do not post another signature unless the bot requests one and the contributor still agrees to the current CLA.
8. Respond to review or push requested revisions only after reviewing the request. If a packaged-content change is required, release a new source version instead of changing the contribution away from its cited tag.
9. After merge, verify the upstream plugin tree, marketplace entry, version, and documented install flow, then update the status table and dossier.

## Record-keeping rules

- Distinguish **prepared**, **submitted**, **accepted into review**, **approved**, **published**, and **indexed**. These states are not interchangeable.
- Keep one record per plugin and channel with the source tag, plugin version, artifact digest, external ID or URL, submitted date, last checked date, review feedback, and next action.
- Put shared channel procedure and cross-plugin status here. Put exact plugin-specific listing copy, tests, archive inventory, validation evidence, and PR body in the relevant dossier.
- Record the public listing URL only after independently opening it and verifying the displayed plugin identity and version.
- Re-check open reviews and issues before posting. Never duplicate an existing submission or response because a local record is stale.
- Preserve released tags. Channel-specific corrections that alter plugin content require a new release, not an overwritten artifact.

Local scanner reports, file inventories, and upstream patch snapshots may be kept in the Git-ignored `docs/submissions/evidence/` and `docs/submissions/patches/` directories. These are disposable working artifacts; committed records must remain useful without them. Preserve upstream PR links, dated outcomes, blockers, and next steps in the documents.
