"""Shared utilities for the Mavka CLI."""

from __future__ import annotations

import json
import sys
from typing import Any

_EMBEDDING_KEYS = frozenset({"embedding", "bluf_embedding", "title_embedding"})


def pretty(obj: Any) -> str:
	return json.dumps(obj, indent=2, ensure_ascii=False)


def strip_embeddings(obj: Any) -> Any:
	if isinstance(obj, dict):
		return {k: strip_embeddings(v) for k, v in obj.items() if k not in _EMBEDDING_KEYS}
	if isinstance(obj, list):
		return [strip_embeddings(i) for i in obj]
	return obj


def resolve_content(content: str | None, use_stdin: bool) -> str:
	if use_stdin:
		return sys.stdin.read()
	return content or ""


def load_json_file(path: str) -> Any:
	try:
		with open(path) as f:
			return json.load(f)
	except (OSError, json.JSONDecodeError) as exc:
		print(f"Error: '{path}' is not valid JSON: {exc}", file=sys.stderr)
		raise SystemExit(1)


def compact_search(items: Any) -> list[dict[str, Any]]:
	if not isinstance(items, list):
		items = [items]
	out = []
	for item in items:
		score = item.get("score")
		out.append({
			"id": item.get("id"),
			"score": round(score, 4) if isinstance(score, (int, float)) else None,
			"kind": item.get("kind") or item.get("status"),
			"bluf": item.get("bluf") or item.get("title"),
			"tags": item.get("tags", []),
		})
	return out
