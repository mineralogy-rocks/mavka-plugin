# Write Protocol

Use this when storing knowledge — logging a finding, decision, error, pattern, note, or review.

> **Required reading**: `../../rules/atomize.md` (atomization rules), `../../rules/api.md` (wrapper command reference)

## Step 1 — Preflight

Run these two calls in parallel before any write:

1. **Duplicate check**: search with a query summarizing the content to store. If a
   near-duplicate exists (same topic, same conclusion), tell the user and ask whether to skip,
   update, or create anyway.
   ```bash
   ~/.claude/skills/mavka/.claude/bin/mavka search knowledge --query "..." --limit 5
   ```
2. **Tag inventory**: get existing tags and reuse them. Only invent a new tag when no existing
   tag fits.
   ```bash
   ~/.claude/skills/mavka/.claude/bin/mavka tag list
   ```

See `../../rules/api.md` for full wrapper signatures.

## Step 2 — Atomize

Break the input into discrete knowledge atoms following the Atomization Rules in SKILL.md and
`../../rules/atomize.md`. Key requirements:

- One topic per entry
- Self-contained content (100-400 words)
- Standalone BLUF (1-2 sentences)
- Accurate kind classification (see `../../rules/atomize.md` for the full kind table)
- 2-4 reused tags

Never use `machine-plan` kind here — that kind is reserved for the Plan Protocol.

## Step 3 — Submit

- **Single atom**:
  ```bash
  ~/.claude/skills/mavka/.claude/bin/mavka entry create \
    --bluf "N+1 query caused by missing select_related on category FK" \
    --content "..." \
    --kind finding \
    --tag django --tag performance
  ```
- **Long content** (use `--stdin` to avoid argv length limits):
  ```bash
  cat <<'EOF' | ~/.claude/skills/mavka/.claude/bin/mavka entry create \
    --bluf "Added select_related to IndicatorViewSet queryset" \
    --stdin --kind decision --tag django-orm --tag api-design
  Full context here...
  EOF
  ```
- **Multiple atoms**: write a JSON file `{"entries":[{content,bluf,kind,tags},...]}` then:
  ```bash
  ~/.claude/skills/mavka/.claude/bin/mavka entry bulk --file /tmp/entries.json
  ```
  The server auto-assigns a shared `group_id` for traceability.

## Step 4 — Confirm

Present what was stored as a markdown table:

```markdown
Stored N entries (group #GID):

| # | Kind | BLUF | Tags |
|---|------|------|------|
| #92 | finding | N+1 query caused by missing select_related on category FK | `django`, `performance` |
| #93 | decision | Added select_related to IndicatorViewSet queryset | `django-orm`, `api-design` |
```

If cross-references (`related_ids`) were auto-detected, append them:

```markdown
Cross-references detected: #92 → #83, #84
```
