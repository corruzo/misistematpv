from datetime import date, datetime, time, timedelta, timezone

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
    return local_date_bounds_as_utc(utc_now().astimezone(LOCAL_TIMEZONE).date())[0]


def local_date_bounds_as_utc(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=LOCAL_TIMEZONE)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=LOCAL_TIMEZONE)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)