# Loupe code review

Loupe runs several independent external reviewers against one Git review scope, then uses the active Codex session to verify their candidate findings and combine them into one structured review. It is designed as the final judgment-oriented check after deterministic formatters, linters, type checks, and tests have passed.

Loupe is a skill in the `la-review` marketplace plugin. It does not modify files, stage changes, commit, or install dependencies during a review.

## Requirements

Install the `la-review` plugin as described in the [marketplace plugin installation guide](installation.md), then invoke Loupe from a Codex session opened in a Git repository.

Loupe requires Bash, Git, `jq`, and at least one supported external reviewer executable:

- `claude` enables the Claude Code Review reviewer.
- `codex` enables Codex Review, Codex Correctness, and Codex Design.

An unavailable provider is skipped rather than installed automatically. If neither provider is available, Loupe cannot perform a review. The external commands need access to their normal user-level state under locations such as `~/.claude/` and `~/.codex/`, so Codex asks for escalated sandbox permission before launching them. The [optional allow rule](installation.md#optional-auto-allow-the-loupe-review-script) avoids approving the bundled runner separately on every invocation.

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

Loupe passes the requested scope to every external reviewer. For the default scope, it also captures one verification snapshot containing staged tracked changes, unstaged tracked changes, and untracked non-ignored files. A file with both staged and unstaged changes can therefore appear in more than one diff segment. Binary changes are represented by compact Git markers rather than binary patch payloads.

For a custom scope, the active Codex session selects the corresponding Git diff used for verification. State the scope precisely when distinctions such as staged versus unstaged changes matter.

## Reviewer roles

Loupe launches every available reviewer in parallel:

| Reviewer           | Provider | Emphasis                                                                 |
|--------------------|----------|--------------------------------------------------------------------------|
| Claude Code Review | Claude   | Claude Code's code-review workflow                                       |
| Codex Review       | Codex    | General code review                                                      |
| Codex Correctness  | Codex    | Correctness, robustness, edge cases, side effects, and adversarial tests |
| Codex Design       | Codex    | Structure, interfaces, maintainability, duplication, and efficiency      |

The reviewers inspect the repository independently and are instructed to review without changing it. After they finish, the active Codex session checks each candidate against the captured diff and current source, runs focused local validation when useful, identifies duplicates, and retains uncertain or rejected claims as `Unsure` instead of silently discarding them.

The result is organized by reviewer and includes:

- a concise diff summary suitable as a starting point for a commit subject;
- each reviewer's status and elapsed time;
- continuously numbered findings with severity, location, evidence, impact, and a concrete recommendation;
- duplicate relationships between findings;
- failure or timeout details when a reviewer did not complete normally.

Loupe does not replace human review of intent, product trade-offs, security-sensitive decisions, or the final patch. Its consolidated output is evidence to assess, not an instruction to apply every suggestion automatically.

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

## Timeouts, partial failures, and artifacts

The bundled runner gives the parallel review batch a 30-minute timeout. An unavailable reviewer, launch failure, nonzero exit, or timeout does not prevent Loupe from using successful reviewer output. The final review reports the status of every reviewer that was eligible to run and explains captured failure or timeout evidence.

Loupe keeps two temporary artifacts while it works:

- `review.diff` is the captured verification diff.
- `reviewers.json` is the exact structured reviewer output.

After a successful review with no timeouts, Loupe removes both artifacts and their private temporary directory. It retains the directory and reports its path when a timeout, malformed result, verification blocker, or another unexpected problem requires diagnosis or recovery.

## Use Loupe during development

Run deterministic checks before Loupe so the external reviewers can spend their effort on correctness, design, and other contextual judgment. This repository's [AI-supported development guide](ai_supported_development.md) recommends Loupe before committing every non-trivial change and describes how review fits into the wider enforcement ladder.

A practical sequence is:

1. Inspect the intended review scope and remove unrelated changes.
2. Run the applicable formatters, linters, type checks, and tests.
3. Invoke Loupe for the exact uncommitted change, commit, range, branch, or pull request.
4. Resolve or consciously reject every actionable finding.
5. Perform the final human review, optionally staging accepted diff hunks or files individually.
