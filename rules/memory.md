# Mavka Memory Rules

These rules apply to all sessions in projects connected to Mavka.

## System Overview

| Component | Trigger | What it does |
|-----------|---------|--------------|
| **`./setup` install symlink** | One-time, at install | Creates `~/.claude/skills/mavka` → `<repo>/skills/mavka` and `~/.claude/agents/mavka-worker.md` → `<repo>/agents/mavka-worker.md`. Static — survives every session with no per-session hook. Re-running `./setup` is idempotent. |
| **PreCompact hook** | Before context compression | Atomizes full session into discrete entries with BLUFs |
| **PostToolUse hook** | After plan approval (ExitPlanMode) | Writes the approved plan to a temp file and returns `hookSpecificOutput.additionalContext` JSON that instructs the main session's Claude to delegate the save to the `mavka-worker` background subagent, which applies the Plan Protocol, atomizes, and calls `plan save` with an idempotent `dedupe_key`. The hook itself does no LLM work and no subprocess spawning; it is pure plumbing. Progress is logged to `/tmp/mavka-plan-hook.log`. |
| **mavka skill** | Manual or auto-invoked | Middleware for all Mavka operations — enforces atomization |
| **mavka-worker agent** | Spawned via Task(run_in_background=true) | User-level subagent with `permissionMode: bypassPermissions`. Owns Mavka CLI work (plan saves, bulk writes, linked searches) so the main session never stalls on tool-call fan-out. |

## When to Act

### Storing knowledge
Invoke the `mavka` skill whenever the user asks to store, log, or remember something. The skill handles atomization, deduplication, and submission.

### Searching past knowledge
Invoke the `mavka` skill when the user asks about previous work, past decisions, or how something was handled before.

### After plan approval
The PostToolUse hook on ExitPlanMode injects a system reminder via `hookSpecificOutput.additionalContext` telling the main session's Claude to save the plan to Mavka as its next action. Claude reads the plan from the temp file the hook writes, invokes the mavka skill's Plan Protocol (proper atomization per `rules/atomize.md`), and saves via `plan save` with the supplied `dedupe_key` (so retries upsert rather than duplicate). No background subprocess, no subagent, no Anthropic Messages API call — the main session's Claude is the atomization brain. Hook trace: `/tmp/mavka-plan-hook.log`.

### Task management
Use the `mavka` skill's Task Protocol to create, update, or add context to tasks.
