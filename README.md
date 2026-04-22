# Mavka Skill Pack for Claude Code

Persistent memory for Claude Code. Stores decisions, findings, errors, and
patterns with semantic search and enforced atomization — so context is never
lost when conversations end or compress.

## Prerequisites

- A running Mavka backend. Set up from the
  [mavka](https://github.com/mineralogy-rocks/mavka) repository with
  `docker-compose up -d`.
- Python 3.8+ on `PATH`.
- Claude Code (any recent version).

## Installation

```bash
git clone https://github.com/mineralogy-rocks/mavka-plugin.git ~/Repos/mavka-plugin
cd ~/Repos/mavka-plugin
./setup
```

- The repo can live anywhere — pick a stable dev location. `~/Repos/...` is
  just a suggestion; `./setup` records the absolute path you ran it from.
- `./setup` is idempotent. Safe to re-run after `git pull`.
- It creates two symlinks:
  - `~/.claude/skills/mavka` → `<repo>/skills/mavka`
  - `~/.claude/agents/mavka-worker.md` → `<repo>/agents/mavka-worker.md`
- It merges `permissions.allow` and a `PostToolUse` hook into
  `~/.claude/settings.json`. Existing settings are preserved — duplicates are
  deduped, unrelated keys are left alone.
- Restart Claude Code after install so the new settings take effect.

## Why this isn't a Claude Code plugin

Claude Code plugins can't ship subagents that do background work. The
subagent docs block `permissionMode` in plugin-shipped agent frontmatter for
security, and background subagents auto-deny anything not pre-approved. The
`mavka-worker` needs `Read(/tmp/…)` and `Bash(cat …)` access on every plan
save — which was silently denied under the plugin model even with matching
allow rules on the parent session.

User-level agents at `~/.claude/agents/` *can* set
`permissionMode: bypassPermissions`. That's the whole reason for the
gstack-style install model — inspired by
[garrytan/gstack](https://github.com/garrytan/gstack). The background worker
now runs silently with zero permission prompts. One-time setup, zero runtime
friction.

## Configuration

| Variable | Required | Purpose |
|---|---|---|
| `MAVKA_API_URL` | yes | API base URL, e.g. `http://mavka.local:81` |
| `MAVKA_CONFIG_DIR` | no | Overrides default `~/.config/mavka` |

Set them in your shell profile:

```bash
export MAVKA_API_URL=http://mavka.local:81
```

## Login

Ask Claude "log me in to Mavka". The skill's Auth Protocol runs the OAuth2
PKCE flow in the background and stores bearer + refresh tokens at
`~/.config/mavka/credentials.json` (mode 600). Re-running login reuses the
registered client — no duplicate rows.

## What this gives you

- Atomized knowledge entries — one topic per entry, semantic search,
  tag-based filtering.
- Approved plans captured automatically as `machine-plan` entries via a
  `PostToolUse`/`ExitPlanMode` hook.
- Tasks grouping related entries with status tracking
  (`planning` → `ready` → `wip` → `review` → `done`).
- Background plan saves via the `mavka-worker` agent — the main session
  never stalls.

## Components

| Skill | Description |
|---|---|
| `mavka` | Middleware for all Mavka operations — stores entries, saves plans, searches knowledge, manages tasks. |

| Agent | Description |
|---|---|
| `mavka-worker` | Background worker for plan saves and bulk Mavka work. Invoked via `Task(run_in_background=true)`; runs with `permissionMode: bypassPermissions`. |

| Hook | Event | What it does |
|---|---|---|
| `on_plan_approved.sh` | `PostToolUse` on `ExitPlanMode` | Writes the approved plan to `/tmp/mavka-plan-<sha>.md` and instructs the main session to delegate atomize-and-save to `mavka-worker`. |

## Migration from the old plugin

```bash
claude plugin uninstall mavka@mineralogy-rocks
rm -f ~/.claude/skills/mavka
rm -rf ~/.claude/plugins/cache/mineralogy-rocks/mavka
cd ~/Repos/mineralogy-rocks/mavka-plugin
./setup
# Restart Claude Code
```

Project-level allow rules in `.claude/settings.local.json` can be left as-is;
the new user-level rules in `~/.claude/settings.json` take effect
session-wide.

## Uninstall

```bash
./uninstall
```

Removes the two symlinks (only if they still point at this repo) and strips
the allow-rules and `PostToolUse` hook entries that `./setup` added from
`~/.claude/settings.json`. Any other settings you have are left untouched.

## Repo layout

```
mavka-plugin/
  README.md
  setup                          # bash installer (idempotent)
  setup.py                       # stdlib JSON merge/strip helper
  uninstall                      # bash reverser
  skills/mavka/                  # ← symlinked to ~/.claude/skills/mavka
    SKILL.md                     # routing + atomization checklist
    bin/
      mavka                      # exec python3 cli.py "$@"
      cli.py
      _auth.py
      _common.py
    references/
      write-protocol.md
      plan-protocol.md
      search-protocol.md
      task-protocol.md
      auth-protocol.md
  agents/
    mavka-worker.md              # symlinked to ~/.claude/agents/; permissionMode: bypassPermissions
  rules/
    atomize.md
    api.md
    memory.md
  hooks/
    on_plan_approved.sh          # registered in ~/.claude/settings.json by ./setup
    _plan_auto_save.py
  settings/
    template.json                # merged into ~/.claude/settings.json
```

## License

MIT
