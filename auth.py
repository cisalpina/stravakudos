import logging
from pathlib import Path
from typing import Optional

from playwright.async_api import BrowserContext, Error as PlaywrightError, Page

from config import Config

log = logging.getLogger(__name__)

_DASHBOARD_URL = "https://www.strava.com/dashboard"
_LOGIN_URL = "https://www.strava.com/login"


async def check_session(page: Page) -> bool:
    """Navigate to dashboard; return True if the session is valid (no redirect to login)."""
    await page.goto(_DASHBOARD_URL, wait_until="domcontentloaded")
    return "login" not in page.url


async def login(page: Page, config: Config) -> bool:
    """
    Navigate to the Strava login page and wait for the user to log in manually.
    Returns True once the session is established (URL leaves the login page).
    """
    log.info("Navigating to Strava login...")
    await page.goto(_LOGIN_URL, wait_until="domcontentloaded")

    if "login" not in page.url:
        log.info("Session restored from cookies — skipping manual login")
        return True

    log.info("Please log in to Strava in the browser window. Waiting up to 5 minutes...")
    try:
        await page.wait_for_url(lambda url: "login" not in url, timeout=300_000)
        await page.wait_for_load_state("domcontentloaded")
        log.info("Manual login detected — continuing")
        return True
    except Exception:
        log.error("Timed out waiting for manual login")
        return False


def storage_state_path(data_dir: str) -> Optional[str]:
    """Return the storage state file path if it exists, else None."""
    path = Path(data_dir) / "storage_state.json"
    return str(path) if path.exists() else None


async def save_storage_state(context: BrowserContext, data_dir: str) -> None:
    path = Path(data_dir) / "storage_state.json"
    try:
        await context.storage_state(path=str(path))
        log.info("Session saved to %s", path)
    except PlaywrightError as exc:
        log.warning("Could not save session state (context closed): %s", exc)


