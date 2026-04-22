# Mavka Plugin for Claude Code

A Claude Code plugin that gives your AI assistant persistent memory across sessions.
Stores decisions, findings, errors, and patterns with semantic search and enforced
atomization — so context is never lost when conversations end or compress.

## Prerequisites

You need a running Mavka instance (API only — no MCP server required). Set up from the
[mavka](https://github.com/mineralogy-rocks/mavka) repository:

```bash
git clone https://github.com/mineralogy-rocks/mavka.git
cd mavka
docker-compose up -d
```

## Install

```bash
claude plugin install github:mineralogy-rocks/mavka-plugin
export MAVKA_API_URL=https://mavka.example.com
```

On session start, the plugin maintains a stable symlink at `~/.claude/skills/mavka`
pointing at the current plugin cache root. Skills and the CLI are always accessed via
this stable path, so one allowlist rule in your user settings survives every plugin
upgrade.

### One-time settings

Add the following block to whichever Claude Code settings file you use —
`~/.claude/settings.json` (user) or `<project>/.claude/settings.local.json` (project).
Merge with your existing `permissions` block if you already have one. Replace
`<your-home>` with your actual home directory (e.g. `/Users/alice`); tilde-shorthand
works for `Bash` rules but `Read` rules need the absolute path.

```json
{
  "permissions": {
    "allow": [
      "Bash(~/.claude/skills/mavka/.claude/bin/mavka:*)",
      "Read(//<your-home>/.claude/plugins/cache/mineralogy-rocks/mavka/**)"
    ],
    "ask": [
      "Bash(~/.claude/skills/mavka/.claude/bin/mavka logout:*)"
    ]
  }
}
```

- `Bash(...mavka:*)` — allows every Mavka CLI subcommand (entry, task, plan, search,
  tag, login) without prompting. The stable symlink makes the literal command string
  identical across plugin upgrades, so this one rule lives forever.
- `Read(//<home>/.claude/plugins/cache/mineralogy-rocks/mavka/**)` — allows Claude
  to read the skill protocol and rule files without prompting. The leading `//` is
  Claude Code's canonical path format for Read rules. We match the plugin cache
  directly because Claude Code's Read matcher resolves symlinks **before** pattern
  matching — so a symlink-based rule (`Read(~/.claude/skills/mavka/**)`) never
  matches. The `**` wildcard absorbs the version directory, so this rule survives
  every plugin upgrade.
- `Bash(...mavka logout:*)` — keeps `logout` on the `ask` list because it revokes
  tokens.

Restart your Claude Code session after editing settings so the new rules take effect.

### Login

Ask Claude "log me in to Mavka" (or run the CLI directly). The skill's Auth Protocol
registers an OAuth2 client, opens your browser for GitHub auth, and stores bearer +
refresh tokens at `~/.config/mavka/credentials.json` (mode 600). Re-running login
reuses the registered client — no duplicate rows.

### Local development

```bash
claude --plugin-dir /path/to/mavka-plugin
```

## Configuration

Set `MAVKA_API_URL` in your shell profile to skip the prompt on each login:

```bash
export MAVKA_API_URL=http://mavka.local:81
```

## What the plugin does

The plugin acts as a middleware layer between the AI agent and Mavka. It enforces
**atomization** — breaking complex knowledge into discrete, standalone,
individually-searchable entries — before anything is written. It also ensures
duplicate checks, tag reuse, correct kind classification, and standalone BLUF summaries.

All Mavka operations go through the single CLI at
`~/.claude/skills/mavka/.claude/bin/mavka` — a stable path maintained by the
SessionStart hook. It calls the REST API directly using a bearer token refreshed
automatically on expiry. Any agent (Claude Code, Codex, Gemini, …) can invoke it with
the same credentials.

When a plan is approved in `/plan` mode, the PostToolUse hook delegates the
atomize-and-save to a `mavka-worker` background subagent, so the main session stays
responsive and plan entries land in Mavka seconds later.

## Skill

| Skill | Description |
|-------|-------------|
| `/mavka` | Unified middleware for all Mavka operations — stores entries, saves plans, searches knowledge, manages tasks |

The skill routes by intent:

| Intent | Protocol |
|--------|----------|
| Store knowledge ("remember this", "log this") | Write Protocol |
| Save an approved plan | Plan Protocol |
| Search/recall ("what do we know about X") | Search Protocol |
| Create/update tasks | Task Protocol |
| Log in / log out | Auth Protocol |

## Subagent

| Agent | Description |
|-------|-------------|
| `mavka-worker` | Background worker that owns multi-step Mavka CLI work (plan saves, bulk writes, linked searches). The plan-approved hook delegates to it with `run_in_background=true` so the main session is never interrupted. |

## Hooks

| Event | Matcher | What it does |
|-------|---------|-------------|
| **SessionStart** | — | Maintains the stable `~/.claude/skills/mavka` symlink pointing at the current plugin cache. Idempotent — no-op if the link is already correct. |
| **PostToolUse** | `ExitPlanMode` | Writes the approved plan to a temp file and emits `additionalContext` telling the main session to spawn `Task(subagent_type=mavka-worker, run_in_background=true)` with the plan path. The worker handles atomization and `mavka plan save` in the background. |

## Plugin structure

```
.claude-plugin/
  plugin.json                          # Plugin manifest
  marketplace.json                     # Marketplace listing
.claude/
  skills/mavka/
    SKILL.md                           # Routing + atomization rules + quality checklist
    references/
      write-protocol.md                # Store entries (findings, decisions, errors, etc.)
      plan-protocol.md                 # Save approved plans with machine-plan entries
      search-protocol.md               # Search and recall past knowledge
      task-protocol.md                 # Task lifecycle management
      auth-protocol.md                 # Login lifecycle (PKCE flow, token refresh, logout)
  agents/
    mavka-worker.md                    # Background worker for plan saves and bulk Mavka work
  hooks/
    hooks.json                         # SessionStart symlink maintainer + PostToolUse plan handoff
    on_session_start.sh                # Maintains ~/.claude/skills/mavka symlink
    on_plan_approved.sh                # Bash launcher — redirects output to log, execs Python
    _plan_auto_save.py                 # Plumbing — extracts plan, emits Task-delegation reminder
  rules/
    atomize.md                         # Shared atomization rules
    api.md                             # CLI command reference
    memory.md                          # When to use what
  bin/
    mavka                              # Executable launcher (exec python3 cli.py "$@")
    cli.py                             # Unified CLI — all subcommands live here
    _auth.py                           # Credentials, token refresh, authed HTTP
    _common.py                         # Output formatting and shared helpers
```

## How it works

Mavka stores knowledge as **entries** — discrete units covering one topic each.
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

## Why the stable symlink

Claude Code plugins install into a version-specific cache at
`~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`. Using that concrete path
in skill commands would break allowlist rules on every plugin upgrade, and using
`${CLAUDE_PLUGIN_ROOT}` triggers Claude Code's "Contains expansion" security prompt on
every call. Maintaining a stable symlink (`~/.claude/skills/mavka`) under the user's
home directory gives us one path that:

- Is identical in every skill invocation (no variable expansion → no security gate)
- Survives plugin upgrades (the SessionStart hook relinks to the new cache)
- Maps cleanly onto a single set of allowlist rules in user settings

This is the pattern used by [garrytan/gstack](https://github.com/garrytan/gstack) and
[Ahacad/gstack](https://github.com/Ahacad/gstack).

## License

MIT
