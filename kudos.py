"""
Strava Kudos Bot — main entry point.

Runs on a configurable interval (default 10 min). Each cycle:
  1. Restores a saved Playwright browser session (cookies).
  2. Logs in fresh if the session has expired.
  3. Scrolls the Strava dashboard feed and gives kudos.
  4. Saves the updated session back to disk.

All configuration via environment variables (see .env.example).
Set RUN_INTERVAL_MINUTES=0 to run once and exit (useful for testing).
"""

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright

import auth
import feed
from config import load_config
from notify import send_failure_email, send_session_expired_email

log = logging.getLogger(__name__)


async def run_once(config) -> dict:
    """
    One complete cycle: session check → optional login → kudos → save session.
    Returns stats dict on success.
    On failure, takes a screenshot, attaches its path to the exception, then re-raises.
    """
    storage = auth.storage_state_path(config.data_dir)

    async with async_playwright() as p:
        # Try system Firefox first (real fingerprint); fall back to Playwright's bundled build.
        try:
            browser = await p.firefox.launch(headless=config.headless, channel="firefox")
        except Exception:
            browser = await p.firefox.launch(headless=config.headless)

        context = await browser.new_context(
            **({"storage_state": storage} if storage else {}),
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:128.0)"
                " Gecko/20100101 Firefox/128.0"
            ),
        )
        # Hide the automation flag that Strava uses to detect bots.
        await context.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
        )
        page = await context.new_page()

        try:
            if not await auth.check_session(page):
                log.info("Session expired — sending notification and waiting for manual login...")
                send_session_expired_email(
                    config.gmail_email,
                    config.gmail_app_password,
                    config.notify_email,
                    config.novnc_url,
                    wait_minutes=5,
                )
                success = await auth.login(page, config)
                if not success:
                    raise RuntimeError(
                        "Login timed out — session still expired after 5-minute wait"
                    )
                await auth.save_storage_state(context, config.data_dir)

            user_id = await feed.get_user_profile_id(page)
            log.info("Running as athlete ID: %s", user_id or "(unknown)")

            stats = await feed.give_kudos(page, config, user_id)

            await auth.save_storage_state(context, config.data_dir)
            return stats

        except Exception as exc:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            shot = str(Path(config.data_dir) / f"error_{ts}.png")
            try:
                await page.screenshot(path=shot, full_page=False)
                exc.screenshot_path = shot  # type: ignore[attr-defined]
            except Exception:
                exc.screenshot_path = None  # type: ignore[attr-defined]
            raise

        finally:
            await context.close()
            await browser.close()


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
