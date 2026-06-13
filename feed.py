import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from playwright.async_api import Page

from config import Config

log = logging.getLogger(__name__)

_DASHBOARD_URL = "https://www.strava.com/dashboard"

# Selectors — sourced from the hobbyist community (isaac-chung/strava-kudos et al.)
_SEL_FEED_ENTRY = "[data-testid=web-feed-entry]"
_SEL_UNFILLED_KUDOS = "[data-testid=unfilled_kudos]"
_SEL_KUDOS_CONTAINER = "[data-testid=kudos_comments_container]"
_SEL_GROUP_HEADER = "[data-testid=group-header]"
_SEL_OWNER_NAME = "[data-testid=owners-name]"
_SEL_CLUB_POST = ".clubMemberPostHeaderLinks"
_SEL_USER_MENU = ".user-menu > a"


async def get_user_profile_id(page: Page) -> str:
    """Extract the logged-in user's Strava athlete ID from the nav bar."""
    try:
        href = await page.locator(_SEL_USER_MENU).first.get_attribute("href") or ""
        parts = href.strip("/").split("/")
        return parts[-1] if parts else ""
    except Exception:
        log.warning("Could not determine user profile ID")
        return ""


async def give_kudos(page: Page, config: Config, user_profile_id: str = "") -> dict:
    """
    Scroll the dashboard feed, giving kudos to all un-kudosed activities.

    Stops when (first condition met):
      1. An already-kudosed activity is found  →  "already_kudosed"
      2. max_kudos limit reached               →  "max_kudos_reached"
      3. Activity older than lookback_hours    →  "lookback_exceeded"
      4. Feed fully scrolled with no new items →  "feed_exhausted"

    Returns {"kudos_given": int, "stop_reason": str}
    """
    try:
        await page.goto(_DASHBOARD_URL, wait_until="networkidle", timeout=90000)
    except Exception:
        # networkidle timed out (persistent connections) — page may still be usable
        log.info("networkidle timeout — proceeding with current page state")

    # Resolve user profile ID now that the page is loaded (avoids a double navigation).
    if not user_profile_id:
        user_profile_id = await get_user_profile_id(page)
    log.info("Running as athlete ID: %s", user_profile_id or "(unknown)")

    # Dismiss any post-login modal (Welcome tour, etc.)
    try:
        await page.keyboard.press("Escape")
    except Exception:
        pass

    # Wait for the feed to populate
    try:
        await page.wait_for_selector(_SEL_FEED_ENTRY, timeout=120000)
    except Exception:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        base = Path(config.data_dir) / f"feed_not_found_{ts}"
        try:
            await page.screenshot(path=f"{base}.png", full_page=True)
        except Exception:
            pass
        try:
            html = await page.content()
            Path(f"{base}.html").write_text(html, encoding="utf-8")
        except Exception:
            pass
        log.warning("Feed entries did not appear — diagnostics saved to %s.{png,html}", base)
        return {"kudos_given": 0, "stop_reason": "feed_not_found"}

    kudos_given = 0
    stop_reason = "feed_exhausted"
    lookback_cutoff = datetime.now(timezone.utc) - timedelta(hours=config.lookback_hours)

    # processed_count tracks how many entries we've examined so far.
    # Strava's feed only appends entries at the bottom on scroll (no virtual list removal),
    # so the index stays valid across scroll cycles.
    processed_count = 0

    while True:
        entries = await page.query_selector_all(_SEL_FEED_ENTRY)
        log.info("Feed entries visible: %d (processed so far: %d)", len(entries), processed_count)

        if processed_count >= len(entries):
            if len(entries) == 0:
                # React flash/re-fetch: wait_for_selector fired on the brief cached
                # render, then React blanked the page to re-fetch. Wait again.
                log.info("Feed shows 0 entries — waiting up to 120s for React re-render...")
                try:
                    await page.wait_for_selector(_SEL_FEED_ENTRY, timeout=120000)
                except Exception:
                    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                    base = Path(config.data_dir) / f"feed_not_found_{ts}"
                    try:
                        await page.screenshot(path=f"{base}.png", full_page=True)
                    except Exception:
                        pass
                    try:
                        html = await page.content()
                        Path(f"{base}.html").write_text(html, encoding="utf-8")
                    except Exception:
                        pass
                    log.warning(
                        "Feed still empty after 60s wait — diagnostics saved to %s.{png,html}", base
                    )
                    return {"kudos_given": 0, "stop_reason": "feed_not_found"}
                continue

            prev_count = len(entries)
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(3000)
            entries = await page.query_selector_all(_SEL_FEED_ENTRY)
            if len(entries) <= prev_count:
                log.info("No new entries after scroll — feed exhausted")
                ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                shot = str(Path(config.data_dir) / f"feed_exhausted_{ts}.png")
                try:
                    await page.screenshot(path=shot, full_page=True)
                    log.info("Screenshot saved to %s", shot)
                except Exception:
                    pass
                break
            continue  # Re-enter loop with updated entries

        for i in range(processed_count, len(entries)):
            entry = entries[i]
            processed_count += 1

            try:
                result = await _process_entry(
                    entry, page, config, user_profile_id, lookback_cutoff
                )
            except Exception:
                log.exception("Error processing feed entry %d — skipping", i)
                continue

            log.info("Entry %d: %s", i, result)

            if result == "kudos":
                kudos_given += 1
                log.info("Kudos given (%d/%d)", kudos_given, config.max_kudos)
                if kudos_given >= config.max_kudos:
                    return {"kudos_given": kudos_given, "stop_reason": "max_kudos_reached"}

            elif result == "already_kudosed":
                log.info("Found already-kudosed activity — caught up to previous run")
                return {"kudos_given": kudos_given, "stop_reason": "already_kudosed"}

            elif result == "too_old":
                log.info("Activity older than %dh — stopping", config.lookback_hours)
                return {"kudos_given": kudos_given, "stop_reason": "lookback_exceeded"}

            # result == "skip" → continue to next entry

    return {"kudos_given": kudos_given, "stop_reason": stop_reason}


async def _process_entry(
    entry,
    page: Page,
    config: Config,
    user_profile_id: str,
    lookback_cutoff: datetime,
) -> str:
    """
    Examine one feed entry and act.
    Returns one of: "kudos" | "already_kudosed" | "too_old" | "skip"
    """
    # Skip club / group posts
    if await entry.query_selector(_SEL_GROUP_HEADER):
        return "skip"
    if await entry.query_selector(_SEL_CLUB_POST):
        return "skip"

    # Skip own activities
    if user_profile_id:
        owner = await entry.query_selector(_SEL_OWNER_NAME)
        if owner:
            href = await owner.get_attribute("href") or ""
            if user_profile_id in href:
                return "skip"

    # Check activity timestamp against lookback window
    time_el = await entry.query_selector("time")
    if time_el:
        dt_str = await time_el.get_attribute("datetime") or ""
        if dt_str:
            try:
                dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                if dt < lookback_cutoff:
                    return "too_old"
            except ValueError:
                pass

    # Entries without a kudos container (challenges, routes, etc.) are not kudosable
    kudos_container = await entry.query_selector(_SEL_KUDOS_CONTAINER)
    if not kudos_container:
        return "skip"

    unfilled = await entry.query_selector(_SEL_UNFILLED_KUDOS)
    if not unfilled:
        # Kudosable activity with no unfilled button → already kudosed
        return "already_kudosed"

    # Give kudos
    await unfilled.scroll_into_view_if_needed()
    await page.wait_for_timeout(300)
    await unfilled.click()
    await page.wait_for_timeout(600)
    return "kudos"
