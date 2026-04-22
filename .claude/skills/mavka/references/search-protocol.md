# Search Protocol

Use this when the user wants to recall past knowledge, find related context, or investigate
how something was handled before.

> **Required reading**: `../../rules/api.md` (wrapper command reference — search modes, parameters)

## Step 1 — Search

Choose the search mode based on the query (see `../../rules/api.md` for details):
- **`hybrid`** (default): Best for general queries. Fuses content and BLUF embeddings via
  Reciprocal Rank Fusion.
- **`bluf`**: When looking for high-level summaries or scanning for a topic.
- **`content`**: When looking for specific implementation details or code-level context.

```bash
~/.claude/skills/mavka/.claude/bin/mavka search knowledge \
  --query "N+1 query on indicators" --mode hybrid --limit 5
```

Also search tasks if the query might relate to tracked work:

```bash
~/.claude/skills/mavka/.claude/bin/mavka search tasks --query "TAU migration" --limit 5
```

## Step 2 — Follow links

For results with a `group_id`, consider fetching siblings to get the full atomization batch:

```bash
~/.claude/skills/mavka/.claude/bin/mavka entry list --group-id <group_id>
```

For results with a `task_id`, fetch the task to show work context:

```bash
~/.claude/skills/mavka/.claude/bin/mavka task get <task_id>
```

For individual entries with related IDs, fetch them:

```bash
~/.claude/skills/mavka/.claude/bin/mavka entry get <id>
```

Limit link-following to avoid noise: max 2 group fetches, 3 related entry fetches, 3 task fetches.

## Step 3 — Present results

Always present results as a markdown table for quick scanning, followed by detail sections.

### Results table

Start with a summary table of all results:

```markdown
Found N entries related to "query":

| # | Kind | BLUF | Tags | Date |
|---|------|------|------|------|
| #42 | decision | We chose Pinia over Vuex for state management | `nuxt`, `migration` | 2026-04-10 |
| #38 | finding | N+1 query on indicators caused 2.3s response times | `django`, `performance` | 2026-04-08 |
| #35 | error | OAuth flow fails when redirect URI has trailing slash | `auth`, `oauth` | 2026-04-05 |
```

### Tasks table (if any)

If tasks were found, present them separately:

```markdown
Related tasks:

| # | Status | Title | Entries | Date |
|---|--------|-------|---------|------|
| #22 | wip | TAU migration into gtaapi | 5 | 2026-04-12 |
| #16 | done | DPA MCP Server launch | 8 | 2026-03-28 |
```

### Detail sections

After the table, expand on results only if the user needs more context. Use collapsible
sections or bullet points per entry:

```markdown
**#42 [decision]** We chose Pinia over Vuex for state management
> Pinia was selected because it has first-class TypeScript support, a simpler API
> without mutations, and is the officially recommended library for Vue 3...
> Tags: `nuxt`, `migration` · Related: #38, #40 · Task: #22
```

### No results

If nothing was found:

```markdown
No entries found in Mavka for "query". Consider checking:
- Different search terms or synonyms
- Broader tags
- Whether this knowledge has been stored yet
```
