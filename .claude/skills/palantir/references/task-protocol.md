# Task Protocol

Tasks are work containers that group related entries and track lifecycle.

> **Required reading**: `../../rules/atomize.md` (for entry creation), `../../rules/api.md` (wrapper command reference)

## Creating a task

1. Search for existing tasks first. If a matching task already exists, tell the user instead
   of creating a duplicate.
   ```bash
   "${CLAUDE_PLUGIN_DIR}/.claude/bin/palantir_search.sh" tasks --query "..."
   ```
2. Create the task:
   ```bash
   "${CLAUDE_PLUGIN_DIR}/.claude/bin/palantir_task.sh" create \
     --title "Migrate indicators API to async" \
     --status planning \
     --tag django --tag api-design
   ```
   Default status is `planning`. See `../../rules/api.md` for task statuses.
3. If the user provided substantive context alongside the task request, atomize it into entries
   linked to the new task via `--task-id` (follow the Write Protocol and Atomization Rules in
   SKILL.md and `../../rules/atomize.md`):
   ```bash
   "${CLAUDE_PLUGIN_DIR}/.claude/bin/palantir_entry.sh" create \
     --bluf "Initial context for async migration task" \
     --content "..." \
     --kind note \
     --tag django --task-id <new_task_id>
   ```

## Updating a task

1. Resolve the task: if the user gives an ID, use `get`; if they describe it by name, search
   and confirm the match.
   ```bash
   "${CLAUDE_PLUGIN_DIR}/.claude/bin/palantir_task.sh" get <id>
   # or
   "${CLAUDE_PLUGIN_DIR}/.claude/bin/palantir_search.sh" tasks --query "..."
   ```
2. Update the task:
   ```bash
   "${CLAUDE_PLUGIN_DIR}/.claude/bin/palantir_task.sh" update <id> --status wip
   "${CLAUDE_PLUGIN_DIR}/.claude/bin/palantir_task.sh" update <id> --status done --tag django --tag completed
   ```
3. Common transitions: `planning` → `ready` → `wip` → `review` → `done`.
   Use `blocked` when stalled, `archived` to soft-delete.

## Adding context to a task

When the user has new findings, decisions, or notes for an existing task:
1. Resolve the task (same as updating).
2. Atomize the new content following the Write Protocol, setting `--task-id` on each entry:
   ```bash
   "${CLAUDE_PLUGIN_DIR}/.claude/bin/palantir_entry.sh" create \
     --bluf "Root cause: missing index on created_at column" \
     --content "..." \
     --kind finding \
     --tag django --tag performance \
     --task-id <id>
   ```
