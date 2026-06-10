# Design Decisions

## Status: APPROVED — ready for implementation

---

## Core technology choices

| Concern | Choice | Reason |
|---|---|---|
| Language | Python 3.12 | Standard for all hobbyist Strava projects |
| Browser automation | Playwright (async) + Firefox | Community confirms Chrome/Chromium is blocked more aggressively by Strava; Firefox works reliably |
| Session persistence | Playwright `storage_state` | Saves cookies + localStorage to a JSON file natively; restored on next run |
| Gmail (read OTC) | `imapclient` + IMAP + app password | Simplest hobbyist approach; no OAuth2 dance needed |
| Email notifications | `smtplib` via Gmail SMTP | Reuses the same Gmail credentials |
| Scheduling | Internal `asyncio` loop with 10-min sleep | Simpler than cron inside Docker; container restart policy handles crashes |
| Docker GUI | Xvfb + x11vnc + noVNC | Standard pattern; exposes browser on port 6080 via web UI; Unraid compatible |

---

## Authentication & session flow

```
startup
  └─> load storage_state.json (cookies) if exists
  └─> validate session: GET /dashboard, check for redirect to /login
      ├─> valid: proceed to kudos loop
      └─> invalid: trigger re-auth
            └─> fill email + password on /login
            └─> check for OTC field (rare edge case)
                ├─> no OTC: proceed
                └─> OTC present:
                      └─> poll Gmail via IMAP for Strava email (up to 90 sec)
                      └─> extract 6-digit code
                      └─> fill OTC field + submit
            └─> save storage_state.json
```

---

## Kudos loop

1. Navigate to `/dashboard`
2. For each `[data-testid=web-feed-entry]` in the feed:
   - Skip if it's a club post (`[data-testid=group-header]` or `.clubMemberPostHeaderLinks`)
   - Skip if it's the user's own activity (compare owner href to stored user profile ID)
   - If `[data-testid=unfilled_kudos]` button exists → click it, increment counter
   - If no unfilled kudos button (already kudosed) → **STOP** (we've caught up to previous run)
3. After processing visible entries, scroll down to load more
4. **Stop conditions** (first one hit wins):
   - Encountered an activity already kudosed → done, this is the normal case
   - 20 kudos given in this run → done (safety cap, configurable via `MAX_KUDOS` env var)
   - Activity timestamp older than `LOOKBACK_HOURS` (default 24h) → done
   - Feed exhausted (no more entries after scrolling) → done

---

## Failure notification

On any unhandled exception or failed re-auth:
- Send email via SMTP to `NOTIFY_EMAIL`
- Include timestamp, error message, and last screenshot attachment
- Screenshot saved to `/data/error_TIMESTAMP.png`

---

## Secrets — all via environment variables, never in code

| Variable | Purpose |
|---|---|
| `STRAVA_EMAIL` | Strava login email |
| `STRAVA_PASSWORD` | Strava password |
| `GMAIL_EMAIL` | Gmail address (for IMAP OTC read + SMTP send) |
| `GMAIL_APP_PASSWORD` | Gmail app password |
| `NOTIFY_EMAIL` | Destination for failure emails (can be same as `GMAIL_EMAIL`) |
| `MAX_KUDOS` | Max kudos per run (default: 20) |
| `LOOKBACK_HOURS` | Max activity age to kudo (default: 24) |
| `RUN_INTERVAL_MINUTES` | How often to run (default: 10) |

---

## Persistent state (volume-mounted at `/data`)

| File | Contents |
|---|---|
| `/data/storage_state.json` | Playwright cookies + localStorage (the session) |
| `/data/last_run.json` | Timestamp of last successful run, kudos count stats |
| `/data/error_TIMESTAMP.png` | Screenshots on failure |

---

## Docker architecture (Phase 2)

```
Base image: python:3.12-slim
Additional layers:
  - Firefox (via playwright install firefox)
  - Xvfb (virtual display)
  - x11vnc (VNC server on :5900)
  - noVNC + websockify (web UI on :6080)
  - fluxbox (minimal window manager, required for browser chrome)

Ports:
  - 6080: noVNC web UI (browser view)
  - 5900: raw VNC (optional)

Volumes:
  - /data: state files (cookies, last_run.json, error screenshots)

Env vars: all secrets as listed above

Restart policy: unless-stopped
```

Playwright runs in **non-headless mode** with `DISPLAY=:1` so the browser appears in noVNC.

For local Mac development: run Python directly (headless optional), no Docker needed.

---

## File layout (once written)

```
stravakudos/
├── kudos.py           # main entry point (async loop)
├── auth.py            # session validation, login, OTC handling
├── feed.py            # feed parsing, kudos clicking
├── gmail.py           # IMAP OTC reader
├── notify.py          # SMTP failure emails
├── config.py          # env var loading with defaults
├── requirements.txt
├── Dockerfile         # Phase 2
├── docker-compose.yml # Phase 2
└── .env.example       # documented list of env vars (no values)
```
