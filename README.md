# Language-Agnostic Development Codex Plugins

This repository is a Codex plugin marketplace, version 0.5.3.

Use the marketplace plugins to get a second, independently verified perspective on a code change or to turn recurring development work into reusable Codex actions. Loupe and Perform are the collection's co-equal entry points: start with the problem you need to solve and install only the plugin that addresses it.

## Plugin catalog

| Plugin                  | Problem it solves                                                                                                                                | Start with         | Status                         | Guide                                                   |
|-------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------|--------------------|--------------------------------|---------------------------------------------------------|
| **Loupe** (`la-review`) | Runs independent code reviews, verifies their candidate findings, and consolidates the evidence instead of merely concatenating reviewer output. | `$la-review:loupe` | Team-ready (pre-1.0 interface) | [Loupe code review](docs/loupe.md)                      |
| **Perform** (`toolkit`) | Runs reusable, configurable development actions from layered catalogs in the current Codex chat or through a standalone launcher.                | `$toolkit:perform` | Team-ready (pre-1.0 interface) | [Codex Perform reusable actions](docs/codex_perform.md) |

Both plugins are maintained for team-wide adoption. Their current `0.x` versions mean that commands and configuration remain pre-1.0 interfaces; incompatible changes are identified and versioned according to the repository's semantic-versioning policy.

See the [plugin FAQ](docs/faq.md) for common adoption questions and [plugin compatibility and stability](docs/compatibility.md) for the public interface and release guarantees.

Both plugins execute locally through the user's Codex session and permissions; neither supplies a hosted service, developer authentication flow, telemetry collector, or external data store. Review the repository [privacy policy](PRIVACY.md), [terms of use](TERMS.md), and [security policy](SECURITY.md). Use [GitHub Issues](https://github.com/pallgeuer/la-dev-codex-plugins/issues) for support and non-security bugs.

## Find a tool by task

| Task                                                                 | Tool                                                             | Delivery                                 | Start with                                                           |
|----------------------------------------------------------------------|------------------------------------------------------------------|------------------------------------------|----------------------------------------------------------------------|
| Review a code change from several independent perspectives           | [Loupe](docs/loupe.md)                                           | `la-review` marketplace plugin           | `$la-review:loupe`                                                   |
| Run or define reusable development actions                           | [Perform](docs/codex_perform.md)                                 | `toolkit` marketplace plugin             | `$toolkit:perform`                                                   |
| Measure a test suite and produce an evidence-based performance audit | [Test-performance audit](docs/actions/audit_test_performance.md) | Action bundled with the `toolkit` plugin | `$toolkit:perform audit-test-performance`                            |
| Format or check Markdown tables                                      | [Markdown table formatting](docs/markdown_tables.md)             | Python distribution                      | `la-dev-markdown-tables --check`                                     |
| Isolate pytest working directories                                   | [Pytest working-directory isolation](docs/pytest_isolation.md)   | Optional Python integration              | `pytest -p la_dev_codex_plugins.pytest_isolation.plugin`             |
| Generate and verify release checksum manifests                       | [Release checksum manifests](docs/release_checksums.md)          | Python distribution                      | `la-dev-release-checksums --output dist/SHA256SUMS dist/package.whl` |

The marketplace plugins and the Python distribution are installed separately. Installing one plugin does not require installing the other plugin or the Python package.

## Install and verify marketplace plugins

Use a stable Codex CLI release at version `0.137.0` or newer. Prerelease Codex builds are supported only on a best-effort basis; see [Plugin compatibility and stability](docs/compatibility.md#codex-cli-compatibility) for the complete policy.

Add the marketplace from `main` once:

```bash
codex plugin marketplace add pallgeuer/la-dev-codex-plugins --ref main
```

Install **Loupe Code Review** when you want independent review with verified findings:

```bash
codex plugin add la-review@la-dev-codex-plugins
```

Install the **Perform Action Toolkit** when you want reusable development actions:

```bash
codex plugin add toolkit@la-dev-codex-plugins
```

Verify that every plugin you selected reports `installed, enabled`:

```bash
codex plugin list --marketplace la-dev-codex-plugins
```

Restart Codex. To smoke-test Loupe without launching external reviewers, type `$la-review:loupe` and confirm that autocomplete recognizes it, but do not submit it. To smoke-test Perform, submit `$toolkit:perform` with no arguments; it should list the effective actions without executing one.

See [Marketplace plugin installation](docs/installation.md) for per-plugin requirements, stable release pinning, focused troubleshooting, the optional Loupe allow rule, updates, and removal.

## Plugins in 30 seconds

### Loupe

Loupe runs the available Claude and Codex reviewers in parallel, independently verifies their candidate findings, and consolidates the results into one structured review. Default review of current uncommitted changes:

```text
$la-review:loupe
```

The representative result contains a diff summary, each reviewer's completion status, numbered findings with evidence and recommendations, duplicate relationships, and verification outcomes. Rejected or unresolved candidates remain visible as unsure rather than silently becoming accepted findings.

**Tip:** Typing `$lou` and then accepting the Codex autocomplete suggestion is usually enough to insert the full `$la-review:loupe` invocation without typing it out manually.

Specify another scope in ordinary text:

```text
$la-review:loupe unstaged changes
$la-review:loupe unstaged and untracked changes
$la-review:loupe last commit
$la-review:loupe feature/loupe-plugin branch
$la-review:loupe PR #123
```

Reasoning effort can also be overridden in ordinary text:

```text
$la-review:loupe last commit; high Claude effort, medium Codex effort
```

See [Loupe code review](docs/loupe.md) for requirements, scopes, reviewer roles, effort configuration, diff capture, output, timeouts, partial failures, artifacts, and recommended development use.

### Perform

List the configured actions without executing one:

```text
$toolkit:perform
```

Run a known action:

```text
$toolkit:perform find-todos
$toolkit:perform find-todos in tools/
```

The representative result previews the selected action and scope, then reports the repository's TODO inventory by location or explicitly reports that no matching TODOs were found. The wording depends on the selected action and repository rather than forming a fixed output contract.

The same Toolkit actions are available through the dependency-free `codex-perform` launcher:

```bash
codex-perform list
codex-perform find-todos
```

Install the launcher in a Python 3.6+ virtual environment:

```bash
python3 -m venv /PATH/TO/VENV
source /PATH/TO/VENV/bin/activate
python -m pip install la-dev-codex-plugins
```

Alternatively, activate it directly from a source checkout, e.g. to run install-free with any system Python 3.6+ interpreter:

```bash
source /PATH/TO/la-dev-codex-plugins/activate.sh
```

See [Codex Perform](docs/codex_perform.md) for action discovery and overrides, inheritance, catalogue safety, installation and activation, all CLI forms, output modes, variables, qualifications, and launcher/plugin compatibility.

The bundled `audit-test-performance[agnostic]` action measures a repository's test suite and creates or updates one evidence-based audit document without changing implementation or tests. See [Test-performance audit action](docs/actions/audit_test_performance.md).

## Recommended further setup

See [Recommended Codex setup](docs/recommended_setup.md) for optional user-level instructions, baseline sandbox and reasoning settings, network access, Python cache roots, model selection, and TUI configuration. For an individual repository, follow [Language-agnostic project setup](docs/project_setup_agnostic.md) and then [Python project setup](docs/project_setup_python.md) when applicable.

Normally, launch Codex with `codex`. The setup guide also explains model and reasoning-effort configuration; command-line overrides can be combined when needed, for example:

```bash
codex --model gpt-5.6 -c model_reasoning_effort=medium -c plan_mode_reasoning_effort=high
```

## Reusable development tools

The Python distribution also installs reusable development tools that are independent of the marketplace plugins:

- [Markdown table formatting](docs/markdown_tables.md) documents the `la-dev-markdown-tables` checker, formatter, library, and pre-commit hooks.
- [Pytest working-directory isolation](docs/pytest_isolation.md) documents the explicitly loaded `la_dev_codex_plugins.pytest_isolation.plugin` module, including private per-test fixtures, the opt-in session-shared guard, and eager or pytest-retained boundary lifecycles.
- [Release checksum manifests](docs/release_checksums.md) documents the deterministic, failure-safe `la-dev-release-checksums` library and command.

The [documentation index](docs/README.md) collects these guides with the marketplace plugin and repository-development documentation.

The base installation remains standard-library-only and has no mandatory dependencies:

```bash
python -m pip install la-dev-codex-plugins
```

Install `la-dev-codex-plugins[pytest]` to obtain the optional pytest dependency, or `[dev]` for the same development integration. The package deliberately has no `pytest11` entry point: downstream suites must explicitly load `la_dev_codex_plugins.pytest_isolation.plugin` as documented. Installing these Python tools does not install the Codex marketplace or its plugins.

## Operating-system support

The officially supported host operating systems are:

- Ubuntu 18.04 or newer, with the shipped runtime code supporting the system Python 3.6+ included with Ubuntu 18.04+
- macOS 14 or newer, with Python 3.6 or newer installed separately; current macOS releases do not include a system `python3`

The repository runs dependency-free runtime smoke checks on Ubuntu 18.04 with Python 3.6, on the oldest non-deprecated GitHub-hosted macOS Intel runner with Python 3.8, and on the current `macos-latest` Arm64 runner with the newest stable Python 3.x. The full lint, type-check, compatibility-analysis, and functional test suite runs on current Ubuntu with Python 3.8 semantics. GitHub retires older macOS runner images over time, so exact macOS 14 execution continues only while GitHub offers it as a non-deprecated hosted image; after that point, the support floor relies on static portability assessment and the portable standard-library runtime constraints rather than continuous execution on macOS 14. Shipped plugin scripts, the source launcher, and the base installation require only Python 3.6+ and the Python standard library. The explicitly loaded pytest-isolation plugin additionally requires caller-supplied pytest 7.0.1 or newer. Loupe additionally requires Bash, Git, `jq`, and at least one supported external reviewer executable (`codex` or `claude`); it reports unavailable reviewer tools rather than attempting to install them.

Only the Ubuntu and macOS hosts listed above are officially supported. Compatibility with other POSIX Linux distributions is intended but is not part of the official support guarantee. Native Windows and WSL are not supported, tested, or maintained, and the runtime intentionally relies on POSIX process, filesystem, signal, and shell behavior.

## Development

Use these guides as the entry points for repository development:

- [Language-agnostic project setup](docs/project_setup_agnostic.md) and [Python project setup](docs/project_setup_python.md) provide ordered setup recipes for new or existing repositories.
- [AI-supported repository development](docs/ai_supported_development.md) explains how to turn recurring decisions into tools, tests, specifications, and repeatable workflows.
- [Testing](TESTING.md) lists focused checks and the complete validation suite.
- [Loupe code review](docs/loupe.md) documents the final multi-reviewer check recommended before every non-trivial commit.
- [Codex Perform](docs/codex_perform.md) documents reusable development actions available in chat and through the standalone launcher.
- [Markdown table formatting](docs/markdown_tables.md), [pytest working-directory isolation](docs/pytest_isolation.md), and [release checksum manifests](docs/release_checksums.md) document the reusable development tools maintained in this repository.
- [Releasing](RELEASE.md) covers release preparation, validation, and publication.
- [Changelog](CHANGELOG.md) records released outcomes and current unreleased work.

The [documentation index](docs/README.md) provides the complete grouped list.

For a fresh environment and repository, follow [Marketplace plugin installation](docs/installation.md), [Recommended Codex setup](docs/recommended_setup.md), [Language-agnostic project setup](docs/project_setup_agnostic.md), and any applicable language-specific setup in that order.

Shipped plugin scripts and package source support Python 3.6+. The base runtime uses only the Python standard library; only the explicitly loaded pytest-isolation plugin may import its declared optional pytest dependency.

## License

This project is licensed under the [MIT License](LICENSE).
