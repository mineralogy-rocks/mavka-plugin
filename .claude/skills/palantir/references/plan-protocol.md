# Plan Protocol

Use this when the user has approved a plan and wants to persist it. Plans are stored as a raw
plan document plus atomized entries derived from it.

> **Required reading**: `../../rules/atomize.md` (atomization rules), `../../rules/api.md` (wrapper command reference)

## Step 1 — Preflight

Same as Write Protocol: search for duplicates and get the tag inventory. Run both in parallel.
See `../../rules/api.md` for wrapper signatures.

```bash
"${CLAUDE_PLUGIN_DIR}/.claude/bin/palantir_search.sh" knowledge --query "..." --limit 5
"${CLAUDE_PLUGIN_DIR}/.claude/bin/palantir_tag.sh" list
```

## Step 2 — Atomize the plan

Break the approved plan into entries. Each entry should cover one of:
- A discrete decision and its rationale
- An implementation step with enough context to act on independently
- A constraint or requirement that shapes the implementation
- A risk or trade-off that was accepted
- A follow-up or open question

Every atomized entry must use `kind: "machine-plan"`. This kind indicates the entry was
machine-curated from an approved plan. Do not override to `decision`, `finding`, or other kinds
— `machine-plan` is the canonical kind for all plan-derived entries, regardless of whether an
individual entry describes a decision, a risk, or an implementation step.

Every entry needs standalone `content` (100-400 words) and a `bluf` (1-2 sentences). Follow
the Atomization Rules in SKILL.md and `../../rules/atomize.md` — someone reading just one entry
should understand it fully without seeing the rest of the plan.

## Step 3 — Submit

Write the atomized entries to a JSON file, then call `palantir_plan.sh save`:

```bash
# entries.json: [{"content":"...","bluf":"...","kind":"machine-plan","tags":["bos","nuxt"]}]
"${CLAUDE_PLUGIN_DIR}/.claude/bin/palantir_plan.sh" save \
  --title "Bos frontend migration from Nuxt 2 to Nuxt 3" \
  --content "$(cat /path/to/approved-plan.md)" \
  --entries-file /tmp/entries.json \
  --tag bos --tag nuxt --tag migration \
  --dedupe-key "bos-nuxt3-migration-2026"
```

- `--title`: Concise plan title
- `--content`: The full raw plan text as approved
- `--entries-file`: Path to JSON file with the atomized entries array
- `--tag`: Plan-level tags (repeatable)
- `--dedupe-key`: Provide one when automation may retry (prevents duplicate plans)

## Step 4 — Confirm

Present the saved plan as a markdown table:

```markdown
Plan #3 saved: "Bos frontend migration from Nuxt 2 to Nuxt 3"
Tags: `bos`, `nuxt`, `migration` · Dedupe key: `bos-nuxt3-migration-2026`

| # | BLUF | Tags |
|---|------|------|
| #99 | Three-phase migration over 3 sprints covering state, syntax, and UI library | `bos`, `nuxt`, `planning` |
| #100 | Phase 1: Replace Vuex with Pinia stores | `bos`, `nuxt`, `pinia` |
| #101 | Phase 2: Convert Options API to Composition API | `bos`, `nuxt`, `frontend` |
| #102 | Phase 3: Replace sgept-ui with sui3 components | `bos`, `sui3`, `frontend` |
| #103 | Risk accepted: build missing sui3 components incrementally | `bos`, `sui3`, `migration` |
```
