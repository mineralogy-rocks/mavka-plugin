---
description: Search Palantir for past decisions, findings, errors, patterns, and notes related to a topic. Use this whenever the user asks about previous work, past context, or how something was handled before.
model: sonnet
context: fork
allowed-tools: Bash(curl *$PALANTIR_API_URL*), Bash(echo *), Bash(jq *), Read
---

# /recall

Search Palantir's knowledge base for entries related to a topic. This skill is automatically invoked when the user asks about previous work, past decisions, how something was handled, or needs context from earlier sessions.

## When to Auto-Invoke

Invoke this skill when the user:
- Asks "how did we handle X?", "what do we know about Y?", "what happened with Z?"
- References past work, previous sessions, or earlier decisions
- Needs context about a feature, bug, or pattern that was worked on before
- Says "check Palantir", "search Palantir", or "recall"
- Is about to start work on something that may have prior context

## Process

### Step 1 — Search

Run a semantic search using the user's query:

```bash
curl -s "$PALANTIR_API_URL/v1/search" \
  -H "Authorization: Bearer $PALANTIR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "SEARCH_QUERY", "project": "'$PALANTIR_PROJECT_NAME'", "limit": 10}'
```

Replace `SEARCH_QUERY` with `$ARGUMENTS`. If `$ARGUMENTS` is empty, ask the user what to search for.

### Step 2 — Search Related Tasks

Search for tasks related to the query:

```bash
curl -s "$PALANTIR_API_URL/v1/tasks/search" \
  -H "Authorization: Bearer $PALANTIR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "SEARCH_QUERY", "project": "'$PALANTIR_PROJECT_NAME'", "limit": 3}'
```

**Date-aware filtering:** If the user's query mentions a timeframe ("due this week", "overdue", "tasks due before April", "what's coming up"), add `due_date_lte` and/or `due_date_gte` to the search payload (format: `YYYY-MM-DD`). For "overdue", use `"due_date_lte": "TODAY"` where TODAY is the current date. For "due this week", set `due_date_gte` to Monday and `due_date_lte` to Sunday of the current week. You can also use `GET /v1/tasks?due_date_lte=DATE&due_date_gte=DATE&project=PROJECT` for date-only queries where semantic search isn't needed.

Additionally, for entry results from Step 1 that have a non-null `task_id`, fetch those tasks to show the connection:

```bash
curl -s "$PALANTIR_API_URL/v1/tasks/TASK_ID" \
  -H "Authorization: Bearer $PALANTIR_API_KEY"
```

Deduplicate task IDs. Limit to 3 unique task fetches total.

### Step 3 — Fetch Sibling and Related Entries

For each result that has a `group_id`, fetch sibling entries from the same group to provide full context of the original atomized source:

```bash
curl -s "$PALANTIR_API_URL/v1/entries?group_id=GROUP_ID" \
  -H "Authorization: Bearer $PALANTIR_API_KEY" \
  -H "Content-Type: application/json"
```

Additionally, for results with non-empty `related_ids`, fetch those entries:

```bash
curl -s "$PALANTIR_API_URL/v1/entries/ENTRY_ID" \
  -H "Authorization: Bearer $PALANTIR_API_KEY" \
  -H "Content-Type: application/json"
```

Limit to 5 unique related entries and 2 group fetches total to avoid noise.

### Step 4 — Present Results

Format the output following the example in `examples/recall-output.md` (relative to this skill's directory). Read that file before formatting results.

---

**If tasks were found** (from Step 2), display them first:

#### Tasks

For each task:
- Status badge: `[planning]`, `[wip]`, `[blocked]`, `[review]`, `[done]`
- **Task title** (bold)
- Due date if set: `Due: YYYY-MM-DD`. If the due date is in the past and status is not `done` or `archived`, append `(overdue)`
- Entry count (e.g., "3 entries")
- Created date
- If the task was found via an entry's `task_id`, note: "↳ linked from entry #ID"

---

#### Entries

1. **Summary line**: "Found N entries related to [query]"
2. **For each entry**, display:
   - Kind badge (e.g., `[decision]`, `[error]`, `[pattern]`)
   - BLUF (if available) — highlighted as the key takeaway
   - Full content
   - Tags
   - Task link (if `task_id` is set): "↳ task #ID"
   - Created and updated dates
3. **Sibling entries** section (if fetched via group_id in Step 3), grouped under the same source
4. **Related entries** section (if any were fetched in Step 3), with the same format but marked as "Related"

---

If no results are found (no entries and no tasks), say: "No entries or tasks found in Palantir for this query."

## Notes

- Uses hybrid search mode (content + BLUF embeddings via Reciprocal Rank Fusion) by default
- Results are scoped to the current project via `$PALANTIR_PROJECT_NAME`
- To search across all projects, omit the project filter (only do this if the user explicitly asks)