# Atomization Rules

Shared rules for breaking content into discrete knowledge entries. Referenced by the PreCompact hook, the mavka skill, and all write operations.

## Entry Structure

Each entry must cover **one topic only**. If two sentences are needed to describe what an entry is "about," split it into separate entries.

### BLUF (Bottom Line Up Front)

1-2 sentences that stand alone as a direct answer to the core question the entry addresses. A reader should understand the key takeaway from the BLUF without reading the body.

### Body

100-400 words. Include enough context for the entry to be useful months later: what was tried, why, what worked or didn't, and any constraints that shaped the decision.
If the content provided by the user is not enough, then ask 1-3 questions to saturate the content, but **do not deviate from the content that the user provided.**

### Kind Classification

| Kind | Use for |
|------|---------|
| `decision` | Architectural/design choices with rationale |
| `finding` | Something discovered during work |
| `error` | Bug, failure, root cause, resolution |
| `pattern` | Reusable approach that worked |
| `note` | General observation or session summary |
| `review` | Feedback or assessment of work |
| `machine-plan` | Atomized entries from approved plans only |

### Tags

Lowercase, hyphenated, inferred from content. Examples: `django`, `api-design`, `nextjs`, `session-summary`. Use 2-4 tags per entry. Always check existing tags first via `list_tags`.

## Guard

If there is no meaningful content to atomize, do nothing silently. Do not create empty or low-value entries.
