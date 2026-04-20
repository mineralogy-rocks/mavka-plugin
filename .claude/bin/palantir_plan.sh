#!/usr/bin/env bash
set -euo pipefail

_DIR="$(dirname "${BASH_SOURCE[0]}")"
source "$_DIR/_auth.sh"
source "$_DIR/_common.sh"

usage() {
	cat >&2 <<EOF
Usage: palantir_plan.sh <subcommand> [flags]

Subcommands:
  save              Save an approved plan with atomized entries
    --title <t>     Plan title (required)
    --content <t>   Full plan text (required; use --stdin to read from stdin)
    --stdin         Read plan content from stdin
    --entries-file <path>
                    JSON file with atomized entries array: [{content,bluf,kind,tags},...] (required)
    --tag <name>    Plan-level tag (repeatable)
    --dedupe-key <k> Idempotency key (prevents duplicates on retry)

  get               Get a plan and its entries by ID
    <id>            Plan ID (positional)

  list              List plans
    --query <q>     Semantic search query (optional)
    --tag <name>    Filter by tag (repeatable)
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
	save)
		TITLE="" CONTENT="" ENTRIES_FILE="" TAGS=() DEDUPE_KEY="" USE_STDIN=0
		while [[ $# -gt 0 ]]; do
			case "$1" in
				--title) TITLE="$2"; shift 2 ;;
				--content) CONTENT="$2"; shift 2 ;;
				--stdin) USE_STDIN=1; shift ;;
				--entries-file) ENTRIES_FILE="$2"; shift 2 ;;
				--tag) TAGS+=("$2"); shift 2 ;;
				--dedupe-key) DEDUPE_KEY="$2"; shift 2 ;;
				-h|--help) usage 0 ;;
				*) echo "Unknown flag: $1" >&2; usage ;;
			esac
		done
		[[ -z "$TITLE" ]] && { echo "Error: --title is required" >&2; usage; }
		if [[ $USE_STDIN -eq 1 ]]; then
			CONTENT=$(cat)
		fi
		[[ -z "$CONTENT" ]] && { echo "Error: --content or --stdin is required" >&2; usage; }
		[[ -z "$ENTRIES_FILE" ]] && { echo "Error: --entries-file is required" >&2; usage; }
		palantir::validate_json_file "$ENTRIES_FILE"
		python3 - "$TITLE" "$CONTENT" "$ENTRIES_FILE" "$DEDUPE_KEY" "${TAGS[@]+"${TAGS[@]}"}" <<'PYEOF' | palantir::curl -X POST "${API_URL}/v1/plans" --data-binary @- | palantir::strip_embeddings | palantir::pretty
import json, sys
title, content, entries_file, dedupe_key = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
tags = sys.argv[5:]
with open(entries_file) as f:
	entries = json.load(f)
if isinstance(entries, dict) and "entries" in entries:
	entries = entries["entries"]
d = {"title": title, "content": content, "entries": entries, "tags": tags}
if dedupe_key:
	d["dedupe_key"] = dedupe_key
print(json.dumps(d))
PYEOF
		;;
	get)
		ID="${1:-}"
		[[ -z "$ID" ]] && { echo "Error: plan ID is required" >&2; usage; }
		palantir::curl "${API_URL}/v1/plans/${ID}" | palantir::strip_embeddings | palantir::pretty
		;;
	list)
		QUERY="" TAGS=() LIMIT=20 OFFSET=0
		while [[ $# -gt 0 ]]; do
			case "$1" in
				--query) QUERY="$2"; shift 2 ;;
				--tag) TAGS+=("$2"); shift 2 ;;
				--limit) LIMIT="$2"; shift 2 ;;
				--offset) OFFSET="$2"; shift 2 ;;
				-h|--help) usage 0 ;;
				*) echo "Unknown flag: $1" >&2; usage ;;
			esac
		done
		PARAMS="limit=${LIMIT}&offset=${OFFSET}"
		[[ -n "$QUERY" ]] && PARAMS="${PARAMS}&query=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "$QUERY")"
		for t in "${TAGS[@]+"${TAGS[@]}"}"; do
			PARAMS="${PARAMS}&tag=${t}"
		done
		palantir::curl "${API_URL}/v1/plans?${PARAMS}" | palantir::strip_embeddings | palantir::pretty
		;;
	-h|--help) usage 0 ;;
	*) echo "Unknown subcommand: $cmd" >&2; usage ;;
esac
