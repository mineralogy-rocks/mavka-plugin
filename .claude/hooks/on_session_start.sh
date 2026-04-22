#!/usr/bin/env bash
# Maintain a stable symlink at ~/.claude/skills/mavka pointing at the current
# plugin cache root. Skill bodies invoke the CLI via that stable path so
# one allowlist rule (Bash(~/.claude/skills/mavka/.claude/bin/mavka:*)) stays
# valid across plugin upgrades. Gstack pattern.

set -uo pipefail

LINK="$HOME/.claude/skills/mavka"
TARGET="${CLAUDE_PLUGIN_ROOT:-}"
LOG="${TMPDIR:-/tmp}/mavka-session-hook.log"

if [ -z "$TARGET" ]; then
	echo "[$(date -u +%FT%TZ)] CLAUDE_PLUGIN_ROOT unset; nothing to do" >> "$LOG"
	exit 0
fi

mkdir -p "$(dirname "$LINK")"

if [ -L "$LINK" ] && [ "$(readlink "$LINK")" = "$TARGET" ]; then
	exit 0
fi

ln -sfn "$TARGET" "$LINK"
echo "[$(date -u +%FT%TZ)] relinked $LINK -> $TARGET" >> "$LOG"
exit 0
