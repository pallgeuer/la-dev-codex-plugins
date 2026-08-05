# Documentation

## Getting started

- [Marketplace plugin installation](installation.md) covers marketplace refs, plugin installation and verification, Loupe permissions, and updates.
- [Recommended Codex setup](recommended_setup.md) collects optional user-level instructions and configuration that complement the plugins.

## Plugin guides

- [Loupe code review](loupe.md) explains review scopes, reviewer roles, effort configuration, output, failure handling, and its place in the development workflow.
- [Codex Perform](codex_perform.md) covers reusable action discovery and overrides, inheritance, catalogues, the in-chat skill, and the standalone launcher.
- [Test-performance audit action](actions/audit_test_performance.md) documents the bundled evidence-based test-suite performance audit.

## Reusable development tools

- [Markdown table formatting](markdown_tables.md) documents the `la-dev-markdown-tables` library, command, and pre-commit hooks.
- [Pytest working-directory isolation](pytest_isolation.md) documents the explicitly loaded `la_dev_codex_plugins.pytest_isolation.plugin` module.
- [Release checksum manifests](release_checksums.md) documents the `la-dev-release-checksums` library and command.

## Repository development

- [AI-supported repository development](ai_supported_development.md) describes the enforcement ladder and repeatable development loop used by this repository.
- [Testing](../TESTING.md) lists focused and complete validation commands.
- [Releasing](../RELEASE.md) defines release preparation, validation, and publication.
