# Published discovery channels

This document is the cross-plugin source of truth for publishing and maintaining this repository's plugins through external discovery channels. Plugin-specific artifacts, listing copy, test cases, validation evidence, and submitted pull-request text belong in the [Loupe dossier](loupe.md) and [Perform dossier](perform.md).

Channel rules and user interfaces can change. Re-read each channel's authoritative instructions immediately before a submission, update, comment, or pull request. Keep each plugin independently installable and independently tracked; success or delay in one channel must not be treated as the status of another.

## Current status

| Channel                          | Loupe                                                                                       | Perform                                                                                     | Waiting for                                                                                   | Last checked |
|----------------------------------|---------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------|--------------|
| Official OpenAI plugin directory | Ready for ZIP-first draft creation; no draft or submission ID yet                           | Ready for ZIP-first draft creation; no draft or submission ID yet                           | Publisher decision on using the released metadata or preparing a new plugin release           | 2026-09-30   |
| Codex Plugin Marketplace         | Published: `https://www.codex-marketplace.com/plugins/la-review`                            | Published: `https://www.codex-marketplace.com/plugins/toolkit`                              | Nothing                                                                                       | 2026-09-29   |
| Hashgraph Awesome Codex Plugins  | Not submitted: multi-plugin repository convention unresolved                                | Not submitted: multi-plugin repository convention unresolved                                | Maintainer guidance in `https://github.com/hashgraph-online/awesome-codex-plugins/issues/430` | 2026-09-29   |
| OpenAI Community Plugins         | PR open; CLA passed; review required: `https://github.com/openai/community-plugins/pull/25` | PR open; CLA passed; review required: `https://github.com/openai/community-plugins/pull/26` | CDE maintainer review, any upstream-requested checks, and merge decisions                     | 2026-09-29   |

The Codex Plugin Marketplace is an independent curated marketplace and is not the official OpenAI plugin directory. The OpenAI Community Plugins repository is also a separate Git-backed marketplace; inclusion there does not publish a plugin to OpenAI's universal directory.

## Published release baseline

The first coordinated publication run used repository release `0.5.4`, annotated tag `v0.5.4`, and release commit `5e6c30b27f4be9acccb1fa4cc8d104e2681b3b03`.

| Plugin  | Plugin ID   | Published version | Immutable source                                                                  | Dossier                  |
|---------|-------------|-------------------|-----------------------------------------------------------------------------------|--------------------------|
| Loupe   | `la-review` | `0.2.4`           | `https://github.com/pallgeuer/la-dev-codex-plugins/tree/v0.5.4/plugins/la-review` | [loupe.md](loupe.md)     |
| Perform | `toolkit`   | `0.4.4`           | `https://github.com/pallgeuer/la-dev-codex-plugins/tree/v0.5.4/plugins/toolkit`   | [perform.md](perform.md) |

Both release archives were reproduced byte-for-byte, extracted into clean directories, compared with the tagged plugin trees, and exercised through plugin-specific smoke tests. The dossiers record the archive names, SHA-256 digests, complete file lists, portal copy, test cases, and validation details.

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

On 2026-09-30, the portal replaced that form with the documented complete-package upload flow, resolving the blocker. The existing `la-review-0.2.4.zip` and `toolkit-0.4.4.zip` each contain exactly one plugin root, an accepted `.codex-plugin/plugin.json` compatibility manifest, one declared skill tree, required square SVG branding, and no MCP configuration. Their recorded digests still match, so `dist/` does not need to be rebuilt merely for the portal change. The newer portable root `plugin.json` format is recommended for newly authored packages but is not required for these compatibility packages.

No official OpenAI directory draft or submission ID exists for either plugin yet. Before upload, decide whether to submit the immutable `v0.5.4` packages exactly as released or make a new release whose manifest incorporates any revised directory copy. The new portal treats package metadata as read-only and requires a corrected ZIP when it changes, so do not patch either recorded archive in place.

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

### Hashgraph Awesome Codex Plugins

The current [contribution guide](https://github.com/hashgraph-online/awesome-codex-plugins/blob/main/CONTRIBUTING.md) asks for one alphabetized repository-root link in `README.md`; a generator then mirrors the plugin bundle. This repository instead contains two independent plugin manifests below `plugins/`, so a root-only entry is ambiguous and could mirror only one package.

The following preparation was completed:

1. Ran HOL Plugin Scanner 3.9.0 against each released plugin root.
2. Recorded 96/100, grade A, with policy and verification passing and no critical, high, medium, or low findings for both plugins.
3. Confirmed issue `#430` already tracked the multi-plugin mirroring ambiguity.
4. Posted this approved question at `https://github.com/hashgraph-online/awesome-codex-plugins/issues/430#issuecomment-5891778025`:

> Hi maintainers, I am preparing two independent plugin submissions from one marketplace-shaped repository and saw this issue, which I believe would also affect me. So before opening PRs I thought maybe I could nudge this thread.
>
> My case:
>
> - Loupe Code Review (`la-review` 0.2.4): `https://github.com/pallgeuer/la-dev-codex-plugins/tree/v0.5.4/plugins/la-review`
> - Perform Action Toolkit (`toolkit` 0.4.4): `https://github.com/pallgeuer/la-dev-codex-plugins/tree/v0.5.4/plugins/toolkit`
>
> The repository root is `https://github.com/pallgeuer/la-dev-codex-plugins` and its marketplace lists both packages. A root-only mirror would be ambiguous and could select only one bundle, while these packages must remain separately installable.
>
> What is the intended way forward for our cases?
>
> Should I open two README-entry PRs that identify the direct subpaths, use the tree URLs despite the current repository-root-link rule, or follow another structure?

No Hashgraph pull request has been opened. Wait for a maintainer answer; do not create an ambiguous root-only submission.

### OpenAI Community Plugins

The [contribution guide](https://github.com/openai/community-plugins/blob/main/CONTRIBUTING.md) requires the plugin package, catalogue entry, package-local documentation, tests, a root `test:<plugin-name>` suite, a single plugin workflow, CLA verification, and CDE code-owner approval.

The following steps were completed:

1. Prepared two isolated contributions from upstream commit `62844ca1cd865b76c7fed7180fc1ffef16e9167b`, one plugin per branch and pull request.
2. Copied each plugin tree byte-for-byte from tag `v0.5.4` and added only its matching catalogue entry, root test command, focused tests, and single-job workflow.
3. Passed `npm run validate:marketplace`, each five-test plugin suite, and `npm run validate` for both contributions.
4. Ran the complete marketplace dispatcher as far as the local managed sandbox allowed. Its pre-existing Autodesk Fusion storage test rejected the sandbox's service-owned `/` ancestry; this limitation was disclosed in each PR body and clean-host CI remains authoritative.
5. Created the contributor fork `https://github.com/pallgeuer/community-plugins`.
6. Published and verified the independent branches and opened the pull requests:

| Plugin  | Branch                | Commit                                     | Pull request                                          | Current result                                |
|---------|-----------------------|--------------------------------------------|-------------------------------------------------------|-----------------------------------------------|
| Loupe   | `add-la-review`       | `1c4e575d48b479c8240cf9d772af2555e9ab0949` | `https://github.com/openai/community-plugins/pull/25` | Open; CLA passed; review required; no reviews |
| Perform | `add-perform-toolkit` | `bbab6f73a1215efcc03e53cdb69c59224cab3676` | `https://github.com/openai/community-plugins/pull/26` | Open; CLA passed; review required; no reviews |

7. After personally reading and agreeing to the Community Plugins CLA, the contributor authorized the exact signature comment on Loupe PR #25 at `https://github.com/openai/community-plugins/pull/25#issuecomment-5892082519`. The CLA bot recorded the signature. Perform PR #26 recognized the repository-wide signature automatically, so no duplicate comment was posted.

The exact submitted PR bodies and plugin-specific source/test evidence are retained in the plugin dossiers.

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

The marketplace currently documents initial repository/tree submission but does not document a separate author update workflow. Use this evidence-led procedure:

1. Ensure the new release is on the repository's default branch and the plugin manifest there reports the released plugin version.
2. Open the existing public listing and verify its displayed version, description, publisher, links, and install command against the new release.
3. If the listing refreshes from GitHub automatically, test the install command in a clean location and record the verified version/date in the dossier and status table.
4. If the listing remains stale, inspect the signed-in listing/submission UI for an update or rescan control. Use that existing-listing flow if present.
5. If no update control is documented or exposed, contact the marketplace maintainer with the existing public URL, prior submission ID, immutable new tag URL, plugin ID, and new version. Do not create a duplicate listing or resubmit blindly.
6. After the update appears, verify both the direct page and general Browse/search discovery. Treat those as separate checks.

### Hashgraph Awesome Codex Plugins

Until issue `#430` is resolved, do not submit or update either plugin through an ambiguous repository-root entry.

After maintainers document a supported multi-plugin convention:

1. Follow that convention independently for the changed plugin and retain its direct package boundary.
2. Run the scanner version and commands currently pinned by the contribution guide against the exact released package; meet the current score and severity thresholds.
3. If the plugin is not listed, fork the catalogue, add one alphabetized README entry in the correct category, and open one focused PR containing the source URL and scanner evidence. Do not commit generated mirror/catalog files.
4. If the plugin is already listed, first verify whether the generator has mirrored the new default-branch version automatically. If it has, validate the mirrored manifest/version and no PR is needed.
5. If the mirror is stale, use the current maintainer-documented refresh process. If none exists, ask on the existing PR/issue before changing the catalogue entry or opening a refresh PR.
6. Verify the generated mirror, catalogue version, install source, and public registry entry after refresh.

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
