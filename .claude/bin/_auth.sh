# Palantir auth library — sourced by all wrappers, not executed directly.
# Usage: source "$(dirname "${BASH_SOURCE[0]}")/_auth.sh"

PALANTIR_CONFIG_DIR="${PALANTIR_CONFIG_DIR:-$HOME/.config/palantir}"
CREDS="$PALANTIR_CONFIG_DIR/credentials.json"
CLIENT_FILE="$PALANTIR_CONFIG_DIR/client.json"

palantir::load_api_url() {
	if [[ -n "${PALANTIR_API_URL:-}" ]]; then
		echo "$PALANTIR_API_URL"
		return
	fi
	if [[ -f "$CREDS" ]]; then
		local url
		url=$(python3 -c "import json,sys; d=json.load(open('$CREDS')); print(d.get('api_url',''))" 2>/dev/null)
		if [[ -n "$url" ]]; then
			echo "$url"
			return
		fi
	fi
	echo "Error [PALANTIR_LOGIN_REQUIRED]: PALANTIR_API_URL is not set and no credentials found. Invoke the palantir skill to log in." >&2
	return 1
}

palantir::require_login() {
	if [[ ! -f "$CREDS" ]]; then
		echo "Error [PALANTIR_LOGIN_REQUIRED]: Not logged in. Invoke the palantir skill to log in." >&2
		return 1
	fi
	local token
	token=$(python3 -c "import json; d=json.load(open('$CREDS')); print(d.get('access_token',''))" 2>/dev/null)
	if [[ -z "$token" ]]; then
		echo "Error [PALANTIR_LOGIN_REQUIRED]: credentials.json is missing access_token. Invoke the palantir skill to log in." >&2
		return 1
	fi
}

palantir::access_token() {
	palantir::require_login || return 1
	local now expires_at
	now=$(date +%s)
	expires_at=$(python3 -c "import json; d=json.load(open('$CREDS')); print(int(d.get('expires_at',0)))" 2>/dev/null)
	if (( now + 30 >= expires_at )); then
		palantir::refresh || return 1
	fi
	python3 -c "import json; d=json.load(open('$CREDS')); print(d['access_token'])"
}

palantir::refresh() {
	local api_url refresh_token client_id client_secret
	api_url=$(palantir::load_api_url) || return 1
	refresh_token=$(python3 -c "import json; d=json.load(open('$CREDS')); print(d.get('refresh_token',''))" 2>/dev/null)
	if [[ -z "$refresh_token" ]]; then
		echo "Error [PALANTIR_LOGIN_REQUIRED]: No refresh token. Invoke the palantir skill to log in." >&2
		return 1
	fi
	client_id=$(python3 -c "import json; d=json.load(open('$CLIENT_FILE')); print(d['client_id'])" 2>/dev/null)
	client_secret=$(python3 -c "import json; d=json.load(open('$CLIENT_FILE')); print(d['client_secret'])" 2>/dev/null)
	if [[ -z "$client_id" || -z "$client_secret" ]]; then
		echo "Error [PALANTIR_LOGIN_REQUIRED]: client.json missing or corrupt. Invoke the palantir skill to log in." >&2
		return 1
	fi
	local response
	response=$(curl --fail-with-body --silent --show-error -X POST "$api_url/oauth/token" \
		-d "grant_type=refresh_token&refresh_token=${refresh_token}&client_id=${client_id}&client_secret=${client_secret}" 2>&1)
	local rc=$?
	if [[ $rc -ne 0 ]]; then
		echo "Error [PALANTIR_LOGIN_REQUIRED]: Token refresh failed: $response" >&2
		echo "Session may have expired. Invoke the palantir skill to log in." >&2
		return 1
	fi
	local new_access new_refresh expires_in issued_at
	new_access=$(python3 -c "import json,sys; d=json.loads(sys.stdin.read()); print(d['access_token'])" <<<"$response" 2>/dev/null)
	new_refresh=$(python3 -c "import json,sys; d=json.loads(sys.stdin.read()); print(d.get('refresh_token',''))" <<<"$response" 2>/dev/null)
	expires_in=$(python3 -c "import json,sys; d=json.loads(sys.stdin.read()); print(int(d.get('expires_in',3600)))" <<<"$response" 2>/dev/null)
	if [[ -z "$new_access" ]]; then
		echo "Error: Refresh response missing access_token: $response" >&2
		return 1
	fi
	issued_at=$(date +%s)
	local expires_at=$(( issued_at + expires_in ))
	python3 - <<PYEOF
import json, os
creds_path = "$CREDS"
tmp = creds_path + ".tmp"
with open(creds_path) as f:
	d = json.load(f)
d["access_token"] = "$new_access"
if "$new_refresh":
	d["refresh_token"] = "$new_refresh"
d["expires_at"] = $expires_at
d["issued_at"] = $issued_at
with open(tmp, "w") as f:
	json.dump(d, f, indent=2)
os.chmod(tmp, 0o600)
os.replace(tmp, creds_path)
PYEOF
}

_palantir::do_curl() {
	local token="$1"
	shift
	local tmp_body tmp_code
	tmp_body=$(mktemp)
	tmp_code=$(mktemp)
	curl --fail-with-body --silent --show-error \
		-H "Authorization: Bearer $token" \
		-H "Content-Type: application/json" \
		-w "%{http_code}" \
		-o "$tmp_body" \
		"$@" >"$tmp_code" 2>&1
	local rc=$?
	local body code
	body=$(cat "$tmp_body")
	code=$(cat "$tmp_code")
	rm -f "$tmp_body" "$tmp_code"
	echo "$code"
	echo "$body"
	return $rc
}

palantir::curl() {
	local api_url token
	api_url=$(palantir::load_api_url) || return 1
	token=$(palantir::access_token) || return 1

	local tmp_out
	tmp_out=$(mktemp)
	_palantir::do_curl "$token" "$@" >"$tmp_out" 2>&1
	local rc=$?
	local http_code body
	http_code=$(head -1 "$tmp_out")
	body=$(tail -n +2 "$tmp_out")
	rm -f "$tmp_out"

	if [[ "$http_code" == "401" ]]; then
		palantir::refresh || { echo "$body" >&2; return 1; }
		token=$(python3 -c "import json; d=json.load(open('$CREDS')); print(d['access_token'])")
		tmp_out=$(mktemp)
		_palantir::do_curl "$token" "$@" >"$tmp_out" 2>&1
		rc=$?
		http_code=$(head -1 "$tmp_out")
		body=$(tail -n +2 "$tmp_out")
		rm -f "$tmp_out"
		if [[ "$http_code" == "401" ]]; then
			echo "Error [PALANTIR_LOGIN_REQUIRED]: Session revoked. Invoke the palantir skill to log in." >&2
			echo "$body" >&2
			return 1
		fi
	fi

	if [[ $rc -ne 0 ]]; then
		echo "HTTP $http_code: $body" >&2
		return 1
	fi
	echo "$body"
}
