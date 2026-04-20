# Palantir common utilities — sourced by CRUD wrappers, not executed directly.
# Usage: source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

palantir::pretty() {
	if command -v jq &>/dev/null; then
		jq .
	else
		cat
	fi
}

# Build a JSON object from key=value pairs passed as positional args.
# Usage: palantir::build_json key1 "value1" key2 "value2" ...
# Produces: {"key1":"value1","key2":"value2"}
palantir::build_json() {
	python3 - "$@" <<'PYEOF'
import sys, json
args = sys.argv[1:]
if len(args) % 2 != 0:
	print("Error: build_json requires pairs of key value", file=sys.stderr)
	sys.exit(1)
d = {}
for i in range(0, len(args), 2):
	k, v = args[i], args[i+1]
	try:
		d[k] = json.loads(v)
	except (json.JSONDecodeError, ValueError):
		d[k] = v
print(json.dumps(d))
PYEOF
}

# Validate that a file contains valid JSON before sending it.
palantir::validate_json_file() {
	local file="$1"
	if ! python3 -c "import json; json.load(open('$file'))" 2>/dev/null; then
		echo "Error: '$file' is not valid JSON." >&2
		return 1
	fi
}

# Strip embedding arrays from a JSON response (they're huge and useless for display).
palantir::strip_embeddings() {
	python3 -c "
import json, sys
data = json.load(sys.stdin)
def strip(obj):
	if isinstance(obj, dict):
		return {k: strip(v) for k, v in obj.items() if k not in ('embedding', 'bluf_embedding', 'title_embedding')}
	if isinstance(obj, list):
		return [strip(i) for i in obj]
	return obj
print(json.dumps(strip(data), indent=2))
"
}
