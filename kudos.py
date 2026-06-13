"""
Strava Kudos Bot — main entry point.

Runs on a configurable interval (default 10 min). Each cycle:
  1. Phase 1 — session: real Firefox (firefox-esr) checks/restores the session.
     Real Firefox is used here because Strava's login page detects Playwright's
     bundled Firefox and rejects it. If login is needed the user logs in manually
     via noVNC; the session cookie is then saved to disk.
  2. Phase 2 — kudos: Playwright's bundled Firefox loads the saved session and
     gives kudos. Playwright's Firefox executes Strava's MFE JavaScript reliably
     (confirmed on Mac with hundreds of kudos given); firefox-esr does not.

All configuration via environment variables (see .env.example).
Set RUN_INTERVAL_MINUTES=0 to run once and exit (useful for testing).
"""

import asyncio
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright

import auth
import feed
from config import load_config
from notify import send_failure_email, send_session_expired_email

log = logging.getLogger(__name__)

_DASHBOARD_URL = "https://www.strava.com/dashboard"
_WEBDRIVER_HIDE = "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"

# Analytics/tracking domains that retry aggressively and delay networkidle.
# Aborting them at the browser level keeps runs fast and predictable.
_ANALYTICS_RE = re.compile(
    r"analytics\.tiktok\.com"
    r"|googletagmanager\.com"
    r"|google-analytics\.com"
    r"|connect\.facebook\.net"
)


async def _make_context(browser, storage, *, ignore_https_errors=False, user_agent=None):
    context = await browser.new_context(
        **({"storage_state": storage} if storage else {}),
        viewport={"width": 1280, "height": 900},
        ignore_https_errors=ignore_https_errors,
        **({"user_agent": user_agent} if user_agent else {}),
    )
    await context.add_init_script(_WEBDRIVER_HIDE)
    return context


async def run_once(config) -> dict:
    """
    One complete cycle: session check → optional login → kudos → save session.
    Returns stats dict on success.
    On failure, takes a screenshot, attaches its path to the exception, then re-raises.
    """
    storage = auth.storage_state_path(config.data_dir)

    async with async_playwright() as p:

        # ── Phase 1: ensure a valid session ──────────────────────────────────
        # Use real Firefox to avoid bot detection on Strava's login page.
        try:
            session_browser = await p.firefox.launch(headless=config.headless, channel="firefox")
            log.info("Session browser: system Firefox (firefox-esr)")
        except Exception:
            session_browser = await p.firefox.launch(headless=config.headless)
            log.info("Session browser: Playwright bundled Firefox (firefox-esr not found)")

        session_context = await _make_context(session_browser, storage)
        session_page = await session_context.new_page()

        try:
            if not await auth.check_session(session_page):
                log.info("Session expired — sending notification and waiting for manual login...")
                send_session_expired_email(
                    config.gmail_email,
                    config.gmail_app_password,
                    config.notify_email,
                    config.novnc_url,
                    wait_minutes=5,
                )
                success = await auth.login(session_page, config)
                if not success:
                    raise RuntimeError(
                        "Login timed out — session still expired after 5-minute wait"
                    )
                await auth.save_storage_state(session_context, config.data_dir)
                storage = auth.storage_state_path(config.data_dir)
        finally:
            await session_context.close()
            await session_browser.close()

        # ── Phase 2: give kudos ───────────────────────────────────────────────
        # Playwright's bundled Firefox executes Strava's MFE JavaScript reliably.
        kudos_browser = await p.firefox.launch(headless=config.headless)
        log.info("Kudos browser: Playwright bundled Firefox")

        kudos_context = await _make_context(
            kudos_browser,
            storage,
            ignore_https_errors=True,
            user_agent="Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
        )
        await kudos_context.route(
            _ANALYTICS_RE,
            lambda route: route.abort(),
        )
        kudos_page = await kudos_context.new_page()
        kudos_page.on("pageerror", lambda err: log.error("Browser JS error: %s", err))
        kudos_page.on(
            "console",
            lambda msg: log.warning("Browser console [%s]: %s", msg.type, msg.text)
            if msg.type == "error"
            else None,
        )
        kudos_page.on(
            "requestfailed",
            lambda req: log.warning("Request failed: %s — %s", req.url, req.failure)
            if req.failure != "NS_BINDING_ABORTED"
            else None,
        )

        try:
            stats = await feed.give_kudos(kudos_page, config)

            await auth.save_storage_state(kudos_context, config.data_dir)
            return stats

        except Exception as exc:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            shot = str(Path(config.data_dir) / f"error_{ts}.png")
            try:
                await kudos_page.screenshot(path=shot, full_page=False)
                exc.screenshot_path = shot  # type: ignore[attr-defined]
            except Exception:
                exc.screenshot_path = None  # type: ignore[attr-defined]
            raise

        finally:
            await kudos_context.close()
            await kudos_browser.close()


def _save_run_state(config, stats: dict) -> None:
    path = Path(config.data_dir) / "last_run.json"
    with open(path, "w") as f:
        json.dump(
            {"timestamp": datetime.now(timezone.utc).isoformat(), **stats},
            f,
            indent=2,
        )


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stdout,
    )

    config = load_config()
    Path(config.data_dir).mkdir(parents=True, exist_ok=True)
    log.info(
        "Strava kudos bot started (interval=%d min, max_kudos=%d, lookback=%dh)",
        config.run_interval_minutes,
        config.max_kudos,
        config.lookback_hours,
    )

    while True:
        log.info("=== Run starting ===")
        try:
            stats = await run_once(config)
            _save_run_state(config, stats)
            log.info("=== Run complete: %s ===", stats)
        except Exception as exc:
            log.exception("Run failed")
            screenshot = getattr(exc, "screenshot_path", None)
            try:
                send_failure_email(
                    config.gmail_email,
                    config.gmail_app_password,
                    config.notify_email,
                    exc,
                    screenshot,
                )
            except Exception:
                log.exception("Also failed to send failure notification email")

        if config.run_interval_minutes == 0:
            log.info("RUN_INTERVAL_MINUTES=0 — exiting after single run")
            break

        log.info("Sleeping %d minutes...", config.run_interval_minutes)
        await asyncio.sleep(config.run_interval_minutes * 60)


if __name__ == "__main__":
    asyncio.run(main())
