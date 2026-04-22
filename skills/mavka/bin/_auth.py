"""Mavka credentials store + authed HTTP helper.

Stores credentials and client info at ~/.config/mavka/ (override via
MAVKA_CONFIG_DIR). Handles OAuth2 refresh-token rotation and retries a
single 401 after refreshing. All functions raise LoginRequired when the
caller must re-authenticate.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


DEFAULT_API_URL = "http://mavka.local:81"


class LoginRequired(Exception):
	"""Raised when the user must (re-)run `mavka login`."""


def config_dir() -> str:
	return os.environ.get("MAVKA_CONFIG_DIR", os.path.expanduser("~/.config/mavka"))


def creds_path() -> str:
	return os.path.join(config_dir(), "credentials.json")


def client_path() -> str:
	return os.path.join(config_dir(), "client.json")


def ensure_config_dir() -> None:
	d = config_dir()
	os.makedirs(d, exist_ok=True)
	try:
		os.chmod(d, 0o700)
	except OSError:
		pass


def _read_json(path: str) -> dict[str, Any]:
	with open(path) as f:
		return json.load(f)


def _atomic_write_json(path: str, data: dict[str, Any]) -> None:
	ensure_config_dir()
	fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".tmp_", suffix=".json")
	try:
		with os.fdopen(fd, "w") as f:
			json.dump(data, f, indent=2)
		os.chmod(tmp, 0o600)
		os.replace(tmp, path)
	except Exception:
		try:
			os.unlink(tmp)
		except OSError:
			pass
		raise


def load_credentials() -> dict[str, Any]:
	path = creds_path()
	if not os.path.isfile(path):
		raise LoginRequired("Not logged in. Invoke the mavka skill to log in.")
	try:
		return _read_json(path)
	except (OSError, json.JSONDecodeError) as exc:
		raise LoginRequired(f"credentials.json unreadable: {exc}")


def load_client() -> dict[str, Any]:
	path = client_path()
	if not os.path.isfile(path):
		raise LoginRequired("client.json missing. Invoke the mavka skill to log in.")
	try:
		return _read_json(path)
	except (OSError, json.JSONDecodeError) as exc:
		raise LoginRequired(f"client.json unreadable: {exc}")


def save_credentials(data: dict[str, Any]) -> None:
	_atomic_write_json(creds_path(), data)


def save_client(data: dict[str, Any]) -> None:
	_atomic_write_json(client_path(), data)


def load_api_url() -> str:
	url = os.environ.get("MAVKA_API_URL")
	if url:
		return url.rstrip("/")
	try:
		creds = load_credentials()
		stored = creds.get("api_url")
		if stored:
			return stored.rstrip("/")
	except LoginRequired:
		pass
	return DEFAULT_API_URL


def _http(method: str, url: str, *, headers: dict[str, str] | None = None,
		  data: bytes | None = None, timeout: float = 30.0) -> tuple[int, bytes, dict[str, str]]:
	req = urllib.request.Request(url, method=method, data=data, headers=headers or {})
	try:
		with urllib.request.urlopen(req, timeout=timeout) as resp:
			body = resp.read()
			return resp.status, body, dict(resp.headers)
	except urllib.error.HTTPError as exc:
		body = exc.read() if exc.fp is not None else b""
		return exc.code, body, dict(exc.headers or {})


def refresh() -> None:
	creds = load_credentials()
	client = load_client()
	refresh_token = creds.get("refresh_token")
	if not refresh_token:
		raise LoginRequired("No refresh token. Invoke the mavka skill to log in.")
	api_url = load_api_url()
	form = urllib.parse.urlencode({
		"grant_type": "refresh_token",
		"refresh_token": refresh_token,
		"client_id": client["client_id"],
		"client_secret": client["client_secret"],
	}).encode()
	code, body, _ = _http(
		"POST", f"{api_url}/oauth/token",
		headers={"Content-Type": "application/x-www-form-urlencoded"},
		data=form,
	)
	if code != 200:
		raise LoginRequired(f"Token refresh failed ({code}): {body.decode(errors='replace')}")
	try:
		tok = json.loads(body)
	except json.JSONDecodeError as exc:
		raise LoginRequired(f"Token refresh returned non-JSON: {exc}")
	new_access = tok.get("access_token")
	if not new_access:
		raise LoginRequired(f"Refresh response missing access_token: {body.decode(errors='replace')}")
	now = int(time.time())
	expires_in = int(tok.get("expires_in", 3600))
	creds["access_token"] = new_access
	new_refresh = tok.get("refresh_token")
	if new_refresh:
		creds["refresh_token"] = new_refresh
	creds["expires_at"] = now + expires_in
	creds["issued_at"] = now
	save_credentials(creds)


def access_token() -> str:
	creds = load_credentials()
	tok = creds.get("access_token")
	if not tok:
		raise LoginRequired("credentials.json missing access_token. Invoke the mavka skill to log in.")
	expires_at = int(creds.get("expires_at", 0))
	if int(time.time()) + 30 >= expires_at:
		refresh()
		creds = load_credentials()
		tok = creds["access_token"]
	return tok


def request(method: str, path: str, *, json_body: Any = None,
			params: dict[str, Any] | list[tuple[str, Any]] | None = None) -> Any:
	"""Authed request. Returns parsed JSON body, raises on non-2xx.

	`params` may be a dict OR a list of (key, value) tuples — the latter
	supports repeated keys like `?tag=a&tag=b`.
	"""
	api_url = load_api_url()
	url = f"{api_url}{path}"
	if params:
		if isinstance(params, dict):
			pairs = [(k, v) for k, v in params.items() if v is not None and v != []]
		else:
			pairs = [(k, v) for k, v in params if v is not None and v != []]
		if pairs:
			url = f"{url}?{urllib.parse.urlencode(pairs, doseq=True)}"

	def _do(tok: str) -> tuple[int, bytes]:
		headers = {"Authorization": f"Bearer {tok}"}
		data = None
		if json_body is not None:
			headers["Content-Type"] = "application/json"
			data = json.dumps(json_body).encode()
		code, body, _ = _http(method, url, headers=headers, data=data)
		return code, body

	tok = access_token()
	code, body = _do(tok)
	if code == 401:
		refresh()
		tok = load_credentials()["access_token"]
		code, body = _do(tok)
		if code == 401:
			raise LoginRequired(f"Session revoked. Invoke the mavka skill to log in. Body: {body.decode(errors='replace')}")
	if code >= 400:
		raise RuntimeError(f"HTTP {code}: {body.decode(errors='replace')}")
	if not body:
		return None
	try:
		return json.loads(body)
	except json.JSONDecodeError:
		return body.decode(errors="replace")


def unauth_request(method: str, url: str, *, json_body: Any = None,
				   form_body: dict[str, Any] | None = None) -> tuple[int, Any]:
	"""Unauthenticated request used by login/logout for /oauth/* endpoints."""
	headers: dict[str, str] = {}
	data: bytes | None = None
	if json_body is not None:
		headers["Content-Type"] = "application/json"
		data = json.dumps(json_body).encode()
	elif form_body is not None:
		headers["Content-Type"] = "application/x-www-form-urlencoded"
		data = urllib.parse.urlencode(form_body).encode()
	code, body, _ = _http(method, url, headers=headers, data=data)
	parsed: Any
	if not body:
		parsed = None
	else:
		try:
			parsed = json.loads(body)
		except json.JSONDecodeError:
			parsed = body.decode(errors="replace")
	return code, parsed
