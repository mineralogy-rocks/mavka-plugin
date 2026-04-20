#!/usr/bin/env bash
set -euo pipefail

# palantir_logout.sh — Revoke tokens and delete local credentials.
# Leaves client.json intact so re-login reuses the registered client.

PALANTIR_CONFIG_DIR="${PALANTIR_CONFIG_DIR:-$HOME/.config/palantir}"
CREDS="$PALANTIR_CONFIG_DIR/credentials.json"

if [[ ! -f "$CREDS" ]]; then
	echo "Not logged in (no credentials found)."
	exit 0
fi

API_URL=$(python3 -c "import json; d=json.load(open('$CREDS')); print(d.get('api_url',''))" 2>/dev/null || true)
ACCESS_TOKEN=$(python3 -c "import json; d=json.load(open('$CREDS')); print(d.get('access_token',''))" 2>/dev/null || true)
REFRESH_TOKEN=$(python3 -c "import json; d=json.load(open('$CREDS')); print(d.get('refresh_token',''))" 2>/dev/null || true)

if [[ -n "$API_URL" ]]; then
	if [[ -n "$ACCESS_TOKEN" ]]; then
		curl --silent --show-error -X POST "$API_URL/oauth/revoke" \
			-d "token=${ACCESS_TOKEN}&token_type_hint=access_token" >/dev/null 2>&1 || true
	fi
	if [[ -n "$REFRESH_TOKEN" ]]; then
		curl --silent --show-error -X POST "$API_URL/oauth/revoke" \
			-d "token=${REFRESH_TOKEN}&token_type_hint=refresh_token" >/dev/null 2>&1 || true
	fi
fi

rm -f "$CREDS"
echo "Logged out. Credentials deleted."
echo "client.json retained — re-running palantir_login.sh will reuse the registered client."
