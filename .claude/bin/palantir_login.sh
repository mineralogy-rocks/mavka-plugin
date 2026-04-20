#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# palantir_login.sh — PKCE authorization-code login for the Palantir REST API.
# Registers a client (once), starts a loopback listener, opens the browser,
# and exchanges the auth code for bearer + refresh tokens stored at
# ~/.config/palantir/credentials.json (chmod 600).
# ---------------------------------------------------------------------------

# --- Preflight ---------------------------------------------------------------
# Marker lines consumed by the palantir skill when this script is run in the
# background via Claude Code's Bash tool:
#   PALANTIR_AUTH_URL: <url>       — printed once the authorization URL is ready
#   PALANTIR_LOGIN_OK: <github>    — printed on successful token exchange
#   PALANTIR_LOGIN_ERROR: <reason> — printed on any failure before exit 1
#
# Markers are additive; human-readable output is preserved for direct shell use.
fail() {
	echo "PALANTIR_LOGIN_ERROR: $*"
	echo "Error: $*" >&2
	exit 1
}

for cmd in openssl python3 curl jq; do
	if ! command -v "$cmd" &>/dev/null; then
		fail "'$cmd' is required but not found. Install it and retry."
	fi
done

PALANTIR_CONFIG_DIR="${PALANTIR_CONFIG_DIR:-$HOME/.config/palantir}"
CREDS="$PALANTIR_CONFIG_DIR/credentials.json"
CLIENT_FILE="$PALANTIR_CONFIG_DIR/client.json"

mkdir -p "$PALANTIR_CONFIG_DIR"
chmod 700 "$PALANTIR_CONFIG_DIR"

# --- API URL -----------------------------------------------------------------
API_URL="${PALANTIR_API_URL:-}"
if [[ -z "$API_URL" && -f "$CREDS" ]]; then
	API_URL=$(python3 -c "import json; d=json.load(open('$CREDS')); print(d.get('api_url',''))" 2>/dev/null || true)
fi
if [[ -z "$API_URL" ]]; then
	read -rp "Palantir API URL (e.g. https://palantir.example.com): " API_URL
fi
API_URL="${API_URL%/}"

# --- Register or reuse client ------------------------------------------------
# Pool of loopback redirect URIs registered with the server so we can pick any
# free port at runtime. The OAuth server does strict exact-match on redirect_uri.
REDIRECT_URI_POOL=(
	"http://127.0.0.1:54321/cb"
	"http://127.0.0.1:54322/cb"
	"http://127.0.0.1:54323/cb"
	"http://127.0.0.1:54324/cb"
	"http://127.0.0.1:54325/cb"
	"http://127.0.0.1:54326/cb"
	"http://127.0.0.1:54327/cb"
	"http://127.0.0.1:54328/cb"
)

register_client() {
	echo "Registering new OAuth2 client with Palantir..."
	local pool_json
	pool_json=$(python3 -c "import json,sys; print(json.dumps(sys.argv[1:]))" "${REDIRECT_URI_POOL[@]}")
	local reg
	reg=$(curl --fail-with-body --silent --show-error -X POST "$API_URL/oauth/register" \
		-H "Content-Type: application/json" \
		-d "{\"client_name\":\"palantir-plugin\",\"redirect_uris\":${pool_json},\"grant_types\":[\"authorization_code\",\"refresh_token\"],\"scope\":\"palantir:read palantir:write\",\"token_endpoint_auth_method\":\"client_secret_post\"}")
	CLIENT_ID=$(jq -r .client_id <<<"$reg")
	CLIENT_SECRET=$(jq -r .client_secret <<<"$reg")
	python3 - "${REDIRECT_URI_POOL[@]}" <<PYEOF
import json, os, sys
data = {
	"client_id": "$CLIENT_ID",
	"client_secret": "$CLIENT_SECRET",
	"redirect_uris": sys.argv[1:],
}
tmp = "$CLIENT_FILE.tmp"
with open(tmp, "w") as f:
	json.dump(data, f, indent=2)
os.chmod(tmp, 0o600)
os.replace(tmp, "$CLIENT_FILE")
PYEOF
	echo "Client registered and stored."
}

NEEDS_REGISTER=1
if [[ -f "$CLIENT_FILE" ]]; then
	CLIENT_ID=$(python3 -c "import json; d=json.load(open('$CLIENT_FILE')); print(d['client_id'])")
	CLIENT_SECRET=$(python3 -c "import json; d=json.load(open('$CLIENT_FILE')); print(d['client_secret'])")
	STORED_URIS=$(python3 -c "import json; d=json.load(open('$CLIENT_FILE')); print(' '.join(d.get('redirect_uris', [])))" 2>/dev/null)
	EXPECTED_URIS="${REDIRECT_URI_POOL[*]}"
	if [[ "$STORED_URIS" == "$EXPECTED_URIS" ]]; then
		echo "Reusing registered client: $CLIENT_ID"
		NEEDS_REGISTER=0
	else
		echo "Stored client has outdated redirect URI pool; re-registering..."
		rm -f "$CLIENT_FILE"
	fi
fi

if [[ $NEEDS_REGISTER -eq 1 ]]; then
	register_client
fi

# --- PKCE + state ------------------------------------------------------------
CODE_VERIFIER=$(openssl rand -base64 32 | tr -d '=+/' | cut -c1-43)
CODE_CHALLENGE=$(printf '%s' "$CODE_VERIFIER" | openssl dgst -sha256 -binary | base64 | tr '+/' '-_' | tr -d '=')
STATE=$(openssl rand -base64 18 | tr -d '=+/' | cut -c1-24)

# --- Pick a free port from the registered pool ------------------------------
pick_redirect_uri() {
	local uri port
	for uri in "${REDIRECT_URI_POOL[@]}"; do
		port="${uri##*:}"
		port="${port%%/*}"
		if python3 -c "import socket; s=socket.socket(); s.bind(('127.0.0.1',$port)); s.close()" 2>/dev/null; then
			echo "$uri"
			return 0
		fi
	done
	echo "Error: All ports in the redirect pool are in use." >&2
	return 1
}
REDIRECT_URI=$(pick_redirect_uri) || fail "All ports in the redirect pool are in use."
CB_PORT="${REDIRECT_URI##*:}"
CB_PORT="${CB_PORT%%/*}"

# --- Authorization URL -------------------------------------------------------
AUTH_URL="${API_URL}/oauth/authorize?response_type=code&client_id=${CLIENT_ID}&redirect_uri=${REDIRECT_URI}&scope=palantir%3Aread%20palantir%3Awrite&state=${STATE}&code_challenge=${CODE_CHALLENGE}&code_challenge_method=S256"

# Machine-readable marker — emit before any blocking I/O so the skill can pick
# it up from background stdout and relay it to the user.
echo "PALANTIR_AUTH_URL: $AUTH_URL"

echo ""
echo "Opening authorization URL in your browser..."
echo ""
echo "  $AUTH_URL"
echo ""
if command -v open &>/dev/null; then
	open "$AUTH_URL" 2>/dev/null || true
elif command -v xdg-open &>/dev/null; then
	xdg-open "$AUTH_URL" 2>/dev/null || true
fi

# --- Start loopback listener -------------------------------------------------
CODE_FILE=$(mktemp)
python3 - "$CB_PORT" "$CODE_FILE" <<'PYEOF'
import sys, socket, urllib.parse

port = int(sys.argv[1])
code_file = sys.argv[2]

srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(("127.0.0.1", port))
srv.listen(1)

conn, _ = srv.accept()
data = b""
while b"\r\n\r\n" not in data:
	chunk = conn.recv(4096)
	if not chunk:
		break
	data += chunk

request_line = data.split(b"\r\n")[0].decode()
path = request_line.split(" ")[1] if len(request_line.split(" ")) > 1 else "/"
params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(path).query))

if "error" in params:
	body = f"<h2>Authorization denied</h2><p>{params.get('error_description', params['error'])}</p><p>You may close this tab.</p>"
	conn.sendall(b"HTTP/1.1 400 Bad Request\r\nContent-Type: text/html\r\n\r\n" + body.encode())
	conn.close()
	with open(code_file, "w") as f:
		f.write("ERROR:" + params.get("error_description", params["error"]) + "\n")
else:
	body = "<h2>Authorized</h2><p>You may close this tab.</p>"
	conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n" + body.encode())
	conn.close()
	with open(code_file, "w") as f:
		f.write(params.get("code", "") + "\n" + params.get("state", "") + "\n")
srv.close()
PYEOF

CODE_LINE=$(head -1 "$CODE_FILE")
RETURNED_STATE=$(sed -n '2p' "$CODE_FILE")
rm -f "$CODE_FILE"

if [[ "$CODE_LINE" == ERROR:* ]]; then
	fail "Authorization denied — ${CODE_LINE#ERROR:}"
fi
if [[ -z "$CODE_LINE" ]]; then
	fail "No authorization code received."
fi
if [[ "$RETURNED_STATE" != "$STATE" ]]; then
	fail "State mismatch — possible CSRF. Re-run login."
fi

# --- Exchange code for tokens ------------------------------------------------
echo "Exchanging authorization code for tokens..."
TOKEN_RESPONSE=$(curl --fail-with-body --silent --show-error -X POST "$API_URL/oauth/token" \
	-d "grant_type=authorization_code&code=${CODE_LINE}&redirect_uri=${REDIRECT_URI}&client_id=${CLIENT_ID}&client_secret=${CLIENT_SECRET}&code_verifier=${CODE_VERIFIER}")

ACCESS_TOKEN=$(jq -r .access_token <<<"$TOKEN_RESPONSE")
REFRESH_TOKEN=$(jq -r '.refresh_token // ""' <<<"$TOKEN_RESPONSE")
EXPIRES_IN=$(jq -r '.expires_in // 3600' <<<"$TOKEN_RESPONSE")
SCOPE=$(jq -r '.scope // "palantir:read palantir:write"' <<<"$TOKEN_RESPONSE")
TOKEN_TYPE=$(jq -r '.token_type // "Bearer"' <<<"$TOKEN_RESPONSE")

if [[ -z "$ACCESS_TOKEN" || "$ACCESS_TOKEN" == "null" ]]; then
	fail "Token exchange failed: $TOKEN_RESPONSE"
fi

ISSUED_AT=$(date +%s)
EXPIRES_AT=$(( ISSUED_AT + EXPIRES_IN ))

python3 - <<PYEOF
import json, os, time
data = {
	"access_token": "$ACCESS_TOKEN",
	"refresh_token": "$REFRESH_TOKEN",
	"token_type": "$TOKEN_TYPE",
	"scope": "$SCOPE",
	"expires_at": $EXPIRES_AT,
	"issued_at": $ISSUED_AT,
	"api_url": "$API_URL",
}
tmp = "$CREDS.tmp"
with open(tmp, "w") as f:
	json.dump(data, f, indent=2)
os.chmod(tmp, 0o600)
os.replace(tmp, "$CREDS")
PYEOF

# --- Confirm identity --------------------------------------------------------
ME=$(curl --fail-with-body --silent --show-error \
	-H "Authorization: Bearer $ACCESS_TOKEN" \
	"$API_URL/auth/me" 2>/dev/null || echo '{}')
GITHUB_LOGIN=$(jq -r '.login // .name // "unknown"' <<<"$ME" 2>/dev/null || echo "unknown")

echo "PALANTIR_LOGIN_OK: $GITHUB_LOGIN"
echo ""
echo "Logged in as: $GITHUB_LOGIN"
echo "Credentials stored at: $CREDS (mode 600)"
echo ""
echo "Set PALANTIR_API_URL=$API_URL in your shell profile to skip the prompt next time."
