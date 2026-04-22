#!/usr/bin/env python3
"""Hand an approved Claude Code plan to the main session for atomization + save.

Wired to PostToolUse/ExitPlanMode via hooks.json. This script deliberately
does no LLM work and spawns no subprocesses: Claude is the brain, and the
only Claude available is the one already running the user's session.

Flow on every plan approval:
1. Parse the Claude Code hook payload from stdin.
2. Extract the plan body (try `tool_response.plan`, fall back to
   `tool_input.plan` — older Claude Code versions used the latter).
3. Write the plan to a stable temp file so the main session can read it
   without hitting argv or stdout length limits.
4. Emit `hookSpecificOutput.additionalContext` JSON on stdout — that is
   the documented channel for a PostToolUse hook to inject a system
   reminder into the main session's next turn. The reminder instructs
   the main session's Claude to invoke the mavka skill's Plan
   Protocol on the plan, atomize it, and save it with the supplied
   `dedupe_key` (so retries upsert cleanly).
5. Log progress to `/tmp/mavka-plan-hook.log` for diagnosis.

The hook itself is synchronous, returns in <100ms, and never blocks
Claude Code. All failure paths log and exit 0 so an error here can never
disrupt the main session.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone

# Use /tmp/ explicitly rather than $TMPDIR. On macOS, $TMPDIR resolves to a
# per-user sandbox at /var/folders/<...>/T/ that is on no Claude Code allow
# rule by default — the mavka-worker subagent tasked with saving the plan
# cannot read files there. /tmp/ (→ /private/tmp/) is world-readable and
# commonly allowed via Read(//tmp/**), so a plan file placed there crosses
# the subagent boundary without a permission prompt.
_TMP = "/tmp"
LOG_PATH = os.path.join(_TMP, "mavka-plan-hook.log")


def _now() -> str:
	return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _log(msg: str) -> None:
	try:
		with open(LOG_PATH, "a", encoding="utf-8") as f:
			f.write(f"[{_now()}] {msg}\n")
	except OSError:
		pass


def _extract_plan(payload: dict) -> str:
	"""Return the approved plan text. Claude Code has put this under
	`tool_response.plan` for recent versions and `tool_input.plan` for older
	ones — check both."""
	for root in ("tool_response", "tool_input"):
		block = payload.get(root) or {}
		if isinstance(block, dict):
			plan = (block.get("plan") or "").strip()
			if plan:
				return plan
	return ""


def _plan_title(plan: str) -> str:
	for line in plan.splitlines():
		s = line.lstrip("# ").strip()
		if s:
			return s[:80]
	return "Approved plan"


def _write_temp_plan(plan: str, sha12: str) -> str:
	path = os.path.join(_TMP, f"mavka-plan-{sha12}.md")
	with open(path, "w", encoding="utf-8") as f:
		f.write(plan)
	return path


def _instructions(temp_path: str, dedupe_key: str, title: str) -> str:
	"""The system reminder injected into the main session's next turn.

	Tells the main session to delegate the atomize-and-save to the `mavka-worker`
	subagent in the background, so the user isn't watching dozens of CLI calls
	scroll past while the main task is interrupted.
	"""
	worker_prompt = (
		f"Save this approved plan to Mavka. "
		f"Plan file: {temp_path}\n"
		f"Title: {title!r}\n"
		f"Required flags: --dedupe-key {dedupe_key} --tag auto-saved\n\n"
		"Follow the Plan Protocol at "
		"~/.claude/skills/mavka/.claude/skills/mavka/references/plan-protocol.md. "
		"Atomize per ~/.claude/skills/mavka/.claude/rules/atomize.md (one topic per "
		"entry, standalone BLUF, kind=machine-plan). Report one line with the plan ID "
		"and entry count."
	)
	return (
		"🧠 Mavka plan auto-save hook fired.\n"
		"\n"
		"A plan was just approved. Delegate the save to the `mavka-worker` subagent "
		"in the background so the user's main work isn't interrupted. Do this now, "
		"before continuing the user's task:\n"
		"\n"
		f"1. Print exactly this line to the user: Saving approved plan to Mavka in background… (title: {title!r})\n"
		"2. Spawn a background worker with the Task tool:\n"
		"     subagent_type=\"mavka-worker\"\n"
		"     run_in_background=true\n"
		f"     description=\"Save plan {title!r} to Mavka\"\n"
		f"     prompt=<the multi-line prompt below>\n"
		"3. Resume whatever the user was doing immediately — do NOT wait for the worker.\n"
		"   The worker's result will surface in a later turn. If it fails, a system "
		"   reminder will tell you.\n"
		"\n"
		"Worker prompt to use verbatim:\n"
		"```\n"
		f"{worker_prompt}\n"
		"```\n"
		"\n"
		f"Do not re-delegate if you have already saved dedupe_key {dedupe_key} in "
		"this session."
	)


def main() -> int:
	raw = sys.stdin.read()
	if not raw.strip():
		_log("empty stdin")
		return 0
	try:
		payload = json.loads(raw)
	except json.JSONDecodeError as exc:
		_log(f"stdin not JSON: {exc}; head={raw[:200]!r}")
		return 0

	_log(f"payload keys: {sorted(payload.keys())}")
	plan = _extract_plan(payload)
	if not plan:
		ti_keys = sorted((payload.get("tool_input") or {}).keys()) if isinstance(payload.get("tool_input"), dict) else []
		tr_keys = sorted((payload.get("tool_response") or {}).keys()) if isinstance(payload.get("tool_response"), dict) else []
		_log(f"no plan body; tool_input_keys={ti_keys} tool_response_keys={tr_keys}")
		return 0

	title = _plan_title(plan)
	session_id = (payload.get("session_id") or "nosession")[:16]
	sha12 = hashlib.sha256(plan.encode("utf-8")).hexdigest()[:12]
	dedupe_key = f"plan-{session_id}-{sha12}"

	try:
		temp_path = _write_temp_plan(plan, sha12)
	except OSError as exc:
		_log(f"temp write failed: {exc!r}")
		return 0

	_log(f"handoff title={title!r} dedupe={dedupe_key} temp={temp_path} bytes={len(plan)}")

	sys.stdout.write(json.dumps({
		"hookSpecificOutput": {
			"hookEventName": "PostToolUse",
			"additionalContext": _instructions(temp_path, dedupe_key, title),
		},
	}))
	sys.stdout.write("\n")
	sys.stdout.flush()
	return 0


if __name__ == "__main__":
	try:
		sys.exit(main())
	except Exception as exc:
		_log(f"unhandled: {exc!r}")
		sys.exit(0)
