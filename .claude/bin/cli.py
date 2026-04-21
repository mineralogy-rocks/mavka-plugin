#!/usr/bin/env python3
"""Palantir CLI — single entrypoint for all API operations.

Invoke via the `palantir` launcher (`palantir <group> <verb> [flags]`) or
directly: `python3 cli.py <group> <verb> [flags]`. The .sh wrappers are gone;
everything lives here.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import http.server
import json
import os
import secrets
import socket
import sys
import tempfile
import threading
import time
import urllib.parse
import webbrowser
from typing import Any

# Allow running as `python3 /path/to/cli.py …` — add our dir to sys.path so
# `_auth` / `_common` resolve regardless of cwd.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
	sys.path.insert(0, _HERE)

import _auth  # noqa: E402
import _common  # noqa: E402

# --------------------------------------------------------------------------
# Output helpers
# --------------------------------------------------------------------------


def _print_json(obj: Any) -> None:
	print(_common.pretty(_common.strip_embeddings(obj)))


def _login_required(msg: str) -> None:
	sys.stderr.write(f"Error [PALANTIR_LOGIN_REQUIRED]: {msg}\n")


# --------------------------------------------------------------------------
# entry
# --------------------------------------------------------------------------


def cmd_entry_create(args: argparse.Namespace) -> None:
	content = _common.resolve_content(args.content, args.stdin)
	if not args.bluf:
		raise SystemExit("Error: --bluf is required")
	if not content:
		raise SystemExit("Error: --content or --stdin is required")
	body: dict[str, Any] = {
		"bluf": args.bluf,
		"content": content,
		"kind": args.kind,
		"tags": args.tag or [],
	}
	if args.task_id is not None:
		body["task_id"] = args.task_id
	_print_json(_auth.request("POST", "/v1/entries", json_body=body))


def cmd_entry_bulk(args: argparse.Namespace) -> None:
	data = _common.load_json_file(args.file)
	_print_json(_auth.request("POST", "/v1/entries/bulk", json_body=data))


def cmd_entry_get(args: argparse.Namespace) -> None:
	_print_json(_auth.request("GET", f"/v1/entries/{args.id}"))


def cmd_entry_list(args: argparse.Namespace) -> None:
	params: list[tuple[str, Any]] = [("limit", args.limit), ("offset", args.offset)]
	if args.kind:
		params.append(("kind", args.kind))
	if args.plan_id is not None:
		params.append(("plan_id", args.plan_id))
	if args.task_id is not None:
		params.append(("task_id", args.task_id))
	if args.group_id is not None:
		params.append(("group_id", args.group_id))
	for t in args.tag or []:
		params.append(("tag", t))
	_print_json(_auth.request("GET", "/v1/entries", params=params))


# --------------------------------------------------------------------------
# task
# --------------------------------------------------------------------------


def cmd_task_create(args: argparse.Namespace) -> None:
	if not args.title:
		raise SystemExit("Error: --title is required")
	body: dict[str, Any] = {
		"title": args.title,
		"status": args.status,
		"tags": args.tag or [],
	}
	if args.due_date:
		body["due_date"] = args.due_date
	_print_json(_auth.request("POST", "/v1/tasks", json_body=body))


def cmd_task_get(args: argparse.Namespace) -> None:
	_print_json(_auth.request("GET", f"/v1/tasks/{args.id}"))


def cmd_task_update(args: argparse.Namespace) -> None:
	body: dict[str, Any] = {}
	if args.status is not None:
		body["status"] = args.status
	if args.title is not None:
		body["title"] = args.title
	if args.tag is not None:
		body["tags"] = args.tag
	if args.due_date is not None:
		body["due_date"] = None if args.due_date == "null" else args.due_date
	_print_json(_auth.request("PATCH", f"/v1/tasks/{args.id}", json_body=body))


def cmd_task_list(args: argparse.Namespace) -> None:
	params: list[tuple[str, Any]] = [("limit", args.limit), ("offset", args.offset)]
	if args.status:
		params.append(("status", args.status))
	if args.due_lte:
		params.append(("due_date_lte", args.due_lte))
	if args.due_gte:
		params.append(("due_date_gte", args.due_gte))
	for t in args.tag or []:
		params.append(("tag", t))
	_print_json(_auth.request("GET", "/v1/tasks", params=params))


# --------------------------------------------------------------------------
# plan
# --------------------------------------------------------------------------


def cmd_plan_save(args: argparse.Namespace) -> None:
	content = _common.resolve_content(args.content, args.stdin)
	if not args.title:
		raise SystemExit("Error: --title is required")
	if not content:
		raise SystemExit("Error: --content or --stdin is required")
	if args.entries_file:
		entries = _common.load_json_file(args.entries_file)
		if isinstance(entries, dict) and "entries" in entries:
			entries = entries["entries"]
	else:
		entries = []
	body: dict[str, Any] = {
		"title": args.title,
		"content": content,
		"entries": entries,
		"tags": args.tag or [],
	}
	if args.dedupe_key:
		body["dedupe_key"] = args.dedupe_key
	_print_json(_auth.request("POST", "/v1/plans", json_body=body))


def cmd_plan_get(args: argparse.Namespace) -> None:
	_print_json(_auth.request("GET", f"/v1/plans/{args.id}"))


def cmd_plan_list(args: argparse.Namespace) -> None:
	params: list[tuple[str, Any]] = [("limit", args.limit), ("offset", args.offset)]
	if args.query:
		params.append(("query", args.query))
	for t in args.tag or []:
		params.append(("tag", t))
	_print_json(_auth.request("GET", "/v1/plans", params=params))


# --------------------------------------------------------------------------
# search
# --------------------------------------------------------------------------


def _search_emit(result: Any, raw: bool) -> None:
	stripped = _common.strip_embeddings(result)
	if raw:
		print(_common.pretty(stripped))
	else:
		print(_common.pretty(_common.compact_search(stripped)))


def cmd_search_knowledge(args: argparse.Namespace) -> None:
	if not args.query:
		raise SystemExit("Error: --query is required")
	body: dict[str, Any] = {
		"query": args.query,
		"search_mode": args.mode,
		"limit": args.limit,
	}
	if args.kind:
		body["kind"] = args.kind
	if args.plan_id is not None:
		body["plan_id"] = args.plan_id
	if args.task_id is not None:
		body["task_id"] = args.task_id
	if args.tag:
		body["tags"] = args.tag
	_search_emit(_auth.request("POST", "/v1/search", json_body=body), args.raw)


def cmd_search_tasks(args: argparse.Namespace) -> None:
	if not args.query:
		raise SystemExit("Error: --query is required")
	body: dict[str, Any] = {"query": args.query, "limit": args.limit}
	if args.status:
		body["status"] = args.status
	if args.due_lte:
		body["due_date_lte"] = args.due_lte
	if args.due_gte:
		body["due_date_gte"] = args.due_gte
	if args.tag:
		body["tags"] = args.tag
	_search_emit(_auth.request("POST", "/v1/tasks/search", json_body=body), args.raw)


# --------------------------------------------------------------------------
# tag
# --------------------------------------------------------------------------


def cmd_tag_list(args: argparse.Namespace) -> None:
	params: list[tuple[str, Any]] = [("limit", args.limit)]
	if args.q:
		params.append(("q", args.q))
	_print_json(_auth.request("GET", "/v1/tags", params=params))


def cmd_tag_create(args: argparse.Namespace) -> None:
	if not args.name:
		raise SystemExit("Error: --name is required")
	_print_json(_auth.request("POST", "/v1/tags", json_body={"name": args.name}))


def cmd_tag_delete(args: argparse.Namespace) -> None:
	if args.id is None:
		raise SystemExit("Error: --id is required")
	_print_json(_auth.request("DELETE", f"/v1/tags/{args.id}"))


# --------------------------------------------------------------------------
# login / logout
# --------------------------------------------------------------------------


REDIRECT_URI_POOL = [
	f"http://127.0.0.1:{p}/cb" for p in range(54321, 54329)
]


def _fail_login(msg: str) -> None:
	print(f"PALANTIR_LOGIN_ERROR: {msg}")
	print(f"Error: {msg}", file=sys.stderr)
	raise SystemExit(1)


def _pkce_pair() -> tuple[str, str]:
	verifier = secrets.token_urlsafe(64)[:43]
	digest = hashlib.sha256(verifier.encode()).digest()
	challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
	return verifier, challenge


def _pick_free_port() -> str:
	for uri in REDIRECT_URI_POOL:
		port = int(uri.rsplit(":", 1)[1].split("/", 1)[0])
		s = socket.socket()
		try:
			s.bind(("127.0.0.1", port))
		except OSError:
			continue
		finally:
			s.close()
		return uri
	_fail_login("All ports in the redirect pool are in use.")
	raise AssertionError  # for type-checkers


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
	result: dict[str, str] = {}

	def log_message(self, format: str, *args: Any) -> None:  # silence access log
		return

	def do_GET(self) -> None:  # noqa: N802
		parsed = urllib.parse.urlparse(self.path)
		params = dict(urllib.parse.parse_qsl(parsed.query))
		if "error" in params:
			body = f"<h2>Authorization denied</h2><p>{params.get('error_description', params['error'])}</p><p>You may close this tab.</p>"
			self.send_response(400)
			self.send_header("Content-Type", "text/html")
			self.end_headers()
			self.wfile.write(body.encode())
			_CallbackHandler.result = {
				"error": params.get("error_description", params["error"]),
			}
		else:
			body = "<h2>Authorized</h2><p>You may close this tab.</p>"
			self.send_response(200)
			self.send_header("Content-Type", "text/html")
			self.end_headers()
			self.wfile.write(body.encode())
			_CallbackHandler.result = {
				"code": params.get("code", ""),
				"state": params.get("state", ""),
			}


def _await_callback(port: int, timeout: float = 300.0) -> dict[str, str]:
	_CallbackHandler.result = {}
	srv = http.server.HTTPServer(("127.0.0.1", port), _CallbackHandler)
	srv.timeout = 1.0
	deadline = time.monotonic() + timeout
	try:
		while not _CallbackHandler.result and time.monotonic() < deadline:
			srv.handle_request()
	finally:
		srv.server_close()
	return _CallbackHandler.result


def _register_client(api_url: str) -> dict[str, Any]:
	print("Registering new OAuth2 client with Palantir...")
	body = {
		"client_name": "palantir-plugin",
		"redirect_uris": REDIRECT_URI_POOL,
		"grant_types": ["authorization_code", "refresh_token"],
		"scope": "palantir:read palantir:write",
		"token_endpoint_auth_method": "client_secret_post",
	}
	code, resp = _auth.unauth_request("POST", f"{api_url}/oauth/register", json_body=body)
	if code != 200 or not isinstance(resp, dict):
		_fail_login(f"Client registration failed ({code}): {resp!r}")
	client = {
		"client_id": resp["client_id"],
		"client_secret": resp["client_secret"],
		"redirect_uris": REDIRECT_URI_POOL,
	}
	_auth.save_client(client)
	print("Client registered and stored.")
	return client


def _load_or_register_client(api_url: str) -> dict[str, Any]:
	path = _auth.client_path()
	if os.path.isfile(path):
		try:
			existing = _auth.load_client()
		except _auth.LoginRequired:
			existing = None
		if existing and existing.get("redirect_uris") == REDIRECT_URI_POOL:
			print(f"Reusing registered client: {existing['client_id']}")
			return existing
		print("Stored client has outdated redirect URI pool; re-registering...")
		try:
			os.unlink(path)
		except OSError:
			pass
	return _register_client(api_url)


def _resolve_api_url() -> str:
	url = os.environ.get("PALANTIR_API_URL")
	if url:
		return url.rstrip("/")
	try:
		creds = _auth.load_credentials()
		if creds.get("api_url"):
			return creds["api_url"].rstrip("/")
	except _auth.LoginRequired:
		pass
	try:
		url = input("Palantir API URL (e.g. https://palantir.example.com): ").strip()
	except EOFError:
		_fail_login("No API URL provided and no TTY to prompt.")
	if not url:
		_fail_login("No API URL provided.")
	return url.rstrip("/")


def cmd_login(args: argparse.Namespace) -> None:
	_auth.ensure_config_dir()
	api_url = _resolve_api_url()
	client = _load_or_register_client(api_url)

	verifier, challenge = _pkce_pair()
	state = secrets.token_urlsafe(18)
	redirect_uri = _pick_free_port()
	cb_port = int(redirect_uri.rsplit(":", 1)[1].split("/", 1)[0])

	# Match the legacy shell flow exactly: pass redirect_uri / client_id / state
	# as-is (they contain only URL-safe chars), and hard-code the scope encoding.
	# Over-escaping redirect_uri breaks OAuth servers that do strict byte-match
	# against the registered URI.
	auth_url = (
		f"{api_url}/oauth/authorize?response_type=code"
		f"&client_id={client['client_id']}"
		f"&redirect_uri={redirect_uri}"
		f"&scope=palantir%3Aread%20palantir%3Awrite"
		f"&state={state}"
		f"&code_challenge={challenge}"
		f"&code_challenge_method=S256"
	)

	# Machine-readable marker for the skill (picked up from background stdout).
	print(f"PALANTIR_AUTH_URL: {auth_url}")
	print()
	print("Opening authorization URL in your browser...")
	print()
	print(f"  {auth_url}")
	print()
	sys.stdout.flush()
	try:
		webbrowser.open(auth_url)
	except Exception:
		pass

	result = _await_callback(cb_port, timeout=300.0)
	if not result:
		_fail_login("Authorization flow timed out.")
	if "error" in result:
		_fail_login(f"Authorization denied — {result['error']}")
	if not result.get("code"):
		_fail_login("No authorization code received.")
	if result.get("state") != state:
		_fail_login("State mismatch — possible CSRF. Re-run login.")

	print("Exchanging authorization code for tokens...")
	code, tok = _auth.unauth_request("POST", f"{api_url}/oauth/token", form_body={
		"grant_type": "authorization_code",
		"code": result["code"],
		"redirect_uri": redirect_uri,
		"client_id": client["client_id"],
		"client_secret": client["client_secret"],
		"code_verifier": verifier,
	})
	if code != 200 or not isinstance(tok, dict) or not tok.get("access_token"):
		_fail_login(f"Token exchange failed ({code}): {tok!r}")

	now = int(time.time())
	creds = {
		"access_token": tok["access_token"],
		"refresh_token": tok.get("refresh_token", ""),
		"token_type": tok.get("token_type", "Bearer"),
		"scope": tok.get("scope", "palantir:read palantir:write"),
		"expires_at": now + int(tok.get("expires_in", 3600)),
		"issued_at": now,
		"api_url": api_url,
	}
	_auth.save_credentials(creds)

	# Confirm identity.
	try:
		me = _auth.request("GET", "/auth/me")
		login = (me or {}).get("login") or (me or {}).get("name") or "unknown"
	except Exception:
		login = "unknown"

	print(f"PALANTIR_LOGIN_OK: {login}")
	print()
	print(f"Logged in as: {login}")
	print(f"Credentials stored at: {_auth.creds_path()} (mode 600)")
	print()
	print(f"Set PALANTIR_API_URL={api_url} in your shell profile to skip the prompt next time.")


def cmd_logout(args: argparse.Namespace) -> None:
	path = _auth.creds_path()
	if not os.path.isfile(path):
		print("Not logged in (no credentials found).")
		return
	try:
		creds = _auth.load_credentials()
	except _auth.LoginRequired:
		creds = {}
	api_url = creds.get("api_url")
	if api_url:
		for key, hint in (("access_token", "access_token"), ("refresh_token", "refresh_token")):
			tok = creds.get(key)
			if tok:
				try:
					_auth.unauth_request("POST", f"{api_url}/oauth/revoke", form_body={
						"token": tok,
						"token_type_hint": hint,
					})
				except Exception:
					pass
	try:
		os.unlink(path)
	except OSError:
		pass
	print("Logged out. Credentials deleted.")
	print("client.json retained — re-running `palantir login` will reuse the registered client.")


# --------------------------------------------------------------------------
# perms — permission installer
# --------------------------------------------------------------------------


_PERMS_GROUPS = ["entry", "task", "plan", "search", "tag", "login", "perms"]
_PERMS_ASK_VERB = "logout"


def _plugin_bin_path() -> str:
	# cli.py lives at <plugin>/.claude/bin/cli.py — resolve the palantir launcher.
	return os.path.abspath(os.path.join(_HERE, "palantir"))


def _perms_patterns() -> tuple[list[str], list[str]]:
	"""Return (allow, ask) matcher sets covering the three plausible invocation forms:

	1. ${CLAUDE_PLUGIN_ROOT}/.claude/bin/palantir … — if matchers expand plugin vars
	2. /abs/path/.claude/bin/palantir …            — concrete path for this machine
	3. palantir …                                  — if .claude/bin/ is on PATH
	"""
	abs_bin = _plugin_bin_path()
	var_bin = "${CLAUDE_PLUGIN_ROOT}/.claude/bin/palantir"
	bare_bin = "palantir"
	allow: list[str] = []
	for group in _PERMS_GROUPS:
		for prefix in (var_bin, abs_bin, bare_bin):
			allow.append(f"Bash({prefix} {group}:*)")
	ask: list[str] = []
	for prefix in (var_bin, abs_bin, bare_bin):
		ask.append(f"Bash({prefix} {_PERMS_ASK_VERB}:*)")
	return allow, ask


def _perms_target(scope: str) -> str:
	if scope == "user":
		return os.path.expanduser("~/.claude/settings.json")
	if scope == "project":
		return os.path.join(os.getcwd(), ".claude", "settings.json")
	if scope == "local":
		return os.path.join(os.getcwd(), ".claude", "settings.local.json")
	raise SystemExit(f"Error: unknown scope {scope!r} (use user|project|local)")


def _atomic_write_settings(path: str, data: dict[str, Any]) -> None:
	parent = os.path.dirname(path) or "."
	os.makedirs(parent, exist_ok=True)
	fd, tmp = tempfile.mkstemp(dir=parent, prefix=".tmp_palantir_", suffix=".json")
	try:
		with os.fdopen(fd, "w") as f:
			json.dump(data, f, indent=2)
			f.write("\n")
		os.replace(tmp, path)
	except Exception:
		try:
			os.unlink(tmp)
		except OSError:
			pass
		raise


def cmd_perms_install(args: argparse.Namespace) -> None:
	target = _perms_target(args.scope)
	want_allow, want_ask = _perms_patterns()

	existing: dict[str, Any] = {}
	if os.path.isfile(target):
		try:
			with open(target) as f:
				existing = json.load(f) or {}
		except (OSError, json.JSONDecodeError) as exc:
			if not args.force:
				raise SystemExit(
					f"Error: failed to read {target}: {exc}. Re-run with --force to overwrite."
				)

	perms = existing.setdefault("permissions", {})
	cur_allow = list(perms.get("allow", []) or [])
	cur_ask = list(perms.get("ask", []) or [])

	cur_allow_set = set(cur_allow)
	cur_ask_set = set(cur_ask)
	add_allow = [p for p in want_allow if p not in cur_allow_set]
	add_ask = [p for p in want_ask if p not in cur_ask_set]

	if not add_allow and not add_ask:
		print(f"PALANTIR_PERMISSIONS_ALREADY_INSTALLED: {target}")
		return

	if args.dry_run:
		diff = {"target": target, "add_allow": add_allow, "add_ask": add_ask}
		print(_common.pretty(diff))
		return

	perms["allow"] = cur_allow + add_allow
	perms["ask"] = cur_ask + add_ask
	_atomic_write_settings(target, existing)
	print(
		f"PALANTIR_PERMISSIONS_INSTALLED: {target} "
		f"(+{len(add_allow)} allow, +{len(add_ask)} ask)"
	)


def cmd_perms_uninstall(args: argparse.Namespace) -> None:
	target = _perms_target(args.scope)
	want_allow, want_ask = _perms_patterns()
	if not os.path.isfile(target):
		print(f"PALANTIR_PERMISSIONS_NOT_INSTALLED: {target}")
		return

	try:
		with open(target) as f:
			existing = json.load(f) or {}
	except (OSError, json.JSONDecodeError) as exc:
		raise SystemExit(f"Error: failed to read {target}: {exc}")

	perms = existing.get("permissions") or {}
	want_allow_set = set(want_allow)
	want_ask_set = set(want_ask)

	new_allow = [p for p in perms.get("allow", []) or [] if p not in want_allow_set]
	new_ask = [p for p in perms.get("ask", []) or [] if p not in want_ask_set]

	removed = (len(perms.get("allow", []) or []) - len(new_allow)) + (
		len(perms.get("ask", []) or []) - len(new_ask)
	)
	if not removed:
		print(f"PALANTIR_PERMISSIONS_NOT_INSTALLED: {target}")
		return

	if args.dry_run:
		print(_common.pretty({"target": target, "would_remove": removed}))
		return

	perms["allow"] = new_allow
	perms["ask"] = new_ask
	if not perms["allow"]:
		perms.pop("allow", None)
	if not perms["ask"]:
		perms.pop("ask", None)
	if not perms:
		existing.pop("permissions", None)
	_atomic_write_settings(target, existing)
	print(f"PALANTIR_PERMISSIONS_UNINSTALLED: {target} (-{removed})")


def cmd_perms_status(args: argparse.Namespace) -> None:
	target = _perms_target(args.scope)
	want_allow, want_ask = _perms_patterns()
	if not os.path.isfile(target):
		print(_common.pretty({"target": target, "installed": False, "reason": "settings file missing"}))
		return
	try:
		with open(target) as f:
			existing = json.load(f) or {}
	except (OSError, json.JSONDecodeError) as exc:
		print(_common.pretty({"target": target, "installed": False, "reason": f"unreadable: {exc}"}))
		return
	perms = existing.get("permissions") or {}
	allow_set = set(perms.get("allow", []) or [])
	ask_set = set(perms.get("ask", []) or [])
	missing_allow = [p for p in want_allow if p not in allow_set]
	missing_ask = [p for p in want_ask if p not in ask_set]
	print(_common.pretty({
		"target": target,
		"installed": not missing_allow and not missing_ask,
		"missing_allow": missing_allow,
		"missing_ask": missing_ask,
	}))


# --------------------------------------------------------------------------
# argparse wiring
# --------------------------------------------------------------------------


ENTRY_KINDS = ["decision", "finding", "error", "pattern", "note", "review", "machine-plan"]
TASK_STATUSES = ["planning", "ready", "wip", "review", "done", "blocked", "archived"]
SEARCH_MODES = ["hybrid", "content", "bluf"]


def _build_parser() -> argparse.ArgumentParser:
	p = argparse.ArgumentParser(
		prog="palantir",
		description="Palantir persistent knowledge system CLI.",
	)
	groups = p.add_subparsers(dest="group", required=True, metavar="<group>")

	# entry
	entry = groups.add_parser("entry", help="Entry CRUD (create, bulk, get, list)")
	entry_sub = entry.add_subparsers(dest="verb", required=True, metavar="<verb>")

	e_create = entry_sub.add_parser("create", help="Create a single entry")
	e_create.add_argument("--bluf", required=False, help="BLUF summary (required)")
	e_create.add_argument("--content", default=None, help="Entry body")
	e_create.add_argument("--stdin", action="store_true", help="Read content from stdin")
	e_create.add_argument("--kind", default="note", choices=ENTRY_KINDS)
	e_create.add_argument("--tag", action="append", help="Tag (repeatable)")
	e_create.add_argument("--task-id", type=int, default=None)
	e_create.set_defaults(func=cmd_entry_create)

	e_bulk = entry_sub.add_parser("bulk", help="Bulk create entries from a JSON file")
	e_bulk.add_argument("--file", required=True)
	e_bulk.set_defaults(func=cmd_entry_bulk)

	e_get = entry_sub.add_parser("get", help="Get a single entry by ID")
	e_get.add_argument("id")
	e_get.set_defaults(func=cmd_entry_get)

	e_list = entry_sub.add_parser("list", help="List entries")
	e_list.add_argument("--kind", choices=ENTRY_KINDS)
	e_list.add_argument("--tag", action="append")
	e_list.add_argument("--plan-id", type=int)
	e_list.add_argument("--task-id", type=int)
	e_list.add_argument("--group-id")
	e_list.add_argument("--limit", type=int, default=20)
	e_list.add_argument("--offset", type=int, default=0)
	e_list.set_defaults(func=cmd_entry_list)

	# task
	task = groups.add_parser("task", help="Task management (create, get, update, list)")
	task_sub = task.add_subparsers(dest="verb", required=True, metavar="<verb>")

	t_create = task_sub.add_parser("create", help="Create a task")
	t_create.add_argument("--title", required=False)
	t_create.add_argument("--status", default="planning", choices=TASK_STATUSES)
	t_create.add_argument("--tag", action="append")
	t_create.add_argument("--due-date")
	t_create.set_defaults(func=cmd_task_create)

	t_get = task_sub.add_parser("get", help="Get a task by ID")
	t_get.add_argument("id")
	t_get.set_defaults(func=cmd_task_get)

	t_update = task_sub.add_parser("update", help="Update a task")
	t_update.add_argument("id")
	t_update.add_argument("--status", choices=TASK_STATUSES)
	t_update.add_argument("--title")
	t_update.add_argument("--tag", action="append")
	t_update.add_argument("--due-date", help="New due date YYYY-MM-DD (use 'null' to clear)")
	t_update.set_defaults(func=cmd_task_update)

	t_list = task_sub.add_parser("list", help="List tasks")
	t_list.add_argument("--status", choices=TASK_STATUSES)
	t_list.add_argument("--tag", action="append")
	t_list.add_argument("--due-lte")
	t_list.add_argument("--due-gte")
	t_list.add_argument("--limit", type=int, default=20)
	t_list.add_argument("--offset", type=int, default=0)
	t_list.set_defaults(func=cmd_task_list)

	# plan
	plan = groups.add_parser("plan", help="Plan management (save, get, list)")
	plan_sub = plan.add_subparsers(dest="verb", required=True, metavar="<verb>")

	p_save = plan_sub.add_parser("save", help="Save approved plan + atomized entries")
	p_save.add_argument("--title", required=False)
	p_save.add_argument("--content", default=None)
	p_save.add_argument("--stdin", action="store_true")
	p_save.add_argument("--entries-file", required=False)
	p_save.add_argument("--tag", action="append")
	p_save.add_argument("--dedupe-key")
	p_save.set_defaults(func=cmd_plan_save)

	p_get = plan_sub.add_parser("get", help="Get a plan by ID")
	p_get.add_argument("id")
	p_get.set_defaults(func=cmd_plan_get)

	p_list = plan_sub.add_parser("list", help="List plans")
	p_list.add_argument("--query")
	p_list.add_argument("--tag", action="append")
	p_list.add_argument("--limit", type=int, default=20)
	p_list.add_argument("--offset", type=int, default=0)
	p_list.set_defaults(func=cmd_plan_list)

	# search
	search = groups.add_parser("search", help="Semantic search (knowledge, tasks)")
	search_sub = search.add_subparsers(dest="verb", required=True, metavar="<verb>")

	s_know = search_sub.add_parser("knowledge", help="Search knowledge entries")
	s_know.add_argument("--query", required=False)
	s_know.add_argument("--kind", choices=ENTRY_KINDS)
	s_know.add_argument("--tag", action="append")
	s_know.add_argument("--plan-id", type=int)
	s_know.add_argument("--task-id", type=int)
	s_know.add_argument("--mode", default="hybrid", choices=SEARCH_MODES)
	s_know.add_argument("--limit", type=int, default=5)
	s_know.add_argument("--raw", action="store_true")
	s_know.set_defaults(func=cmd_search_knowledge)

	s_task = search_sub.add_parser("tasks", help="Search tasks")
	s_task.add_argument("--query", required=False)
	s_task.add_argument("--status", choices=TASK_STATUSES)
	s_task.add_argument("--tag", action="append")
	s_task.add_argument("--due-lte")
	s_task.add_argument("--due-gte")
	s_task.add_argument("--limit", type=int, default=5)
	s_task.add_argument("--raw", action="store_true")
	s_task.set_defaults(func=cmd_search_tasks)

	# tag
	tag = groups.add_parser("tag", help="Tag management (list, create, delete)")
	tag_sub = tag.add_subparsers(dest="verb", required=True, metavar="<verb>")

	tag_list = tag_sub.add_parser("list", help="List all tags")
	tag_list.add_argument("--q", help="Filter by prefix")
	tag_list.add_argument("--limit", type=int, default=50)
	tag_list.set_defaults(func=cmd_tag_list)

	tag_create = tag_sub.add_parser("create", help="Create a new tag")
	tag_create.add_argument("--name", required=False)
	tag_create.set_defaults(func=cmd_tag_create)

	tag_delete = tag_sub.add_parser("delete", help="Delete a tag by ID")
	tag_delete.add_argument("--id", required=False)
	tag_delete.set_defaults(func=cmd_tag_delete)

	# login / logout
	login = groups.add_parser("login", help="PKCE authorization-code login")
	login.set_defaults(func=cmd_login)
	logout = groups.add_parser("logout", help="Revoke tokens and clear credentials")
	logout.set_defaults(func=cmd_logout)

	# perms — install/uninstall/status Claude Code permissions for the Palantir CLI
	perms = groups.add_parser(
		"perms",
		help="Manage Claude Code permissions (install, uninstall, status)",
	)
	perms_sub = perms.add_subparsers(dest="verb", required=True, metavar="<verb>")

	def _add_scope(parser: argparse.ArgumentParser) -> None:
		parser.add_argument(
			"--scope",
			default="user",
			choices=["user", "project", "local"],
			help="Where to install permissions (default: user → ~/.claude/settings.json)",
		)

	pi = perms_sub.add_parser("install", help="Install Claude Code permissions for the Palantir CLI")
	_add_scope(pi)
	pi.add_argument("--dry-run", action="store_true", help="Print diff without writing")
	pi.add_argument("--force", action="store_true", help="Overwrite unreadable settings.json")
	pi.set_defaults(func=cmd_perms_install)

	pu = perms_sub.add_parser("uninstall", help="Remove managed Palantir CLI permissions")
	_add_scope(pu)
	pu.add_argument("--dry-run", action="store_true")
	pu.set_defaults(func=cmd_perms_uninstall)

	ps = perms_sub.add_parser("status", help="Report whether managed permissions are installed")
	_add_scope(ps)
	ps.set_defaults(func=cmd_perms_status)

	return p


def main(argv: list[str] | None = None) -> int:
	parser = _build_parser()
	args = parser.parse_args(argv)
	try:
		args.func(args)
	except _auth.LoginRequired as exc:
		_login_required(str(exc))
		return 1
	except SystemExit:
		raise
	except Exception as exc:
		print(f"Error: {exc}", file=sys.stderr)
		return 1
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
