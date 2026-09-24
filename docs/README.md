# Documentation for Loupe, Perform, and development tools

## Getting started

- [Marketplace plugin installation](installation.md) covers marketplace refs, plugin installation and verification, Loupe permissions, and updates.
- [Plugin FAQ](faq.md) answers common questions about choosing, installing, configuring, and trusting Loupe and Perform.
- [Plugin compatibility and stability](compatibility.md) defines public plugin interfaces, independent versioning, and breaking-change documentation.
- [Privacy policy](../PRIVACY.md), [terms of use](../TERMS.md), and [security policy](../SECURITY.md) document the plugins' local execution, data handling, user responsibilities, and private vulnerability-reporting process.
- [Recommended Codex setup](recommended_setup.md) collects optional user-level instructions and configuration that complement the plugins.
- [Language-agnostic project setup](project_setup_agnostic.md) is an ordered repository setup recipe with ready-to-copy files and checks.
- [Python project setup](project_setup_python.md) extends that recipe with uv, packaging, pytest, Ruff, pydocformatter, ty, CI, and PyPI releases.
- [AI-supported repository development](ai_supported_development.md) describes the development loop to use after repository setup.

## Plugin guides

- [Loupe code review](loupe.md) explains review scopes, reviewer roles, effort configuration, output, failure handling, and its place in the development workflow.
- [Codex Perform reusable actions](codex_perform.md) covers reusable action discovery and overrides, inheritance, catalogues, the in-chat skill, and the standalone launcher.
- [Test-performance audit action](actions/audit_test_performance.md) documents the bundled evidence-based test-suite performance audit.

## Reusable development tools

- [Markdown table formatting](markdown_tables.md) documents the `la-dev-markdown-tables` library, command, and pre-commit hooks.
- [Pytest working-directory isolation](pytest_isolation.md) documents the explicitly loaded `la_dev_codex_plugins.pytest_isolation.plugin` module.
- [Release checksum manifests](release_checksums.md) documents the `la-dev-release-checksums` library and command.

## Repository development

- [Testing](../TESTING.md) lists focused and complete validation commands.
- [Releasing](../RELEASE.md) defines release preparation, validation, and publication.
- [Loupe public submission dossier](submissions/loupe.md) and [Perform public submission dossier](submissions/perform.md) record the exact directory fields, reviewer tests, release artifacts, and discovery-channel status.
