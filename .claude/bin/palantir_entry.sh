#!/usr/bin/env bash
set -euo pipefail

_DIR="$(dirname "${BASH_SOURCE[0]}")"
source "$_DIR/_auth.sh"
source "$_DIR/_common.sh"

usage() {
	cat >&2 <<EOF
Usage: palantir_entry.sh <subcommand> [flags]

Subcommands:
  create            Create a single entry
    --bluf <text>   BLUF summary (required)
    --content <t>   Entry body (required; use --stdin to read from stdin)
    --stdin         Read content from stdin instead of --content
    --kind <k>      Kind: decision|finding|error|pattern|note|review|machine-plan (default: note)
    --tag <name>    Tag (repeatable)
    --task-id <id>  Associate with a task

  bulk              Bulk create entries from a JSON file
    --file <path>   Path to JSON file: {"entries":[{content,bluf,kind,tags},...]}

  get               Get a single entry by ID
    <id>            Entry ID (positional)

  list              List entries
    --kind <k>      Filter by kind
    --tag <name>    Filter by tag (repeatable)
    --plan-id <id>  Filter by plan
    --task-id <id>  Filter by task
    --group-id <id> Filter by group
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
		BLUF="" CONTENT="" KIND="note" TAGS=() TASK_ID="" USE_STDIN=0
		while [[ $# -gt 0 ]]; do
			case "$1" in
				--bluf) BLUF="$2"; shift 2 ;;
				--content) CONTENT="$2"; shift 2 ;;
				--stdin) USE_STDIN=1; shift ;;
				--kind) KIND="$2"; shift 2 ;;
				--tag) TAGS+=("$2"); shift 2 ;;
				--task-id) TASK_ID="$2"; shift 2 ;;
				-h|--help) usage 0 ;;
				*) echo "Unknown flag: $1" >&2; usage ;;
			esac
		done
		[[ -z "$BLUF" ]] && { echo "Error: --bluf is required" >&2; usage; }
		if [[ $USE_STDIN -eq 1 ]]; then
			CONTENT=$(cat)
		fi
		[[ -z "$CONTENT" ]] && { echo "Error: --content or --stdin is required" >&2; usage; }
		python3 - "$BLUF" "$CONTENT" "$KIND" "$TASK_ID" "${TAGS[@]+"${TAGS[@]}"}" <<'PYEOF' | palantir::curl -X POST "${API_URL}/v1/entries" --data-binary @- | palantir::strip_embeddings | palantir::pretty
import json, sys
bluf, content, kind, task_id = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
tags = sys.argv[5:]
d = {"bluf": bluf, "content": content, "kind": kind, "tags": tags}
if task_id:
	d["task_id"] = int(task_id)
print(json.dumps(d))
PYEOF
		;;
	bulk)
		FILE=""
		while [[ $# -gt 0 ]]; do
			case "$1" in
				--file) FILE="$2"; shift 2 ;;
				-h|--help) usage 0 ;;
				*) echo "Unknown flag: $1" >&2; usage ;;
			esac
		done
		[[ -z "$FILE" ]] && { echo "Error: --file is required" >&2; usage; }
		palantir::validate_json_file "$FILE"
		palantir::curl -X POST "${API_URL}/v1/entries/bulk" --data-binary "@${FILE}" | palantir::pretty
		;;
	get)
		ID="${1:-}"
		[[ -z "$ID" ]] && { echo "Error: entry ID is required" >&2; usage; }
		palantir::curl "${API_URL}/v1/entries/${ID}" | palantir::strip_embeddings | palantir::pretty
		;;
	list)
		KIND="" TAGS=() PLAN_ID="" TASK_ID="" GROUP_ID="" LIMIT=20 OFFSET=0
		while [[ $# -gt 0 ]]; do
			case "$1" in
				--kind) KIND="$2"; shift 2 ;;
				--tag) TAGS+=("$2"); shift 2 ;;
				--plan-id) PLAN_ID="$2"; shift 2 ;;
				--task-id) TASK_ID="$2"; shift 2 ;;
				--group-id) GROUP_ID="$2"; shift 2 ;;
				--limit) LIMIT="$2"; shift 2 ;;
				--offset) OFFSET="$2"; shift 2 ;;
				-h|--help) usage 0 ;;
				*) echo "Unknown flag: $1" >&2; usage ;;
			esac
		done
		PARAMS="limit=${LIMIT}&offset=${OFFSET}"
		[[ -n "$KIND" ]] && PARAMS="${PARAMS}&kind=${KIND}"
		[[ -n "$PLAN_ID" ]] && PARAMS="${PARAMS}&plan_id=${PLAN_ID}"
		[[ -n "$TASK_ID" ]] && PARAMS="${PARAMS}&task_id=${TASK_ID}"
		[[ -n "$GROUP_ID" ]] && PARAMS="${PARAMS}&group_id=${GROUP_ID}"
		for t in "${TAGS[@]+"${TAGS[@]}"}"; do
			PARAMS="${PARAMS}&tag=${t}"
		done
		palantir::curl "${API_URL}/v1/entries?${PARAMS}" | palantir::strip_embeddings | palantir::pretty
		;;
	-h|--help) usage 0 ;;
	*) echo "Unknown subcommand: $cmd" >&2; usage ;;
esac
