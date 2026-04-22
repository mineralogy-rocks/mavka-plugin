#!/usr/bin/env python3
"""JSON merge/strip helper for the Mavka setup/uninstall scripts.

Stdlib only. Two subcommands:

    setup.py merge <template_path> <settings_path> --repo REPO
    setup.py strip <settings_path> --repo REPO

merge: reads the template, substitutes ${REPO} with the absolute repo
path, and merges it into the target settings.json idempotently.

strip: reverses merge by re-rendering the template and removing matching
entries from the target settings.json.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile


EXIT_PLAN_MODE_MATCHER = "ExitPlanMode"


def read_template(template_path: str, repo: str) -> dict:
	with open(template_path, "r", encoding="utf-8") as fh:
		raw = fh.read()
	rendered = raw.replace("${REPO}", repo)
	return json.loads(rendered)


def read_settings(settings_path: str) -> dict:
	if not os.path.exists(settings_path):
		return {}
	try:
		with open(settings_path, "r", encoding="utf-8") as fh:
			text = fh.read()
	except OSError as exc:
		print(f"error: cannot read {settings_path}: {exc}", file=sys.stderr)
		sys.exit(1)
	if text.strip() == "":
		return {}
	try:
		data = json.loads(text)
	except json.JSONDecodeError as exc:
		print(
			f"error: {settings_path} is not valid JSON ({exc}); refusing to rewrite",
			file=sys.stderr,
		)
		sys.exit(1)
	if not isinstance(data, dict):
		print(
			f"error: {settings_path} root is not a JSON object; refusing to rewrite",
			file=sys.stderr,
		)
		sys.exit(1)
	return data


def atomic_write(path: str, data: dict) -> None:
	directory = os.path.dirname(os.path.abspath(path)) or "."
	os.makedirs(directory, exist_ok=True)
	fd, tmp_path = tempfile.mkstemp(
		prefix=".mavka-setup-", suffix=".json", dir=directory
	)
	try:
		with os.fdopen(fd, "w", encoding="utf-8") as fh:
			json.dump(data, fh, indent=2, sort_keys=False)
			fh.write("\n")
		os.replace(tmp_path, path)
	except Exception:
		try:
			os.unlink(tmp_path)
		except OSError:
			pass
		raise


def merge_allow_list(
	existing: list, incoming: list, changes: list, label: str
) -> list:
	if not isinstance(existing, list):
		existing = []
	merged = list(existing)
	seen = set(merged)
	for entry in incoming:
		if entry in seen:
			continue
		merged.append(entry)
		seen.add(entry)
		changes.append(f"added permissions.{label}: {entry}")
	return merged


def merge_hooks(
	settings: dict, template: dict, changes: list
) -> None:
	tpl_hooks = template.get("hooks") or {}
	tpl_post = tpl_hooks.get("PostToolUse") or []
	if not tpl_post:
		return

	hooks_section = settings.get("hooks")
	if not isinstance(hooks_section, dict):
		hooks_section = {}
		settings["hooks"] = hooks_section

	post_section = hooks_section.get("PostToolUse")
	if not isinstance(post_section, list):
		post_section = []
		hooks_section["PostToolUse"] = post_section

	for tpl_matcher_entry in tpl_post:
		matcher_name = tpl_matcher_entry.get("matcher")
		tpl_hook_list = tpl_matcher_entry.get("hooks") or []
		target_entry = None
		for existing_entry in post_section:
			if (
				isinstance(existing_entry, dict)
				and existing_entry.get("matcher") == matcher_name
			):
				target_entry = existing_entry
				break
		if target_entry is None:
			post_section.append(
				{"matcher": matcher_name, "hooks": list(tpl_hook_list)}
			)
			for hk in tpl_hook_list:
				cmd = hk.get("command", "<?>")
				changes.append(
					f"added hooks.PostToolUse[{matcher_name}] command: {cmd}"
				)
			continue

		target_hooks = target_entry.get("hooks")
		if not isinstance(target_hooks, list):
			target_hooks = []
			target_entry["hooks"] = target_hooks

		existing_commands = {
			hk.get("command")
			for hk in target_hooks
			if isinstance(hk, dict)
		}
		for hk in tpl_hook_list:
			cmd = hk.get("command")
			if cmd in existing_commands:
				continue
			target_hooks.append(dict(hk))
			existing_commands.add(cmd)
			changes.append(
				f"added hooks.PostToolUse[{matcher_name}] command: {cmd}"
			)


def cmd_merge(args: argparse.Namespace) -> int:
	template = read_template(args.template_path, args.repo)
	settings = read_settings(args.settings_path)
	changes: list = []

	tpl_perms = template.get("permissions") or {}
	perms = settings.get("permissions")
	if not isinstance(perms, dict):
		perms = {}
		settings["permissions"] = perms

	for key in ("allow", "ask"):
		incoming = tpl_perms.get(key) or []
		if not incoming:
			continue
		merged = merge_allow_list(perms.get(key), incoming, changes, key)
		perms[key] = merged

	merge_hooks(settings, template, changes)

	if not changes:
		print("no changes")
		return 0

	atomic_write(args.settings_path, settings)
	for line in changes:
		print(line)
	return 0


def cmd_strip(args: argparse.Namespace) -> int:
	template_path = os.path.join(args.repo, "settings", "template.json")
	template = read_template(template_path, args.repo)
	settings = read_settings(args.settings_path)
	removed: list = []

	tpl_perms = template.get("permissions") or {}
	perms = settings.get("permissions")
	if isinstance(perms, dict):
		for key in ("allow", "ask"):
			incoming = tpl_perms.get(key) or []
			existing = perms.get(key)
			if not isinstance(existing, list) or not incoming:
				continue
			to_remove = set(incoming)
			kept = [e for e in existing if e not in to_remove]
			for e in existing:
				if e in to_remove:
					removed.append(f"removed permissions.{key}: {e}")
			if kept:
				perms[key] = kept
			else:
				del perms[key]
		if not perms:
			del settings["permissions"]

	tpl_hooks = template.get("hooks") or {}
	tpl_post = tpl_hooks.get("PostToolUse") or []
	hooks_section = settings.get("hooks")
	if isinstance(hooks_section, dict) and tpl_post:
		post_section = hooks_section.get("PostToolUse")
		if isinstance(post_section, list):
			for tpl_matcher_entry in tpl_post:
				matcher_name = tpl_matcher_entry.get("matcher")
				tpl_cmds = {
					hk.get("command")
					for hk in (tpl_matcher_entry.get("hooks") or [])
					if isinstance(hk, dict)
				}
				for existing_entry in list(post_section):
					if (
						not isinstance(existing_entry, dict)
						or existing_entry.get("matcher") != matcher_name
					):
						continue
					target_hooks = existing_entry.get("hooks")
					if not isinstance(target_hooks, list):
						continue
					kept = []
					for hk in target_hooks:
						if (
							isinstance(hk, dict)
							and hk.get("command") in tpl_cmds
						):
							removed.append(
								f"removed hooks.PostToolUse[{matcher_name}] command: {hk.get('command')}"
							)
							continue
						kept.append(hk)
					if kept:
						existing_entry["hooks"] = kept
					else:
						post_section.remove(existing_entry)
			if not post_section:
				del hooks_section["PostToolUse"]
		if not hooks_section:
			del settings["hooks"]

	if not removed:
		print("no changes")
		return 0

	atomic_write(args.settings_path, settings)
	for line in removed:
		print(line)
	return 0


def main(argv: list) -> int:
	parser = argparse.ArgumentParser(description="Mavka settings.json helper")
	sub = parser.add_subparsers(dest="command", required=True)

	p_merge = sub.add_parser("merge", help="merge template into settings")
	p_merge.add_argument("template_path")
	p_merge.add_argument("settings_path")
	p_merge.add_argument("--repo", required=True)
	p_merge.set_defaults(func=cmd_merge)

	p_strip = sub.add_parser("strip", help="strip template entries from settings")
	p_strip.add_argument("settings_path")
	p_strip.add_argument("--repo", required=True)
	p_strip.set_defaults(func=cmd_strip)

	args = parser.parse_args(argv)
	return args.func(args)


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))
