from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Optional, Union

IST = ZoneInfo("Asia/Kolkata")
UTC = timezone.utc

def get_now_ist() -> datetime:
    """Returns the current datetime in Asia/Kolkata (IST, UTC+05:30)."""
    return datetime.now(IST)

def get_today_ist() -> date:
    """Returns the current date in Asia/Kolkata (IST)."""
    return datetime.now(IST).date()

def get_utc_now() -> datetime:
    """Returns the current UTC time as naive datetime for PostgreSQL timestamp compatibility."""
    return datetime.now(UTC).replace(tzinfo=None)

def to_ist(dt: Optional[Union[datetime, date, str]]) -> Optional[datetime]:
    """Converts a datetime, date or ISO string to an IST-aware datetime."""
    if dt is None:
        return None
    if isinstance(dt, str):
        try:
            # Parse ISO string
            parsed = datetime.fromisoformat(dt.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(IST)
        except Exception:
            return None
    if isinstance(dt, date) and not isinstance(dt, datetime):
        return datetime.combine(dt, datetime.min.time(), tzinfo=IST)
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            # Assume UTC if naive
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(IST)
    return None

def to_ist_iso(dt: Optional[Union[datetime, date, str]]) -> Optional[str]:
    """Converts any datetime/date to an ISO string with explicit IST (+05:30) offset."""
    if dt is None:
        return None
    ist_dt = to_ist(dt)
    return ist_dt.isoformat() if ist_dt else None

def to_utc_iso(dt: Optional[Union[datetime, date, str]]) -> Optional[str]:
    """Converts any datetime to an ISO string with explicit UTC (Z) suffix."""
    if dt is None:
        return None
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return str(dt)

def format_ist_datetime(
    dt: Optional[Union[datetime, date, str]],
    fmt: str = "%d %b %Y, %I:%M:%S %p IST"
) -> str:
    """Formats any datetime into a standardized IST display string."""
    ist_dt = to_ist(dt)
    if not ist_dt:
        return "-"
    return ist_dt.strftime(fmt)

def format_ist_date(
    d: Optional[Union[date, datetime, str]],
    fmt: str = "%d %b %Y"
) -> str:
    """Formats any date into a standardized IST display string."""
    if d is None:
        return "-"
    if isinstance(d, str):
        try:
            parsed = date.fromisoformat(d[:10])
            return parsed.strftime(fmt)
        except Exception:
            return d
    if isinstance(d, datetime):
        ist_dt = to_ist(d)
        return ist_dt.strftime(fmt) if ist_dt else "-"
    if isinstance(d, date):
        return d.strftime(fmt)
    return str(d)
