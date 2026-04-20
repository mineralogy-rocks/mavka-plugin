# Palantir API Reference

All Palantir operations go through bash wrappers in `${CLAUDE_PLUGIN_DIR}/.claude/bin/`. Use these
wrappers exclusively — do not call the REST API directly with curl.

## Wrapper Commands

### Tags

```bash
# Always call before creating entries to reuse existing tags
"${CLAUDE_PLUGIN_DIR}/.claude/bin/palantir_tag.sh" list [--q <prefix>] [--limit <n>]
"${CLAUDE_PLUGIN_DIR}/.claude/bin/palantir_tag.sh" create --name <name>
```

### Search

```bash
# Semantic search across knowledge entries
"${CLAUDE_PLUGIN_DIR}/.claude/bin/palantir_search.sh" knowledge \
  --query <q> [--kind <k>] [--tag <name>]... [--mode hybrid|content|bluf] [--limit <n>] [--raw]

# Search tasks by title
"${CLAUDE_PLUGIN_DIR}/.claude/bin/palantir_search.sh" tasks \
  --query <q> [--status <s>] [--tag <name>]... [--due-lte <d>] [--due-gte <d>] [--limit <n>] [--raw]
```

### Entries

```bash
# Create a single entry
"${CLAUDE_PLUGIN_DIR}/.claude/bin/palantir_entry.sh" create \
  --bluf <text> --content <text> [--kind <k>] [--tag <name>]... [--task-id <id>]

# Create with long content via stdin (avoids argv length limits)
echo "..." | "${CLAUDE_PLUGIN_DIR}/.claude/bin/palantir_entry.sh" create \
  --bluf <text> --stdin [--kind <k>] [--tag <name>]...

# Bulk create from JSON file: {"entries":[{content,bluf,kind,tags},...]}
"${CLAUDE_PLUGIN_DIR}/.claude/bin/palantir_entry.sh" bulk --file <path>

# Get a single entry by ID
"${CLAUDE_PLUGIN_DIR}/.claude/bin/palantir_entry.sh" get <id>

# List entries with optional filters
"${CLAUDE_PLUGIN_DIR}/.claude/bin/palantir_entry.sh" list \
  [--kind <k>] [--tag <name>]... [--plan-id <id>] [--task-id <id>] [--limit <n>] [--offset <n>]
```

### Plans

```bash
# Save an approved plan with atomized entries
"${CLAUDE_PLUGIN_DIR}/.claude/bin/palantir_plan.sh" save \
  --title <t> --content <text> --entries-file <path> [--tag <name>]... [--dedupe-key <k>]

# Get a plan by ID
"${CLAUDE_PLUGIN_DIR}/.claude/bin/palantir_plan.sh" get <id>

# List plans
"${CLAUDE_PLUGIN_DIR}/.claude/bin/palantir_plan.sh" list [--query <q>] [--tag <name>]... [--limit <n>]
```

### Tasks

```bash
# Create a task
"${CLAUDE_PLUGIN_DIR}/.claude/bin/palantir_task.sh" create \
  --title <t> [--status <s>] [--tag <name>]... [--due-date <d>]

# Get a task by ID
"${CLAUDE_PLUGIN_DIR}/.claude/bin/palantir_task.sh" get <id>

# Update a task
"${CLAUDE_PLUGIN_DIR}/.claude/bin/palantir_task.sh" update <id> \
  [--status <s>] [--title <t>] [--tag <name>]... [--due-date <d>]

# List tasks
"${CLAUDE_PLUGIN_DIR}/.claude/bin/palantir_task.sh" list \
  [--status <s>] [--tag <name>]... [--due-lte <d>] [--due-gte <d>] [--limit <n>]
```

### Auth

Auth is handled by the palantir skill's **Auth Protocol** — do not prompt the user to run these
commands. When a wrapper prints `[PALANTIR_LOGIN_REQUIRED]`, or when the user says "log me in",
invoke the palantir skill and follow `references/auth-protocol.md`. The skill runs
`palantir_login.sh` in the background on the user's behalf and surfaces only the authorization
URL they need to click. Logout stays on the `ask` permission list because it revokes tokens.

```bash
# Invoked by the skill, not by the user:
"${CLAUDE_PLUGIN_DIR}/.claude/bin/palantir_login.sh"     # allowed — run by the Auth Protocol
"${CLAUDE_PLUGIN_DIR}/.claude/bin/palantir_logout.sh"    # asks — user confirms each time
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
- `PALANTIR_API_URL` — API base URL (required if not stored in credentials.json)
- `PALANTIR_CONFIG_DIR` — override default `~/.config/palantir`
