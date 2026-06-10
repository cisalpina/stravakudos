import logging
import smtplib
import traceback
from email.message import EmailMessage
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_SMTP_HOST = "smtp.gmail.com"
_SMTP_PORT = 587


def send_session_expired_email(
    gmail_email: str,
    app_password: str,
    notify_email: str,
    novnc_url: str,
    wait_minutes: int,
) -> None:
    msg = EmailMessage()
    msg["Subject"] = "Strava Kudos Bot: Login Required"
    msg["From"] = gmail_email
    msg["To"] = notify_email
    msg.set_content(
        f"The Strava session has expired. Manual login is needed.\n\n"
        f"Open the browser at: {novnc_url}\n\n"
        f"The bot will wait up to {wait_minutes} minutes. "
        f"If no login is detected in that time it will send a failure email."
    )
    try:
        with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT) as smtp:
            smtp.starttls()
            smtp.login(gmail_email, app_password)
            smtp.send_message(msg)
        log.info("Session-expired email sent to %s", notify_email)
    except Exception:
        log.exception("Could not send session-expired notification email")


def send_failure_email(
    gmail_email: str,
    app_password: str,
    notify_email: str,
    error: Exception,
    screenshot_path: Optional[str] = None,
) -> None:
    msg = EmailMessage()
    msg["Subject"] = "Strava Kudos Bot: Run Failed"
    msg["From"] = gmail_email
    msg["To"] = notify_email

    tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    msg.set_content(f"The Strava kudos bot encountered an error:\n\n{tb}")

    if screenshot_path:
        path = Path(screenshot_path)
        if path.exists():
            msg.add_attachment(
                path.read_bytes(),
                maintype="image",
                subtype="png",
                filename="screenshot.png",
            )

    try:
        with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT) as smtp:
            smtp.starttls()
            smtp.login(gmail_email, app_password)
            smtp.send_message(msg)
        log.info("Failure email sent to %s", notify_email)
    except Exception:
        log.exception("Could not send failure notification email")
