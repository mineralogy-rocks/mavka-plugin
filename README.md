# Palantir Plugin for Claude Code

A Claude Code plugin that gives your AI assistant persistent memory across sessions.
Stores decisions, findings, errors, and patterns with semantic search and enforced
atomization — so context is never lost when conversations end or compress.

## Prerequisites

You need a running Palantir instance (API only — no MCP server required). Set up from the
[palantir](https://github.com/mineralogy-rocks/palantir) repository:

```bash
git clone https://github.com/mineralogy-rocks/palantir.git
cd palantir
docker-compose up -d
```

## Install + Login

```bash
claude plugin install github:mineralogy-rocks/palantir-plugin
export PALANTIR_API_URL=https://palantir.example.com
"${CLAUDE_PLUGIN_DIR}/.claude/bin/palantir_login.sh"
```

That's it. The login script registers an OAuth2 client, opens your browser for GitHub auth,
and stores bearer + refresh tokens at `~/.config/palantir/credentials.json` (mode 600).
Re-running login reuses the registered client — no duplicate client rows.

For local development/testing without installing:

```bash
claude --plugin-dir /path/to/palantir-plugin
```

## Configuration

Set `PALANTIR_API_URL` in your shell profile to skip the prompt on each login:

```bash
export PALANTIR_API_URL=http://palantir.local:81
```

Optionally set a project scope:

```bash
export PALANTIR_PROJECT_NAME=my-project
```

## What the plugin does

The plugin acts as a middleware layer between the AI agent and Palantir. It enforces
**atomization** — breaking complex knowledge into discrete, standalone,
individually-searchable entries — before anything is written. It also ensures
duplicate checks, tag reuse, correct kind classification, and standalone BLUF summaries.

All Palantir operations go through bash wrappers in `${CLAUDE_PLUGIN_DIR}/.claude/bin/` that
call the REST API directly using a bearer token refreshed automatically on expiry.

When a plan is approved in `/plan` mode, an async hook sends a deferred reminder
to save the plan to Palantir during a natural pause — implementation starts immediately.

## Skill

| Skill | Description |
|-------|-------------|
| `/palantir` | Unified middleware for all Palantir operations — stores entries, saves plans, searches knowledge, manages tasks |

The skill routes by intent:

| Intent | Protocol |
|--------|----------|
| Store knowledge ("remember this", "log this") | Write Protocol |
| Save an approved plan | Plan Protocol |
| Search/recall ("what do we know about X") | Search Protocol |
| Create/update tasks | Task Protocol |

## Hook

| Event | Matcher | What it does |
|-------|---------|-------------|
| **PostToolUse** | `ExitPlanMode` | Async deferred reminder to save the approved plan to Palantir |

## Plugin structure

```
.claude-plugin/
  plugin.json                          # Plugin manifest (v3.0.0)
  marketplace.json                     # Marketplace listing
.claude/
  settings.json                        # Bash permission allowlist for wrappers
  skills/palantir/
    SKILL.md                           # Routing + atomization rules + quality checklist
    references/
      write-protocol.md                # Store entries (findings, decisions, errors, etc.)
      plan-protocol.md                 # Save approved plans with machine-plan entries
      search-protocol.md               # Search and recall past knowledge
      task-protocol.md                 # Task lifecycle management
  hooks/
    hooks.json                         # Async hook (PostToolUse on ExitPlanMode)
  rules/
    atomize.md                         # Shared atomization rules
    api.md                             # Wrapper command reference
    memory.md                          # When to use what
bin/
  _auth.sh                             # Auth library (sourced, not executed)
  _common.sh                           # Common utilities (sourced, not executed)
  palantir_login.sh                    # PKCE authorization-code login
  palantir_logout.sh                   # Revoke tokens + delete credentials
  palantir_entry.sh                    # Entry CRUD (create, bulk, get, list)
  palantir_search.sh                   # Semantic search (knowledge, tasks)
  palantir_plan.sh                     # Plan management (save, get, list)
  palantir_task.sh                     # Task management (create, get, update, list)
  palantir_tag.sh                      # Tag management (list, create, delete)
```

## How it works

Palantir stores knowledge as **entries** — discrete units covering one topic each.
Each entry has:
- A **BLUF** (Bottom Line Up Front) — 1-2 sentence summary
- **Content** — full context (100-400 words)
- **Kind** — `decision`, `finding`, `error`, `pattern`, `note`, `review`, or `machine-plan`
- **Tags** — for categorization and retrieval

Entries are embedded for semantic search using dual embeddings (content + BLUF)
merged via Reciprocal Rank Fusion.

**Plans** store approved plans with atomized `machine-plan` entries.

**Tasks** group related entries and track work status
(`planning` -> `ready` -> `wip` -> `review` -> `done`).

## Manual hook setup (without the plugin)

If you want plan persistence without installing the full plugin, add to your
project's `.claude/settings.local.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "ExitPlanMode",
        "hooks": [
          {
            "type": "command",
            "command": "sleep 5 && echo 'Plan approved. Invoke the palantir skill to save it during a natural pause.' >&2 && exit 2",
            "asyncRewake": true
          }
        ]
      }
    ]
  }
}
```

The hook runs in the background (`asyncRewake`). After 5 seconds it exits with
code 2, which wakes Claude with a system reminder. By then the agent is already
implementing and treats the save as a deferred task.

## Changes from v2

- **Bash wrappers**: Replaced MCP server dependency with five bash wrappers that call the
  REST API directly (`palantir_entry.sh`, `palantir_search.sh`, `palantir_plan.sh`,
  `palantir_task.sh`, `palantir_tag.sh`) plus auth helpers (`palantir_login.sh`,
  `palantir_logout.sh`)
- **No MCP server**: Removed `palantir-mcp` container from the Palantir stack — one fewer
  service, ~30x fewer tool-surface tokens
- **Auto token refresh**: `_auth.sh` refreshes the bearer token on 401 transparently
- **Permission allowlist**: `settings.json` pre-approves wrapper calls; login/logout still prompt
- **Version**: 3.0.0 (breaking — `.mcp.json` configuration no longer required)

## License

MIT
