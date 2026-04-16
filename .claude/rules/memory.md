# Palantir Memory Rules

These rules apply to all sessions in projects connected to Palantir.

## System Overview

| Component | Trigger | What it does |
|-----------|---------|--------------|
| **PreCompact hook** | Before context compression | Atomizes full session into discrete entries with BLUFs |
| **PostToolUse hook** | After plan approval (ExitPlanMode) | Async hook — wakes the agent to spawn a background sonnet agent that saves the plan to Palantir |
| **palantir skill** | Manual or auto-invoked | Middleware for all Palantir operations — enforces atomization |

## When to Act

### Storing knowledge
Invoke the `palantir` skill whenever the user asks to store, log, or remember something. The skill handles atomization, deduplication, and submission.

### Searching past knowledge
Invoke the `palantir` skill when the user asks about previous work, past decisions, or how something was handled before.

### After plan approval
The async PostToolUse hook on ExitPlanMode wakes you with instructions to spawn a background Agent (model: sonnet) to save the plan. Follow those instructions — delegate to the background agent and start implementing immediately.

### Task management
Use the `palantir` skill's Task Protocol to create, update, or add context to tasks.
