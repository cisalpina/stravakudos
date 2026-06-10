# Questions Log

## Resolved

| # | Question | Answer |
|---|---|---|
| Q1 | OTC frequency | Rare edge case; Strava cookie sessions last a very long time |
| Q2 | Gmail approach | App password + IMAP (`imapclient`); SMTP for outbound notifications |
| Q3 | Browser vs API | Browser automation — Strava's API has not supported giving kudos for years |
| Q4 | Activity scope | All activities, all athletes; stop at 20 kudos OR already-kudosed activity OR 24h lookback |
| Q5 | Run frequency | Every 10 minutes |
| Q6 | Run environment | Local Mac for dev; Unraid Docker for production |
| Q7 | Failure notification | Email (SMTP via Gmail) |
| Q8 | Docker GUI | noVNC web UI so user can see the live browser; needed for auth debugging |
| Q9 | Secrets | All env vars — no hard-coded credentials, Docker-friendly |

## Still open

None — ready to implement.
