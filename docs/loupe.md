# Loupe: Independently verified code review

Loupe runs several independent external reviewers against one Git review scope, then uses the active Codex session to verify their candidate findings and combine them into one structured review. It is designed as the final judgment-oriented check after deterministic formatters, linters, type checks, and tests have passed.

Loupe is a team-ready skill in the `la-review` marketplace plugin. Its command and configuration remain pre-1.0 interfaces. Loupe does not modify files, stage changes, commit, or install dependencies during a review. See the [plugin FAQ](faq.md) for common comparisons and adoption questions and the [compatibility policy](compatibility.md) for interface guarantees.

## How Loupe works

1. **Independent candidate generation:** Every available reviewer receives the same requested review scope in a role-specific prompt and inspects the repository independently. Loupe can launch one Claude reviewer and three Codex reviewers in parallel.
2. **Evidence-based verification:** After the external reviews finish, the active Codex session checks every candidate against the captured verification diff and current source, running focused local validation when useful.
3. **Consolidation without silent promotion:** The final review identifies duplicates and normally retains unsupported, rejected, or unresolved claims as `Unsure`. It does not simply concatenate reviewer responses or silently promote every allegation to a finding.

The consolidated result includes a diff summary, each eligible reviewer's status and elapsed time, continuously numbered findings with evidence and recommendations, duplicate relationships, and failure details.

## Data and trust boundary

Loupe can send repository information to more than one external provider. The Codex reviewer processes use the installed Codex CLI and OpenAI services; the Claude reviewer uses the installed Claude CLI and Anthropic services. Run Loupe only when you are authorized to disclose the review material to every available provider.

The explicit input passed to each reviewer is the textual review scope, such as `uncommitted changes` or `HEAD~2..HEAD`. Each reviewer starts at the repository's Git root and may inspect the working tree, full files, Git metadata and history, and output from local validation commands. The reviewer processes are not technically restricted to the captured diff or to files changed within it. Depending on the child CLI's controls, other host-readable files may also be technically accessible. Loupe does not redact secrets or establish a file allowlist.

The reviewer subprocesses inherit their launch environment and use normal user-level authentication and configuration state under locations such as `~/.codex/` and `~/.claude/`. Loupe does not add environment-variable values to reviewer prompts, but the review-only prompt is a behavioral instruction rather than a confidentiality boundary. Repository files, command output, or other context that a reviewer reads can enter that provider's model context. Provider-side storage and retention follow the applicable account, CLI, and service policies rather than a Loupe-specific policy.

Codex asks for escalated sandbox permission before launching the external CLIs because they need their normal user-level state. The child Codex commands use their own workspace-write sandbox, and Claude uses its own automatic permission mode, but approving the runner is not equivalent to confining every child process to the review diff. See the [optional Loupe allow rule](installation.md#optional-auto-allow-the-loupe-review-script) before deciding whether repeated automatic approval is appropriate for your environment.

## Install and run in 30 seconds

Loupe requires stable Codex CLI 0.137.0+, Python 3.6+ with the standard library, Bash, Git, `jq`, and at least one authenticated supported reviewer executable. `claude` enables Claude Code Review; `codex` enables Codex Review, Codex Correctness, and Codex Design. Install and authenticate both reviewer CLIs when you want provider diversity. See the [Codex CLI compatibility policy](compatibility.md#codex-cli-compatibility) for later stable releases and prerelease builds.

Add the marketplace and install only the independent **Loupe Code Review** (`la-review`) plugin:

```bash
codex plugin marketplace add pallgeuer/la-dev-codex-plugins --ref main
codex plugin add la-review@la-dev-codex-plugins
```

Confirm that `la-review` reports `installed, enabled`:

```bash
codex plugin list --marketplace la-dev-codex-plugins
```

Restart Codex, type `$la-review:loupe`, and confirm that autocomplete recognizes the skill. Do not submit that invocation merely as an installation check because it launches external reviewers. To perform the first review, open Codex in a Git repository with an uncommitted change and run:

```text
$la-review:loupe
```

An unavailable provider is skipped rather than installed automatically. If neither provider is available, Loupe cannot perform a review. The [marketplace plugin installation guide](installation.md) covers stable release pinning, updates, removal, and detailed installation verification.

## End-to-end example

This illustrative example is intentionally stable documentation, not a captured benchmark result. Assume a configuration contract that treats a missing or malformed retry count as `3`, requires an explicitly supplied count to contain decimal digits only and represent a positive integer, and defines no maximum.

### Code change

The change adds parsing but omits the positive-value validation:

```diff
 DEFAULT_RETRY_COUNT = 3

+def parse_retry_count(raw):
+    if raw is None:
+        return DEFAULT_RETRY_COUNT
+    try:
+        return int(raw)
+    except ValueError:
+        return DEFAULT_RETRY_COUNT
```

### Independent candidates

| Reviewer           | Candidate                                                                                             |
|--------------------|-------------------------------------------------------------------------------------------------------|
| Claude Code Review | Zero and negative values are returned even though configured retry counts must be positive.           |
| Codex Review       | Catching `ValueError` can mask an unrelated programming error in the parser.                          |
| Codex Correctness  | Negative retry counts bypass the documented positive-value requirement.                               |
| Codex Correctness  | Values with surrounding whitespace are accepted even though supplied values must contain digits only. |
| Codex Design       | The parser should impose an upper bound to prevent unreasonable retry counts.                         |

### Verification

| Candidate                | Decision  | Evidence                                                                                                                    |
|--------------------------|-----------|-----------------------------------------------------------------------------------------------------------------------------|
| Non-positive values      | Confirmed | `parse_retry_count("-1")` returns `-1`, contradicting the stated positive-value contract.                                   |
| Broad exception handling | Rejected  | The `try` block contains only `int(raw)`, whose `ValueError` is exactly the malformed-input case that should fall back.     |
| Negative values          | Duplicate | It identifies the same missing lower-bound validation and impact as the first candidate.                                    |
| Surrounding whitespace   | Confirmed | `parse_retry_count(" 2 ")` returns `2` instead of treating the noncanonical value as malformed.                             |
| Missing upper bound      | Unsure    | No maximum is part of the stated contract, so adopting one requires a product decision rather than a code-review assertion. |

### Consolidated result

The shortened representative result keeps every candidate while distinguishing evidence quality. Reviewer timings and the diff summary are omitted here for brevity:

```text
**Claude Code Review:** Succeeded

1. [Medium] Reject zero and negative retry counts. The parser returns non-positive integers despite the positive-value contract.

**Codex Review:** Succeeded

2. [Unsure] The ValueError handler does not mask an unrelated error. Verification showed that the guarded conversion raises ValueError for the intended malformed-input case.

**Codex Correctness:** Succeeded

3. [Medium] Duplicate of #1. Negative retry counts bypass the required lower bound.

4. [Low] Reject retry counts with surrounding whitespace. The parser accepts a value that violates the digits-only input contract.

**Codex Design:** Succeeded

5. [Unsure] An upper retry-count limit needs a product decision because the current contract defines no maximum.
```

`Unsure` preserves the audit trail for both disproved allegations and unresolved product questions; it does not mean that Loupe recommends implementing them. Exact findings, severity judgments, timings, and wording depend on the reviewed change, available reviewers, model behavior, and verification evidence.

## Choose a review scope

With no qualification, Loupe reviews all current uncommitted changes:

```text
$la-review:loupe
```

Specify another scope in ordinary text:

```text
$la-review:loupe unstaged and untracked changes
$la-review:loupe last commit
$la-review:loupe last two commits
$la-review:loupe HEAD~2..HEAD
$la-review:loupe feature/loupe-plugin branch
$la-review:loupe PR #123
```

Loupe passes the requested textual scope to every external reviewer. The reviewers resolve and inspect that scope from the repository rather than receiving `review.diff` as their only context.

For the default scope, the active Codex session separately captures a verification snapshot containing staged tracked changes, unstaged tracked changes, and untracked non-ignored files. A file with both staged and unstaged changes can therefore appear in more than one diff segment. Binary changes are represented by compact Git markers rather than binary patch payloads. For a custom scope, the active session selects the corresponding Git diff used for verification. State the scope precisely when distinctions such as staged versus unstaged changes matter.

## Reviewer roles

Loupe launches every available reviewer in parallel:

| Reviewer           | Provider | Emphasis                                                                 |
|--------------------|----------|--------------------------------------------------------------------------|
| Claude Code Review | Claude   | Claude Code's code-review workflow                                       |
| Codex Review       | Codex    | General code review                                                      |
| Codex Correctness  | Codex    | Correctness, robustness, edge cases, side effects, and adversarial tests |
| Codex Design       | Codex    | Structure, interfaces, maintainability, duplication, and efficiency      |

The reviewers are instructed to review without changing the repository. Loupe does not replace human review of intent, product trade-offs, security-sensitive decisions, or the final patch. Its consolidated output is evidence to assess, not an instruction to apply every suggestion automatically.

## Cost and latency

One Loupe invocation can launch up to four separately billed or quota-consuming external reviewer sessions: one Claude review and three Codex reviews. It then uses the active Codex session for verification and consolidation. When only one provider CLI is available, fewer reviewers run and provider usage falls, but review diversity and coverage also decrease. Loupe does not provide a monetary estimate because pricing, plans, quotas, model behavior, repository size, and reasoning effort are provider- and account-dependent.

The reviewers run concurrently, so reviewer wall time is usually closer to the slowest reviewer than to the sum of all reviewer durations. Verification and consolidation happen afterward and add their own latency. The parallel reviewer batch has a 30-minute global timeout; focused verification in the active session can extend the total end-to-end time beyond that limit. Higher reasoning efforts generally trade additional time and provider usage for more analysis. A failed or timed-out request may still have consumed provider resources before it stopped.

## Failure and degradation modes

| Situation                                          | Result                                                                                                                                                                           |
|----------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| One provider executable is unavailable             | Reviewers from that provider are skipped; available reviewers still run with reduced coverage.                                                                                   |
| Neither `codex` nor `claude` is available          | No reviewer can launch, so Loupe stops and reports the missing capability.                                                                                                       |
| `jq` is unavailable                                | Each otherwise eligible reviewer records a launch failure because its provider output cannot be extracted safely.                                                                |
| A provider returns invalid output or exits nonzero | That reviewer is marked failed with captured diagnostics; successful reviewer output remains usable.                                                                             |
| One or more reviewers exceed the global timeout    | Unfinished process groups are terminated, completed results remain usable, and the final review explains the latest captured output instead of reporting only `Timed out`.       |
| Reviewers disagree                                 | The active session checks each claim independently. Supported claims remain findings; duplicates are linked; rejected or unresolved claims remain visible as `Unsure`.           |
| Reviewer JSON is truncated or malformed            | The active session reads the exact `reviewers.json` artifact. If that copy is also unusable, it stops rather than inventing results and reports the retained artifact directory. |
| Verification is blocked                            | Loupe reports the blocker and retains diagnostic artifacts instead of presenting unverified candidates as confirmed findings.                                                    |

Loupe keeps two files in a private temporary directory while it works:

- `review.diff` is the captured verification diff used by the active Codex session.
- `reviewers.json` is the exact structured runner output, including reviewer stdout and stderr.

Claude also records its assigned reviewer session under its normal local configuration tree so truncated findings can be recovered when necessary. Codex reviewers are launched as ephemeral sessions. After a successful review with no timeout or unexpected blocker, Loupe removes its two artifacts and their temporary directory. It retains the directory and reports its path when a timeout, malformed result, verification blocker, or another unexpected problem requires diagnosis or recovery.

## Configure reasoning effort

Claude reviewers use `medium` reasoning effort and Codex reviewers use `high` by default. Provider-wide and reviewer-specific configuration uses these stable keys:

| Key                  | Persistent environment variable   |
|----------------------|-----------------------------------|
| `claude`             | `LOUPE_EFFORT_CLAUDE`             |
| `codex`              | `LOUPE_EFFORT_CODEX`              |
| `claude-code-review` | `LOUPE_EFFORT_CLAUDE_CODE_REVIEW` |
| `codex-review`       | `LOUPE_EFFORT_CODEX_REVIEW`       |
| `codex-correctness`  | `LOUPE_EFFORT_CODEX_CORRECTNESS`  |
| `codex-design`       | `LOUPE_EFFORT_CODEX_DESIGN`       |

Export the variables normally, or persist them for Codex-launched commands in `~/.codex/config.toml`:

```toml
[shell_environment_policy]
set = { LOUPE_EFFORT_CLAUDE = "high", LOUPE_EFFORT_CODEX = "medium", LOUPE_EFFORT_CODEX_DESIGN = "xhigh" }
```

For a one-off override, include the desired effort in the invocation:

```text
$la-review:loupe last commit; high Claude effort, medium Codex effort
$la-review:loupe uncommitted changes; xhigh Codex Design effort
```

One-off requests take precedence over persistent environment settings, and reviewer-specific values take precedence over provider-wide values within the same layer. Claude accepts `low`, `medium`, `high`, `xhigh`, and `max`. Codex accepts `minimal`, `low`, `medium`, `high`, `xhigh`, `max`, and `ultra`.

## Use Loupe during development

Run deterministic checks before Loupe so the external reviewers can spend their effort on correctness, design, and other contextual judgment. This repository's [AI-supported development guide](ai_supported_development.md) recommends Loupe before committing every non-trivial change and describes how review fits into the wider enforcement ladder.

A practical sequence is:

1. Inspect the intended review scope and remove unrelated changes.
2. Run the applicable formatters, linters, type checks, and tests.
3. Invoke Loupe for the exact uncommitted change, commit, range, branch, or pull request.
4. Resolve or consciously reject every actionable finding.
5. Perform the final human review, optionally staging accepted diff hunks or files individually.
