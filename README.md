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
"${CLAUDE_PLUGIN_ROOT}/.claude/bin/palantir" login
"${CLAUDE_PLUGIN_ROOT}/.claude/bin/palantir" perms install
```

That's it. Login registers an OAuth2 client, opens your browser for GitHub auth,
and stores bearer + refresh tokens at `~/.config/palantir/credentials.json` (mode 600).
Re-running login reuses the registered client — no duplicate client rows.

`perms install` appends a managed allow/ask block to `~/.claude/settings.json` so
Claude Code doesn't prompt on every CLI call. It's idempotent (safe to re-run) and
scope-aware (`--scope project|local`). Run `perms status` to see what's installed
and `perms uninstall` to remove it.

For local development/testing without installing:

```bash
claude --plugin-dir /path/to/palantir-plugin
```

## Configuration

Set `PALANTIR_API_URL` in your shell profile to skip the prompt on each login:

```bash
export PALANTIR_API_URL=http://palantir.local:81
```

## What the plugin does

The plugin acts as a middleware layer between the AI agent and Palantir. It enforces
**atomization** — breaking complex knowledge into discrete, standalone,
individually-searchable entries — before anything is written. It also ensures
duplicate checks, tag reuse, correct kind classification, and standalone BLUF summaries.

All Palantir operations go through a single CLI at `${CLAUDE_PLUGIN_ROOT}/.claude/bin/palantir`
that calls the REST API directly using a bearer token refreshed automatically on expiry. Any
agent (Claude Code, Codex, Gemini, …) can invoke it with the same credentials.

When a plan is approved in `/plan` mode, an async hook fires `claude -p` in the
background to auto-save the plan via the palantir skill's Plan Protocol — the
parent session is never interrupted and the plan lands in Palantir seconds later.

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
| **PostToolUse** | `ExitPlanMode` | Fires `async: true`; runs `claude -p` in the background so a sub-agent invokes the palantir skill's Plan Protocol on the approved plan. Emits an OS notification at start and at completion (success or failure). No interruption to the parent session. Set `PALANTIR_HOOK_NOTIFY=0` to silence notifications. |

## Plugin structure

```
.claude-plugin/
  plugin.json                          # Plugin manifest
  marketplace.json                     # Marketplace listing
.claude/
  skills/palantir/
    SKILL.md                           # Routing + atomization rules + quality checklist
    references/
      write-protocol.md                # Store entries (findings, decisions, errors, etc.)
      plan-protocol.md                 # Save approved plans with machine-plan entries
      search-protocol.md               # Search and recall past knowledge
      task-protocol.md                 # Task lifecycle management
      auth-protocol.md                 # Login lifecycle (PKCE flow, token refresh, logout)
  hooks/
    hooks.json                         # Async hook (PostToolUse on ExitPlanMode)
    on_plan_approved.sh                # Bash launcher — redirects output to log, execs Python
    _plan_auto_save.py                 # Plumbing — extracts plan from payload, runs claude -p
  rules/
    atomize.md                         # Shared atomization rules
    api.md                             # CLI command reference
    memory.md                          # When to use what
  bin/
    palantir                           # Executable launcher (exec python3 cli.py "$@")
    cli.py                             # Unified CLI — all subcommands live here
    _auth.py                           # Credentials, token refresh, authed HTTP
    _common.py                         # Output formatting and shared helpers
```

Permissions live in the user's `~/.claude/settings.json`, not in the plugin — install via
`palantir perms install`. See [Install + Login](#install--login).

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

The plugin already wires the ExitPlanMode hook on install. If you want plan
auto-save without the full plugin, point your `.claude/settings.local.json` at
a checkout of `on_plan_approved.sh`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "ExitPlanMode",
        "hooks": [
          {
            "type": "command",
            "command": "/abs/path/to/palantir-plugin/.claude/hooks/on_plan_approved.sh",
            "async": true
          }
        ]
      }
    ]
  }
}
```

`async: true` runs the hook fire-and-forget — no wake-up, no interruption. The
script reads the hook payload on stdin, extracts the approved plan, and launches
`claude -p` in the background so a sub-agent runs the palantir skill's Plan
Protocol. Logs at `$TMPDIR/palantir-plan-hook.log`.

## Changes from v2

- **Unified CLI**: Replaced the MCP server dependency (and, in v3.1, the seven per-domain bash
  wrappers) with a single `palantir` CLI covering entry / task / plan / search / tag / login /
  logout / perms. Any agent (Claude Code, Codex, Gemini, …) can invoke it directly.
- **No MCP server**: Removed `palantir-mcp` container from the Palantir stack — one fewer
  service, ~30x fewer tool-surface tokens.
- **Auto token refresh**: `_auth.py` refreshes the bearer token on 401 transparently.
- **Managed permission install**: `palantir perms install` writes the allow/ask block into
  the user's `~/.claude/settings.json` (idempotent). Plugin-shipped `.claude/settings.json`
  is not loaded by Claude Code, so the installer is the supported path.
- **True background plan auto-save**: ExitPlanMode hook uses `async: true` + `claude -p` to
  run the palantir skill's Plan Protocol in a headless sub-agent. Previous behavior
  (`asyncRewake: true` + reminder) is replaced — parent session is never woken.

## License

MIT
