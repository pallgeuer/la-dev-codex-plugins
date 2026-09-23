# Plugin compatibility and stability

The repository and each marketplace plugin use independent [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Repository releases select one marketplace snapshot, while each plugin manifest records that plugin's own version. The versions do not need to match.

## Public plugin interfaces

The documented public plugin interfaces include:

- the `la-dev-codex-plugins` marketplace identity;
- the `la-review` plugin identity and `$la-review:loupe` skill invocation;
- the `toolkit` plugin identity and `$toolkit:perform` skill invocation;
- the `codex-perform` command and its documented launcher-facing API; and
- documented configuration formats, selectors, and behavior in the plugin guides.

Loupe and Perform are maintained for team-wide adoption, but their current `0.x` versions remain pre-1.0 interfaces. A breaking change to a pre-1.0 plugin advances that plugin's minor version; after a plugin reaches `1.0.0`, a breaking change advances its major version. Removing or renaming a plugin identity is also a breaking repository change.

## Compatible and breaking changes

Backward-compatible fixes and narrowly scoped enhancements normally advance the affected plugin's patch version. Substantial backward-compatible capability additions normally advance its minor version. Incompatible changes to a documented name, command, selector, configuration format, launcher API, or required behavior are classified as breaking for the affected component.

Breaking changes must be identified under the affected product's heading in the changelog and release notes. The entry must name the previous interface, its replacement, and any migration required. There is no fixed deprecation window for pre-1.0 interfaces; when a compatibility alias or transition period is provided, its duration is stated with that change rather than implied as a general guarantee.

Repository-only changes are classified independently from plugin changes. Documentation or infrastructure changes do not trigger a plugin version change unless the shipped plugin payload also changes. Ordinary development does not update versions; version declarations are changed together only during an explicitly requested release.

## Product documentation links

Plugin `homepage` and `websiteURL` metadata intentionally point to product guides on the canonical `main` branch. These links are stable entry points to the latest Loupe and Perform documentation and are not rewritten for each repository release.

Pinning a marketplace to `vX.Y.Z` fixes the repository snapshot and installed plugin payload at that tag, but following a plugin homepage still opens the latest product guide. When version-exact documentation is required, replace `blob/main` in that guide URL with `blob/vX.Y.Z`, using the same repository release tag as the pinned marketplace. This keeps release metadata maintainable while preserving direct access to the matching historical instructions.

## Codex CLI compatibility

The marketplace plugins support stable Codex CLI releases from `0.137.0` onward. This is the project's compatibility floor, not a minimum version published by OpenAI. Codex CLI `0.137.0` is the first stable release that exposes the complete command surface used by the documented workflows: marketplace and plugin installation, listing, removal, and the JSON plugin listing consumed by the standalone `codex-perform` launcher.

The compatibility guarantee applies to stable Codex CLI releases. Alpha, beta, preview, and other prerelease builds are supported only on a best-effort basis because their plugin interfaces can change before a stable release. The marketplace plugins are not supported in the Codex IDE extension, which the [official OpenAI plugin documentation](https://learn.chatgpt.com/docs/plugins) identifies as a surface without plugin support; use Codex CLI for the workflows documented in this repository.

Stable Codex CLI releases newer than `0.137.0` are supported unless a known exception is documented here or in the changelog. When preparing each repository release, the maintainers assess relevant changes in the current stable Codex plugin system and either adapt the plugins or document the incompatibility. This release-based tracking policy has no separate calendar response-time guarantee.

The [installation guide](installation.md#requirements-by-plugin) records the other runtime requirements and explains how to verify the active Codex CLI version and plugin-management commands.

The [changelog](../CHANGELOG.md) is the human-readable record of released capabilities, fixes, compatibility changes, and migrations. The [release runbook](../RELEASE.md) defines component classification, exact version selection, validation, and publication.
