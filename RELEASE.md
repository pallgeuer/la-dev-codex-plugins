# Releasing

This runbook describes how to make a stable release of the repository and its Codex plugin marketplace. A release consists of version updates committed to `main`, an unsigned annotated Git tag named `vX.Y.Z`, and a published GitHub Release. GitHub supplies the source archives automatically; this project does not build or publish Python packages or attach release artifacts.

Run all commands from the repository root. Replace example values such as `X.Y.Z` before executing them. Stop whenever a command fails and resolve the failure before continuing.

## 1. Check the prerequisites

The release maintainer needs:

- Push access to `pallgeuer/la-dev-codex-plugins`.
- Git, Python 3, `uvx`, ripgrep (`rg`), and the GitHub CLI (`gh`).
- A GitHub CLI session authorized to read Actions and create releases.

Check the tools and authentication:

```bash
git --version
python3 --version
uvx --version
rg --version
gh --version
gh auth status --hostname github.com
```

If necessary, authenticate before proceeding:

```bash
gh auth login
```

Record and verify the one canonical release repository. The Git remote must use either its SSH or HTTPS URL, and every GitHub CLI command below explicitly uses the same repository:

```bash
EXPECTED_REPOSITORY="pallgeuer/la-dev-codex-plugins"
ORIGIN_URL="$(git remote get-url origin)"
case "$ORIGIN_URL" in
    git@github.com:pallgeuer/la-dev-codex-plugins.git|https://github.com/pallgeuer/la-dev-codex-plugins|https://github.com/pallgeuer/la-dev-codex-plugins.git) ;;
    *) echo "origin does not identify $EXPECTED_REPOSITORY: $ORIGIN_URL" >&2; false ;;
esac
test "$(gh repo view "$EXPECTED_REPOSITORY" --json nameWithOwner --jq .nameWithOwner)" = "$EXPECTED_REPOSITORY"
```

Check that the installed GitHub CLI exposes the options used by this runbook:

```bash
GH_RUN_LIST_HELP="$(gh run list --help)"
GH_RELEASE_CREATE_HELP="$(gh release create --help)"
require_help_flag() {
    case "$1" in
        *"$2"*) ;;
        *) echo "gh does not support required option $2" >&2; return 1 ;;
    esac
}
require_help_flag "$GH_RUN_LIST_HELP" "--commit"
require_help_flag "$GH_RELEASE_CREATE_HELP" "--verify-tag"
require_help_flag "$GH_RELEASE_CREATE_HELP" "--generate-notes"
require_help_flag "$GH_RELEASE_CREATE_HELP" "--notes-start-tag"
require_help_flag "$GH_RELEASE_CREATE_HELP" "--fail-on-no-commits"
require_help_flag "$GH_RELEASE_CREATE_HELP" "--latest"
```

Stable releases are made directly from `main`. Finish and commit all intended development work first, then start from a clean, up-to-date checkout:

```bash
git switch main
git status --short --branch
git fetch origin main --tags
git pull --ff-only origin main
test -z "$(git status --porcelain)"
```

The final command must succeed. Do not release from a dirty worktree, a detached `HEAD`, or a local `main` that has diverged from `origin/main`.

## 2. Find the previous release and inspect the changes

List all stable release tags:

```bash
git tag --sort=-version:refname | rg '^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$'
```

Set `LAST_TAG` to the highest stable release shown:

```bash
LAST_TAG=vX.Y.Z
test "$(git rev-list --count "$LAST_TAG"..HEAD)" -gt 0
python3 scripts/validate_release.py baseline "$LAST_TAG"
```

The validator requires every stable tag to be annotated and reachable from `HEAD`, requires `LAST_TAG` to be the highest stable tag, verifies that the tag's version matches its repository declarations, and rejects committed development-time version bumps. Stop and reconcile the history instead of releasing if any stable tag is divergent. The other check requires at least one new commit. Review everything that changed after the tag:

```bash
git log --oneline --decorate "$LAST_TAG"..HEAD
git diff --stat "$LAST_TAG"..HEAD
git diff --name-status "$LAST_TAG"..HEAD
git diff "$LAST_TAG"..HEAD
```

Identify changed plugins independently:

```bash
for manifest in plugins/*/.codex-plugin/plugin.json; do
    plugin_dir="${manifest%/.codex-plugin/plugin.json}"
    if ! git diff --quiet "$LAST_TAG"..HEAD -- "$plugin_dir"; then
        echo "Changed plugin: ${plugin_dir#plugins/}"
    fi
done
```

Inspect each reported plugin separately:

```bash
git diff "$LAST_TAG"..HEAD -- plugins/PLUGIN_NAME
```

Any change in a plugin's runtime subtree counts as a plugin change, including its manifest, skills, agent metadata, references, assets, and scripts. Changes outside `plugins/` are repository-only unless they are accompanied by changes to a plugin subtree.

Also account manually for structural changes that the loop cannot classify:

- A newly added plugin must use the initial version `0.1.0`; do not increment it merely because this is its first release. Adding the plugin is a repository-level feature.
- Removing a plugin is a breaking repository change. There is no removed manifest to bump.
- Renaming a plugin is removal of the old identity plus addition of a new identity at `0.1.0`; do not carry the old plugin's version forward.
- Changing only marketplace policy or metadata in `.agents/plugins/marketplace.json` is a repository change, not a plugin version change.

## 3. Choose the version bumps

Classify the complete set of changes for each changed existing plugin and classify repository-only changes independently:

| Classification | Change | Component below `1.0.0` | Component at or above `1.0.0` |
| --- | --- | --- | --- |
| `fix` | Backward-compatible fix, documentation correction, or maintenance | Patch | Patch |
| `feature` | Backward-compatible functionality | Minor | Minor |
| `breaking` | Incompatible user-facing behavior, configuration, interface, or removal | Minor | Major |

For a component in initial development (`0.x.y`), a breaking change advances the minor version and resets the patch version. Moving to `1.0.0` is reserved for declaring its public interface stable.

Apply these repository rules:

- Bump every changed existing plugin independently from the version in its manifest.
- Give each changed existing plugin its highest applicable classification when it contains several kinds of changes.
- Leave every unchanged plugin version untouched.
- Classify changes outside plugin runtime subtrees according to their independent effect on the repository. Ancillary repository changes that only accompany plugin work may be classified as `none`.
- Bump the repository exactly once using the highest effective bump contributed by repository-only changes, structural plugin changes, and changed existing plugins.
- A plugin patch contributes a repository patch, and a plugin minor contributes a repository minor.
- A plugin major contributes a repository major when the repository is at or above `1.0.0`, but contributes a repository minor while the repository remains below `1.0.0`.
- Adding a plugin contributes a repository minor. Removing or renaming a plugin contributes the repository's effective breaking-change bump.

Examples:

- A plugin bug fix changes that plugin from `0.1.6` to `0.1.7` and applies a patch bump to the repository.
- A minor feature in one plugin and a patch fix in another bump those plugins by minor and patch respectively, and apply a minor bump to the repository.
- README-only corrections leave all plugin versions unchanged and apply a patch bump to the repository when those corrections are intentionally released.
- A breaking change to a `0.2.1` plugin changes it to `0.3.0` and applies a minor bump to a repository that is also below `1.0.0`.
- A breaking change to a stable plugin changes it from `1.4.2` to `2.0.0`; if the repository is `0.5.3`, its effective contribution is a repository minor bump to `0.6.0`.
- A breaking repository-only CLI change and a plugin patch apply a breaking repository bump rather than allowing the plugin patch to lower the repository bump.

Record the classifications. `REPOSITORY_CHANGE` must be `none`, `fix`, `feature`, or `breaking`. Add one `PLUGIN_CHANGES` entry for every changed existing plugin and no entry for new, removed, or unchanged plugins:

```bash
REPOSITORY_CHANGE=feature
PLUGIN_CHANGES=(
    "PLUGIN_NAME=fix"
    "ANOTHER_PLUGIN=breaking"
)
```

Record the selected repository version:

```bash
NEW_REPO_VERSION=X.Y.Z
TAG="v${NEW_REPO_VERSION}"
```

Ensure the new tag does not already exist locally or remotely:

```bash
test -z "$(git tag --list "$TAG")"
test -z "$(git ls-remote --tags origin "refs/tags/$TAG" "refs/tags/$TAG^{}")"
```

## 4. Update the version declarations

Update the repository version in all three locations:

- `setup.cfg`, in `metadata.version`.
- `src/la_dev_codex_plugins/__init__.py`, in `__version__`.
- The opening sentence of `README.md`.

Update the `"version"` in `plugins/PLUGIN_NAME/.codex-plugin/plugin.json` for every changed existing plugin. Leave unchanged plugins at their current versions. No release version is stored in `.agents/plugins/marketplace.json`.

Validate the exact release versions against the committed development changes and the classifications selected above:

```bash
RELEASE_VALIDATOR_ARGS=(versions "$LAST_TAG" --repository-change "$REPOSITORY_CHANGE")
for plugin_change in "${PLUGIN_CHANGES[@]}"; do
    RELEASE_VALIDATOR_ARGS+=(--plugin-change "$plugin_change")
done
python3 scripts/validate_release.py "${RELEASE_VALIDATOR_ARGS[@]}"
test "$(sed -n 's/^version = //p' setup.cfg)" = "$NEW_REPO_VERSION"
```

The validator infers changed, new, and removed plugins from `LAST_TAG..HEAD`. It requires an exact classification for every changed existing plugin, checks the precise SemVer result for every repository and plugin declaration, rejects bumps to unchanged plugins, and requires every new plugin identity to remain at `0.1.0`.

Review every version declaration:

```bash
rg -n '^(version =|__version__ =)|marketplace, version |"version":' setup.cfg src/la_dev_codex_plugins/__init__.py README.md plugins/*/.codex-plugin/plugin.json
```

Validate every plugin manifest:

```bash
MANIFESTS_VALID=true
for manifest in plugins/*/.codex-plugin/plugin.json; do
    python3 -m json.tool "$manifest" >/dev/null || {
        MANIFESTS_VALID=false
        break
    }
done
test "$MANIFESTS_VALID" = true
```

Review the complete release diff before running tools that may apply fixes:

```bash
git diff --check
git diff
```

## 5. Run all checks

Stage all intended release changes before the all-files checks. Pre-commit only includes files known to Git, so this also ensures that any newly added files from the release are checked:

```bash
git add --all
git status --short
```

Run the repository's auto-fixing hooks:

```bash
uvx --python 3.10 --from pre-commit==4.6.0 pre-commit run --all-files
```

If a hook changes files, inspect and stage those changes:

```bash
git diff
git add --all
```

Run the exact read-only checks used by CI:

```bash
uvx --python 3.10 --from pre-commit==4.6.0 pre-commit run --all-files --hook-stage manual
```

The manual-stage suite validates JSON, TOML, YAML, linting, formatting, typing, tests, and Python 3.6 compatibility. Run the focused release-validator and version-declaration tests as an explicit release check:

```bash
uvx --python 3.8 --from pytest==8.3.5 pytest tests/test_validate_release.py tests/test_versions.py
```

Finally, inspect the staged release snapshot:

```bash
git diff --cached --check
git diff --cached --stat
git diff --cached
git status --short
```

Confirm manually that:

- The repository version matches in `setup.cfg`, `src/la_dev_codex_plugins/__init__.py`, and `README.md`.
- Every changed existing plugin has the intended independent version.
- No unchanged plugin was bumped.
- The staged snapshot contains all intended work and no unrelated files.

## 6. Commit, push, and wait for CI

Create the release commit:

```bash
git commit -m "Release $TAG"
RELEASE_COMMIT="$(git rev-parse HEAD)"
test -z "$(git status --porcelain)"
```

Push `main`:

```bash
git push origin main
```

Wait for GitHub to register the `Checks` workflow run for this exact commit, then watch it to completion:

```bash
RUN_ID=""
RUN_DEADLINE=$((SECONDS + 300))
while test -z "$RUN_ID" && test "$SECONDS" -lt "$RUN_DEADLINE"; do
    RUN_ID="$(gh run list --repo "$EXPECTED_REPOSITORY" --workflow Checks --branch main --commit "$RELEASE_COMMIT" --event push --limit 1 --json databaseId --jq '.[0].databaseId // empty')" || break
    test -n "$RUN_ID" || sleep 5
done
if test -z "$RUN_ID"; then
    echo "Checks did not register for $RELEASE_COMMIT within five minutes, or the query failed." >&2
    gh workflow view Checks --repo "$EXPECTED_REPOSITORY"
    gh run list --repo "$EXPECTED_REPOSITORY" --workflow Checks --branch main --limit 10
    false
else
    gh run watch "$RUN_ID" --repo "$EXPECTED_REPOSITORY" --exit-status
fi
```

The registration wait is limited to five minutes so a disabled, renamed, inaccessible, or untriggered workflow cannot leave the release shell polling forever. Once the exact run appears, `gh run watch` waits without a separate time limit. If registration or CI fails, do not tag the commit. Diagnose the workflow problem or fix the failure on `main`, repeat the local checks, commit and push any required fix, update `RELEASE_COMMIT`, and wait for the new commit's workflow run.

After CI succeeds, ensure that the local checkout and remote branch still identify the verified commit:

```bash
git fetch origin main --tags
test -z "$(git status --porcelain)"
test "$(git rev-parse HEAD)" = "$RELEASE_COMMIT"
test "$(git rev-parse origin/main)" = "$RELEASE_COMMIT"
```

## 7. Create and push the annotated tag

Create an unsigned annotated tag that explicitly targets the verified release commit:

```bash
git tag --no-sign -a "$TAG" "$RELEASE_COMMIT" -m "Release $TAG"
```

Verify the tag type, annotation, and target:

```bash
test "$(git cat-file -t "$TAG")" = tag
test "$(git rev-list -n 1 "$TAG")" = "$RELEASE_COMMIT"
git show --no-patch --format=fuller "$TAG"
```

Push only the new tag:

```bash
git push origin "refs/tags/$TAG"
```

The `Checks` workflow intentionally runs on branch pushes and pull requests, not tag pushes. The release commit was already verified on `main`, so pushing its annotated tag does not create a redundant run.

Verify that the remote annotated tag peels to the release commit:

```bash
REMOTE_RELEASE_COMMIT="$(git ls-remote origin "refs/tags/$TAG^{}" | cut -f1)"
test "$REMOTE_RELEASE_COMMIT" = "$RELEASE_COMMIT"
```

## 8. Publish the GitHub Release

Create and immediately publish a stable GitHub Release. Explicitly starting the generated notes at `LAST_TAG` makes the comparison correct even if earlier tags do not have corresponding GitHub Releases:

```bash
gh release create "$TAG" \
    --repo "$EXPECTED_REPOSITORY" \
    --verify-tag \
    --generate-notes \
    --notes-start-tag "$LAST_TAG" \
    --fail-on-no-commits \
    --title "Release $TAG" \
    --latest
```

This command must use the already-pushed annotated tag; `--verify-tag` prevents GitHub CLI from silently creating a different tag.

Verify the published release:

```bash
test "$(gh release view "$TAG" --repo "$EXPECTED_REPOSITORY" --json tagName --jq .tagName)" = "$TAG"
test "$(gh release view "$TAG" --repo "$EXPECTED_REPOSITORY" --json isDraft --jq .isDraft)" = false
test "$(gh release view "$TAG" --repo "$EXPECTED_REPOSITORY" --json isPrerelease --jq .isPrerelease)" = false
test "$(gh release view --repo "$EXPECTED_REPOSITORY" --json tagName --jq .tagName)" = "$TAG"
gh release view "$TAG" --repo "$EXPECTED_REPOSITORY" --json name,tagName,isDraft,isPrerelease,publishedAt,url
```

Open the URL printed by the final command and check that the title, generated notes, comparison range, tag, and Latest status are correct. Correct wording or categorization mistakes by editing the GitHub Release notes; do not change the tag.

No local Codex marketplace or plugin installation needs to be modified as part of release verification.

## 9. Recovery rules

- If an incorrect tag exists only locally, delete it with `git tag -d "$TAG"`, fix the release commit or variables, and recreate it.
- If tag creation succeeds but the tag push fails, resolve the push or authentication problem and retry the same explicit tag push.
- If the tag is pushed but `gh release create` reports failure, keep the tag and first run `gh release view "$TAG" --repo "$EXPECTED_REPOSITORY"` in case creation succeeded but its response was lost. Retry creation against the same verified tag only when the release is confirmed absent.
- Never force-push, move, or replace a tag after it has been pushed or published.
- If a published release contains a functional problem, fix it and make a new release using this complete procedure. Classify the corrective changes normally; a backward-compatible bug fix is usually a patch, but a feature or incompatible correction requires its corresponding bump.
- Generated release notes may be edited after publication without changing the release tag or source snapshot.

## Manual checkpoints

Most of the recipe is command-driven, but the maintainer must make and verify these decisions:

1. Before version editing, inspect all commits and diffs since `LAST_TAG`, classify each changed existing plugin and the independent repository changes, and choose the plugin and repository bumps.
2. Before committing, run the release validator, review its component summary and the complete staged snapshot, and confirm every version declaration.
3. After publication, inspect the GitHub Release page and generated notes. No local plugin reinstall or package upload is required.
