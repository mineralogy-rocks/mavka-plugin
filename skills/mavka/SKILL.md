---
name: mavka
description: >-
  Middleware for the Mavka persistent knowledge system. Invoke this skill whenever the user
  wants to store, search, recall, or manage knowledge in Mavka — including saving decisions,
  findings, errors, patterns, notes, plans, or tasks. Also invoke when the user says "remember
  this", "store this", "save to Mavka", "log this", "what do we know about", "recall",
  "search Mavka", or wants to persist an approved plan. Also invoke when the user wants to
  log in or log out of Mavka, or when any wrapper prints `[MAVKA_LOGIN_REQUIRED]` — the
  skill owns the login lifecycle and runs `mavka login` on the user's behalf. This skill
  enforces atomization — breaking complex knowledge into discrete, standalone, individually-
  searchable entries — before anything is written to Mavka. Use it even for simple
  single-entry writes, because it ensures BLUF quality, correct kind classification, tag reuse,
  and duplicate prevention.
---

# Mavka Middleware

You are the atomization layer between the agent and Mavka. Your job is to ensure every piece
of knowledge written to Mavka is properly decomposed, classified, and deduplicated before
submission.

Mavka is a persistent knowledge system backed by PostgreSQL with pgvector. It stores entries
with OpenAI vector embeddings for semantic search. The three core entities are entries (knowledge
atoms), plans (approved plans with atomized entries), and tasks (work containers grouping entries).

## Reference Files

Read these before proceeding — they contain the detailed steps for each operation:

| File | What it covers |
|------|---------------|
| `references/write-protocol.md` | Storing entries (findings, decisions, errors, patterns, notes, reviews) |
| `references/plan-protocol.md` | Saving approved plans with atomized `machine-plan` entries |
| `references/search-protocol.md` | Searching, recalling, and presenting past knowledge |
| `references/task-protocol.md` | Creating, updating, and enriching tasks |
| `references/auth-protocol.md` | Logging in and out — triggered on `[MAVKA_LOGIN_REQUIRED]` or direct user intent |

Supporting rules (shipped alongside this skill in the repo):

| Rule file | What it provides |
|-----------|-----------------|
| `../../rules/atomize.md` | Detailed atomization rules shared across all protocols |
| `../../rules/api.md` | Wrapper command reference with flags and environment variables |

## Transport

All Mavka operations go through a single CLI at `~/.claude/skills/mavka/bin/mavka`.
Always call `~/.claude/skills/mavka/bin/mavka tag list` before creating entries to reuse existing tags.
Use `~/.claude/skills/mavka/bin/mavka entry create --stdin` for long content to avoid argv length limits.

The path is a stable symlink created once by the repo's `./setup` installer; it points at
`<repo>/skills/mavka` in the checkout. Because the symlink is static, one
`Bash(~/.claude/skills/mavka/bin/mavka:*)` allow rule in `~/.claude/settings.json` covers
every call indefinitely — no per-session hook, no plugin cache indirection.

## Routing

Classify the user's intent, then **read the corresponding protocol file** before proceeding:

| Intent | Protocol |
|--------|----------|
| Store knowledge, log a finding/decision/error, "remember this" | **Write Protocol** |
| Save an approved plan | **Plan Protocol** |
| Search, recall, "what do we know about X" | **Search Protocol** |
| Create/update/manage tasks | **Task Protocol** |
| "log me in", "authenticate", or wrapper output contains `[MAVKA_LOGIN_REQUIRED]` | **Auth Protocol** |

If the intent is ambiguous, ask the user to clarify before proceeding.

When another protocol's wrapper call fails with `[MAVKA_LOGIN_REQUIRED]`, first run the
**Auth Protocol** to restore the session, then retry the original call.

---

## Atomization Rules

These rules are shared across the Write, Plan, and Task protocols. Every entry written to
Mavka must satisfy all of these.

### One topic per entry

If you need two sentences to describe what an entry is "about", split it into separate entries.

### Self-contained content (100-400 words)

A reader months from now, seeing only this entry, must understand the full picture — what
happened, why, what was tried, what worked or didn't, and any constraints. No forward/backward
references ("as mentioned above", "see below"). No vague pronouns ("the project" without naming
it, "as discussed" without saying what).

### Standalone BLUF (1-2 sentences)

Bottom Line Up Front. Start with the most important fact. A reader should understand the entry's
value from the BLUF alone, without reading the content body.

### Kind classification

Pick the most specific kind for the entry:

| Kind | When to use |
|------|------------|
| `decision` | A choice was made. Include alternatives considered and why this one won. |
| `finding` | Something discovered during investigation. Include what led to the discovery. |
| `error` | A bug, mistake, or failure. Include root cause and resolution (or that it's unresolved). |
| `pattern` | A reusable approach that worked. Include when to apply it and when not to. |
| `note` | General information worth preserving that doesn't fit the above. |
| `review` | Feedback or assessment of work. Include what was reviewed and the verdict. |
| `machine-plan` | Reserved for Plan Protocol only. All plan-derived entries use this kind. |

### Tags (2-4 per entry)

Lowercase, hyphenated (e.g., `django-orm`, `api-design`). Prefer specific over generic.
Always call `list_tags` first and reuse existing tags. Only invent a new tag when no existing
tag fits.

### Guard

If the input has no meaningful content to atomize (too vague, too short, or just restating
something already stored), say so and do nothing. Do not create empty or low-value entries.

---

## Quality Checklist

Before submitting anything, verify:

- [ ] Searched for duplicates first
- [ ] Each atom covers exactly one topic
- [ ] Each BLUF makes sense without reading the content
- [ ] Each content block is 100-400 words and self-contained
- [ ] Kind classification is the most specific fit
- [ ] Tags are reused from existing inventory where possible
- [ ] No forward/backward references between atoms
- [ ] No vague references ("the project", "as discussed") without specifics
