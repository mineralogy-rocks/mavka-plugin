# Auth Protocol

The skill owns the login lifecycle so users never have to run shell commands themselves. Browser
consent stays with the user — everything else is handled here.

## When to run

Run this protocol in any of these cases:

- The user says "log me in", "authenticate Mavka", "sign in to Mavka", "reconnect
  Mavka", or similar.
- The CLI (`mavka …`) prints a line containing `[MAVKA_LOGIN_REQUIRED]`.
- Before starting a long Mavka task, if `~/.config/mavka/credentials.json` is missing.
- The user says "log me out" — skip to [Logout](#logout).

## Step 1 — Use the stable CLI path

The plugin's SessionStart hook maintains `~/.claude/skills/mavka` as a symlink to the current
plugin cache. Always invoke via this stable path:

```
~/.claude/skills/mavka/.claude/bin/mavka
```

If the symlink is missing (e.g. the user ran a stale session before the plugin upgraded),
tell the user once to restart Claude Code and stop. Do NOT guess alternate paths.

## Step 2 — Run login in the background

The CLI resolves the API URL itself: env `MAVKA_API_URL` > stored creds > default
`http://mavka.local:81`. Do not pass it inline unless the user explicitly asks for a one-off
override.

Invoke the CLI with the Bash tool and `run_in_background: true`. Example:

```bash
~/.claude/skills/mavka/.claude/bin/mavka login
```

The script runs three phases:

1. Registers (or reuses) an OAuth2 client — fast, ~1s.
2. Picks a free loopback port, prints the authorization URL, then **blocks** on a Python
   listener until the browser callback arrives.
3. Exchanges the code for tokens, writes credentials, prints identity.

## Step 3 — Surface the authorization URL

Poll the background task's stdout. As soon as you see a line starting with
`MAVKA_AUTH_URL: `, extract the URL and show it to the user in a single short message:

> Click this link to authorize Mavka in your browser:
> &lt;URL&gt;
>
> Your browser may open automatically. Approve the request and then come back — I'll pick it up
> from here.

Do not show the rest of the script's stdout — it is noisy. Only the URL matters to the user.

## Step 4 — Wait for completion

Keep polling the background task's output. Exit the wait loop on any of:

- A line starting with `MAVKA_LOGIN_OK: ` — login succeeded. Extract the GitHub login and
  confirm to the user (e.g. "Logged in as @foo. Continuing...").
- A line starting with `MAVKA_LOGIN_ERROR: ` — login failed. Show the reason to the user
  and stop. Do not retry automatically.
- The background task exits with a non-zero status and neither marker was emitted — treat as
  a generic failure and show the last few lines of stderr.
- A timeout of 3 minutes — tell the user the auth flow timed out and ask whether to retry.

## Step 5 — Retry the triggering operation

If an earlier CLI call surfaced `[MAVKA_LOGIN_REQUIRED]`, re-run that exact call now.
If the user invoked Auth Protocol directly ("log me in"), stop here — the task is done.

## Logout

When the user asks to log out, run `~/.claude/skills/mavka/.claude/bin/mavka logout` in the
foreground (this subcommand is on the `ask` permission list, which is intentional — logout is
destructive because it revokes tokens). Confirm once to the user after completion.

## Things to avoid

- Do not print raw CLI stdout to the user — the login flow is chatty. Extract only the URL and
  status markers.
- Do not move `mavka login` to the `ask` list and ask the user to approve each call;
  it is already on `allow` so Claude can trigger it on their behalf.
- Do not repeatedly poll the creds file as a sole progress signal — rely on the markers, and
  use the creds file only as a final sanity check.
- Do not ask the user to "run the command yourself". The whole point of this protocol is to
  spare them that.
