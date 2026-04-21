# Auth Protocol

The skill owns the login lifecycle so users never have to run shell commands themselves. Browser
consent stays with the user — everything else is handled here.

## When to run

Run this protocol in any of these cases:

- The user says "log me in", "authenticate Palantir", "sign in to Palantir", "reconnect
  Palantir", or similar.
- The CLI (`palantir …`) prints a line containing `[PALANTIR_LOGIN_REQUIRED]`.
- Before starting a long Palantir task, if `~/.config/palantir/credentials.json` is missing.
- The user says "log me out" — skip to [Logout](#logout).

## Step 1 — Resolve the CLI path

Use, in order:

1. `${CLAUDE_PLUGIN_ROOT}/.claude/bin/palantir` — set when the plugin is installed.
2. If `CLAUDE_PLUGIN_ROOT` is empty, ask the user for the plugin repo path and cache it for the
   session, or try `$(git rev-parse --show-toplevel)/palantir-plugin/.claude/bin/palantir`
   when the user is working inside the mineralogy-rocks monorepo.

Do NOT guess paths silently. If resolution fails, tell the user once and stop.

## Step 2 — Check the API URL

The CLI needs `PALANTIR_API_URL` in the environment unless credentials already exist. If the
user has not set it, ask them for the base URL (e.g. `http://palantir.local:81` for local dev)
and pass it as an env var on the invocation — do not rely on their shell profile.

## Step 3 — Run login in the background

Invoke the CLI with the Bash tool and `run_in_background: true`. Example:

```bash
PALANTIR_API_URL=http://palantir.local:81 \
  "${CLAUDE_PLUGIN_ROOT}/.claude/bin/palantir" login
```

The script runs three phases:

1. Registers (or reuses) an OAuth2 client — fast, ~1s.
2. Picks a free loopback port, prints the authorization URL, then **blocks** on a Python
   listener until the browser callback arrives.
3. Exchanges the code for tokens, writes credentials, prints identity.

## Step 4 — Surface the authorization URL

Poll the background task's stdout. As soon as you see a line starting with
`PALANTIR_AUTH_URL: `, extract the URL and show it to the user in a single short message:

> Click this link to authorize Palantir in your browser:
> &lt;URL&gt;
>
> Your browser may open automatically. Approve the request and then come back — I'll pick it up
> from here.

Do not show the rest of the script's stdout — it is noisy. Only the URL matters to the user.

## Step 5 — Wait for completion

Keep polling the background task's output. Exit the wait loop on any of:

- A line starting with `PALANTIR_LOGIN_OK: ` — login succeeded. Extract the GitHub login and
  confirm to the user (e.g. "Logged in as @foo. Continuing...").
- A line starting with `PALANTIR_LOGIN_ERROR: ` — login failed. Show the reason to the user
  and stop. Do not retry automatically.
- The background task exits with a non-zero status and neither marker was emitted — treat as
  a generic failure and show the last few lines of stderr.
- A timeout of 3 minutes — tell the user the auth flow timed out and ask whether to retry.

## Step 6 — Retry the triggering operation

If an earlier CLI call surfaced `[PALANTIR_LOGIN_REQUIRED]`, re-run that exact call now.
If the user invoked Auth Protocol directly ("log me in"), stop here — the task is done.

## Logout

When the user asks to log out, run `${CLAUDE_PLUGIN_ROOT}/.claude/bin/palantir logout` in the
foreground (this subcommand is on the `ask` permission list, which is intentional — logout is
destructive because it revokes tokens). Confirm once to the user after completion.

## Things to avoid

- Do not print raw CLI stdout to the user — the login flow is chatty. Extract only the URL and
  status markers.
- Do not move `palantir login` to the `ask` list and ask the user to approve each call;
  it is already on `allow` so Claude can trigger it on their behalf.
- Do not repeatedly poll the creds file as a sole progress signal — rely on the markers, and
  use the creds file only as a final sanity check.
- Do not ask the user to "run the command yourself". The whole point of this protocol is to
  spare them that.
