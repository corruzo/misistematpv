from datetime import datetime, time, timezone

from app.core.config import LOCAL_TIMEZONE


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def to_local(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return as_utc(value).astimezone(LOCAL_TIMEZONE)


def local_day_start_as_utc() -> datetime:
    local_today = utc_now().astimezone(LOCAL_TIMEZONE).date()
    return datetime.combine(local_today, time.min, tzinfo=LOCAL_TIMEZONE).astimezone(timezone.utc)