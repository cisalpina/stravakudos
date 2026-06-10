import os
from dataclasses import dataclass


@dataclass
class Config:
    strava_email: str
    strava_password: str
    gmail_email: str
    gmail_app_password: str
    notify_email: str
    max_kudos: int = 20
    lookback_hours: int = 24
    run_interval_minutes: int = 10
    data_dir: str = "./data"
    headless: bool = False
    novnc_url: str = "http://localhost:6080"


def load_config() -> Config:
    def req(name: str) -> str:
        val = os.environ.get(name, "").strip()
        if not val:
            raise EnvironmentError(f"Required env var {name!r} is not set")
        return val

    return Config(
        strava_email=req("STRAVA_EMAIL"),
        strava_password=req("STRAVA_PASSWORD"),
        gmail_email=req("GMAIL_EMAIL"),
        gmail_app_password=req("GMAIL_APP_PASSWORD"),
        notify_email=req("NOTIFY_EMAIL"),
        max_kudos=int(os.environ.get("MAX_KUDOS", "20")),
        lookback_hours=int(os.environ.get("LOOKBACK_HOURS", "24")),
        run_interval_minutes=int(os.environ.get("RUN_INTERVAL_MINUTES", "10")),
        data_dir=os.environ.get("DATA_DIR", "./data"),
        headless=os.environ.get("HEADLESS", "false").lower() == "true",
        novnc_url=os.environ.get("NOVNC_URL", "http://localhost:6080"),
    )
