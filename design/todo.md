# Implementation TODO

## Phase 1 — Core (local Mac)

- [x] `config.py` — env var loading with defaults, validates required vars on startup
- [x] `gmail.py` — IMAP connect, search for Strava OTC email, extract 6-digit code
- [x] `notify.py` — SMTP failure email with screenshot attachment
- [x] `auth.py` — session check, login, OTC detection + Gmail fetch, CAPTCHA wait, storage_state
- [x] `feed.py` — navigate dashboard, iterate feed entries, click unfilled kudos, stopping conditions
- [x] `kudos.py` — main async loop, calls auth → feed → notify on error, sleeps N minutes
- [x] `requirements.txt`
- [x] `.env.example`
- [ ] **Manual end-to-end test on local Mac** ← NEXT SESSION STARTS HERE

## Phase 2 — Docker + noVNC

- [ ] `Dockerfile` — python:3.12-slim + Firefox (via playwright) + Xvfb + x11vnc + noVNC + fluxbox
- [ ] `docker-compose.yml` — ports 6080/5900, volume /data, env_file, restart: unless-stopped
- [ ] Verify HEADLESS=false + DISPLAY=:1 shows browser in noVNC
- [ ] Test on local Docker (Mac)
- [ ] Deploy to Unraid + notes on Unraid template setup

## Nice to have (post Phase 2)

- [ ] Configurable LOOKBACK_HOURS + MAX_KUDOS env vars — already wired, just needs testing
- [ ] Append per-run stats to /data/stats.jsonl for a historical log
- [ ] Health-check endpoint (tiny HTTP server, port 8080) so Docker HEALTHCHECK works
