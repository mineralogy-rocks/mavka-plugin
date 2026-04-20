#!/usr/bin/env bash
set -euo pipefail

_DIR="$(dirname "${BASH_SOURCE[0]}")"
source "$_DIR/_auth.sh"
source "$_DIR/_common.sh"

usage() {
	cat >&2 <<EOF
Usage: palantir_tag.sh <subcommand> [flags]

Subcommands:
  list              List all tags
    --q <prefix>    Filter by prefix
    --limit <n>     Max results (default 50)

  create            Create a new tag
    --name <name>   Tag name (required)

  delete            Delete a tag by ID
    --id <id>       Tag ID (required)

Environment:
  PALANTIR_API_URL         API base URL (required if not in credentials.json)
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
	list)
		QUERY=""
		LIMIT=50
		while [[ $# -gt 0 ]]; do
			case "$1" in
				--q) QUERY="$2"; shift 2 ;;
				--limit) LIMIT="$2"; shift 2 ;;
				-h|--help) usage 0 ;;
				*) echo "Unknown flag: $1" >&2; usage ;;
			esac
		done
		PARAMS="limit=${LIMIT}"
		[[ -n "$QUERY" ]] && PARAMS="${PARAMS}&q=${QUERY}"
		palantir::curl "${API_URL}/v1/tags?${PARAMS}" | palantir::strip_embeddings | palantir::pretty
		;;
	create)
		NAME=""
		while [[ $# -gt 0 ]]; do
			case "$1" in
				--name) NAME="$2"; shift 2 ;;
				-h|--help) usage 0 ;;
				*) echo "Unknown flag: $1" >&2; usage ;;
			esac
		done
		[[ -z "$NAME" ]] && { echo "Error: --name is required" >&2; usage; }
		palantir::curl -X POST "${API_URL}/v1/tags" \
			--data-binary "{\"name\":\"${NAME}\"}" | palantir::strip_embeddings | palantir::pretty
		;;
	delete)
		ID=""
		while [[ $# -gt 0 ]]; do
			case "$1" in
				--id) ID="$2"; shift 2 ;;
				-h|--help) usage 0 ;;
				*) echo "Unknown flag: $1" >&2; usage ;;
			esac
		done
		[[ -z "$ID" ]] && { echo "Error: --id is required" >&2; usage; }
		palantir::curl -X DELETE "${API_URL}/v1/tags/${ID}" | palantir::pretty
		;;
	-h|--help) usage 0 ;;
	*) echo "Unknown subcommand: $cmd" >&2; usage ;;
esac
