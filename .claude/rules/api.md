# Palantir API Reference

Base URL: `$PALANTIR_API_URL`. All endpoints require `Authorization: Bearer $PALANTIR_API_KEY` and `Content-Type: application/json`.

## Search (Semantic)

```bash
curl -s "$PALANTIR_API_URL/v1/search" \
  -H "Authorization: Bearer $PALANTIR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "TEXT", "project": "PROJECT", "limit": 5}'
```

Optional body fields: `kind`, `task_id`, `search_mode`.

### Search Modes
- `"content"` — search content embeddings only (original behavior)
- `"bluf"` — search BLUF embeddings only
- `"hybrid"` (default) — search both, merge via Reciprocal Rank Fusion

## Entries

**Create one:**
```bash
curl -s "$PALANTIR_API_URL/v1/entries" \
  -H "Authorization: Bearer $PALANTIR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"content": "TEXT", "bluf": "SUMMARY", "kind": "KIND", "project": "PROJECT"}'
```

Optional fields: `bluf`, `task_id`, `tags` (array).

When `bluf` is provided, the server embeds it separately for dual-embedding search. Cross-references (`related_ids`) are auto-detected via similarity search after creation.

**Create bulk** (preferred for 2+ entries):
```bash
curl -s "$PALANTIR_API_URL/v1/entries/bulk" \
  -H "Authorization: Bearer $PALANTIR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"entries": [{"content": "...", "bluf": "...", "kind": "KIND", "project": "PROJECT"}]}'
```

The server auto-assigns a shared `group_id` (integer) to all entries in a bulk request. Use `group_id` to retrieve all entries from the same atomization.

**List:** `GET /v1/entries?project=PROJECT&kind=KIND&task_id=ID&group_id=ID&limit=N`

**Get:** `GET /v1/entries/{id}`

**Delete:** `DELETE /v1/entries/{id}`

### Entry Kinds

| Kind | Use for |
|------|---------|
| `decision` | Architectural/design choices with rationale |
| `finding` | Something discovered during work |
| `error` | Bug, failure, root cause, resolution |
| `pattern` | Reusable approach that worked |
| `note` | General observation or session summary |
| `review` | Code/design review feedback |

## Tasks

Tasks are containers that group entries. Title is embedded for semantic search.

**Create:**
```bash
curl -s "$PALANTIR_API_URL/v1/tasks" \
  -H "Authorization: Bearer $PALANTIR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"title": "TITLE", "project": "PROJECT", "status": "planning", "due_date": "YYYY-MM-DD"}'
```

Optional fields: `due_date` (ISO date, nullable). The server auto-embeds the title for semantic search.

**Search (semantic):**
```bash
curl -s "$PALANTIR_API_URL/v1/tasks/search" \
  -H "Authorization: Bearer $PALANTIR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "TEXT", "project": "PROJECT", "limit": 5}'
```

Optional body fields: `status`, `due_date_lte`, `due_date_gte` (ISO dates for range filtering). Returns tasks with `score`, `entry_count`, and `due_date`.

**List:** `GET /v1/tasks?project=PROJECT&status=STATUS&due_date_lte=DATE&due_date_gte=DATE`

**Get (with linked entries):** `GET /v1/tasks/{id}`

**Update:**
```bash
curl -s "$PALANTIR_API_URL/v1/tasks/{id}" -X PATCH \
  -H "Authorization: Bearer $PALANTIR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"status": "STATUS"}'
```

Updatable fields: `status`, `title`, `due_date`. If title changes, embedding is regenerated. Send `"due_date": null` to clear.

**Archive (soft-delete):** `DELETE /v1/tasks/{id}` — sets status to `archived`, does not remove the record.

### Task Statuses
`planning` | `ready` | `wip` | `review` | `done` | `blocked` | `archived`

## Health

`GET /health` (no auth required)