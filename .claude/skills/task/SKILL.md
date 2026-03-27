---
description: Create, update, or add context to tasks in Palantir. Accepts a text description or file path. Auto-detects whether to create a new task, update status, or enrich an existing task with entries.
argument_hint: "<text or file path>"
model: sonnet
allowed-tools: Bash(curl *$PALANTIR_API_URL*), Bash(echo *), Bash(jq *), Read, Grep
context: fork
---

# /task

Manage tasks in Palantir — create new tasks, update status, or add context entries to existing tasks.

## When to Auto-Invoke

Invoke this skill when the user:
- Wants to track a piece of work ("create a task for X", "track this")
- Wants to update task status ("mark X as done", "start working on Y", "block Z")
- Wants to add findings/decisions/context to an existing task
- References a task by name or ID for any lifecycle operation

## Process

### Step 0 — Input Resolution

If `$ARGUMENTS` looks like a file path (starts with `/` or `~`, or ends in `.md`, `.txt`, etc.), read the file content first. Otherwise treat `$ARGUMENTS` as raw text.

If `$ARGUMENTS` is empty, ask the user what they want to do.

### Step 1 — Classify Intent

Analyze the text and classify into one of three intents:

**status-update** — Text references a task (by ID like `#5` or by topic/title fragment like "Provision Explorer") combined with a status keyword:
- done / complete / finish → `done`
- start / begin → `wip`
- block → `blocked`
- unblock → `ready`
- review → `review`
- plan → `planning`
- archive → `archived`

**add-context** — Text references an existing task AND provides substantive new information (findings, decisions, notes) to store as entries linked to that task.

**new-task** — Text describes work to be done without clearly referencing an existing task. This is the default/fallback.

### Step 2 — Task Resolution (for status-update and add-context)

If the user provides an explicit task ID (e.g., `#5`, `task 5`), fetch it directly:

```bash
curl -s "$PALANTIR_API_URL/v1/tasks/TASK_ID" \
  -H "Authorization: Bearer $PALANTIR_API_KEY"
```

Otherwise, use semantic search to find the task:

```bash
curl -s "$PALANTIR_API_URL/v1/tasks/search" \
  -H "Authorization: Bearer $PALANTIR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "TASK_REFERENCE_TEXT", "project": "'$PALANTIR_PROJECT_NAME'", "limit": 5}'
```

Exclude `done` and `archived` tasks from consideration by default (unless the user explicitly references them).

**Resolution rules:**
- **Single match with high score**: Proceed automatically. Confirm which task you're acting on in the output.
- **Multiple plausible matches**: Present a numbered list to the user showing ID, title, status, entry count, and created date. Ask them to specify which one. Do NOT proceed until clarified.
- **No matches**: Report that no matching task was found. Ask if the user wants to create a new one instead.

### Step 3 — Execute

#### For new-task:

1. Extract a concise title (under 80 chars) from the text.
2. Create the task:

```bash
curl -s "$PALANTIR_API_URL/v1/tasks" \
  -H "Authorization: Bearer $PALANTIR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"title": "TITLE", "project": "'$PALANTIR_PROJECT_NAME'", "status": "planning"}'
```

3. If the text contains substantive information worth persisting (decisions, findings, context — not just the task title restated), atomize it into entries linked to the new task. Follow the atomization rules from `${CLAUDE_PLUGIN_ROOT}/.claude/rules/atomize.md`:
   - Each entry covers one topic
   - Include BLUF (1-2 sentence standalone summary)
   - Body: 100-400 words with enough context
   - Classify kind: `decision`, `finding`, `error`, `pattern`, `note`
   - Add 2-4 lowercase hyphenated tags

```bash
curl -s "$PALANTIR_API_URL/v1/entries/bulk" \
  -H "Authorization: Bearer $PALANTIR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"entries": [{"content": "BODY", "bluf": "BLUF", "kind": "KIND", "project": "'$PALANTIR_PROJECT_NAME'", "task_id": TASK_ID, "tags": ["tag1", "tag2"]}]}'
```

#### For status-update:

```bash
curl -s "$PALANTIR_API_URL/v1/tasks/TASK_ID" -X PATCH \
  -H "Authorization: Bearer $PALANTIR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"status": "NEW_STATUS"}'
```

#### For add-context:

Atomize the new information into entries linked to the task via `task_id`, following the same atomization rules as new-task above.

### Step 4 — Summary

Always end with a clear summary:
- **new-task**: "Created task #ID: 'TITLE' [planning]" + count of entries created
- **status-update**: "Task #ID 'TITLE': STATUS_OLD → STATUS_NEW"
- **add-context**: "Added N entries to task #ID 'TITLE'"

## Notes

- All API calls use `$PALANTIR_API_URL`, `$PALANTIR_API_KEY`, and `$PALANTIR_PROJECT_NAME` env vars
- Tasks are never deleted — use `archived` status instead
- When creating entries for a task, always set `task_id` to link them