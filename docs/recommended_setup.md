# Recommended Codex setup

These optional user-level instructions and configuration defaults complement the marketplace plugins across all projects. Review and adapt them to your own security requirements, tools, and working style.

For a new empty directory, follow the [New repository setup recipe](new_repo_recipe.md) to group user/repository configuration and permanent instructions before the activation handoff. These settings are optional across all Codex use; once adopting this complete setup, apply the selected settings consistently unless an explicit user decision changes them.

## User-level instructions

This repository includes a recommended [user-level AGENTS.md file](../AGENTS_user.md) with global Codex instructions that complement the plugins. Inspect the existing file first. Show the exact proposed diff and obtain explicit authorization before changing user-level instructions, config, or persistent rules; preserve stronger existing guidance, model choices, and unrelated settings. Prior approval of that same exact change remains valid: do not ask again unnecessarily. For a genuinely absent file, a reviewed copy can use:

```bash
cp AGENTS_user.md ~/.codex/AGENTS.md  # <-- CAUTION: Check first whether you have an existing AGENTS.md that might get clobbered!
```

Codex applies `~/.codex/AGENTS.md` as user-level guidance across all your projects. If that file already exists, merge the recommendations into it instead of overwriting your existing instructions.

## User-level configuration

The following generic defaults are a practical starting point for `~/.codex/config.toml`:

```toml
approval_policy = "on-request"
sandbox_mode = "workspace-write"
model_reasoning_effort = "medium"
plan_mode_reasoning_effort = "high"

[history]
persistence = "save-all"
max_bytes = 52428800
```

You can additionally opt in to live web search and outbound network access for sandboxed commands. Merge these entries into the appropriate locations rather than duplicating TOML tables; `web_search` is a top-level setting.

```toml
web_search = "live"

[sandbox_workspace_write]
network_access = true
```

Command network access allows package managers such as `pip`, `uv`, `npm`, and `cargo` to query registries and download dependencies. Live web search and command network access both increase exposure to untrusted external content, so enable them deliberately.

You can also opt in to pinning a preferred model with the following top-level setting:

```toml
model = "gpt-5.6-sol"
```

Use `/model` within Codex to select an available model and add or update this setting automatically, especially when switching to a newer model.

For pre-commit projects include its normal `~/.cache/pre-commit` root, even outside Python. For Python development, add these writable roots to the same `[sandbox_workspace_write]` table to let `pip` and `uv` reuse their caches and let `uv` manage downloaded tools and Python installations:

```toml
writable_roots = [
  "~/.cache/gh",
  "~/.cache/pip",
  "~/.cache/pre-commit",
  "~/.cache/uv",
  "~/.local/share/uv",
]
```

The following is one possible TUI setup for a detailed status line and informative terminal title:

```toml
[tui]
status_line = ["project-name", "git-branch", "model-with-reasoning", "run-state", "task-progress", "context-used", "total-input-tokens", "total-output-tokens", "five-hour-limit", "weekly-limit", "thread-title", "session-id"]
terminal_title = ["activity", "project-name"]
```

See [Marketplace plugin installation](installation.md) if the `la-review` and `toolkit` plugins are not installed yet. After completing the user-level setup, continue with [Language-agnostic project setup](project_setup_agnostic.md) for each repository and then [Python project setup](project_setup_python.md) when applicable.

## Project trust and activation

Project `.codex/config.toml` is loaded only for trusted projects. Inspect current trust before claiming that a new repository's config is active. If a trust addition is needed, show the exact resolved path and proposed user-config diff and obtain explicit approval before adding it, preserving every other setting:

```toml
[projects."/ABSOLUTE/PATH/TO/REPOSITORY"]
trust_level = "trusted"
```

A repository writable_roots list replaces the user/system list, so repeat every required external root in the repository example, including pre-commit. Declaring a path and initializing its directory are separate concerns: a managed environment can still expose a missing cache read-only until permission/initialization is resolved. On a cache failure, stop and notify the user; obtain the required execution approval for the normal cache instead of inventing UV_CACHE_DIR or a temporary cache workaround. Do not silently weaken the sandbox.

Follow the entry recipe's activation checkpoint after applicable plugin/user/repository configuration and permanent AGENTS.md are ready. Save decisions and exact next steps in the ignored journal; end the turn for a normal host restart/resume, then verify `/debug-config`, `/status`, loaded instructions, and the installation guide's non-destructive explicit skill checks. Treat a refreshed marketplace, an installed plugin, and guidance loaded by the running session as distinct facts. Use a fresh chat with the journal if resume is stale. See the official [configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference), [developer settings](https://learn.chatgpt.com/docs/developer-settings), [skills](https://learn.chatgpt.com/docs/build-skills), and [plugins](https://learn.chatgpt.com/docs/plugins) documentation.
