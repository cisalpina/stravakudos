# stravakudos

Automated Strava kudos bot. Logs in to Strava, reads the activity feed, and gives kudos to all activities found.

## Quick start (local Mac)

```bash
# 1. Create and activate a virtualenv
python3 -m venv .venv && source .venv/bin/activate

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Install the Playwright Firefox browser binary
playwright install firefox

# 4. Copy and fill in credentials
cp .env.example .env
# edit .env with your real values

# 5. Export env vars and run
export $(grep -v '^#' .env | xargs)
python kudos.py
```

Set `RUN_INTERVAL_MINUTES=0` in `.env` to do a single run and exit (good for testing).

## Quick start (Docker)

```bash
cp .env.example .env
# edit .env with your real values

docker compose build
docker compose up
```

Open **http://localhost:6080** to see the browser via noVNC.
First run: log in to Strava manually in the browser window. The session cookie is saved to
`./data/storage_state.json` and reused on all subsequent runs.

## Files

| File | Purpose |
|---|---|
| `kudos.py` | Main entry point — async loop |
| `auth.py` | Session check, manual login wait, storage_state save/load |
| `feed.py` | Dashboard feed parsing and kudos clicking |
| `gmail.py` | IMAP OTC reader — present but not currently used in the main flow |
| `notify.py` | SMTP emails: failure alerts and session-expired notifications |
| `config.py` | Env var loading with defaults |
| `requirements.txt` | Python deps |
| `.env.example` | All supported env vars documented |
| `Dockerfile` | Container image definition |
| `docker-compose.yml` | Single-service compose config |
| `entrypoint.sh` | Container startup: Xvfb → fluxbox → x11vnc → noVNC → kudos.py |

## Login flow

On first run (or when the session cookie expires):
1. Bot navigates to the Strava login page
2. A **"Login Required" email** is sent to `NOTIFY_EMAIL` with a link to the noVNC URL
3. Bot waits up to 5 minutes for you to log in manually via the browser
4. Once logged in, the session cookie is saved and reused until it expires again

No automated password/OTC handling — Strava's reCAPTCHA blocks it reliably.

## Persistent data (DATA_DIR, default ./data)

| File | Contents |
|---|---|
| `storage_state.json` | Playwright cookies — the live Strava session |
| `last_run.json` | Timestamp + stats from the last successful run |
| `error_TIMESTAMP.png` | Screenshot captured on any failed run |

## Kudos loop — stopping conditions

The bot stops giving kudos when the FIRST of these is met:

1. Encounters an activity it already kudosed (normal case — caught up to previous run)
2. `MAX_KUDOS` given in this run (default 20, safety cap)
3. Activity older than `LOOKBACK_HOURS` (default 24h)
4. Feed fully scrolled with no new entries

## Known limitations / watch-outs

- **Selectors** — uses `data-testid` attributes from Strava's DOM. These are relatively stable
  but can change on major Strava redesigns.
- **Browser** — must use Firefox. Chrome/Chromium is blocked more aggressively by Strava.
- **reCAPTCHA** — blocks automated form submission reliably; manual login via noVNC is the
  working solution.
- **"already_kudosed" stop condition** — assumes the feed is roughly chronological. If Strava
  surfaces a re-ordered activity (e.g. backdated), the bot may stop one entry early.
- **Python 3.9 compatibility** — local venv runs 3.9; use `Optional[x]` not `x | None` for
  type hints. Docker uses 3.12 so this only matters for local dev.

## Docker architecture

```
Base image:  python:3.12-slim
Added:       Firefox (via playwright install firefox)
             Xvfb (virtual display on :1)
             x11vnc (VNC server on :5900)
             noVNC + websockify (web UI on :6080)
             fluxbox (minimal window manager)

Ports:       6080 — noVNC web UI
Volumes:     ./data → /data  (cookies, last_run.json, error screenshots)
Restart:     unless-stopped
```

## Future: publishing to Docker Hub

```bash
docker login
docker build -t <user>/stravakudos:latest .
docker push <user>/stravakudos:latest
```

Source code lives on GitHub (private repo); built image lives on Docker Hub.
Secrets are never baked into the image — always passed via env vars at runtime.
