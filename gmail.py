import email
import email.message
import email.utils
import logging
import re
import time
from datetime import datetime, timezone
from typing import Optional

from imapclient import IMAPClient

log = logging.getLogger(__name__)

_STRAVA_SENDER = "no-reply@strava.com"
_IMAP_HOST = "imap.gmail.com"


def fetch_strava_otc(
    gmail_email: str,
    app_password: str,
    wait_start: datetime,
    timeout: int = 90,
) -> Optional[str]:
    """
    Poll Gmail IMAP for a Strava OTC email received after wait_start.
    Returns the 6-digit code, or None if not found within timeout seconds.

    Synchronous — call via asyncio.to_thread from async code.
    """
    deadline = time.monotonic() + timeout
    log.info("Polling Gmail for Strava OTC (timeout=%ds)...", timeout)

    with IMAPClient(_IMAP_HOST, ssl=True) as client:
        client.login(gmail_email, app_password)
        client.select_folder("INBOX")

        while time.monotonic() < deadline:
            uids = client.search(["FROM", _STRAVA_SENDER, "UNSEEN"])
            for uid in uids:
                raw = client.fetch([uid], ["RFC822"])[uid][b"RFC822"]
                msg = email.message_from_bytes(raw)

                if not _is_after(msg, wait_start):
                    log.debug("Skipping old Strava email uid=%s", uid)
                    continue

                body = _get_text_body(msg)
                code = _extract_six_digit_code(body)
                if code:
                    client.set_flags([uid], [rb"\Seen"])
                    log.info("Found Strava OTC")
                    return code

            remaining = deadline - time.monotonic()
            if remaining > 5:
                time.sleep(5)

    log.warning("OTC not found within %ds", timeout)
    return None


def _is_after(msg: email.message.Message, cutoff: datetime) -> bool:
    date_str = msg.get("Date", "")
    if not date_str:
        return True
    try:
        dt = email.utils.parsedate_to_datetime(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        cutoff_aware = cutoff if cutoff.tzinfo else cutoff.replace(tzinfo=timezone.utc)
        return dt >= cutoff_aware
    except Exception:
        return True


def _get_text_body(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode("utf-8", errors="ignore")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            return payload.decode("utf-8", errors="ignore")
    return ""


def _extract_six_digit_code(body: str) -> Optional[str]:
    match = re.search(r"\b(\d{6})\b", body)
    return match.group(1) if match else None
