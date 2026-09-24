# Security policy

## Supported versions

Security fixes are prepared for the latest released repository version and the plugin versions it contains. Older repository tags and plugin versions do not receive separate backports unless a release note explicitly says otherwise.

## Report a vulnerability

Use [GitHub private vulnerability reporting](https://github.com/pallgeuer/la-dev-codex-plugins/security/advisories/new) for a suspected vulnerability. Include the affected repository and plugin versions, operating system, reproduction steps, impact, and any suggested remediation. Do not disclose sensitive details in a public issue.

If private reporting is unexpectedly unavailable, open a minimal [GitHub issue](https://github.com/pallgeuer/la-dev-codex-plugins/issues) asking the maintainer to establish a private contact channel, without including vulnerability details. Use the ordinary issue tracker directly for non-security bugs.

## Local execution trust model

Loupe and Perform run locally under the user's Codex session and permissions. They do not provide authentication, telemetry, a hosted backend, or an external data store. Loupe can launch external reviewer CLIs that inspect repository and host-readable material under their own provider accounts. Perform executes selected action definitions, which may read, write, run tools, or access networks as disclosed by the action and allowed by the active session. Users must review requested commands and permissions and protect credentials and repository secrets accordingly.
