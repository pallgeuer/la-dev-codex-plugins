# Releasing

This runbook describes how to make a stable release of the repository, its Codex plugin marketplace, and its dependency-free Python distribution. A release consists of version updates committed to `main`, an unsigned annotated Git tag named `vX.Y.Z`, a validated Python-package preflight, and a published GitHub Release. Publishing the GitHub Release triggers trusted publication of the matching minimal sdist and universal wheel to PyPI.

Run `$toolkit:perform publish-release` to execute this runbook. The action must stop for the exact-version confirmation, the final publication confirmation, and any protected-environment approval required below.

Run all commands from the repository root. Replace example values such as `X.Y.Z` before executing them. Stop whenever a command fails and resolve the failure before continuing.

## 1. Check the prerequisites

The release maintainer needs:

- Push access to `pallgeuer/la-dev-codex-plugins`.
- Git, Python 3, `uvx`, ripgrep (`rg`), and the GitHub CLI (`gh`).
- A GitHub CLI session authorized to read Actions and create releases.
- Access to approve the protected `pypi` GitHub environment when approval is required.
- A configured PyPI trusted publisher for project `la-dev-codex-plugins`, repository `pallgeuer/la-dev-codex-plugins`, workflow `python-package-release.yml`, and environment `pypi`.

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

| Classification | Change                                                                  | Component below `1.0.0` | Component at or above `1.0.0` |
|----------------|-------------------------------------------------------------------------|-------------------------|-------------------------------|
| `fix`          | Backward-compatible fix, documentation correction, or maintenance       | Patch                   | Patch                         |
| `enhancement`  | Narrow backward-compatible capability addition                          | Patch                   | Patch                         |
| `feature`      | Substantial backward-compatible public capability or workflow expansion | Minor                   | Minor                         |
| `breaking`     | Incompatible user-facing behavior, configuration, interface, or removal | Minor                   | Major                         |

For a component in initial development (`0.x.y`), a breaking change advances the minor version and resets the patch version. Moving to `1.0.0` is reserved for declaring its public interface stable.

Apply these repository rules:

- Bump every changed existing plugin independently from the version in its manifest.
- Give each changed existing plugin its highest applicable classification when it contains several kinds of changes.
- Judge `enhancement` versus `feature` by compatibility, public surface area, and overall user impact rather than by the mere presence of new functionality. When the distinction is debatable, require the release maintainer to confirm it explicitly.
- Leave every unchanged plugin version untouched.
- Classify changes outside plugin runtime subtrees according to their independent effect on the repository. Ancillary repository changes that only accompany plugin work may be classified as `none`.
- Bump the repository exactly once using the highest effective bump contributed by repository-only changes, structural plugin changes, and changed existing plugins.
- A plugin patch contributes a repository patch, and a plugin minor contributes a repository minor.
- A plugin major contributes a repository major when the repository is at or above `1.0.0`, but contributes a repository minor while the repository remains below `1.0.0`.
- Adding a plugin contributes a repository minor. Removing or renaming a plugin contributes the repository's effective breaking-change bump.

Examples:

- A plugin bug fix changes that plugin from `0.1.6` to `0.1.7` and applies a patch bump to the repository.
- Adding one action to an existing plugin is normally an enhancement unless it changes the plugin's core runtime or interaction contract.
- Adding recovery behavior to an existing workflow is normally an enhancement unless it substantially expands or changes that workflow's public contract.
- A substantial public workflow in one plugin and a patch fix in another bump those plugins by minor and patch respectively, and apply a minor bump to the repository.
- README-only corrections leave all plugin versions unchanged and apply a patch bump to the repository when those corrections are intentionally released.
- A breaking change to a `0.2.1` plugin changes it to `0.3.0` and applies a minor bump to a repository that is also below `1.0.0`.
- A breaking change to a stable plugin changes it from `1.4.2` to `2.0.0`; if the repository is `0.5.3`, its effective contribution is a repository minor bump to `0.6.0`.
- A breaking repository-only CLI change and a plugin patch apply a breaking repository bump rather than allowing the plugin patch to lower the repository bump.

Record the classifications. `REPOSITORY_CHANGE` must be `none`, `fix`, `enhancement`, `feature`, or `breaking`. Add one `PLUGIN_CHANGES` entry for every changed existing plugin and no entry for new, removed, or unchanged plugins:

```bash
REPOSITORY_CHANGE=feature
PLUGIN_CHANGES=(
    "PLUGIN_NAME=enhancement"
    "ANOTHER_PLUGIN=breaking"
)
```

Record the selected repository version:

```bash
NEW_REPO_VERSION=X.Y.Z
TAG="v${NEW_REPO_VERSION}"
```

Summarize the exact repository version, every changed plugin version, every component classification, and the evidence for those choices. Stop and obtain explicit user confirmation of those exact versions before editing any version declaration or other release metadata. Do not treat approval of a classification, general release request, or earlier plan as approval of the exact versions.

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

Move the completed `CHANGELOG.md` `Unreleased` outcomes into a dated `NEW_REPO_VERSION` section and restore an empty `Unreleased` section. Add the new release comparison from `LAST_TAG` through `TAG`, update the `Unreleased` comparison to `TAG...HEAD`, and leave every historical release comparison unchanged. Verify that the release notes describe shipped outcomes rather than intermediate implementation work.

Update the `"version"` in `plugins/PLUGIN_NAME/.codex-plugin/plugin.json` for every changed existing plugin. Leave unchanged plugins at their current versions. No release version is stored in `.agents/plugins/marketplace.json`.

Refresh the dependency snapshot in the example `pyproject.toml` in `docs/project_setup_python.md` as part of every release:

- Set both the base and `[pytest]` `la-dev-codex-plugins` pins to `NEW_REPO_VERSION`.
- By default, set the `pydocformatter` pin to the latest released pydocformatter version and verify that exact version is available from PyPI and has a corresponding `vVERSION` Git tag in `pallgeuer/pydocformatter`. If using the released version and tag is unsuitable, stop, explain the exact reason, and obtain explicit user confirmation of both the intended pydocformatter version and permission to use its current `main` branch as a direct fallback. After that confirmation, do not require the confirmed version to exist on PyPI or as a Git tag.
- By default, read `pyproject.toml` from that exact pydocformatter release tag, treating the released file as the source of truth for the remaining direct `docs`, `test`, and `dev` dependency pins and include-group structure. With the explicit fallback approval above, read the current `main` version of that file instead and treat that single retrieved snapshot as the source of truth. Add, remove, and update those example entries to match the selected source, while retaining the separately required `pydocformatter` pin and substituting `NEW_REPO_VERSION` for that file's `la-dev-codex-plugins` pins. Never use pydocformatter's moving `main` branch without the explicit stop and confirmation.
- Apply the completed public-guide change byte-for-byte to `plugins/toolkit/skills/perform/references/project_setup_python.md`; do not edit the bundled reference independently.

Inspect the resulting dependency block and mirror before continuing:

```bash
rg -n 'dependency-groups|==|include-group' docs/project_setup_python.md
cmp docs/project_setup_python.md plugins/toolkit/skills/perform/references/project_setup_python.md
```

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

Run the exact read-only checks used by CI's main pre-commit job:

```bash
uvx --python 3.10 --from pre-commit==4.6.0 pre-commit run --all-files --hook-stage manual
```

The manual-stage suite validates JSON, TOML, YAML, linting, formatting, typing, tests, and Python 3.6 compatibility. Run the focused release-validator and version-declaration tests as an explicit release check:

```bash
uvx --python 3.8 --from pytest==8.3.5 --with pytest-xdist==3.6.1 pytest tests/scripts/test_validate_release.py tests/repo/test_versions.py
```

The Python distribution is built only during release preflight and publication. Its workflow first runs this repository's complete non-mutating manual-stage checks, builds the wheel from the sdist, validates exact archive contents and metadata, and installs the wheel without package-index access on Python 3.6, Python 3.8, and the newest stable Python. Only after every smoke job succeeds does it generate `SHA256SUMS` and upload the finalized wheel, sdist, and checksum manifest as one workflow artifact.

Run the dependency-free supported-platform smoke checks with the active Python interpreter. CI repeats these checks on Ubuntu 18.04 with Python 3.6, the oldest non-deprecated hosted macOS Intel runner with Python 3.8, and the current `macos-latest` Arm64 runner with the newest stable Python 3.x:

```bash
python3 tests/platform/supported_platform_smoke.py
```

Verify that the official runner metadata still selects one safe oldest macOS Intel label:

```bash
curl -fsSL https://raw.githubusercontent.com/actions/runner-images/main/README.md | python3 scripts/select_oldest_macos_runner.py
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

Run the non-publishing Python-package preflight against the exact tag:

```bash
PACKAGE_PREFLIGHT_PREVIOUS_ID="$(gh run list --repo "$EXPECTED_REPOSITORY" --workflow "Python package release" --event workflow_dispatch --limit 1 --json databaseId --jq '.[0].databaseId // 0')"
gh workflow run python-package-release.yml --repo "$EXPECTED_REPOSITORY" --ref "$TAG" -f ref="$TAG"
```

Wait for GitHub to register the manual run for the tag and watch it to completion:

```bash
PACKAGE_PREFLIGHT_ID=""
PACKAGE_PREFLIGHT_DEADLINE=$((SECONDS + 300))
while test -z "$PACKAGE_PREFLIGHT_ID" && test "$SECONDS" -lt "$PACKAGE_PREFLIGHT_DEADLINE"; do
    PACKAGE_PREFLIGHT_ID="$(gh run list --repo "$EXPECTED_REPOSITORY" --workflow "Python package release" --event workflow_dispatch --limit 100 --json databaseId,headSha --jq "[.[] | select(.databaseId > $PACKAGE_PREFLIGHT_PREVIOUS_ID and .headSha == \"$RELEASE_COMMIT\")] | max_by(.databaseId).databaseId // empty")" || break
    test -n "$PACKAGE_PREFLIGHT_ID" || sleep 5
done
if test -z "$PACKAGE_PREFLIGHT_ID"; then
    echo "Python package preflight did not register for $TAG within five minutes." >&2
    gh run list --repo "$EXPECTED_REPOSITORY" --workflow "Python package release" --limit 10
    false
else
    gh run watch "$PACKAGE_PREFLIGHT_ID" --repo "$EXPECTED_REPOSITORY" --exit-status
fi
```

The manual workflow never publishes. If it fails, keep the immutable remote tag but do not publish the GitHub Release. A code or packaging defect requires a new corrective repository release because the pushed tag must not be moved; an infrastructure-only failure may be retried against the same tag.

Download and inspect the finalized preflight artifact, including its already-generated checksum manifest:

```bash
PREFLIGHT_ARTIFACT_DIRECTORY="$(mktemp -d)"
gh run download "$PACKAGE_PREFLIGHT_ID" --repo "$EXPECTED_REPOSITORY" --name python-package-distributions --dir "$PREFLIGHT_ARTIFACT_DIRECTORY"
PREFLIGHT_PACKAGES="$PREFLIGHT_ARTIFACT_DIRECTORY/packages"
PREFLIGHT_WHEEL="$PREFLIGHT_PACKAGES/la_dev_codex_plugins-$NEW_REPO_VERSION-py3-none-any.whl"
PREFLIGHT_SDIST="$PREFLIGHT_PACKAGES/la_dev_codex_plugins-$NEW_REPO_VERSION.tar.gz"
PREFLIGHT_CHECKSUMS="$PREFLIGHT_ARTIFACT_DIRECTORY/SHA256SUMS"
test -f "$PREFLIGHT_WHEEL"
test -f "$PREFLIGHT_SDIST"
test -f "$PREFLIGHT_CHECKSUMS"
PREFLIGHT_CHECKSUM_STDOUT="$(PYTHONPATH=src python3 -c 'import sys; import la_dev_codex_plugins.release_checksums.core as core; sys.stdout.write(core.generate_sha256_manifest(sys.argv[1:]))' "$PREFLIGHT_WHEEL" "$PREFLIGHT_SDIST")"
printf '%s\n' "$PREFLIGHT_CHECKSUM_STDOUT" | cmp - "$PREFLIGHT_CHECKSUMS"
```

Summarize the exact repository and plugin versions, tag, verified commit, wheel, sdist, checksum manifest, GitHub Release destination, and PyPI trusted-publishing pipeline. Stop and obtain explicit user approval before running `gh release create` or any other publication-triggering operation. This is a second approval distinct from the exact-version confirmation.

## 8. Publish the GitHub Release and Python distribution

Only after the second explicit approval, create and immediately publish a stable GitHub Release. Explicitly starting the generated notes at `LAST_TAG` makes the comparison correct even if earlier tags do not have corresponding GitHub Releases:

```bash
PACKAGE_PUBLISH_PREVIOUS_ID="$(gh run list --repo "$EXPECTED_REPOSITORY" --workflow "Python package release" --event release --limit 1 --json databaseId --jq '.[0].databaseId // 0')"
gh release create "$TAG" --repo "$EXPECTED_REPOSITORY" --verify-tag --generate-notes --notes-start-tag "$LAST_TAG" --fail-on-no-commits --title "Release $TAG" --latest
```

This command must use the already-pushed annotated tag; `--verify-tag` prevents GitHub CLI from silently creating a different tag.

Publishing the stable GitHub Release triggers the `Python package release` workflow for the same tag. That workflow repeats artifact construction and validation, then requests trusted publication through the protected `pypi` environment. It does not use `skip-existing`; a duplicate or inconsistent upload fails visibly.

Verify the published release:

```bash
test "$(gh release view "$TAG" --repo "$EXPECTED_REPOSITORY" --json tagName --jq .tagName)" = "$TAG"
test "$(gh release view "$TAG" --repo "$EXPECTED_REPOSITORY" --json isDraft --jq .isDraft)" = false
test "$(gh release view "$TAG" --repo "$EXPECTED_REPOSITORY" --json isPrerelease --jq .isPrerelease)" = false
test "$(gh release view --repo "$EXPECTED_REPOSITORY" --json tagName --jq .tagName)" = "$TAG"
gh release view "$TAG" --repo "$EXPECTED_REPOSITORY" --json name,tagName,isDraft,isPrerelease,publishedAt,url
```

Open the URL printed by the final command and check that the title, generated notes, comparison range, tag, and Latest status are correct. Correct wording or categorization mistakes by editing the GitHub Release notes; do not change the tag.

Wait for GitHub to register the publication workflow run, then wait until its protected `pypi` deployment is ready for approval:

```bash
PACKAGE_PUBLISH_ID=""
PACKAGE_PUBLISH_DEADLINE=$((SECONDS + 300))
while test -z "$PACKAGE_PUBLISH_ID" && test "$SECONDS" -lt "$PACKAGE_PUBLISH_DEADLINE"; do
    PACKAGE_PUBLISH_ID="$(gh run list --repo "$EXPECTED_REPOSITORY" --workflow "Python package release" --event release --limit 100 --json databaseId,headSha --jq "[.[] | select(.databaseId > $PACKAGE_PUBLISH_PREVIOUS_ID and .headSha == \"$RELEASE_COMMIT\")] | max_by(.databaseId).databaseId // empty")" || break
    test -n "$PACKAGE_PUBLISH_ID" || sleep 5
done
if test -z "$PACKAGE_PUBLISH_ID"; then
    echo "Python package publication did not register for $TAG within five minutes." >&2
    gh run list --repo "$EXPECTED_REPOSITORY" --workflow "Python package release" --limit 10
    false
else
    PACKAGE_PUBLISH_URL="$(gh run view "$PACKAGE_PUBLISH_ID" --repo "$EXPECTED_REPOSITORY" --json url --jq .url)"

    PACKAGE_PUBLISH_DEPLOYMENT=""
    PACKAGE_PUBLISH_DEPLOYMENT_ERROR=""
    PACKAGE_PUBLISH_DEPLOYMENT_DEADLINE=$((SECONDS + 1800))
    while test -z "$PACKAGE_PUBLISH_DEPLOYMENT" && test "$SECONDS" -lt "$PACKAGE_PUBLISH_DEPLOYMENT_DEADLINE"; do
        if ! PACKAGE_PUBLISH_DEPLOYMENT="$(gh api --method GET "repos/$EXPECTED_REPOSITORY/actions/runs/$PACKAGE_PUBLISH_ID/pending_deployments" --jq '([.[] | select(.environment.name == "pypi")][0].environment // empty) | [.id, .name, .html_url] | @tsv')"; then
            PACKAGE_PUBLISH_DEPLOYMENT_ERROR="Could not inspect pending deployments for workflow run $PACKAGE_PUBLISH_ID."
            break
        fi
        test -z "$PACKAGE_PUBLISH_DEPLOYMENT" || break
        if ! PACKAGE_PUBLISH_STATE="$(gh run view "$PACKAGE_PUBLISH_ID" --repo "$EXPECTED_REPOSITORY" --json status,conclusion,jobs --jq '[.status, (.conclusion // ""), ([.jobs[] | select(.conclusion != null and .conclusion != "" and .conclusion != "success" and .conclusion != "skipped") | "\(.name)=\(.conclusion)"] | join(", "))] | @tsv')"; then
            PACKAGE_PUBLISH_DEPLOYMENT_ERROR="Could not inspect workflow run $PACKAGE_PUBLISH_ID."
            break
        fi
        IFS=$'\t' read -r PACKAGE_PUBLISH_STATUS PACKAGE_PUBLISH_CONCLUSION PACKAGE_PUBLISH_FAILED_JOBS <<< "$PACKAGE_PUBLISH_STATE"
        if test -n "$PACKAGE_PUBLISH_FAILED_JOBS"; then
            PACKAGE_PUBLISH_DEPLOYMENT_ERROR="Workflow run $PACKAGE_PUBLISH_ID had failed jobs before requesting pypi approval: $PACKAGE_PUBLISH_FAILED_JOBS."
            break
        elif test "$PACKAGE_PUBLISH_STATUS" = completed; then
            PACKAGE_PUBLISH_DEPLOYMENT_ERROR="Workflow run $PACKAGE_PUBLISH_ID completed with conclusion $PACKAGE_PUBLISH_CONCLUSION before requesting pypi approval."
            break
        fi
        sleep 10
    done
    if test -z "$PACKAGE_PUBLISH_DEPLOYMENT"; then
        if test -n "$PACKAGE_PUBLISH_DEPLOYMENT_ERROR"; then
            printf '%s\n' "$PACKAGE_PUBLISH_DEPLOYMENT_ERROR" >&2
        else
            echo "Workflow run $PACKAGE_PUBLISH_ID did not request pypi approval within 30 minutes." >&2
        fi
        gh run view "$PACKAGE_PUBLISH_ID" --repo "$EXPECTED_REPOSITORY" --json status,conclusion,url,jobs
        false
    else
        IFS=$'\t' read -r PACKAGE_PUBLISH_ENVIRONMENT_ID PACKAGE_PUBLISH_ENVIRONMENT_NAME PACKAGE_PUBLISH_ENVIRONMENT_URL <<< "$PACKAGE_PUBLISH_DEPLOYMENT"
        printf 'Pending deployment: environment %s (ID %s)\n' "$PACKAGE_PUBLISH_ENVIRONMENT_NAME" "$PACKAGE_PUBLISH_ENVIRONMENT_ID"
        printf 'Approve it from workflow run %s: %s\n' "$PACKAGE_PUBLISH_ID" "$PACKAGE_PUBLISH_URL"
        printf 'Environment details: %s\n' "$PACKAGE_PUBLISH_ENVIRONMENT_URL"
    fi
fi
```

The workflow must complete its checks, builds, and smoke tests before its `publish` job requests approval for the protected `pypi` environment. The commands wait up to 30 minutes for that request while detecting an early workflow completion or failure. After identifying the exact run and deployment to the user, immediately end the turn. The user must approve that deployment on GitHub and send new input before release execution resumes.

After new user input confirms the environment approval, require the complete workflow, including PyPI publication and checksum asset upload, to succeed:

```bash
gh run watch "$PACKAGE_PUBLISH_ID" --repo "$EXPECTED_REPOSITORY" --exit-status
```

Download the workflow's finalized artifact and verify its checksum manifest without regenerating or modifying it:

```bash
RELEASE_ARTIFACT_DIRECTORY="$(mktemp -d)"
gh run download "$PACKAGE_PUBLISH_ID" --repo "$EXPECTED_REPOSITORY" --name python-package-distributions --dir "$RELEASE_ARTIFACT_DIRECTORY"
RELEASE_PACKAGES="$RELEASE_ARTIFACT_DIRECTORY/packages"
WHEEL="$RELEASE_PACKAGES/la_dev_codex_plugins-$NEW_REPO_VERSION-py3-none-any.whl"
SDIST="$RELEASE_PACKAGES/la_dev_codex_plugins-$NEW_REPO_VERSION.tar.gz"
CHECKSUMS="$RELEASE_ARTIFACT_DIRECTORY/SHA256SUMS"
test -f "$WHEEL"
test -f "$SDIST"
test -f "$CHECKSUMS"
CHECKSUM_STDOUT="$(PYTHONPATH=src python3 -c 'import sys; import la_dev_codex_plugins.release_checksums.core as core; sys.stdout.write(core.generate_sha256_manifest(sys.argv[1:]))' "$WHEEL" "$SDIST")"
printf '%s\n' "$CHECKSUM_STDOUT" | cmp - "$CHECKSUMS"
test "$(gh release view "$TAG" --repo "$EXPECTED_REPOSITORY" --json assets --jq '[.assets[] | select(.name == "SHA256SUMS")] | length')" = 1
```

The wheel and sdist remain distributed through PyPI; the GitHub Release carries the exact prepublication checksum manifest generated after smoke validation. Never regenerate that manifest after publication.

Open `https://pypi.org/project/la-dev-codex-plugins/$NEW_REPO_VERSION/` and verify that it shows one source distribution and one `py3-none-any` wheel with the expected description, Python requirement, and trusted-publishing provenance.

No local Codex marketplace or plugin installation needs to be modified as part of release verification.

## 9. Recovery rules

- If an incorrect tag exists only locally, delete it with `git tag -d "$TAG"`, fix the release commit or variables, and recreate it.
- If tag creation succeeds but the tag push fails, resolve the push or authentication problem and retry the same explicit tag push.
- If the tag is pushed but `gh release create` reports failure, keep the tag and first run `gh release view "$TAG" --repo "$EXPECTED_REPOSITORY"` in case creation succeeded but its response was lost. Retry creation against the same verified tag only when the release is confirmed absent.
- Never force-push, move, or replace a tag after it has been pushed or published.
- If the package preflight fails before GitHub Release publication, do not publish that release. Retry infrastructure failures against the same tag; fix package defects in a new release without moving the existing tag.
- If trusted publication fails before any file reaches PyPI, correct the environment, publisher, permission, or transient service problem and rerun the failed workflow job against the unchanged release.
- If only part of a Python distribution reaches PyPI, stop and inspect the immutable uploaded files before taking further action. Do not enable `skip-existing` or replace an uploaded filename; complete recovery manually only when the remaining artifact is byte-for-byte from the validated release workflow.
- If checksum generation or finalized-artifact upload fails, do not publish. Retry an infrastructure failure against the unchanged tag; a code or artifact defect requires a new release. Never generate a replacement manifest after any package file has reached PyPI.
- If checksum asset upload fails after PyPI publication, retain the finalized workflow artifact and upload its existing `SHA256SUMS`; do not regenerate it. If the response is lost, inspect release assets before retrying and never replace an existing checksum asset without first comparing its bytes with the finalized artifact.
- If a published release contains a functional problem, fix it and make a new release using this complete procedure. Classify the corrective changes normally; a backward-compatible bug fix is usually a patch, but a feature or incompatible correction requires its corresponding bump.
- Generated release notes may be edited after publication without changing the release tag or source snapshot.

## Manual checkpoints

Most of the recipe is command-driven, but the maintainer must make and verify these decisions:

1. Before version editing, inspect all commits and diffs since `LAST_TAG`, classify each changed existing plugin and the independent repository changes, choose the exact plugin and repository versions, and obtain explicit confirmation of those versions.
2. Before committing, run the release validator, review its component summary and the complete staged snapshot, and confirm every version declaration and changelog entry.
3. After tagging and the nonpublishing preflight, summarize the exact release identity, artifacts, destinations, and pipeline, then obtain a second explicit approval before creating the GitHub Release.
4. When the protected `pypi` deployment is requested, show the exact run and stop without polling until the user approves it and sends new input.
5. After publication, inspect the GitHub Release, checksum asset, successful package workflow, and PyPI project version. No local plugin reinstall, checksum regeneration, or manual package upload is required.
