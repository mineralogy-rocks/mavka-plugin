#!/usr/bin/env bash
set -euo pipefail

_DIR="$(dirname "${BASH_SOURCE[0]}")"
source "$_DIR/_auth.sh"
source "$_DIR/_common.sh"

usage() {
	cat >&2 <<EOF
Usage: palantir_task.sh <subcommand> [flags]

Subcommands:
  create            Create a new task
    --title <t>     Task title (required)
    --status <s>    Initial status (default: planning)
    --tag <name>    Tag (repeatable)
    --due-date <d>  Due date YYYY-MM-DD (optional)

  get               Get a task and its entries by ID
    <id>            Task ID (positional)

  update            Update a task
    <id>            Task ID (positional, required)
    --status <s>    New status: planning|ready|wip|review|done|blocked|archived
    --title <t>     New title
    --tag <name>    Replace tags (repeatable)
    --due-date <d>  New due date YYYY-MM-DD (use 'null' to clear)

  list              List tasks
    --status <s>    Filter by status
    --tag <name>    Filter by tag (repeatable)
    --due-lte <d>   Due date ≤ YYYY-MM-DD
    --due-gte <d>   Due date ≥ YYYY-MM-DD
    --limit <n>     Max results (default 20)
    --offset <n>    Pagination offset (default 0)

Environment:
  PALANTIR_API_URL         API base URL (required if not in credentials.json)
  PALANTIR_PROJECT_NAME    Scope requests to a specific project (optional)
  PALANTIR_CONFIG_DIR      Override default ~/.config/palantir
EOF
	exit "${1:-2}"
}

cmd="${1:-}"
[[ -z "$cmd" ]] && usage
[[ "$cmd" == "-h" || "$cmd" == "--help" ]] && usage 0

API_URL=$(palantir::load_api_url)
shift

case "$cmd" in
	create)
		TITLE="" STATUS="planning" TAGS=() DUE_DATE=""
		while [[ $# -gt 0 ]]; do
			case "$1" in
				--title) TITLE="$2"; shift 2 ;;
				--status) STATUS="$2"; shift 2 ;;
				--tag) TAGS+=("$2"); shift 2 ;;
				--due-date) DUE_DATE="$2"; shift 2 ;;
				-h|--help) usage 0 ;;
				*) echo "Unknown flag: $1" >&2; usage ;;
			esac
		done
		[[ -z "$TITLE" ]] && { echo "Error: --title is required" >&2; usage; }
		python3 - "$TITLE" "$STATUS" "$DUE_DATE" "${TAGS[@]+"${TAGS[@]}"}" <<'PYEOF' | palantir::curl -X POST "${API_URL}/v1/tasks" --data-binary @- | palantir::strip_embeddings | palantir::pretty
import json, sys
title, status, due_date = sys.argv[1], sys.argv[2], sys.argv[3]
tags = sys.argv[4:]
d = {"title": title, "status": status, "tags": tags}
if due_date:
	d["due_date"] = due_date
print(json.dumps(d))
PYEOF
		;;
	get)
		ID="${1:-}"
		[[ -z "$ID" ]] && { echo "Error: task ID is required" >&2; usage; }
		palantir::curl "${API_URL}/v1/tasks/${ID}" | palantir::strip_embeddings | palantir::pretty
		;;
	update)
		ID="${1:-}"
		[[ -z "$ID" ]] && { echo "Error: task ID is required" >&2; usage; }
		shift
		STATUS="" TITLE="" TAGS=() DUE_DATE="" HAS_DUE=0 HAS_TAGS=0
		while [[ $# -gt 0 ]]; do
			case "$1" in
				--status) STATUS="$2"; shift 2 ;;
				--title) TITLE="$2"; shift 2 ;;
				--tag) TAGS+=("$2"); HAS_TAGS=1; shift 2 ;;
				--due-date) DUE_DATE="$2"; HAS_DUE=1; shift 2 ;;
				-h|--help) usage 0 ;;
				*) echo "Unknown flag: $1" >&2; usage ;;
			esac
		done
		python3 - "$STATUS" "$TITLE" "$DUE_DATE" "$HAS_DUE" "$HAS_TAGS" "${TAGS[@]+"${TAGS[@]}"}" <<'PYEOF' | palantir::curl -X PATCH "${API_URL}/v1/tasks/${ID}" --data-binary @- | palantir::strip_embeddings | palantir::pretty
import json, sys
status, title, due_date, has_due, has_tags = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] == "1", sys.argv[5] == "1"
tags = sys.argv[6:]
d = {}
if status: d["status"] = status
if title: d["title"] = title
if has_tags: d["tags"] = tags
if has_due:
	d["due_date"] = None if due_date == "null" else due_date
print(json.dumps(d))
PYEOF
		;;
	list)
		STATUS="" TAGS=() DUE_LTE="" DUE_GTE="" LIMIT=20 OFFSET=0
		while [[ $# -gt 0 ]]; do
			case "$1" in
				--status) STATUS="$2"; shift 2 ;;
				--tag) TAGS+=("$2"); shift 2 ;;
				--due-lte) DUE_LTE="$2"; shift 2 ;;
				--due-gte) DUE_GTE="$2"; shift 2 ;;
				--limit) LIMIT="$2"; shift 2 ;;
				--offset) OFFSET="$2"; shift 2 ;;
				-h|--help) usage 0 ;;
				*) echo "Unknown flag: $1" >&2; usage ;;
			esac
		done
		PARAMS="limit=${LIMIT}&offset=${OFFSET}"
		[[ -n "$STATUS" ]] && PARAMS="${PARAMS}&status=${STATUS}"
		[[ -n "$DUE_LTE" ]] && PARAMS="${PARAMS}&due_date_lte=${DUE_LTE}"
		[[ -n "$DUE_GTE" ]] && PARAMS="${PARAMS}&due_date_gte=${DUE_GTE}"
		for t in "${TAGS[@]+"${TAGS[@]}"}"; do
			PARAMS="${PARAMS}&tag=${t}"
		done
		palantir::curl "${API_URL}/v1/tasks?${PARAMS}" | palantir::strip_embeddings | palantir::pretty
		;;
	-h|--help) usage 0 ;;
	*) echo "Unknown subcommand: $cmd" >&2; usage ;;
esac
