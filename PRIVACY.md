# Privacy policy

Effective date: 2026-09-24

This policy covers the Loupe Code Review (`la-review`) and Perform Action Toolkit (`toolkit`) plugins published by Philipp Allgeuer from this repository.

## Developer-operated data collection

Neither plugin independently collects telemetry, sends analytics, creates a developer account, or transmits data to a service operated by Philipp Allgeuer. The plugins do not provide a hosted service or external data store.

## Loupe data handling

Loupe launches available Codex and Claude reviewer processes under the active user's local account, Codex session, and granted permissions. Those reviewers can inspect repository files, Git data, and command output, and the material they inspect can be sent to the corresponding model provider. Loupe creates temporary local review artifacts and normally deletes them after a successful review; it retains and reports their local path when they are needed to diagnose a timeout, malformed result, verification blocker, or other unexpected failure.

Loupe does not redact secrets or confine reviewers to the captured diff. Users must run it only on material they are authorized to disclose to every enabled provider.

## Perform data handling

Perform discovers action definitions from the bundled, system, user, and repository catalogues, previews the selected action, and executes it through the user's Codex session. Perform itself does not transmit data to a developer-operated service. An individual action may read files, write files, run tools, or access networks only according to its action definition, the active Codex session, and the permissions the user grants.

The optional `codex-perform` companion is installed separately from the Python distribution. It launches Codex locally with the selected action prompt and does not add a developer-operated service or telemetry collector.

## Third-party services and credentials

Repository content, prompts, command output, credentials, and other context processed by Codex, Claude, GitHub, or another user-selected tool remain subject to that service's terms and privacy policy. The plugins do not control third-party collection, retention, training, logging, or account behavior. Authentication remains in the user's existing tool configuration; the plugins do not ask the user to provide credentials to Philipp Allgeuer.

## Policy changes and questions

Material changes are recorded in this repository and take effect when published. For non-sensitive questions, use the repository's [GitHub Issues page](https://github.com/pallgeuer/la-dev-codex-plugins/issues). Report sensitive security or privacy concerns through the private process in [SECURITY.md](SECURITY.md).
