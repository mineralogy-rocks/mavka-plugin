# Palantir Plugin for Claude Code

A Claude Code plugin that gives your AI assistant persistent memory across sessions. Stores decisions, findings, errors, and patterns with semantic search — so context is never lost when conversations end or compress.

## Prerequisites

You need a running Palantir API (locally or on a remote server). The API handles storage, embeddings, and semantic search.

Set up the API from the [palantir](https://github.com/mineralogy-rocks/palantir) repository:

```bash
git clone https://github.com/mineralogy-rocks/palantir.git
cd palantir
docker-compose up -d
```

## Installation

```bash
claude plugin install github:mineralogy-rocks/palantir-plugin
```

For local development/testing without installing:

```bash
claude --plugin-dir /path/to/palantir-plugin
```

## Configuration

Add the following env vars to your project's `.claude/settings.local.json`:

```json
{
  "env": {
    "PALANTIR_API_URL": "http://palantir.local:81",
    "PALANTIR_API_KEY": "your-api-key",
    "PALANTIR_PROJECT_NAME": "your-project"
  }
}
```

| Variable | Description |
|----------|-------------|
| `PALANTIR_API_URL` | Base URL of your Palantir API |
| `PALANTIR_API_KEY` | Authentication token |
| `PALANTIR_PROJECT_NAME` | Project identifier for scoping entries and tasks |

## Skills

| Skill | Description |
|-------|-------------|
| `/palantir:recall` | Search past decisions, findings, errors, and patterns by topic |
| `/palantir:atomize-me` | Break text or a file into discrete knowledge entries |
| `/palantir:atomize-session` | Atomize the current conversation into entries |
| `/palantir:task` | Create, update, or add context to tasks |

## Hooks

| Event | What it does |
|-------|-------------|
| **PreCompact** | Automatically atomizes the session before context compression, so nothing is lost |

## How It Works

Palantir stores knowledge as **entries** — discrete units covering one topic each. Each entry has:
- A **BLUF** (Bottom Line Up Front) — 1-2 sentence summary
- **Content** — full context (100-400 words)
- **Kind** — `decision`, `finding`, `error`, `pattern`, `note`, or `review`
- **Tags** — for categorization

Entries are embedded for semantic search using dual embeddings (content + BLUF) merged via Reciprocal Rank Fusion.

**Tasks** group related entries and track work status (`planning` → `wip` → `review` → `done`).

## License

MIT