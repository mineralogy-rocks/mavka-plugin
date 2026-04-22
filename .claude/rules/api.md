# Mavka API Reference

All Mavka operations go through a single CLI at `~/.claude/skills/mavka/.claude/bin/mavka`. Use
it exclusively — do not call the REST API directly with curl. Any agent (Claude Code, Codex,
Gemini, etc.) can invoke the same CLI; credentials persist at `~/.config/mavka/credentials.json`
so one login covers every agent on the same machine.

The path is a stable symlink maintained by the plugin's SessionStart hook
(`on_session_start.sh`). It always points at the current plugin cache root, so a single
`Bash(~/.claude/skills/mavka/.claude/bin/mavka:*)` allow rule in `~/.claude/settings.json`
survives every plugin upgrade. Never call the CLI via `${CLAUDE_PLUGIN_ROOT}` — Claude Code's
security gate prompts on any `${VAR}` expansion in a Bash command, regardless of allow rules.

## CLI Commands

### Tags

```bash
# Always call before creating entries to reuse existing tags
~/.claude/skills/mavka/.claude/bin/mavka tag list [--q <prefix>] [--limit <n>]
~/.claude/skills/mavka/.claude/bin/mavka tag create --name <name>
```

### Search

```bash
# Semantic search across knowledge entries
~/.claude/skills/mavka/.claude/bin/mavka search knowledge \
  --query <q> [--kind <k>] [--tag <name>]... [--mode hybrid|content|bluf] [--limit <n>] [--raw]

# Search tasks by title
~/.claude/skills/mavka/.claude/bin/mavka search tasks \
  --query <q> [--status <s>] [--tag <name>]... [--due-lte <d>] [--due-gte <d>] [--limit <n>] [--raw]
```

### Entries

```bash
# Create a single entry
~/.claude/skills/mavka/.claude/bin/mavka entry create \
  --bluf <text> --content <text> [--kind <k>] [--tag <name>]... [--task-id <id>]

# Create with long content via stdin (avoids argv length limits)
echo "..." | ~/.claude/skills/mavka/.claude/bin/mavka entry create \
  --bluf <text> --stdin [--kind <k>] [--tag <name>]...

# Bulk create from JSON file: {"entries":[{content,bluf,kind,tags},...]}
~/.claude/skills/mavka/.claude/bin/mavka entry bulk --file <path>

# Get a single entry by ID
~/.claude/skills/mavka/.claude/bin/mavka entry get <id>

# List entries with optional filters
~/.claude/skills/mavka/.claude/bin/mavka entry list \
  [--kind <k>] [--tag <name>]... [--plan-id <id>] [--task-id <id>] [--limit <n>] [--offset <n>]
```

### Plans

```bash
# Save an approved plan with atomized entries
~/.claude/skills/mavka/.claude/bin/mavka plan save \
  --title <t> --content <text> --entries-file <path> [--tag <name>]... [--dedupe-key <k>]

# Get a plan by ID
~/.claude/skills/mavka/.claude/bin/mavka plan get <id>

# List plans
~/.claude/skills/mavka/.claude/bin/mavka plan list [--query <q>] [--tag <name>]... [--limit <n>]
```

### Tasks

```bash
# Create a task
~/.claude/skills/mavka/.claude/bin/mavka task create \
  --title <t> [--status <s>] [--tag <name>]... [--due-date <d>]

# Get a task by ID
~/.claude/skills/mavka/.claude/bin/mavka task get <id>

# Update a task
~/.claude/skills/mavka/.claude/bin/mavka task update <id> \
  [--status <s>] [--title <t>] [--tag <name>]... [--due-date <d>]

# List tasks
~/.claude/skills/mavka/.claude/bin/mavka task list \
  [--status <s>] [--tag <name>]... [--due-lte <d>] [--due-gte <d>] [--limit <n>]
```

### Auth

Auth is handled by the mavka skill's **Auth Protocol** — do not prompt the user to run these
commands. When any CLI call prints `[MAVKA_LOGIN_REQUIRED]`, or when the user says "log me in",
invoke the mavka skill and follow `references/auth-protocol.md`. The skill runs `mavka login`
in the background on the user's behalf and surfaces only the authorization URL they need to click.
Logout stays on the `ask` permission list because it revokes tokens.

```bash
# Invoked by the skill, not by the user:
~/.claude/skills/mavka/.claude/bin/mavka login     # allowed — run by the Auth Protocol
~/.claude/skills/mavka/.claude/bin/mavka logout    # asks — user confirms each time
```

## Entry Kinds
`decision` | `finding` | `error` | `pattern` | `note` | `review` | `machine-plan`

## Task Statuses
`planning` | `ready` | `wip` | `review` | `done` | `blocked` | `archived`

## Search Modes
- `hybrid` (default) — fuses content + BLUF embeddings via Reciprocal Rank Fusion
- `content` — content embeddings only
- `bluf` — BLUF embeddings only

## Environment Variables
- `MAVKA_API_URL` — API base URL (required if not stored in credentials.json)
- `MAVKA_CONFIG_DIR` — override default `~/.config/mavka`

## Agent-agnostic invocation

Other agents can call the same CLI via the same stable path:

```bash
~/.claude/skills/mavka/.claude/bin/mavka <group> <verb> [flags]
```

Or directly against the Python entrypoint if needed:

```bash
python3 ~/.claude/skills/mavka/.claude/bin/cli.py <group> <verb> [flags]
```
