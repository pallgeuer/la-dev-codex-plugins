# Test-performance audit action

`audit-test-performance[agnostic]` inventories and measures a repository's complete runnable test suite, then creates or updates one evidence-based Markdown audit. It is a language-agnostic Toolkit Perform action that runs in goal mode with high reasoning effort.

The audit is observational. It may inspect the repository and run safe bounded test collection and timing commands, but it does not weaken or delete tests, edit application code, change test infrastructure or CI, or implement performance fixes. The selected audit document is its only permitted edit.

## Invocation

In a Codex chat with Toolkit installed:

```text
$toolkit:perform audit-test-performance
```

The canonical selector is also accepted:

```text
$toolkit:perform audit-test-performance[agnostic]
```

Through the standalone launcher:

```text
codex-perform audit-test-performance
codex-perform 'audit-test-performance[agnostic]'
```

The action has no prompt variables and does not require an interactive launcher. It does not install missing dependencies unless the enclosing Codex session separately has authority for that action, and it does not contact external services merely to fill the report.

## Audit-file selection

An audit file is identified only by these exact first two lines:

```markdown
<!-- la-dev-test-performance-audit:v1 -->
# Test performance audit
```

The marker must be the first line and the heading the second. A leading blank line, UTF-8 BOM, surrounding whitespace, different heading level, or marker/heading later in a document does not qualify.

Discovery searches Git-tracked Markdown files and also checks `docs/test_performance_audit.md` when that default path exists but is still untracked. Ignored files and every other untracked file are excluded.

- Exactly one candidate is updated in place, preserving its marker and heading as the first two lines.
- No candidate causes creation of `docs/test_performance_audit.md`.
- Multiple candidates stop the action with an ambiguity report and no audit-file edit.
- A nonempty default path without the exact marker and heading stops the action rather than overwriting unrelated content.

Selection remains stable across repeat runs. A nondefault path is never inferred from its filename or visible heading alone.

## Measurements and inventory

The action first discovers the repository's test runners, configuration, scripts, workflows, fixtures, helpers, and established commands. It inventories the complete automatically collected and runnable suite by meaningful category instead of stopping after the first hotspot.

Each report records:

- audit date, commit identifier, and dirty-worktree state;
- operating system, architecture, Python/runtime versions, and relevant test-tool versions;
- discovered runners and configuration files;
- the full categorized test inventory;
- every exact command used;
- collection-only and serial-suite timing;
- parallel-suite timing when the repository already supports it without unsafe environment mutation;
- available per-file, per-module, slowest-test, setup/teardown, and fixture-heavy timing;
- expensive helper processes, repeated builds, network access, filesystem scans, sleeps, and subprocess patterns observed in support code;
- cache warmth, unavailable optional services, skipped integration tests, platform exclusions, and other distortions;
- comparison with compatible prior audit data;
- ranked findings with evidence and likely impact, or an explicit no-material-finding conclusion; and
- follow-up recommendations separated from changes actually made.

Failures, skips, and unavailable tools remain visible in the report. Coarse wall-clock measurements are identified as such and are not presented as benchmark precision.

## Serial and parallel interpretation

Serial time is the primary broadly comparable suite measurement because it avoids scheduler and worker-count differences. Parallel time describes the repository's already-supported parallel execution path and must be interpreted together with the worker count, process start cost, test distribution, shared-resource contention, and platform.

A parallel speedup does not prove that individual tests became cheaper, and a regression can reflect worker imbalance or environmental contention rather than test logic. Compare prior results only when commands, runner/tool versions, worker configuration, platform, available services, and cache conditions are compatible.

## Repeatability limits

Test timing is sensitive to CPU frequency, system load, filesystem and package caches, process startup, virtualization, network/service availability, test ordering, randomized seeds, and platform-specific exclusions. The action records this context so a later audit can distinguish a meaningful change from environmental noise.

The report is a diagnostic baseline and recommendation document, not an automated benchmark certification. Re-run it under comparable conditions before treating small timing differences as actionable.
