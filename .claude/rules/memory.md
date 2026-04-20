# Palantir Memory Rules

These rules apply to all sessions in projects connected to Palantir.

## System Overview

| Component | Trigger | What it does |
|-----------|---------|--------------|
| **PreCompact hook** | Before context compression | Atomizes full session into discrete entries with BLUFs |
| **PostToolUse hook** | After plan approval (ExitPlanMode) | Async deferred reminder — save plan to Palantir during a natural pause |
| **palantir skill** | Manual or auto-invoked | Middleware for all Palantir operations — enforces atomization |

## When to Act

### Storing knowledge
Invoke the `palantir` skill whenever the user asks to store, log, or remember something. The skill handles atomization, deduplication, and submission.

### Searching past knowledge
Invoke the `palantir` skill when the user asks about previous work, past decisions, or how something was handled before.

### After plan approval
The async PostToolUse hook on ExitPlanMode wakes you with a deferred reminder. Do NOT block implementation — save the plan during a natural pause (between phases, after a commit, etc.) by invoking the palantir skill and following the Plan Protocol.

### Task management
Use the `palantir` skill's Task Protocol to create, update, or add context to tasks.
