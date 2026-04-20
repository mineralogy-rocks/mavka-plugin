#!/usr/bin/env bash
set -euo pipefail

_DIR="$(dirname "${BASH_SOURCE[0]}")"
source "$_DIR/_auth.sh"
source "$_DIR/_common.sh"

usage() {
	cat >&2 <<EOF
Usage: palantir_search.sh <subcommand> [flags]

Subcommands:
  knowledge         Search knowledge entries (semantic)
    --query <q>     Search query (required)
    --kind <k>      Filter by kind: decision|finding|error|pattern|note|review|machine-plan
    --tag <name>    Filter by tag (repeatable)
    --plan-id <id>  Filter to entries in a plan
    --task-id <id>  Filter to entries in a task
    --mode <m>      Search mode: hybrid|content|bluf (default: hybrid)
    --limit <n>     Max results (default 5)
    --raw           Output full JSON (default: compact id/score/bluf/kind/tags)

  tasks             Search tasks (semantic by title)
    --query <q>     Search query (required)
    --status <s>    Filter by status: planning|ready|wip|review|done|blocked|archived
    --tag <name>    Filter by tag (repeatable)
    --due-lte <d>   Due date ≤ YYYY-MM-DD
    --due-gte <d>   Due date ≥ YYYY-MM-DD
    --limit <n>     Max results (default 5)
    --raw           Output full JSON

Environment:
  PALANTIR_API_URL         API base URL (required if not in credentials.json)
  PALANTIR_CONFIG_DIR      Override default ~/.config/palantir
EOF
	exit "${1:-2}"
}

_compact_results() {
	python3 -c "
import json, sys
items = json.load(sys.stdin)
if not isinstance(items, list):
	items = [items]
out = []
for item in items:
	out.append({
		'id': item.get('id'),
		'score': round(item.get('score', 0), 4) if 'score' in item else None,
		'kind': item.get('kind') or item.get('status'),
		'bluf': item.get('bluf') or item.get('title'),
		'tags': item.get('tags', []),
	})
print(json.dumps(out, indent=2))
"
}

cmd="${1:-}"
[[ -z "$cmd" ]] && usage
[[ "$cmd" == "-h" || "$cmd" == "--help" ]] && usage 0

API_URL=$(palantir::load_api_url)
shift

case "$cmd" in
	knowledge)
		QUERY="" KIND="" TAGS=() PLAN_ID="" TASK_ID="" MODE="hybrid" LIMIT=5 RAW=0
		while [[ $# -gt 0 ]]; do
			case "$1" in
				--query) QUERY="$2"; shift 2 ;;
				--kind) KIND="$2"; shift 2 ;;
				--tag) TAGS+=("$2"); shift 2 ;;
				--plan-id) PLAN_ID="$2"; shift 2 ;;
				--task-id) TASK_ID="$2"; shift 2 ;;
				--mode) MODE="$2"; shift 2 ;;
				--limit) LIMIT="$2"; shift 2 ;;
				--raw) RAW=1; shift ;;
				-h|--help) usage 0 ;;
				*) echo "Unknown flag: $1" >&2; usage ;;
			esac
		done
		[[ -z "$QUERY" ]] && { echo "Error: --query is required" >&2; usage; }
		python3 - "$QUERY" "$KIND" "$MODE" "$LIMIT" "$PLAN_ID" "$TASK_ID" "${TAGS[@]+"${TAGS[@]}"}" <<'PYEOF' | palantir::curl -X POST "${API_URL}/v1/search" --data-binary @- | palantir::strip_embeddings | { [[ $RAW -eq 1 ]] && palantir::pretty || _compact_results; }
import json, sys
query, kind, mode, limit, plan_id, task_id = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6]
tags = sys.argv[7:]
d = {"query": query, "search_mode": mode, "limit": int(limit)}
if kind: d["kind"] = kind
if plan_id: d["plan_id"] = int(plan_id)
if task_id: d["task_id"] = int(task_id)
if tags: d["tags"] = tags
print(json.dumps(d))
PYEOF
		;;
	tasks)
		QUERY="" STATUS="" TAGS=() DUE_LTE="" DUE_GTE="" LIMIT=5 RAW=0
		while [[ $# -gt 0 ]]; do
			case "$1" in
				--query) QUERY="$2"; shift 2 ;;
				--status) STATUS="$2"; shift 2 ;;
				--tag) TAGS+=("$2"); shift 2 ;;
				--due-lte) DUE_LTE="$2"; shift 2 ;;
				--due-gte) DUE_GTE="$2"; shift 2 ;;
				--limit) LIMIT="$2"; shift 2 ;;
				--raw) RAW=1; shift ;;
				-h|--help) usage 0 ;;
				*) echo "Unknown flag: $1" >&2; usage ;;
			esac
		done
		[[ -z "$QUERY" ]] && { echo "Error: --query is required" >&2; usage; }
		python3 - "$QUERY" "$STATUS" "$LIMIT" "$DUE_LTE" "$DUE_GTE" "${TAGS[@]+"${TAGS[@]}"}" <<'PYEOF' | palantir::curl -X POST "${API_URL}/v1/tasks/search" --data-binary @- | palantir::strip_embeddings | { [[ $RAW -eq 1 ]] && palantir::pretty || _compact_results; }
import json, sys
query, status, limit, due_lte, due_gte = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
tags = sys.argv[6:]
d = {"query": query, "limit": int(limit)}
if status: d["status"] = status
if due_lte: d["due_date_lte"] = due_lte
if due_gte: d["due_date_gte"] = due_gte
if tags: d["tags"] = tags
print(json.dumps(d))
PYEOF
		;;
	-h|--help) usage 0 ;;
	*) echo "Unknown subcommand: $cmd" >&2; usage ;;
esac
