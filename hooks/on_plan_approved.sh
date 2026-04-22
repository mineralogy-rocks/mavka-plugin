#!/usr/bin/env bash
# Thin wrapper around the Python hook. Stdout is the JSON payload Claude Code
# reads to inject `additionalContext` into the main session; stderr is routed
# to the diagnostic log so nothing stray reaches the user.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="${TMPDIR:-/tmp}/mavka-plan-hook.log"

exec python3 "$HERE/_plan_auto_save.py" 2>> "$LOG"
