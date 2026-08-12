# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and the project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Release diffs

- **Unreleased:** https://github.com/pallgeuer/la-dev-codex-plugins/compare/v0.4.4...HEAD
- **v0.4.4:** https://github.com/pallgeuer/la-dev-codex-plugins/compare/v0.4.3...v0.4.4
- **v0.4.3:** https://github.com/pallgeuer/la-dev-codex-plugins/compare/v0.4.2...v0.4.3
- **v0.4.2:** https://github.com/pallgeuer/la-dev-codex-plugins/compare/v0.4.1...v0.4.2
- **v0.4.1:** https://github.com/pallgeuer/la-dev-codex-plugins/compare/v0.4.0...v0.4.1
- **v0.4.0:** https://github.com/pallgeuer/la-dev-codex-plugins/compare/v0.3.0...v0.4.0
- **v0.3.0:** https://github.com/pallgeuer/la-dev-codex-plugins/compare/v0.2.0...v0.3.0
- **v0.2.0:** https://github.com/pallgeuer/la-dev-codex-plugins/compare/v0.1.6...v0.2.0
- **v0.1.6:** https://github.com/pallgeuer/la-dev-codex-plugins/compare/v0.1.5...v0.1.6
- **v0.1.5:** https://github.com/pallgeuer/la-dev-codex-plugins/compare/v0.1.3...v0.1.5
- **v0.1.3:** https://github.com/pallgeuer/la-dev-codex-plugins/compare/v0.1.2...v0.1.3
- **v0.1.2:** https://github.com/pallgeuer/la-dev-codex-plugins/compare/v0.1.1...v0.1.2
- **v0.1.1:** https://github.com/pallgeuer/la-dev-codex-plugins/compare/v0.1.0...v0.1.1
- **v0.1.0:** https://github.com/pallgeuer/la-dev-codex-plugins/releases/tag/v0.1.0

## Unreleased

### Added

- **Project development:**
  - Added recommended project-setup guides and provenance-grouped Perform action catalogues.
  - Added this retrospective changelog and made it part of the release workflow.

### Changed

- **Project checks:**
  - Enabled parallel pytest execution by default and strengthened ty exclusion handling.
  - Added baseline editor, swap-file, and tool-cache ignores.
- **Release safety:**
  - Added explicit version and publication approvals, protected-environment handoff, prepublication checksums, and checksum release assets.
- **Codex workflows:**
  - Refined repository instructions, action prompts, audit notes, local Perform testing guidance, and GitHub CLI cache access.
- **Maintenance:**
  - Simplified project code and documentation without changing supported runtime behavior.

## 0.4.4 (2026-08-10)

### Added

- **Pytest isolation:**
  - Added the pytest-retained cleanup lifecycle for interpreter-owned resources.
- **Perform actions:**
  - Added Python-distribution compatibility auditing.

## 0.4.3 (2026-08-05)

### Added

- **Pytest isolation:**
  - Added session-shared guarded working-directory isolation.

### Changed

- **Documentation:**
  - Reorganized project documentation around the expanded isolation workflow.

## 0.4.2 (2026-08-04)

### Added

- **Development workflow:**
  - Added guidance for AI-supported repository development.

## 0.4.1 (2026-08-02)

### Fixed

- **Python distribution:**
  - Made the Python 3.6 package smoke test trust its mounted source checkout.

## 0.4.0 (2026-08-02)

### Added

- **Development tools:**
  - Added Markdown table formatting, release checksum generation, and pytest working-directory isolation.
- **Markdown tables:**
  - Added configurable Git-aware path selection and exclusions.

### Changed

- **Codex Perform:**
  - Reorganized launcher packaging, tests, and documentation.
- **Platform support:**
  - Clarified operating-system support and expanded macOS wheel testing.
- **Loupe:**
  - Added recovery of truncated reviewer output from Claude session logs.

## 0.3.0 (2026-07-28)

### Added

- **Python distribution:**
  - Added the installable `la-dev-codex-plugins` package and PyPI release workflow.

## 0.2.0 (2026-07-28)

### Added

- **Codex Perform:**
  - Added the dependency-free source launcher, runtime API, executable help, question support, and cross-platform audit actions.
- **Repository guidance:**
  - Added reusable user-level Codex instructions and setup guidance.

### Changed

- **Codex Perform:**
  - Made interactive execution the default, improved noninteractive output and standard-error handling, and added the `--ni` alias.
- **Project quality:**
  - Added ASCII enforcement and simplified unnecessary re-exports and thin wrappers.

## 0.1.6 (2026-07-23)

### Changed

- **Loupe:**
  - Improved polling guidance and related user documentation.

## 0.1.5 (2026-07-21)

### Added

- **Action Toolkit:**
  - Added the Toolkit plugin and the initial JSON-configured Perform skill.

### Changed

- **Codex Perform:**
  - Adopted compact direct-argument JSON protocols and expanded action configuration.
- **Repository quality:**
  - Hardened pre-commit, CI, release versioning, and code-style guidance.
- **Loupe:**
  - Improved polling and temporary-artifact cleanup behavior.

## 0.1.3 (2026-07-03)

### Changed

- **Loupe:**
  - Improved timeout handling and reviewer instructions.

## 0.1.2 (2026-06-30)

### Changed

- **Documentation:**
  - Improved repository usage documentation and agent instructions.

## 0.1.1 (2026-06-30)

### Added

- **Codex configuration:**
  - Added repository-local Codex defaults.

### Changed

- **Loupe:**
  - Namespaced skill invocation and refined marker handling.

## 0.1.0 (2026-06-30)

### Added

- **Initial release:**
  - Added the Language-Agnostic Review marketplace plugin, Loupe skill, baseline project checks, and documentation.
