# FAQ: Loupe, Perform, and the Codex plugin marketplace

This FAQ answers common questions about choosing, installing, and configuring the repository's marketplace plugins. See the [installation guide](installation.md) for commands and troubleshooting, and the [compatibility policy](compatibility.md) for stability guarantees.

## How is Loupe different from asking Codex to review twice?

Loupe launches the available external reviewers independently with distinct review roles, then asks the active Codex session to verify their candidate findings against the review scope and current source. Its final result preserves reviewer attribution, duplicate relationships, rejected or unresolved claims, and partial failures instead of treating two model responses as equally established findings. The [Loupe guide](loupe.md#how-loupe-works) describes the complete workflow and includes an end-to-end example.

## Do I need Claude to use Loupe?

No. Loupe can run with the Codex reviewers alone when the `codex` reviewer executable is available and authenticated. If `claude` is unavailable, its reviewer is reported as skipped; installing and authenticating both reviewer CLIs adds provider diversity. Loupe needs at least one launchable reviewer. See [Loupe requirements and installation](loupe.md#install-and-run-in-30-seconds).

## Can plugins be configured per repository?

Plugin installation belongs to the active user-level Codex home rather than to one repository. Toolkit can nevertheless load repository-specific Perform actions from `<repository-root>/.codex/toolkit_perform_actions/` when that repository also contains `.codex/config.toml`; higher-precedence repository definitions can extend or override lower layers. Loupe operates on the repository where Codex is running, and its invocation selects the review scope. See [Perform action discovery](codex_perform.md#discover-and-customize-actions) and [Loupe review scopes](loupe.md#choose-a-review-scope).

## Can I use only one plugin from the marketplace?

Yes. Install `la-review` for Loupe, `toolkit` for Perform, or both. Neither plugin requires the other, and neither marketplace plugin requires installation of the repository's separate Python distribution. The [installation guide](installation.md#2-install-the-plugins-you-want) shows the independent selectors.

## What data is sent to external models?

Loupe's reviewer processes can inspect the repository working tree, full files, Git metadata and history, and local validation output; material they inspect can enter the corresponding provider's model context. Loupe does not redact secrets or confine reviewers to the captured diff. The [Loupe data and trust boundary](loupe.md#data-and-trust-boundary) documents the exact scope and provider behavior.

Perform uses the active Codex session, or launches Codex through `codex-perform`, to execute the selected action prompt. An action can inspect repository content and invoke tools according to its displayed prompt and the active Codex permissions. Perform previews the selected action and resolved prompt before execution; action definitions, project instructions, and Codex permissions determine the resulting access and external communication.

## Which plugins are language-agnostic?

Loupe reviews Git changes without requiring a particular implementation language. Perform's action system is also language-agnostic, while individual actions can provide an `agnostic` variant, language-specific variants, or project-tool requirements. Python 3.6+ is a runtime requirement for the shipped plugin scripts, not a requirement that the repository being reviewed or automated be a Python project.
